# -*- coding: utf-8 -*-
# pages/43_頁抽出.py
# 各PDFページを個別に走査し、「行単独の頁ラベル」を高々1つ抽出。
# 抽出できたラベル列に対して連番チェック（seq / chap / series）を実施。

from __future__ import annotations
import re, io, tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import streamlit as st
import pandas as pd

# ==== PDF→テキスト ====
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
try:
    import pdfplumber
except Exception:
    pdfplumber = None


# =========================
# ページ設定 & メインUI
# =========================
st.set_page_config(page_title="📄 頁ラベル抽出（1頁=高々1ラベル）+ 連番チェック", page_icon="📄", layout="wide")
st.title("📄 頁ラベル抽出（1頁=高々1ラベル）→ 連番チェック")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 抽出・連番チェックを実行", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    show_debug = st.checkbox("内部情報（デバッグ）を表示", value=False)

if not uploaded or not run:
    st.stop()

if fitz is None and pdfplumber is None:
    st.error("PyMuPDF か pdfplumber のどちらかをインストールしてください。`pip install pymupdf pdfplumber`")
    st.stop()


# =========================
# PDF → ページ別テキスト
# =========================
def pdf_to_text_per_page(pdf_path: Path) -> List[str]:
    texts: List[str] = []
    if fitz is not None:
        doc = fitz.open(str(pdf_path))
        for p in doc:
            texts.append(p.get_text("text") or "")
    else:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for p in pdf.pages:
                texts.append(p.extract_text() or "")
    return texts

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    pdf_path = td / "input.pdf"
    pdf_path.write_bytes(uploaded.getvalue())
    pages_text: List[str] = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")


# =========================
# 正規化・ラベル判定
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D\u30FC]"   # 各種ハイフン
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"
NUM     = r"[0-9０-９]+"

# リーダー系（……や・やドットの連なり）
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"
LEADERS_SPACED = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"

def z2h_numhy(s: str) -> str:
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝", "0123456789()[]{}"))
    return re.sub(HY, "-", s)

def normalize_strict(s: str) -> str:
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)  # 行末のリーダー列除去
    s = re.sub(r"[ \t]+", " ", s)                   # 連続空白を1つへ
    return s.strip()

# 「行単独のページラベル」を検出（page/p. など任意、seq/chap/series対応）
def build_label_line_regex_mixed() -> re.Pattern:
    core_seq    = r"[0-9０-９]{1,6}"                     # 12
    core_chap   = rf"{NUM}(?:\s*{HY}\s*{NUM})+"          # 2-1, 3-10-2（空白OK）

# 区切り: ①ハイフン/ドット（前後に任意空白） ②または空白のみ ③どちらも無し（直結）
    SEP_OPT = rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"
    series_word = rf"[（(［\[]?{ALPHAJP}[）)\]］]?"
    core_series = rf"{series_word}{SEP_OPT}{NUM}"  # 例: 資料1 / 資料 1 / 資料-1 / 資料．1 / 序ー1 など

    core = rf"(?:{core_seq}|{core_chap}|{core_series})"

    # 行“単独”で一致（前後空白のみOK）
    return re.compile(
        rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$",
        re.MULTILINE
    )

LABEL_LINE_RE = build_label_line_regex_mixed()


