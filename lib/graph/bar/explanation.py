# -*- coding: utf-8 -*-
# lib/bar/explanation.py
#
# 図表番号・タイトル照合ロジックの利用者向け説明（Streamlit用）

from __future__ import annotations
import streamlit as st


def render_numbering_logic_expander() -> None:
    """
    """
    with st.expander("", expanded=False):
        st.markdown()