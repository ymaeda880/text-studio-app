# -*- coding: utf-8 -*-
# pages/44_頁ラベル抽出_1頁1ラベル.py
# 各PDFページを個別に走査し、
#  1) 「行単独の頁ラベル」… 高々1つ抽出 → 連番チェック
#  2) 「行単独の 図/表/図表 見出し」… キャプション一覧
#  3) 「行途中の 図/表/図表 参照」… 文脈つき参照一覧
#
# ※ 参照は見出し行とは分離し、見出し行に含まれる出現は参照側から除外

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
st.set_page_config(page_title="📄 頁ラベル + 図表見出し/参照 抽出", page_icon="📄", layout="wide")
st.title("📄 頁ラベル（1頁=高々1）→ 連番チェック → 図表 見出し/参照（分離）")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 解析を実行", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    show_debug = st.checkbox("内部情報（デバッグ）を表示", value=False)
    ctx_chars  = st.slider("参照の前後コンテキスト文字数", 10, 200, 40, 5)

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
# 正規化・ラベル判定（頁ラベル用）
# =========================
# =========================
# 正規化・ラベル判定に使う基本パターン定義
# =========================

# HY:
# 各種「ハイフン（-）」や「長音（ー）」をひとまとめに扱う。
# 文書によっては、普通のハイフン(-)以外に以下のような類似記号が混ざることがあるため、
# 全てを1つの共通パターンで吸収しておく：
#   \u2010 〜 \u2015  : Unicodeの異体ハイフン（‐-‒–—―）
#   \u2212            : 数学用マイナス記号（−）
#   \uFF0D            : 全角ハイフン（－）
#   \u30FC            : 長音記号（ー）
HY  = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D\u30FC]"  # 各種ハイフン/長音

# NUM:
# 半角・全角の数字（0〜9, ０〜９）をまとめて認識する。
# 例: "3", "１２３" のどちらも一致する。
NUM = r"[0-9０-９]+"

# ALPHAJP:
# 英字（A〜Z, a〜z）、ひらがな、カタカナ、漢字をすべて含む。
# シリーズ名・章名・資料名など（例: "資料", "序", "Appendix", "表" など）を検出するため。
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"

# LEADER_CHARS_CLASS:
# 「リーダー線（……や・･・など）」の構成文字を定義。
# 行の末尾に「……」「・ ・ ・」などが並ぶ場合、それは装飾や区切りであり、
# ラベルや番号の一部ではないので削除対象にするため。
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"

# LEADERS_SPACED:
# 上記のリーダー文字が3個以上連続しているパターンを定義。
# 例: "・・・・・・", "… … …", "．．．" などに一致。
# normalize_strict() 内で、この部分を行末から除去している。
LEADERS_SPACED = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"


# ========================================
# 文字正規化・ページラベル抽出ロジック
# ========================================

def z2h_numhy(s: str) -> str:
    """
    全角文字や特殊ハイフンを正規化して、統一的な形式に変換する関数。

    処理内容：
      1. 全角スペース（\u3000）を半角スペースに置換。
      2. 全角数字・括弧・角括弧などを半角に変換。
      3. 各種ハイフン類（−, —, ―, ー など）を半角ハイフン（-）に統一。

    引数:
        s (str): 入力文字列
    戻り値:
        正規化済み文字列（str）
    """
    s = (s or "").replace("\u3000", " ")  # 全角スペース→半角スペース
    # 全角数字・記号を半角に変換
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝", "0123456789()[]{}"))
    # 全ての異体ハイフンを "-" に統一
    return re.sub(HY, "-", s)


def normalize_strict(s: str) -> str:
    """
    行単位で文字列を正規化し、見出しやラベル検出に不要なノイズを削除する。

    処理内容：
      1. z2h_numhy() で全角→半角・ハイフン統一。
      2. 行末に並ぶ「リーダー（……や・・・・・・）」を削除。
      3. 連続する空白・タブを1つに圧縮。
      4. 前後の余白をstrip()で削除。

    例:
        "３．１　……" → "3.1"
        "資料　１　　" → "資料 1"

    引数:
        s (str): 行テキスト
    戻り値:
        正規化済み文字列（str）
    """
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)  # 行末のリーダー列を削除
    s = re.sub(r"[ \t]+", " ", s)                   # 空白・タブを1個に圧縮
    return s.strip()                                # 前後の空白を除去


