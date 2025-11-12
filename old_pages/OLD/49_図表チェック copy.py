# -*- coding: utf-8 -*-
# pages/44_図表抽出.py
# 目的：
#   PDFテキストから「図/表/図表」の
#   ① 行単独の見出し（キャプション）
#   ② 本文中の参照（行途中の言及）
# を分離抽出して一覧表示＋CSV保存するページ。
# さらに各PDFページの「頁ラベル（行単独のページ番号/章-頁/資料1等）」も抽出し、
# 見出し・参照の出力に page_label 列として併記する。

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
st.set_page_config(page_title="🖼️ 図表 抽出（見出し/参照 分離 + 頁ラベル併記）", page_icon="🖼️", layout="wide")
st.title("🖼️ 図表 抽出 — 見出し（行単独）／参照（行途中）＋ 頁ラベル")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 解析を実行", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    ctx_chars  = st.slider("参照の前後コンテキスト文字数", 10, 200, 40, 5)
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
# 正規化ユーティリティ（共通）
# =========================
# 各種ハイフン/長音をまとめるクラス
HY  = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D\u30FC]"
# 数字（半角/全角）
NUM = r"[0-9０-９]+"
# 日本語＋英字（シリーズ語に使う）
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"

# 行末のリーダー（……・･・等）
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"
LEADERS_SPACED     = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"

def z2h_numhy(s: str) -> str:
    """全角数字/記号→半角、各種ハイフン類→ '-' に統一。"""
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝", "0123456789()[]{}"))
    return re.sub(HY, "-", s)

def normalize_strict(s: str) -> str:
    """行単位の正規化（リーダー削除・空白圧縮）。"""
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)  # 行末のリーダー列を削除
    s = re.sub(r"[ \t]+", " ", s)                   # 連続空白を1つに
    return s.strip()


# =========================
# 頁ラベル 抽出（1頁=高々1）
# =========================
def build_label_line_regex_mixed() -> re.Pattern:
    """
    行単独で現れる頁ラベル（数字 / 章-頁 / シリーズ＋番号）を検出する正規表現。
      例: "12", "2-1", "3-10-2", "資料1", "資料-1", "資料 1", "序．1", "(資料)12", "［序］-3"
      先頭の "p." / "page" も任意で許容。
    """
    core_seq    = r"[0-9０-９]{1,6}"                # 12
    core_chap   = rf"{NUM}(?:\s*{HY}\s*{NUM})+"     # 2-1, 3-10-2（空白OK）
    series_word = rf"[（(［\[]?{ALPHAJP}[）)\]］]?"  # (資料) / ［序］ など
    SEP_OPT     = rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"  # ハイフン/ドット/空白/省略
    core_series = rf"{series_word}{SEP_OPT}{NUM}"
    core = rf"(?:{core_seq}|{core_chap}|{core_series})"
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_LINE_RE = build_label_line_regex_mixed()

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
# 図/表/図表 の抽出パターン
# =========================
DOT = r"[\.．・･]"
NUM_ZH = r"[0-9０-９]+"

# 図表番号トークン：
#  例）3.1-2 / ３．１－２ / 3・1-2 / （１） 等の揺れを吸収
# より堅牢な図表番号トークン：
# 例: 3.1-1 / 3-2 / 2.1.3-4 / （1）などをすべて拾う
NUM_TOKEN = rf"""
(
    {NUM_ZH}                                     # 先頭の数字
    (?:\s*(?:{DOT}|{HY})\s*{NUM_ZH})*            # . や - による区切りを複数許容
    |                                            # または
    [（(]\s*{NUM_ZH}\s*[）)]                     # 括弧つき数字
)
"""


# 見出し（行単独）を拾う：
#   「図/表/図表 + 番号」の直後に助詞や読点などが続く行は “本文参照” とみなして除外。
#   区切り（:：.-、）＋タイトル もOK（タイトル無しでもOK）。

# 追加：番号の“続き”が残っていないことを要求する先読み
AFTER_NUM_CONT_BLOCK = rf"(?!\s*(?:{DOT}|{HY})\s*{NUM_ZH})"

# 見出し（行単独）
HEADING_RE = re.compile(
    rf"""^
        \s*(?P<kind>図表|図|表)
        \s*(?P<num>{NUM_TOKEN}){AFTER_NUM_CONT_BLOCK}   # ← ここがポイント
        (?!                          # 見出しではない（参照っぽい）続きを禁止
            [ 　、,．。]*
            (?:に|を|は|へ|で|として|
               に示す|に示した|における|に関する|
               に対する|による|の|等)\b
        )
        \s*(?:[:：.\-．、]\s*(?P<title>.+))?\s*$
    """,
    re.X
)

# 参照（行途中）を拾う：
#   見出し行に含まれる出現は後で span 除外する。
REF_RE = re.compile(
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})(?![0-9])",
    re.X
)

