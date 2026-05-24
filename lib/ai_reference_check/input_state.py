# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/input_state.py
# ============================================================
# AI図表チェック：入力候補 state 管理
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import streamlit as st

from lib.ai_reference_check.session_state import clear_ai_reference_loaded_state


# ============================================================
# 入力候補セット
# ============================================================
def set_ai_reference_input_candidate(
    *,
    data_bytes: bytes,
    filename: str,
    sig: str,
) -> None:
    # ------------------------------------------------------------
    # 入力候補を session_state に保持する
    # ------------------------------------------------------------
    st.session_state.ai_ref_input_bytes = data_bytes or b""
    st.session_state.ai_ref_input_name = filename or "input.jsonl"
    st.session_state.ai_ref_input_sig = sig or ""


# ============================================================
# 入力候補クリア
# ============================================================
def clear_ai_reference_input_candidate() -> None:
    # ------------------------------------------------------------
    # 入力候補をクリアする
    # ------------------------------------------------------------
    st.session_state.ai_ref_input_bytes = b""
    st.session_state.ai_ref_input_name = ""
    st.session_state.ai_ref_input_sig = ""


# ============================================================
# 入力候補更新
# ============================================================
def update_ai_reference_input_candidate_if_changed(
    *,
    data_bytes: bytes,
    filename: str,
    sig: str,
) -> bool:
    # ------------------------------------------------------------
    # sig が変わった場合だけ、読み込み済み状態をクリアして入力候補を更新する
    # ------------------------------------------------------------
    current_sig = str(st.session_state.get("ai_ref_input_sig") or "")

    if current_sig == str(sig or ""):
        return False

    clear_ai_reference_loaded_state()

    set_ai_reference_input_candidate(
        data_bytes=data_bytes,
        filename=filename,
        sig=sig,
    )

    return True