def build_label_line_regex_mixed() -> re.Pattern:
    """
    「行単独でページラベルと見なせる」テキスト行を検出する正規表現を生成。

    対応パターン例：
        - 数字のみ              → "12", "３"
        - 章＋ページ形式         → "2-1", "3-10-2", "４－３"
        - シリーズ＋番号         → "資料1", "資料-1", "資料 1", "序．1", "(資料)12", "［序］-3"
        - "page 1", "p.2" なども先頭にある場合を許可

    正規表現の設計意図：
      - 行全体がラベルとして独立している（他の文脈がない）ことを保証するため、
        ^ と $ で全体を囲み、MULTILINE フラグで複数行に対応。
      - 各シリーズの語（資料, 序, A, Appendix など）は日本語・英字混在に対応。
      - ハイフン・ドット・空白などの区切りを柔軟に許容。
      - 空白だけで結ばれているケース（"資料 1"）も含める。

    戻り値:
        ページラベル検出用コンパイル済み正規表現（re.Pattern）
    """

    # 【単純な数値ページ】 例: "1", "12", "３"
    core_seq = r"[0-9０-９]{1,6}"

    # 【章-ページ形式】 例: "2-1", "3-10-2", "４－３"
    # 空白・異体ハイフンも柔軟に許容
    core_chap = rf"{NUM}(?:\s*{HY}\s*{NUM})+"

    # 【シリーズ付き形式】 例: "資料1", "資料-1", "資料 1", "序．1", "(資料)12", "［序］-3"
    # ・( )［ ］ などの括弧付きも許容
    # ・区切りはハイフン/ドット/空白を許可（または省略）
    series_word = rf"[（(［\[]?{ALPHAJP}[）)\]］]?"   # シリーズ語（日本語・英字）＋括弧オプション
    SEP_OPT     = rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"  # 区切り：ハイフン or ドット or 空白
    core_series = rf"{series_word}{SEP_OPT}{NUM}"

    # 上記3種をまとめたパターン
    core = rf"(?:{core_seq}|{core_chap}|{core_series})"

    # ^ と $ で「行単独」を保証。page/p. 接頭辞も許容。
    return re.compile(
        rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$",
        re.MULTILINE
    )


# ページラベル検出用の正規表現を生成して保持
LABEL_LINE_RE = build_label_line_regex_mixed()


# =========================
# 1ページ=高々1ラベル抽出（頁ラベル）
# =========================
def extract_single_page_label(page_text: str) -> Tuple[Optional[str], Optional[str]]:
    if not page_text:
        return None, None
    for raw in page_text.replace("\r\n","\n").replace("\r","\n").split("\n"):
        s = normalize_strict(raw)
        if not s:
            continue
        m = LABEL_LINE_RE.match(s)
        if m:
            return z2h_numhy(m.group("label")), raw
    return None, None

# =========================
# 連番チェック（seq/chap/series）
# =========================
def _parse_label_kind(label: str) -> Tuple[str, Any]:
    lab = z2h_numhy(label)
    lab_chap = re.sub(r"\s*-\s*", "-", lab)
    if re.fullmatch(r"[0-9]+", lab_chap):
        return "seq", int(lab_chap)
    if re.fullmatch(r"[0-9]+(?:-[0-9]+)+", lab_chap):
        return "chap", [int(p) for p in lab_chap.split("-")]
    series_pat = re.compile(
        rf"""^
        [（(［\[]?           # 開きカッコ（任意）
        ({ALPHAJP})          # シリーズ語
        [）)\]］]?           # 閉じカッコ（任意）
        (?:\s*(?:{HY}|[\.．・･])\s*|\s+)?  # 区切り or 空白 or 省略
        ([0-9]+)
        $""", re.X
    )
    m = series_pat.fullmatch(lab_chap)
    if m:
        return "series", (m.group(1), int(m.group(2)))
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
# 実行：頁ラベル抽出 → 連番チェック
# =========================
rows_page: List[Dict[str, Any]] = []
page_labels: List[Optional[str]] = []
for i, ptxt in enumerate(pages_text, start=1):
    label, matched = extract_single_page_label(ptxt)
    page_labels.append(label)
    rows_page.append({
        "pdf_page": i,
        "page_label": label if label is not None else "-",
        "matched_line": matched if matched is not None else "-",
        "has_label": label is not None,
    })

