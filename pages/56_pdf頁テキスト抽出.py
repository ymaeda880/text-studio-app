# -*- coding: utf-8 -*-
# pages/56_PDF頁テキスト抽出.py
#
# 目的：
#   PDF をアップロードして読み込み，
#   1ページごとのテキストをページ単位で区切って表示・ダウンロードする。

from __future__ import annotations
from pathlib import Path
import tempfile
import io
from typing import List

import streamlit as st

# ==== 共通ライブラリからインポート（14_図表チェック.py などと同じ） ====
from lib.toc_check.toc_segments import pdf_to_text_per_page

# （任意）ここでも PyMuPDF / pdfplumber の有無をチェックしておく
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
st.set_page_config(
    page_title="📄 PDF 頁テキスト抽出",
    page_icon="📄",
    layout="wide",
)

st.title("📄 PDF 頁テキスト抽出")
st.markdown(
    """
PDF のテキスト層からテキストを抽出し，ページごとに区切って表示します．<br>
（OCR は行いません．画像だけのPDFは空になる場合があります．）<br>
PDFから抽出した**テキストをそのまま**表示します．加工は行っていません．
    """,
    unsafe_allow_html=True
)
uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ ページごとのテキストを表示", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    show_download = st.checkbox("全ページを1つのTXTとしてダウンロードリンクを出す", value=True)

if not uploaded or not run:
    st.stop()

if fitz is None and pdfplumber is None:
    st.error(
        "PyMuPDF か pdfplumber のどちらかをインストールしてください。\n"
        "`pip install pymupdf pdfplumber`"
    )
    st.stop()

# =========================
# PDF → ページ別テキスト
# =========================
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    pdf_path = td_path / "input.pdf"
    pdf_path.write_bytes(uploaded.getvalue())

    pages_text: List[str] = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")

# =========================
# 画面表示（ページごとに expander で区切る）
# =========================
if not pages_text:
    st.warning("テキストが抽出できませんでした（画像だけのPDFの可能性があります）。")
else:
    for i, txt in enumerate(pages_text, start=1):
        with st.expander(f"📄 ページ {i}", expanded=(i == 1)):
            # st.text はそのまま表示（改行を維持）
            st.text(txt or "")

# =========================
# TXT ダウンロード（任意）
# =========================
if show_download and pages_text:
    buf = io.StringIO()
    for i, txt in enumerate(pages_text, start=1):
        header = f"==== Page {i} ====\n"
        buf.write(header)
        buf.write((txt or "").rstrip("\n") + "\n\n")

    base = uploaded.name.rsplit(".", 1)[0]
    out_name = f"頁テキスト_{base}.txt"

    st.download_button(
        "📥 全ページテキスト（txt）をダウンロード",
        data=buf.getvalue().encode("utf-8"),
        file_name=out_name,
        mime="text/plain",
        use_container_width=True,
    )
