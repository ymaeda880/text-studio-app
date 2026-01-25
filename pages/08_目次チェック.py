# -*- coding: utf-8 -*-
# pages/12_目次チェック.py
# ============================================================
# 📄 目次チェック（ローカル照合 / 非AI）
#
# ✅ 非AIテンプレ準拠：
# - page_session_heartbeat でログイン/heartbeat（利用状況）を記録
# - AI は一切使わない（ローカル照合のみ）
# - busy_run / 実行時間測定は行わない（AIページ専用）
#
# UI方針：
# - use_container_width は使わない
# - st.form は使わない
# - st.button()/st.download_button() に width 引数は使わない
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
import io
import sys
import tempfile
from pathlib import Path

# ============================================================
# imports（3rd party）
# ============================================================
import pandas as pd
import streamlit as st

# ============================================================
# sys.path（テンプレ準拠：common_lib を import できるように）
# ============================================================
_THIS = Path(__file__).resolve()
APP_DIR = _THIS.parents[1]
PROJ_DIR = _THIS.parents[2]
MONO_ROOT = _THIS.parents[3]

for p in (MONO_ROOT, PROJ_DIR, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PROJECTS_ROOT = MONO_ROOT
APP_NAME = _THIS.parents[1].name
PAGE_NAME = _THIS.stem

# ============================================================
# common_lib（正本：ログイン/heartbeat + UI）
# ============================================================
from common_lib.sessions.page_entry import page_session_heartbeat
from common_lib.ui.ui_basics import subtitle
from common_lib.ui.banner_lines import render_banner_line_by_key

# ============================================================
# lib（目次チェック：ローカル照合）
# ============================================================
from lib.toc_check.toc_segments import (
    pdf_to_text_per_page,
    extract_toc_lines,
    build_segments,
    validate_segments,
    check_toc_by_order,
)
from lib.toc_check.explanation import render_toc_logic_expander


# ============================================================
# ページ設定（必須・統一）
# ============================================================
st.set_page_config(page_title="📄 目次チェック（ローカル照合）", page_icon="📄", layout="wide")

render_banner_line_by_key("purple_light")

sub = page_session_heartbeat(
    st,
    PROJECTS_ROOT,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
)

left, right = st.columns([2, 1])
with left:
    st.title("📄 目次チェック")
with right:
    st.success(f"✅ ログイン中: **{sub}**")

subtitle("（非AI / ローカル照合）")
st.caption("目次候補（目次タイトルと頁）を本文に対して **行ごとに順番に** 照合します。")
st.caption("AIは使用していません。安心して PDF を丸ごとアップロードできます。")
st.caption(
    "内部ではパターンマッチによる照合を行います。"
    " 想定しないパターンでは結果が正しくない場合があります。"
    " その際は **管理者に報告**してください（**プログラム修正**で対応します）。"
)

# ============================================================
# ロジック説明（expander）
# ============================================================
render_toc_logic_expander()

# ============================================================
# 入力（PDFアップロード + オプション）
# - type を外して、自前で PDF チェックする
# ============================================================
uploaded = st.file_uploader("PDF をアップロード", type=None)

c1, c2 = st.columns([1, 1])
with c1:
    toc_join_front = st.checkbox("目次抽出は冒頭10pを連結", value=True)
with c2:
    search_all_pages = st.checkbox("未検出時に全ページ探索も行う", value=False)

run = st.button("▶ 解析・照合を実行", type="primary")

# ============================================================
# 実行トリガ（ボタンが押されていなければ何もしない）
# ============================================================
if not run:
    st.stop()

# ============================================================
# 入力チェック
# ============================================================
if uploaded is None:
    st.warning("先に PDF ファイル（.pdf）をアップロードしてください。")
    st.stop()

suffix = Path(uploaded.name).suffix.lower()
if suffix != ".pdf":
    st.error("PDF 以外のファイルがアップロードされました。このページは PDF（.pdf）専用です。")
    st.stop()

# ============================================================
# PDF 読み込み（ページごとテキスト化）
# ============================================================
with tempfile.TemporaryDirectory() as td:
    pdf_path = Path(td) / "input.pdf"
    pdf_path.write_bytes(uploaded.getvalue())
    pages_text = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")

# ============================================================
# 1) 目次候補抽出
# ============================================================
front_n = min(10, len(pages_text))
sample_text = "\n".join(pages_text[:front_n]) if toc_join_front else pages_text[0]
toc_lines = extract_toc_lines(sample_text, limit=120)

st.subheader("抽出された目次候補（上位）")
if not toc_lines:
    st.warning("目次候補が見つかりませんでした。")
    st.stop()
st.code("\n".join(toc_lines[:80]))

# ============================================================
# 2) 本文 segments 構築 & 検証
# ============================================================
segments = build_segments(pages_text)

df_overview = pd.DataFrame(
    [
        {
            "pdf_page": s["pdf_page"],
            "page_label": s["page_label"],
            "char_count": len(s["body"]),
            "matched_line": (
                s["matched_line"][:120].replace("\n", " ")
                if isinstance(s["matched_line"], str)
                else "-"
            ),
        }
        for s in segments
    ]
)

st.subheader("抽出ページ（各ページの単独行ラベル）— 概観")
st.dataframe(df_overview)

rows_check, valid_segments, seg_index = validate_segments(segments)
df_check = pd.DataFrame(rows_check)

st.subheader("📑 ページラベル検証（連番/章番号/シリーズ）")
st.dataframe(df_check)

# ============================================================
# valid のみ TXT 保存
# ============================================================
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
        mime="text/plain",
    )

