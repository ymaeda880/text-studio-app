# -*- coding: utf-8 -*-
# lib/graph/bar/helpers.py
#
# 棒グラフ用の共通ヘルパ関数
# - 色変換（HEX → rgba）
# - 棒幅の自動計算
# - 内側/外側の枠線（Plotly shapes）

from __future__ import annotations
from typing import Literal

import numpy as np
import plotly.graph_objects as go


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """#RRGGBB → rgba(r,g,b,a) 文字列に変換"""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def auto_bar_width(preview_px: int, num_cats: int, bars_per_cat: int) -> float:
    """
    プレビュー幅とカテゴリ数・1カテゴリあたりの棒本数から、
    見栄えのよい棒の相対太さ（0〜1）を自動計算。
    """
    preview_px = max(600.0, float(preview_px))
    num_cats = max(1, int(num_cats))
    bars_per_cat = max(1, int(bars_per_cat))

    # 軸方向の利用可能幅から1カテゴリあたりのスロット幅を推定
    slot_px = max(24.0, (preview_px - 120.0) / num_cats)

    # スロット幅の 70% を棒群に割り当てるイメージ
    target_px_per_bar = slot_px * 0.70 / bars_per_cat
    target_px_per_bar = float(np.clip(target_px_per_bar, 6.0, 48.0))

    width_norm = float(np.clip(target_px_per_bar / slot_px, 0.10, 0.95))
    return width_norm


def dash_value(jp: str) -> str:
    """日本語の線種指定 → Plotly の dash 指定に変換"""
    return {"実線": "solid", "破線": "dash", "点線": "dot"}.get(jp, "solid")


def _rounded_rect_path(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
    """paper / domain 上での角丸矩形 path（SVG path 文字列）を生成"""
    w = x1 - x0
    h = y1 - y0
    rr = max(0.0, min(r, min(w, h) / 2.0))
    x0r, x1r = x0 + rr, x1 - rr
    y0r, y1r = y0 + rr, y1 - rr
    return (
        f"M {x0r},{y0} H {x1r} A {rr},{rr} 0 0 1 {x1},{y0r} "
        f"V {y1r} A {rr},{rr} 0 0 1 {x1r},{y1} H {x0r} "
        f"A {rr},{rr} 0 0 1 {x0},{y1r} V {y0r} A {rr},{rr} 0 0 1 {x0r},{y0} Z"
    )


def add_inner_frame(
    fig: go.Figure,
    *,
    kind: Literal["なし", "四角", "角丸"],
    line_width: int,
    line_dash: str,
    # radius_frac: float,
    use_domain: bool,
) -> None:
    """
    プロット領域（内側）の枠線を追加。
    kind: "なし" / "四角" / "角丸"
    use_domain: True → x/y domain, False → paper
    """
    if kind == "なし":
        return

    xr = "x domain" if use_domain else "paper"
    yr = "y domain" if use_domain else "paper"

    if kind == "四角":
        fig.add_shape(
            type="rect",
            xref=xr,
            yref=yr,
            x0=0,
            y0=0,
            x1=1,
            y1=1,
            line=dict(color="rgba(0,0,0,0.8)", width=line_width, dash=line_dash),
            fillcolor="rgba(0,0,0,0)",
            layer="above",
        )





   
  
# =========================
# 凡例レイアウトヘルパ
# =========================
def legend_config(
    loc: str,
    legend_orient_sel: str,
    legend_bg: str,
    legend_bcol: str,
    legend_bwid: int,
    legend_font_size: int,
) -> dict:
    """
    凡例の位置・向き・枠線などをまとめて dict にして返す。
    Plotly layout.legend にそのまま渡せる形。
    """
    orient = {"自動": None, "横(h)": "h", "縦(v)": "v"}.get(legend_orient_sel, None)

    if loc == "外-上":
        cfg = dict(orientation=orient or "h", x=1.0, y=1.02, xanchor="right", yanchor="bottom")
    elif loc == "外-下":
        cfg = dict(orientation=orient or "h", x=1.0, y=-0.20, xanchor="right", yanchor="top")
    elif loc == "外-左":
        cfg = dict(orientation=orient or "v", x=-0.02, y=1.0, xanchor="right", yanchor="top")
    elif loc == "外-右":
        cfg = dict(orientation=orient or "v", x=1.02, y=1.0, xanchor="left", yanchor="top")
    elif loc == "内-右上":
        cfg = dict(orientation=orient or "v", x=0.98, y=0.98, xanchor="right", yanchor="top")
    elif loc == "内-右下":
        cfg = dict(orientation=orient or "v", x=0.98, y=0.02, xanchor="right", yanchor="bottom")
    elif loc == "内-左上":
        cfg = dict(orientation=orient or "v", x=0.02, y=0.98, xanchor="left", yanchor="top")
    elif loc == "内-左下":
        cfg = dict(orientation=orient or "v", x=0.02, y=0.02, xanchor="left", yanchor="bottom")
    else:
        # フォールバック：外上
        cfg = dict(orientation=orient or "h", x=1.0, y=1.02, xanchor="right", yanchor="bottom")

    cfg.update(
        dict(
            bgcolor=legend_bg,
            bordercolor=legend_bcol,
            borderwidth=legend_bwid,
            font=dict(size=legend_font_size),
            traceorder="normal",
        )
    )
    return cfg
