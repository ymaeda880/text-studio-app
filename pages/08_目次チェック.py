# -*- coding: utf-8 -*-
# text_studio_app/pages/08_目次チェック.py
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
# session_state keys
# ============================================================
SS_TOC_RESULT_READY = f"{PAGE_NAME}__result_ready"
SS_TOC_PAGES_TEXT = f"{PAGE_NAME}__pages_text"
SS_TOC_LINES = f"{PAGE_NAME}__toc_lines"
SS_TOC_OVERVIEW = f"{PAGE_NAME}__df_overview"
SS_TOC_CHECK = f"{PAGE_NAME}__df_check"
SS_TOC_RESULT = f"{PAGE_NAME}__df_result"
SS_TOC_SUMMARY = f"{PAGE_NAME}__summary"
SS_TOC_VALID_TXT_BYTES = f"{PAGE_NAME}__valid_txt_bytes"
SS_TOC_XLSX_BYTES = f"{PAGE_NAME}__xlsx_bytes"
SS_TOC_XLSX_FILENAME = f"{PAGE_NAME}__xlsx_filename"
SS_TOC_SOURCE = f"{PAGE_NAME}__source_filename"


# ============================================================
# common_lib（正本：ログイン/UI）
# ============================================================
from common_lib.ui.page_header import render_standard_page_header
from common_lib.ui.input_source import render_input_source

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
from lib.toc_check.explanation import (
    render_toc_page_intro,
    render_toc_logic_expander,
)

# ============================================================
# ページ設定（必須・統一）
# ============================================================
st.set_page_config(page_title="📄 Text Studio", page_icon="📄", layout="wide")

# ============================================================
# 共通ヘッダー
# ============================================================
sub, theme, BANNER_KEY, settings = render_standard_page_header(
    st_module=st,
    projects_root=PROJECTS_ROOT,
    app_dir=APP_DIR,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
    title="📄 目次チェック",
    subtitle_text="パターンマッチングによる目次チェック",
    default_banner_key="purple_light",
)

# ============================================================
# ページ説明
# ============================================================
render_toc_page_intro()

# ============================================================
# ロジック説明
# ============================================================
render_toc_logic_expander(
    theme=theme,
)

# ============================================================
# sidebar options
# ============================================================
with st.sidebar:

    st.header("🔧 オプション")

    toc_join_front = st.checkbox(
        "目次抽出は冒頭10pを連結",
        value=True,
        help=(
            "ON：先頭10ページを連結して目次候補を抽出します。\n"
            "OFF：1ページ目のみを対象にします。"
        ),
    )

    search_all_pages = st.checkbox(
        "未検出時に全ページ探索も行う",
        value=False,
        help=(
            "ON：頁ラベル一致が見つからない時に全ページ探索を行います。\n"
            "OFF：通常探索のみを行います。"
        ),
    )

# ============================================================
# 解析ファイル設定
# ============================================================
st.divider()
st.subheader("① PDFファイルの設定")

input_result = render_input_source(
    projects_root=PROJECTS_ROOT,
    user_sub=sub,
    page_name=PAGE_NAME,
    key_prefix=f"{PAGE_NAME}__toc_input",
    allowed_sources=["upload", "inbox"],
    upload_types=["pdf"],
    inbox_kinds=None,
    inbox_extensions=["pdf"],
    input_label="入力方法",
    upload_label="PDF ファイル（.pdf）をアップロードしてください",
    inbox_page_size=8,
)

if not input_result.confirmed:
    st.info("まずチェックするファイルを設定してください。")
    st.stop()


# ============================================================
# 解析・照合を実行
# ============================================================
st.divider()
st.subheader("② 目次チェック")
run = st.button(
    "チェックを実行",
    type="primary",
    key=f"{PAGE_NAME}__run_toc_check",
)

# ============================================================
# cached result check
# ============================================================
has_cached = (
    bool(st.session_state.get(SS_TOC_RESULT_READY))
    and st.session_state.get(SS_TOC_SOURCE) == input_result.file_name
)

if (not run) and (not has_cached):
    st.stop()

# ============================================================
# PDF 読み込み（ページごとテキスト化）
# ============================================================
with tempfile.TemporaryDirectory() as td:
    pdf_path = Path(td) / "input.pdf"
    pdf_path.write_bytes(
        input_result.data_bytes
    )
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

base = input_result.file_name.rsplit(".", 1)[0]
xlsx_filename = f"目次チェック_{base}.xlsx"

# ============================================================
# save result to session_state
# ============================================================
st.session_state[SS_TOC_RESULT_READY] = True
st.session_state[SS_TOC_SOURCE] = input_result.file_name
st.session_state[SS_TOC_LINES] = toc_lines
st.session_state[SS_TOC_OVERVIEW] = df_overview
st.session_state[SS_TOC_CHECK] = df_check
st.session_state[SS_TOC_RESULT] = df_result
st.session_state[SS_TOC_SUMMARY] = summary
st.session_state[SS_TOC_XLSX_BYTES] = xlsx_buf.getvalue()
st.session_state[SS_TOC_XLSX_FILENAME] = xlsx_filename


# ============================================================
# ③ 結果をダウンロード
# ============================================================
st.divider()
st.subheader("③ 結果をダウンロード")
st.download_button(
    "📥 結果をExcelで保存",
    data=st.session_state[SS_TOC_XLSX_BYTES],
    file_name=st.session_state[SS_TOC_XLSX_FILENAME],
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)