df_per_page = pd.DataFrame(rows_page)
st.subheader("🔎 各ページの頁ラベル（1頁=高々1）")
st.dataframe(df_per_page, use_container_width=True)

found_labels = [lab for lab in page_labels if lab]
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
st.subheader("✅ 見つかった頁ラベル列の連番チェック")
st.dataframe(df_seq if not df_seq.empty else pd.DataFrame(), use_container_width=True)

# =========================
# 図/表/図表 の見出し（行単独）と 参照（行途中）を分離抽出
# =========================
DOT = r"[\.．・･]"
NUM_ZH = r"[0-9０-９]+"

# 図表番号トークン
NUM_TOKEN = rf"""
(?:{NUM_ZH}(?:\s*{DOT}\s*{NUM_ZH})*(?:\s*-\s*{NUM_ZH})* | [（(]\s*{NUM_ZH}\s*[）)])
"""

# 見出し（行単独）:
#  - 「図/表/図表 + 番号」の直後に助詞・読点等が続く行は除外（≒本文参照）
#  - 区切り（:：.-、）の後に任意タイトル、または行末でもOK
HEADING_RE = re.compile(
    rf"""^
        \s*(?P<kind>図表|図|表)
        \s*(?P<num>{NUM_TOKEN})
        (?!                          # ← 見出しではないパターンを除外
            [ 　、,．。]*             # 空白・全角空白・読点など
            (?:に|を|は|へ|で|として|
               に示す|に示した|における|に関する|
               に対する|による|の|等)\b
        )
        \s*(?:[:：.\-．、]\s*(?P<title>.+))?\s*$
    """,
    re.X
)

# 参照（行途中）: 図/表/図表 + 番号（見出し行は後で除外）
REF_RE = re.compile(
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})(?![0-9])",
    re.X
)

