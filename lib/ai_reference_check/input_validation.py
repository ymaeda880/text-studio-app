# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/input_validation.py
# ============================================================
# AI図表チェック：JSONL入力チェック
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import streamlit as st

from lib.ai_reference_check.job_store import is_jsonl_like_file


# ============================================================
# JSONL入力チェック
# ============================================================
def stop_if_invalid_jsonl_input(
    *,
    filename: str,
    data_bytes: bytes,
    invalid_message: str,
    empty_message: str,
) -> None:
    # ------------------------------------------------------------
    # 拡張子チェック
    # ------------------------------------------------------------
    if not is_jsonl_like_file(filename):
        st.error(invalid_message)
        st.stop()

    # ------------------------------------------------------------
    # 空ファイルチェック
    # ------------------------------------------------------------
    if not data_bytes:
        st.warning(empty_message)
        st.stop()