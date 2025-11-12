# -*- coding: utf-8 -*-
# pages/43_頁抽出.py
# 各PDFページを個別に走査し、
#  「行単独の頁ラベル」を高々1つ抽出 → 連番チェック（seq / chap / series）
#
# 例）
#   - 純数字: 12
#   - 章-頁: 2-1, 3-10-2
#   - シリーズ語+番号: 資料1, 資料-1, 資料 1, 序．1, (資料)12, ［序］-3
#
# ※ 図・表の抽出機能は本ファイルから完全に削除しています。

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
st.set_page_config(page_title="📄 頁ラベル抽出（1頁=高々1）+ 連番チェック", page_icon="📄", layout="wide")
st.title("📄 頁ラベル抽出（1頁=高々1）→ 連番チェック")

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
    """PDFを1ページずつテキスト抽出して返す。PyMuPDF優先、なければpdfplumber。"""
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
# 正規化・ラベル判定に使う基本パターン定義
# =========================

# HY:
# 各種「ハイフン（-）」や「長音（ー）」をひとまとめに扱う。
# 例: -, ‐, ‒, –, —, ―, −, －, ー
HY  = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D\u30FC]"

# NUM:
# 半角・全角の数字をまとめて認識。
NUM = r"[0-9０-９]+"

# ALPHAJP:
# 英字・ひらがな・カタカナ・漢字を包括（シリーズ語に利用）。
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"

# 行末のリーダー（……・･・等）を削るための定義。
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"
LEADERS_SPACED     = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"


# =========================
# 文字正規化ユーティリティ
# =========================
def z2h_numhy(s: str) -> str:
    """
    全角数字/括弧/角括弧を半角化し、各種ハイフン類を '-' に統一。
    """
    s = (s or "").replace("\u3000", " ")  # 全角スペース→半角
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝", "0123456789()[]{}"))
    return re.sub(HY, "-", s)

def normalize_strict(s: str) -> str:
    """
    行末のリーダー削除・空白圧縮などの行正規化。
    """
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)  # 末尾の……などを削除
    s = re.sub(r"[ \t]+", " ", s)                   # 連続空白を1個へ
    return s.strip()


# =========================
# 頁ラベル検出用の正規表現
# =========================
def build_label_line_regex_mixed() -> re.Pattern:
    """
    行単独で現れる頁ラベル（数字 / 章-頁 / シリーズ+数字）を検出。
    例: "12", "2-1", "3-10-2", "資料1", "資料-1", "資料 1", "序．1", "(資料)12", "［序］-3"
        先頭の "p." / "page" も任意で許容。
    """
    core_seq    = r"[0-9０-９]{1,6}"                # 12
    core_chap   = rf"{NUM}(?:\s*{HY}\s*{NUM})+"     # 2-1, 3-10-2（空白OK）
    series_word = rf"[（(［\[]?{ALPHAJP}[）)\]］]?"  # (資料) / ［序］ など
    SEP_OPT     = rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"  # ハイフン/ドット/空白/省略
    core_series = rf"{series_word}{SEP_OPT}{NUM}"
    core = rf"(?:{core_seq}|{core_chap}|{core_series})"

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
    1ページのテキストから、行単独の頁ラベルを高々1つ抽出。
    戻り値: (label or None, matched_line or None)
    """
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
    """
    ラベルを seq / chap / series / unknown に分類し、比較用の値を返す。
    """
    lab = z2h_numhy(label)
    lab_chap = re.sub(r"\s*-\s*", "-", lab)

    # 純数字
    if re.fullmatch(r"[0-9]+", lab_chap):
        return "seq", int(lab_chap)

    # 章-頁（2-1 / 3-10-2）
    if re.fullmatch(r"[0-9]+(?:-[0-9]+)+", lab_chap):
        return "chap", [int(p) for p in lab_chap.split("-")]

    # シリーズ語 + 数字
    series_pat = re.compile(
        rf"""^
        [（(［\[]?           # 開きカッコ任意
        ({ALPHAJP})          # シリーズ語
        [）)\]］]?           # 閉じカッコ任意
        (?:\s*(?:{HY}|[\.．・･])\s*|\s+)?  # 区切り or 空白 or 省略
        ([0-9]+)
        $""", re.X
    )
    m = series_pat.fullmatch(lab_chap)
    if m:
        return "series", (m.group(1), int(m.group(2)))

    return "unknown", None


def valid_and_reason_auto(label: str, prev_ok: Optional[str]) -> Tuple[bool, str]:
    """
    見つかったラベル列に対して連番妥当性を判定。
    """
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
# ダウンロード（サイドバー）
# =========================
with st.sidebar:
    st.markdown("### ダウンロード")
    if not df_per_page.empty:
        buf = io.StringIO(); df_per_page.to_csv(buf, index=False)
        st.download_button("📥 per_page_labels.csv",
                           data=buf.getvalue().encode("utf-8-sig"),
                           file_name="per_page_labels.csv",
                           mime="text/csv",
                           use_container_width=True)
    if not df_seq.empty:
        buf = io.StringIO(); df_seq.to_csv(buf, index=False)
        st.download_button("📥 label_sequence_check.csv",
                           data=buf.getvalue().encode("utf-8-sig"),
                           file_name="label_sequence_check.csv",
                           mime="text/csv",
                           use_container_width=True)


# =========================
# デバッグ
# =========================
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.code(f"LABEL_LINE_RE = {LABEL_LINE_RE.pattern}")
