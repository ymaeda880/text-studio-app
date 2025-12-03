# -*- coding: utf-8 -*-
# pages/43_頁抽出チェック.py
#
# 目的：
#   lib/toc_check/toc_segments.py のロジックをそのまま利用して
#   ・PDF → page_text
#   ・ページラベル抽出（1頁=高々1）
#   ・連番チェック(seq/chap/series)
#   を行う。
#
# ※ 図・表抽出ロジックは取り除いてあります。

from __future__ import annotations
import io
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any

import streamlit as st
import pandas as pd

# =========================
# 🔗 重要：共通ロジックをここからインポート
# =========================
from lib.toc_check.toc_segments import (
    pdf_to_text_per_page,
    extract_single_page_label,
    valid_and_reason_auto,
)

# =========================
# ページ設定 & メインUI
# =========================
st.set_page_config(
    page_title="📄 頁ラベル抽出（1頁=高々1）+ 連番チェック",
    page_icon="📄",
    layout="wide"
)

st.title("📄 頁ラベル抽出（1頁=高々1）→ 連番チェック")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 抽出・連番チェックを実行", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    show_debug = st.checkbox("内部情報（デバッグ）を表示", value=False)


if not uploaded or not run:
    st.stop()

# =========================
# PDF → ページ別テキスト
# =========================
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    pdf_path = td / "input.pdf"
    pdf_path.write_bytes(uploaded.getvalue())

    # ★ ここが toc_segments 版
    pages_text: List[str] = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")


# =========================
# 1頁 = 高々1ページラベル抽出
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


# =========================
# 連番チェック（seq/chap/series）
# =========================
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
# XLSX ダウンロード
# =========================
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

def df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    for r in dataframe_to_rows(df, index=False, header=True):
        ws.append(r)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

with st.sidebar:
    st.markdown("### ダウンロード")

    if not df_per_page.empty:
        st.download_button(
            "📘 per_page_labels.xlsx",
            data=df_to_xlsx_bytes(df_per_page, "per_page_labels"),
            file_name="per_page_labels.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    if not df_seq.empty:
        st.download_button(
            "📗 label_sequence_check.xlsx",
            data=df_to_xlsx_bytes(df_seq, "label_sequence_check"),
            file_name="label_sequence_check.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

# =========================
# デバッグ表示
# =========================
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.write("pages_text[0:3] =", pages_text[:3])