# ============================================================
# 3) 照合（行ベース）
# ============================================================
rows = check_toc_by_order(
    toc_lines=toc_lines,
    seg_index=seg_index,
    pages_text=pages_text,
    search_all_pages=search_all_pages,  # ← ユーザー操作で切替
)

df_result = pd.DataFrame(rows)

st.subheader("🔍 照合結果（行ベース）")
st.dataframe(df_result)

summary = df_result["判定"].value_counts().to_dict() if "判定" in df_result.columns else {}
st.markdown(f"**結果概要**: {summary}")

# ============================================================
# Excel 出力（列幅/文字列セル設定）
# ============================================================
xlsx_buf = io.BytesIO()
with pd.ExcelWriter(xlsx_buf, engine="xlsxwriter") as writer:
    sheet = "result"
    df_result.to_excel(writer, index=False, sheet_name=sheet)

    wb = writer.book
    ws = writer.sheets[sheet]

    text_fmt = wb.add_format({"num_format": "@"})
    header_fmt = wb.add_format({"bold": True})
    wrap_fmt = wb.add_format({"text_wrap": True})

    cols = list(df_result.columns)
    col_idx = {n: i for i, n in enumerate(cols)}

    for name in ["目次頁ラベル", "pdf頁ラベル"]:
        if name in col_idx:
            ws.set_column(col_idx[name], col_idx[name], 16, text_fmt)

    if "一致テキスト行" in col_idx:
        ws.set_column(col_idx["一致テキスト行"], col_idx["一致テキスト行"], 40, wrap_fmt)

    widths = {"タイトル": 28, "pdf頁": 10, "判定": 12}
    for name, w in widths.items():
        if name in col_idx:
            ws.set_column(col_idx[name], col_idx[name], w)

    for j, name in enumerate(cols):
        ws.write(0, j, name, header_fmt)

    ws.freeze_panes(1, 0)

base = uploaded.name.rsplit(".", 1)[0]
xlsx_filename = f"目次チェック_{base}.xlsx"

st.download_button(
    "📥 照合結果をExcelで保存 (.xlsx)",
    data=xlsx_buf.getvalue(),
    file_name=xlsx_filename,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
