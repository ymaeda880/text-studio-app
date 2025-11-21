# -*- coding: utf-8 -*-
# pages/22_目次チェック.py — 目次候補 ↔ 本文（行スキャン）照合（簡略版）

from __future__ import annotations
import io, tempfile
from pathlib import Path
import pandas as pd
import streamlit as st

from lib.toc_segments import (
    pdf_to_text_per_page,
    extract_toc_lines,
    build_segments,
    validate_segments,
    check_toc_by_order,
)

st.set_page_config(page_title="📄 目次チェック（ローカル照合）", page_icon="📄", layout="wide")
st.title("📄 目次チェック")
st.caption("目次候補（目次タイトルと頁）を本文に対して **行ごとに順番に** 照合します。")
st.caption("AIは使用していません．安心してpdfを丸ごとアップロードしてください．")

with st.expander("ℹ️ このツールが拾う目次と頁番号のルール（クリックで展開）", expanded=False):
    st.markdown("""
**概要**: PDFの目次から「見出し＋頁番号」を抽出し、本文の該当ページで行スキャン照合します（2行結合窓対応）。  
- 末尾ラベルの形式: `12`, `1-2`, `3-10-2`, `資料2`, `資料2-1`, `(資料)12` など  
- 本文ページの単独行ラベルを抽出し、**連番/章番号/シリーズ**の妥当性をチェックしてから照合します。  
- 章番号タイトル（例 `4-2-2`）は **完全一致** のみ許可。
""")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
c1, c2 = st.columns([1,1])
with c1:
    toc_join_front = st.checkbox("目次抽出は冒頭10pを連結", value=True)
with c2:
    search_all_pages = st.checkbox("未検出時に全ページ探索も行う", value=False)

run = st.button("▶ 解析・照合を実行", type="primary", use_container_width=True)

if not uploaded or not run:
    st.stop()

with tempfile.TemporaryDirectory() as td:
    pdf_path = Path(td) / "input.pdf"
    pdf_path.write_bytes(uploaded.getvalue())
    pages_text = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")

# 1) 目次候補
front_n = min(10, len(pages_text))
sample_text = "\n".join(pages_text[:front_n]) if toc_join_front else pages_text[0]
toc_lines = extract_toc_lines(sample_text, limit=120)

st.subheader("抽出された目次候補（上位）")
if not toc_lines:
    st.warning("目次候補が見つかりませんでした。")
    st.stop()
st.code("\n".join(toc_lines[:80]))

# 2) 本文 segments 構築 & 検証
segments = build_segments(pages_text)
df_overview = pd.DataFrame([{
    "pdf_page": s["pdf_page"],
    "page_label": s["page_label"],
    "char_count": len(s["body"]),
    "matched_line": (s["matched_line"][:120].replace("\n"," ") if isinstance(s["matched_line"], str) else "-")
} for s in segments])
st.subheader("抽出ページ（各ページの単独行ラベル）— 概観")
st.dataframe(df_overview, use_container_width=True)

rows_check, valid_segments, seg_index = validate_segments(segments)
df_check = pd.DataFrame(rows_check)
st.subheader("📑 ページラベル検証（連番/章番号/シリーズ）")
st.dataframe(df_check, use_container_width=True)

# valid のみ TXT 保存
if valid_segments:
    txt_buf = io.StringIO()
    for s in valid_segments:
        header = f"==== pdf_page={s['pdf_page']} page_label={s['page_label']} (chars={len(s['body'])}) ====\n"
        txt_buf.write(header)
        txt_buf.write(s["body"].rstrip("\n") + "\n\n")
    st.download_button(
        "📥 抽出ページTXTをダウンロード（valid=True のみ）",
        data=txt_buf.getvalue().encode("utf-8"),
        file_name="extracted_pages_valid.txt",
        mime="text/plain"
    )

# 3) 照合
rows = check_toc_by_order(
    toc_lines=toc_lines,
    seg_index=seg_index,
    pages_text=pages_text,
    search_all_pages=search_all_pages,   # ← ユーザー操作で切替
)
df_result = pd.DataFrame(rows)

st.subheader("🔍 照合結果（行ベース）")
st.dataframe(df_result, use_container_width=True)

summary = df_result["判定"].value_counts().to_dict()
st.markdown(f"**結果概要**: {summary}")

# Excel 出力（列幅/文字列セル設定）
xlsx_buf = io.BytesIO()
with pd.ExcelWriter(xlsx_buf, engine="xlsxwriter") as writer:
    sheet = "result"
    df_result.to_excel(writer, index=False, sheet_name=sheet)
    wb = writer.book; ws = writer.sheets[sheet]
    text_fmt = wb.add_format({"num_format": "@"})
    header_fmt = wb.add_format({"bold": True})
    wrap_fmt = wb.add_format({"text_wrap": True})
    cols = list(df_result.columns); col_idx = {n:i for i,n in enumerate(cols)}
    for name in ["目次頁ラベル", "pdf頁ラベル"]:
        if name in col_idx: ws.set_column(col_idx[name], col_idx[name], 16, text_fmt)
    if "一致テキスト行" in col_idx: ws.set_column(col_idx["一致テキスト行"], col_idx["一致テキスト行"], 40, wrap_fmt)
    widths = {"タイトル":28, "pdf頁":10, "判定":12}
    for name, w in widths.items():
        if name in col_idx: ws.set_column(col_idx[name], col_idx[name], w)
    for j, name in enumerate(cols): ws.write(0, j, name, header_fmt)
    ws.freeze_panes(1, 0)

st.download_button(
    "📥 照合結果をExcelで保存 (.xlsx)",
    data=xlsx_buf.getvalue(),
    file_name="toc_check_local_result.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
