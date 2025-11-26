# -*- coding: utf-8 -*-
# lib/graph/flowchart/lowlevel.py
#
# フローチャート用の低レベル図形 API
# - デフォルトスタイル (DEFAULTS)
# - session_state への初期書き込み
# - 矩形 / テキスト annotation ラッパー

from __future__ import annotations

from typing import Dict, Tuple

import streamlit as st
import plotly.graph_objects as go


# ============================
# デフォルトの設定
# ============================
DEFAULTS: Dict[str, object] = {
    # 箱の枠線・塗り
    "frame_line_color": "black",
    "frame_fill_color": "rgb(0,153,255)",
    "frame_line_width": 1.5,

    # 外枠
    "outer_frame_line_width": 2,

    # タイトルテキスト
    "text_title_xanchor": "left",
    "text_title_yanchor": "middle",
    "text_title_align": "left",
    "text_title_font_size": 18,
    "text_title_font_color": "white",

    # 本文テキスト
    "text_xanchor": "left",
    "text_yanchor": "middle",
    "text_align": "left",
    "text_font_size": 14,
    "text_font_color": "white",
}


# ============================
# DEFAULTS → session_state 初期書き込み
# ============================
def init_flowchart_defaults() -> None:
    """
    DEFAULTS にあるキーを session_state へ初期書き込み。
    すでに session_state に値がある場合は上書きしない。
    """
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ============================
# 低レベル図形 API
# ============================
def add_rect_shape(
    fig: go.Figure,
    pos0: Tuple[float, float],
    pos1: Tuple[float, float],
    *,
    line_color: str | None = None,
    fill_color: str | None = None,
    line_width: float | None = None,
) -> None:
    """
    矩形を 1 つ追加する薄いラッパー。
    pos0=(x0, y0), pos1=(x1, y1)
    """
    x0, y0 = pos0
    x1, y1 = pos1

    ss = st.session_state
    lc = line_color if line_color is not None else ss["frame_line_color"]
    fc = fill_color if fill_color is not None else ss["frame_fill_color"]
    lw = line_width if line_width is not None else ss["frame_line_width"]

    fig.add_shape(
        type="rect",
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        line=dict(color=lc, width=lw),
        fillcolor=fc,
    )


def add_text_annotation(
    fig: go.Figure,
    kind: str,
    text: str,
    pos: Tuple[float, float],
    *,
    xanchor: str | None = None,
    yanchor: str | None = None,
    align: str | None = None,
    font_size: int | None = None,
    font_color: str | None = None,
) -> None:
    """
    テキスト annotation を 1 つ追加するラッパー。
    pos=(x, y)
    kind: "title" / "desc" などでスタイルを切り替える。
    """
    x, y = pos
    ss = st.session_state

    # --- タイトル or 本文のデフォルトを分岐 ---
    if kind == "title":
        default_size = ss["text_title_font_size"]
        default_color = ss["text_title_font_color"]
        default_xanchor = ss["text_title_xanchor"]
        default_yanchor = ss["text_title_yanchor"]
        default_align = ss["text_title_align"]
    else:
        default_size = ss["text_font_size"]
        default_color = ss["text_font_color"]
        default_xanchor = ss["text_xanchor"]
        default_yanchor = ss["text_yanchor"]
        default_align = ss["text_align"]

    # --- None の場合のみデフォルトを使う ---
    final_size = font_size if font_size is not None else default_size
    final_color = font_color if font_color is not None else default_color
    final_xanchor = xanchor if xanchor is not None else default_xanchor
    final_yanchor = yanchor if yanchor is not None else default_yanchor
    final_align = align if align is not None else default_align

    fig.add_annotation(
        x=x,
        y=y,
        text=text,
        showarrow=False,
        xanchor=final_xanchor,
        yanchor=final_yanchor,
        align=final_align,
        font=dict(size=final_size, color=final_color),
    )