def canon_num(num: str) -> str:
    s = z2h_numhy(num)
    s = re.sub(r"[()（）]", "", s)       # （1）→1
    s = re.sub(DOT, ".", s)             # ．・ → .
    s = re.sub(r"\s*\.\s*", ".", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", "", s)
    return s

def canon_label(kind: str, num: str) -> str:
    return f"{kind}{canon_num(num)}"

def extract_headings_from_page(page_text: str) -> List[Dict[str, Any]]:
    """行単独の見出し（キャプション）だけを抽出"""
    out: List[Dict[str, Any]] = []
    lines = page_text.replace("\r\n","\n").replace("\r","\n").split("\n")
    for raw in lines:
        s = normalize_strict(raw)
        if not s:
            continue
        m = HEADING_RE.match(s)
        if not m:
            continue
        kind = m.group("kind")
        num  = m.group("num")
        title= (m.group("title") or "").strip()
        out.append({
            "図表種類": kind,
            "図表番号": f"{kind}{z2h_numhy(num)}",
            "図表キー": canon_label(kind, num),
            "見出しタイトル": title,
            "matched_line": raw,
        })
    return out

def collect_heading_line_spans(page_text: str) -> List[Tuple[int,int]]:
    """見出し行のテキスト範囲（start,end）をページ内オフセットで返す"""
    spans: List[Tuple[int,int]] = []
    pos = 0
    for raw in page_text.replace("\r\n","\n").replace("\r","\n").split("\n"):
        line = raw
        s = normalize_strict(line)
        start = pos
        end   = pos + len(line) + 1  # +改行
        if s and HEADING_RE.match(s):
            spans.append((start, end))
        pos = end
    return spans

def extract_refs_from_page(page_text: str, ctx: int, heading_spans: List[Tuple[int,int]]) -> List[Dict[str, Any]]:
    """見出し行を除外して、本文中の参照（行途中）を抽出。前後ctx文字の文脈つき。"""
    out: List[Dict[str, Any]] = []
    text = page_text.replace("\r\n","\n").replace("\r","\n")
    for m in REF_RE.finditer(text):
        a, b = m.span()
        # 見出し行に含まれていればスキップ
        skip = False
        for s, e in heading_spans:
            if a >= s and a < e:
                skip = True
                break
        if skip:
            continue

        kind = m.group("kind")
        num  = m.group("num")
        key  = canon_label(kind, num)

        left  = max(0, a - ctx)
        right = min(len(text), b + ctx)
        pre   = text[left:a]
        hit   = text[a:b]
        post  = text[b:right]
        # context には前後を入れ、ヒット文字列は別フィールドで保持
        context = f"{pre}{post}"
        out.append({
            "参照テキスト": m.group(0),
            "図表種類": kind,
            "図表番号": f"{kind}{z2h_numhy(num)}",
            "図表キー": key,
            "context": context,
            "hit": hit,
            "start": a,
            "end": b,
        })
    return out

# ===== 全ページを走査：見出し（行単独）と参照（行途中）を分離 =====
caption_rows: List[Dict[str, Any]] = []
ref_rows: List[Dict[str, Any]] = []

for i, ptxt in enumerate(pages_text, start=1):
    page_label = page_labels[i-1] if i-1 < len(page_labels) and page_labels[i-1] else "-"
    # 見出し
    heads = extract_headings_from_page(ptxt)
    for h in heads:
        caption_rows.append({
            "pdf_page": i,
            "page_label": page_label,
            **h
        })
    # 参照（見出し行は除外して拾う）
    spans = collect_heading_line_spans(ptxt)
    refs = extract_refs_from_page(ptxt, ctx=ctx_chars, heading_spans=spans)
    for r in refs:
        ref_rows.append({
            "pdf_page": i,
            "page_label": page_label,
            **r
        })

df_captions = pd.DataFrame(caption_rows)
df_refs     = pd.DataFrame(ref_rows)

st.subheader("🖼️ 行単独の 図/表/図表 見出し（キャプション）")
st.dataframe(df_captions if not df_captions.empty else pd.DataFrame(), use_container_width=True)

st.subheader("🔗 本文中の 図/表/図表 参照（文脈つき）")
st.dataframe(df_refs if not df_refs.empty else pd.DataFrame(), use_container_width=True)

# =========================
# ダウンロード（サイドバー）
# =========================
with st.sidebar:
    st.markdown("### ダウンロード")
    if not df_per_page.empty:
        buf = io.StringIO(); df_per_page.to_csv(buf, index=False)
        st.download_button("📥 per_page_labels.csv", data=buf.getvalue().encode("utf-8-sig"),
                           file_name="per_page_labels.csv", mime="text/csv", use_container_width=True)
    if not df_seq.empty:
        buf = io.StringIO(); df_seq.to_csv(buf, index=False)
        st.download_button("📥 label_sequence_check.csv", data=buf.getvalue().encode("utf-8-sig"),
                           file_name="label_sequence_check.csv", mime="text/csv", use_container_width=True)
    if not df_captions.empty:
        buf = io.StringIO(); df_captions.to_csv(buf, index=False)
        st.download_button("📥 figure_table_captions.csv", data=buf.getvalue().encode("utf-8-sig"),
                           file_name="figure_table_captions.csv", mime="text/csv", use_container_width=True)
    if not df_refs.empty:
        buf = io.StringIO(); df_refs.to_csv(buf, index=False)
        st.download_button("📥 figure_table_references.csv", data=buf.getvalue().encode("utf-8-sig"),
                           file_name="figure_table_references.csv", mime="text/csv", use_container_width=True)

# =========================
# デバッグ
# =========================
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.code(f"LABEL_LINE_RE = {LABEL_LINE_RE.pattern}")
    st.code(f"HEADING_RE = {HEADING_RE.pattern}\nREF_RE = {REF_RE.pattern}")
