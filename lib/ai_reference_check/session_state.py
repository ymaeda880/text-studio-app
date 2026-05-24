# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/session_state.py
# ============================================================
# AI図表チェック：session_state 管理
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import pandas as pd
import streamlit as st

from common_lib.ai.models import DEFAULT_TEXT_MODEL_KEY


# ============================================================
# session_state 初期化
# ============================================================
def ensure_ai_reference_check_state() -> None:
    # ------------------------------------------------------------
    # 入力
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_ref_source_file", "")
    st.session_state.setdefault("ai_ref_input_df", pd.DataFrame())
    st.session_state.setdefault("ai_ref_records", [])

    st.session_state.setdefault("ai_ref_input_bytes", b"")
    st.session_state.setdefault("ai_ref_input_name", "")
    st.session_state.setdefault("ai_ref_input_sig", "")

    st.session_state.setdefault("ai_ref_inbox_bytes", b"")
    st.session_state.setdefault("ai_ref_inbox_name", "")
    st.session_state.setdefault("ai_ref_inbox_item_id", "")

    # ------------------------------------------------------------
    # AI結果
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_ref_result_objects", [])
    st.session_state.setdefault("ai_ref_raw_answers", [])
    st.session_state.setdefault("ai_ref_checks_df", pd.DataFrame())
    st.session_state.setdefault("ai_ref_result_df", pd.DataFrame())
    st.session_state.setdefault("ai_ref_xlsx_bytes", b"")

    # ------------------------------------------------------------
    # 実行情報
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_ref_last_run_id", "")
    st.session_state.setdefault("ai_ref_last_model", "")
    st.session_state.setdefault("ai_ref_last_provider", "")
    st.session_state.setdefault("ai_ref_last_in_tok", None)
    st.session_state.setdefault("ai_ref_last_out_tok", None)
    st.session_state.setdefault("ai_ref_last_cost_obj", None)
    st.session_state.setdefault("ai_ref_last_note", "")

    # ------------------------------------------------------------
    # usage集計
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_ref_usage_rows", [])

    # ------------------------------------------------------------
    # AI送信内容
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_ref_last_system_text", "")
    st.session_state.setdefault("ai_ref_last_prompt_text", "")

    # ------------------------------------------------------------
    # モデル設定
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_ref_model_key", DEFAULT_TEXT_MODEL_KEY)
    st.session_state.setdefault("ai_ref_max_output_tokens", 8000)


# ============================================================
# 読み込み・判定結果クリア
# ============================================================
def clear_ai_reference_loaded_state() -> None:
    # ------------------------------------------------------------
    # 入力データ
    # ------------------------------------------------------------
    st.session_state.ai_ref_input_df = pd.DataFrame()
    st.session_state.ai_ref_records = []

    # ------------------------------------------------------------
    # AI判定結果
    # ------------------------------------------------------------
    clear_ai_reference_result_state()


# ============================================================
# AI判定結果クリア
# ============================================================
def clear_ai_reference_result_state() -> None:
    # ------------------------------------------------------------
    # AI結果
    # ------------------------------------------------------------
    st.session_state.ai_ref_result_objects = []
    st.session_state.ai_ref_raw_answers = []
    st.session_state.ai_ref_checks_df = pd.DataFrame()
    st.session_state.ai_ref_result_df = pd.DataFrame()
    st.session_state.ai_ref_xlsx_bytes = b""
    st.session_state.ai_ref_usage_rows = []

    # ------------------------------------------------------------
    # 実行情報
    # ------------------------------------------------------------
    st.session_state.ai_ref_last_run_id = ""
    st.session_state.ai_ref_last_model = ""
    st.session_state.ai_ref_last_provider = ""
    st.session_state.ai_ref_last_in_tok = None
    st.session_state.ai_ref_last_out_tok = None
    st.session_state.ai_ref_last_cost_obj = None
    st.session_state.ai_ref_last_note = ""

    # ------------------------------------------------------------
    # AI送信内容
    # ------------------------------------------------------------
    st.session_state.ai_ref_last_system_text = ""
    st.session_state.ai_ref_last_prompt_text = ""