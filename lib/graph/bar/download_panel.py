# -*- coding: utf-8 -*-
# lib/graph/bar/download_panel.py
#
# 「5) ダウンロード」パネル
# - PNG / SVG 出力（サイズは session_state から取得）

from __future__ import annotations
from typing import Any

import streamlit as st
import plotly.io as pio


def render_download_panel(fig: Any, preview_h: int) -> None:
    """
    「5) ダウンロード」UI を描画する。
    fig: Plotly Figure
    preview_h: プレビュー部分で利用している高さ（px）
    """
    st.markdown("### 📥 Plotly 図のダウンロード")

    # 出力寸法（使用値）
    if st.session_state.get("sync_export_to_preview", True):
        out_w_export = int(st.session_state["m_k_preview_width"])
        out_h_export = int(preview_h)
    else:
        out_w_export = int(st.session_state.get("m_k_out_w", int(st.session_state["m_k_preview_width"])))
        out_h_export = int(st.session_state.get("m_k_out_h", int(preview_h)))

    if st.session_state.get("lock_export_square", False):
        out_h_export = int(out_w_export)

    # PNG
    try:
        png_bytes = pio.to_image(
            fig,
            format="png",
            width=out_w_export,
            height=out_h_export,
            scale=int(max(1, round(int(st.session_state.get("m_k_out_dpi", 220)) / 96))),
        )
        st.download_button(
            "📊 高解像PNGをダウンロード（Word向け）",
            data=png_bytes,
            file_name="bar_chart.png",
            mime="image/png",
            use_container_width=True,
        )
    except Exception as e:
        st.warning(f"PNG生成エラー（kaleido未導入またはフォント未対応の可能性）: {e}")

    # SVG
    try:
        svg_bytes = pio.to_image(
            fig,
            format="svg",
            width=out_w_export,
            height=out_h_export,
            scale=1,
        )
        st.download_button(
            "🖋️ SVGをダウンロード（ベクター）",
            data=svg_bytes,
            file_name="bar_chart.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )
    except Exception as e:
        st.warning(f"SVG生成エラー: {e}")