def canon_num(num: str) -> str:
    """図表番号の正規化：全角→半角、（1）→1、全角ドット→., 中黒→.、空白除去。"""
    s = z2h_numhy(num)
    s = re.sub(r"[()（）]", "", s)       # （1）→1
    s = re.sub(DOT, ".", s)             # ．・ → .
    s = re.sub(r"\s*\.\s*", ".", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", "", s)
    return s

def canon_label(kind: str, num: str) -> str:
    """図表キー（例: '図3.1-2'）を正規化して生成。"""
    return f"{kind}{canon_num(num)}"


# =========================
# 見出し（行単独）抽出
# =========================
def extract_headings_from_page(page_text: str) -> List[Dict[str, Any]]:
    """1ページの中から、行単独の見出しを抽出。"""
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
    """見出し行のテキスト範囲（start,end）をページ内オフセットで返す。"""
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


# =========================
# 参照（行途中）抽出（見出し行は除外）
# =========================
def extract_refs_from_page(page_text: str, ctx: int, heading_spans: List[Tuple[int,int]]) -> List[Dict[str, Any]]:
    """本文中の参照（行途中）を抽出。見出し行に含まれる出現は除外。"""
    out: List[Dict[str, Any]] = []
    text = page_text.replace("\r\n","\n").replace("\r","\n")

    for m in REF_RE.finditer(text):
        a, b = m.span()
        # 見出し行の範囲内にある出現は参照から除外
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

        out.append({
            "参照テキスト": m.group(0),
            "図表種類": kind,
            "図表番号": f"{kind}{z2h_numhy(num)}",
            "図表キー": key,
            "context": f"{pre}{post}",  # ヒット以外の前後文脈
            "hit": hit,                 # マッチ箇所そのもの
            "start": a,
            "end": b,
        })
    return out


# =========================
# 全ページ走査（頁ラベル → 見出し/参照）
# =========================
# まず各ページの頁ラベルを抽出
page_labels: List[Optional[str]] = []
per_page_rows: List[Dict[str, Any]] = []
for i, ptxt in enumerate(pages_text, start=1):
    label, matched = extract_single_page_label(ptxt)
    page_labels.append(label)
    per_page_rows.append({
        "pdf_page": i,
        "page_label": label if label else "-",
        "matched_line": matched if matched else "-",
        "has_label": label is not None,
    })
df_per_page_labels = pd.DataFrame(per_page_rows)

# 次に図表 見出し/参照を抽出し、page_label を併記
caption_rows: List[Dict[str, Any]] = []
ref_rows:     List[Dict[str, Any]] = []

for i, ptxt in enumerate(pages_text, start=1):
    page_label = page_labels[i-1] if i-1 < len(page_labels) and page_labels[i-1] else "-"
    # 見出し
    heads = extract_headings_from_page(ptxt)
    for h in heads:
        caption_rows.append({
            "pdf_page": i,
            "page_label": page_label,  # 併記
            **h
        })
    # 参照（見出し行は除外して拾う）
    spans = collect_heading_line_spans(ptxt)
    refs = extract_refs_from_page(ptxt, ctx=ctx_chars, heading_spans=spans)
    for r in refs:
        ref_rows.append({
            "pdf_page": i,
            "page_label": page_label,  # 併記
            **r
        })

df_captions = pd.DataFrame(caption_rows)
df_refs     = pd.DataFrame(ref_rows)

st.subheader("📑 各ページの頁ラベル（1頁=高々1）")
st.dataframe(df_per_page_labels if not df_per_page_labels.empty else pd.DataFrame(), use_container_width=True)

st.subheader("🖼️ 行単独の 図/表/図表 見出し（キャプション）")
st.dataframe(df_captions if not df_captions.empty else pd.DataFrame(), use_container_width=True)

st.subheader("🔗 本文中の 図/表/図表 参照（文脈つき）")
st.dataframe(df_refs if not df_refs.empty else pd.DataFrame(), use_container_width=True)


# =========================
# ダウンロード（サイドバー）
# =========================
with st.sidebar:
    st.markdown("### ダウンロード")
    if not df_per_page_labels.empty:
        buf = io.StringIO(); df_per_page_labels.to_csv(buf, index=False)
        st.download_button("📥 per_page_labels.csv",
                           data=buf.getvalue().encode("utf-8-sig"),
                           file_name="per_page_labels.csv",
                           mime="text/csv",
                           use_container_width=True)
    if not df_captions.empty:
        buf = io.StringIO(); df_captions.to_csv(buf, index=False)
        st.download_button("📥 figure_table_captions.csv",
                           data=buf.getvalue().encode("utf-8-sig"),
                           file_name="figure_table_captions.csv",
                           mime="text/csv",
                           use_container_width=True)
    if not df_refs.empty:
        buf = io.StringIO(); df_refs.to_csv(buf, index=False)
        st.download_button("📥 figure_table_references.csv",
                           data=buf.getvalue().encode("utf-8-sig"),
                           file_name="figure_table_references.csv",
                           mime="text/csv",
                           use_container_width=True)


# =========================
# デバッグ
# =========================
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.code(f"LABEL_LINE_RE = {LABEL_LINE_RE.pattern}")
    st.code(f"HEADING_RE    = {HEADING_RE.pattern}")
    st.code(f"REF_RE        = {REF_RE.pattern}")
