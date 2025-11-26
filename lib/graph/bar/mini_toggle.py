# -*- coding: utf-8 -*-
# lib/graph/bar/mini_toggle.py
#
# エクスパンダ直上に置く小さなトグル（チェックボックス）と，
# そのための CSS を注入するユーティリティ。

from __future__ import annotations

import streamlit as st


# =========================================================
# 1) CSS の注入
# =========================================================
def inject_mini_toggle_css() -> None:
    """
    mini_toggle 用の CSS をページに注入する。
    ページ冒頭で 1 回だけ呼び出す想定。

    例：
        from lib.graph.bar.mini_toggle import inject_mini_toggle_css, mini_toggle

        inject_mini_toggle_css()
        ...
        render_style_panel(..., mini_toggle=mini_toggle)
    """
    st.markdown(
        """
<style>

/* ▼ mini-toggle-row 全体の余白をかなり詰める */
.mini-toggle-row {
    margin-top: -12px;
    margin-bottom: -18px;
}

/* ▼ Streamlit checkbox の外側 margin を強制リセット */
.mini-toggle-row .stCheckbox {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

/* ▼ チェックボックス内部のラベル配置と高さを詰める */
.mini-toggle-row .stCheckbox > label {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    line-height: 1.0 !important;
}

/* ▼ その外側の Streamlit コンテナも余白を潰す */
.mini-toggle-row div[data-testid="stHorizontalBlock"] {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

/* ▼ さらに上部に入る stMarkdown の余白を削る */
.mini-toggle-row p {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

</style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# 2) ミニトグル本体
# =========================================================
def mini_toggle(label: str, key: str) -> None:
    """
    エクスパンダの直前に置く小さなトグル（チェックボックス）。

    - CSS クラス .mini-toggle-row で囲んで余白を詰める。
    - label と key だけを指定すれば通常の st.checkbox と同じように使える。

    例：
        mini_toggle("軸・凡例の詳細設定を表示", key="m_k_show_style_panel")
    """
    st.markdown('<div class="mini-toggle-row">', unsafe_allow_html=True)
    st.checkbox(label, key=key)
    st.markdown("</div>", unsafe_allow_html=True)