# =========================
# 1ページ=高々1ラベル抽出
# =========================
def extract_single_page_label(page_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    1ページのテキストから、行単独のラベルを高々1つ抽出。
    戻り値: (label or None, matched_line or None)
    """
    if not page_text:
        return None, None

    # 行ごとにチェック（normalize_strictの前に折返し保持）
    lines = page_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for raw in lines:
        s = normalize_strict(raw)
        if not s:
            continue
        m = LABEL_LINE_RE.match(s)
        if m:
            label = z2h_numhy(m.group("label"))
            return label, raw  # 生の行も返しておく（確認用）
    return None, None


# =========================
# 連番妥当性チェック
# =========================
def _parse_label_kind(label: str) -> Tuple[str, Any]:
    # 1) 正規化（全角→半角、各種ハイフン→'-'）
    lab = z2h_numhy(label)

    # 章-ページ用にハイフン周りの空白を詰める
    lab_chap = re.sub(r"\s*-\s*", "-", lab)

    # 2) 連番（純数字）
    if re.fullmatch(r"[0-9]+", lab_chap):
        return "seq", int(lab_chap)

    # 3) 章-ページ（2-1 / 3-10-2 等）
    if re.fullmatch(r"[0-9]+(?:-[0-9]+)+", lab_chap):
        return "chap", [int(p) for p in lab_chap.split("-")]

    # 4) シリーズ-数字（区切りなし/空白/ドット/各種ハイフン/括弧付きシリーズ語も許容）
    #   例: 資料1, 資料 1, 資料-1, 資料．1, 序ー1, (資料) 1, ［序］-12
    series_pat = re.compile(
        rf"""^
        [（(［\[]?          # 開きカッコ（任意）
        ({ALPHAJP})         # シリーズ語
        [）)\]］]?          # 閉じカッコ（任意）
        (?:\s*(?:{HY}|[\.．・･])\s*|\s+)?  # 区切り：ハイフン/ドット/空白 または無し
        ([0-9]+)            # 数字
        $""", re.X
    )
    m = series_pat.fullmatch(lab)
    if m:
        series_word = m.group(1)
        num = int(m.group(2))
        return "series", (series_word, num)

    return "unknown", None


def valid_and_reason_auto(label: str, prev_ok: Optional[str]) -> Tuple[bool, str]:
    k, cur = _parse_label_kind(label)
    if k == "unknown":
        return False, "不明なラベル形式"
    if prev_ok is None:
        return True, ""
    pk, prev = _parse_label_kind(prev_ok)
    if pk == "unknown":
        return True, ""
    if k != pk:
        return True, "形式切替"
    if k == "seq":
        return (cur == prev + 1, "" if cur == prev + 1 else "非連番")
    if k == "chap":
        c, p = (cur + [1, 1])[:2]; pc, pp = (prev + [1, 1])[:2]
        ok = (c == pc and p == pp + 1) or (c == pc + 1 and p == 1)
        return (ok, "" if ok else "非連番")
    if k == "series":
        s, n = cur; ps, pn = prev
        if s != ps:
            return True, "形式切替"
        return (n == pn + 1, "" if n == pn + 1 else "非連番")
    return True, ""


# =========================
# 実行：各ページから1ラベル抽出 → 見つかったラベル列で連番チェック
# =========================
rows_page: List[Dict[str, Any]] = []
for i, ptxt in enumerate(pages_text, start=1):
    label, matched = extract_single_page_label(ptxt)
    rows_page.append({
        "pdf_page": i,
        "detected_label": label if label is not None else "-",
        "matched_line": matched if matched is not None else "-",
        "has_label": label is not None,
    })

df_per_page = pd.DataFrame(rows_page)
st.subheader("🔎 各ページのラベル抽出結果（1頁=高々1ラベル）")
st.dataframe(df_per_page, use_container_width=True)

# 見つかったラベルだけで連番チェック（PDF上の出現順）
found_labels = [r["detected_label"] for r in rows_page if r["detected_label"] != "-"]

rows_seq: List[Dict[str, Any]] = []
prev_ok: Optional[str] = None
for idx, lab in enumerate(found_labels, start=1):
    ok, reason = valid_and_reason_auto(lab, prev_ok)
    if ok:
        prev_ok = lab
    rows_seq.append({
        "order_in_found": idx,
        "label": lab,
        "valid": ok,
        "reason": "" if ok else reason
    })
df_seq = pd.DataFrame(rows_seq)

st.subheader("✅ 見つかったラベル列の連番チェック")
if df_seq.empty:
    st.info("抽出できたページラベルがありません。版面の出力形式（行単独のラベル）かOCR品質をご確認ください。")
else:
    st.dataframe(df_seq, use_container_width=True)

# 便利: CSVダウンロード
with st.sidebar:
    st.markdown("### ダウンロード")
    buf1, buf2 = io.StringIO(), io.StringIO()
    if not df_per_page.empty:
        df_per_page.to_csv(buf1, index=False)
        st.download_button("📥 per_page_labels.csv", data=buf1.getvalue().encode("utf-8-sig"),
                           file_name="per_page_labels.csv", mime="text/csv", use_container_width=True)
    if not df_seq.empty:
        df_seq.to_csv(buf2, index=False)
        st.download_button("📥 label_sequence_check.csv", data=buf2.getvalue().encode("utf-8-sig"),
                           file_name="label_sequence_check.csv", mime="text/csv", use_container_width=True)

# デバッグ
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.code(f"LABEL_LINE_RE = {LABEL_LINE_RE.pattern}")


# =========================
# 追記：単独行の 図/表/図表 見出し抽出（1頁あたり複数可）
# =========================

# 区切り記号（ドット類）
DOT = r"[\.．・･]"
# 数字（全角含む）
NUM = r"[0-9０-９]+"

# 図表番号トークン：
#   例) 2.2-1 / 2. 2-1 / ２．１－１ / （１）
NUM_TOKEN = rf"""
(?:                                     
    {NUM}                                # 先頭の数
    (?:\s*{DOT}\s*{NUM})*               # 2.2 / 2． 2 など
    (?:\s*{HY}\s*{NUM})*                # -1 / － 1 など
  |
    [（(]\s*{NUM}\s*[）)]               # （１） / (12)
)
"""
NUM_TOKEN_RE = re.compile(NUM_TOKEN, re.X)

# 見出し（行“単独”）：行頭に 図|表|図表 + 番号 (+ 任意のタイトル)
HEADING_RE = re.compile(
    rf"^\s*(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})\s*[:：.\-．、]?\s*(?P<title>.+?)?\s*$",
    re.X
)

def canon_num_for_caption(num: str) -> str:
    """番号の正規化：全角→半角、ハイフン統一、ドット統一、空白除去、括弧除去"""
    s = z2h_numhy(num)                 # 全角→半角、各種ハイフン→'-'
    s = re.sub(r"[()（）]", "", s)      # （1）→1
    s = re.sub(DOT, ".", s)            # ．・ → .
    s = re.sub(r"\s*\.\s*", ".", s)    # '2 . 2' → '2.2'
    s = re.sub(r"\s*-\s*", "-", s)     # '2 - 1' → '2-1'
    s = re.sub(r"\s+", "", s)          # 残りの空白除去
    return s

def canon_caption_label(kind: str, num: str) -> str:
    return f"{kind}{canon_num_for_caption(num)}"

def extract_headings_from_page(page_text: str) -> List[Tuple[str, str, str]]:
    """
    1ページのテキストから、行単独の 図/表/図表 見出しをすべて抽出。
    戻り値: List[(図表キー, 図表番号(表示用), 行の生テキスト)]
    """
    out: List[Tuple[str, str, str]] = []
    if not page_text:
        return out
    lines = page_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for raw in lines:
        s = normalize_strict(raw)
        if not s:
            continue
        m = HEADING_RE.match(s)
        if not m:
            continue
        kind  = m.group("kind")
        num   = m.group("num")
        title = (m.group("title") or "").strip()
        key   = canon_caption_label(kind, num)          # 例: 図2.2-1 / 表1 / 図表1
        disp  = f"{kind}{z2h_numhy(num)}"               # 表示用：全角→半角・ハイフン統一のみ
        # （必要なら title も保持できます。今回は raw 行を残します）
        out.append((key, disp, raw))
    return out

# 全ページを走査
caption_rows: List[Dict[str, Any]] = []
for i, ptxt in enumerate(pages_text, start=1):

    page_label, _ = extract_single_page_label(ptxt)
    hits = extract_headings_from_page(ptxt)
    for key, disp, raw in hits:
        caption_rows.append({
            "pdf_page": i,
            "page_label": page_label if page_label else "-",  # ← ページラベルを追加
            "図表キー": key,          # 照合用に正規化したキー（例: 図2.2-1 / 表1 / 図表1）
            "図表番号": disp,         # 表示用番号（全角→半角・ハイフン統一）
            "matched_line": raw,      # 行の生テキスト
        })

df_captions = pd.DataFrame(caption_rows)

st.subheader("🖼️ 単独行の図/表/図表 見出し（ページ別）")
if df_captions.empty:
    st.info("単独行の図・表・図表の見出しは検出されませんでした。")
else:
    st.dataframe(df_captions, use_container_width=True)

# 追加のCSVダウンロード（サイドバーに配置）
with st.sidebar:
    if not df_captions.empty:
        buf3 = io.StringIO()
        df_captions.to_csv(buf3, index=False)
        st.download_button(
            "📥 page_headings.csv（図/表/図表）",
            data=buf3.getvalue().encode("utf-8-sig"),
            file_name="page_headings.csv",
            mime="text/csv",
            use_container_width=True,
        )

# デバッグ表示（任意）
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug (captions)")
    st.code(f"HEADING_RE = {HEADING_RE.pattern}")

