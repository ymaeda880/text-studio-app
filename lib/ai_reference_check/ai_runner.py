# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/ai_runner.py
# ============================================================
# AI図表チェック：AI実行 wrapper
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pathlib import Path
from typing import Any, Dict, Tuple

import streamlit as st

from common_lib.busy import busy_run
from common_lib.ai.routing import call_text
from common_lib.ai.usage_extract import extract_text_in_out_tokens
from common_lib.busy.apply_text_result import apply_text_result_to_busy


# ============================================================
# AI実行：busy_run付き call_text
# ============================================================
def run_reference_check_call_text_with_busy(
    *,
    projects_root: Path,
    user_sub: str,
    app_name: str,
    page_name: str,
    provider: str,
    model: str,
    system_text: str,
    prompt_text: str,
    max_output_tokens: int,
    feature: str,
    action: str,
    meta: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    # ------------------------------------------------------------
    # 直近実行情報を初期化
    # ------------------------------------------------------------
    st.session_state.ai_ref_last_in_tok = None
    st.session_state.ai_ref_last_out_tok = None
    st.session_state.ai_ref_last_cost_obj = None
    st.session_state.ai_ref_last_provider = str(provider)
    st.session_state.ai_ref_last_model = str(model)

    # ------------------------------------------------------------
    # usage行の初期化
    # ------------------------------------------------------------
    usage_row: Dict[str, Any] = {
        "provider": str(provider),
        "model": str(model),
        "in_tokens": "",
        "out_tokens": "",
        "note": "",
        "run_id": "",
    }

    # ------------------------------------------------------------
    # busy_run付きAI実行
    # ------------------------------------------------------------
    with busy_run(
        projects_root=projects_root,
        user_sub=str(user_sub),
        app_name=str(app_name),
        page_name=str(page_name),
        task_type="text",
        provider=str(provider),
        model=str(model),
        meta={
            "feature": feature,
            "action": action,
            **meta,
            "prompt_chars": int(len(prompt_text)),
        },
    ) as br:
        res = call_text(
            provider=str(provider),
            model=str(model),
            prompt=str(prompt_text),
            system=str(system_text),
            temperature=None,
            max_output_tokens=int(max_output_tokens),
            extra=None,
        )

        answer_text = (getattr(res, "text", "") or "").strip()

        if not answer_text:
            br.add_finish_meta(note="empty")
            raise RuntimeError("AIの回答が空でした。")

        pp = apply_text_result_to_busy(
            br=br,
            res=res,
            extract_text_in_out_tokens=extract_text_in_out_tokens,
            note_ok="ok",
            note_no_usage="no_usage",
            note_no_cost="no_cost",
        )

        # ------------------------------------------------------------
        # 直近実行情報を session_state に反映
        # ------------------------------------------------------------
        st.session_state.ai_ref_last_in_tok = pp.in_tokens
        st.session_state.ai_ref_last_out_tok = pp.out_tokens
        st.session_state.ai_ref_last_cost_obj = pp.cost_obj
        st.session_state.ai_ref_last_note = str(pp.note or "")

        # ------------------------------------------------------------
        # usage行に反映
        # ------------------------------------------------------------
        usage_row["in_tokens"] = pp.in_tokens if pp.in_tokens is not None else ""
        usage_row["out_tokens"] = pp.out_tokens if pp.out_tokens is not None else ""
        usage_row["note"] = str(pp.note or "")
        usage_row["run_id"] = br.run_id

        br.add_finish_meta(note=str(pp.note or "ok"))
        st.session_state.ai_ref_last_run_id = br.run_id

    return answer_text, usage_row