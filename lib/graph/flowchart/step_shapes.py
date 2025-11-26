# -*- coding: utf-8 -*-
# lib/graph/flowchart/step_shapes.py
#
# ステップ単位の図形描画（箱＋タイトル＋説明・矢印）
# 低レベル API は lowlevel.py を使用

from __future__ import annotations

import textwrap
from typing import Dict, Tuple

import plotly.graph_objects as go

from .lowlevel import add_rect_shape, add_text_annotation


# -----------------------------
# 1 ステップの箱（矩形＋タイトル＋説明）
# -----------------------------
def add_step_box(
    fig: go.Figure,
    *,
    x0: float,
    x1: float,
    y_center: float,
    height: float,
    title: str,
    desc: str,
) -> None:
    """1 ステップ分の四角＋タイトル＋説明を追加"""

    y0 = y_center - height / 2
    y1 = y_center + height / 2

    # 本体の矩形（lowlevel ラッパー）
    add_rect_shape(fig, (x0, y0), (x1, y1))

    # タイトル（左寄せ）
    add_text_annotation(
        fig,
        kind="title",
        text=title,
        pos=(x0 + 0.02 * (x1 - x0), y_center + height * 0.25),
    )

    # 説明（左寄せ・改行あり）
    if desc:
        wrapped = "<br>".join(textwrap.wrap(desc, width=26))
        add_text_annotation(
            fig,
            kind="desc",
            text=wrapped,
            pos=(x0 + 0.02 * (x1 - x0), y_center - height * 0.20),
        )


# -----------------------------
# 上下矢印
# -----------------------------
def add_vertical_arrow(
    fig: go.Figure,
    *,
    x: float,
    y_from: float,
    y_to: float,
    color: str = "rgb(0,176,80)",
    width: float = 2,
) -> None:
    """上下方向の矢印を annotation で追加"""

    fig.add_annotation(
        x=x,
        y=y_to,
        ax=x,
        ay=y_from,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.4,
        arrowwidth=width,
        arrowcolor=color,
    )
