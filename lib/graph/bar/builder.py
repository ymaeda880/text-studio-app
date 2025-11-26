# -*- coding: utf-8 -*-
# lib/graph/bar/builder.py
#
# DataFrame とセッション状態から棒グラフ (Plotly) を構築するビルダー。
# - ハイライト（上位Kカテゴリ）判定
# - 割合(%) モードの正規化
# - 値ラベルのフォーマット
# - 軸・凡例・枠線・背景などのレイアウト設定
# - ラベル表示時の余白調整
# - カテゴリラベルを annotation で描画（横棒グラフ向け）

from __future__ import annotations

from typing import List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .presets import PALETTES
from .helpers import (
    hex_to_rgba,
    dash_value,
    legend_config,
    add_inner_frame,
)

# ← ここで、さきほどのヘルパーをまとめて import
from .builder_helpers import (
    SessionStateLike,
    _get_state,
    _make_value_labels,
    _build_axis_tickformat,
    _ticks_val,
    _ticklabelpos_x,
    _ticklabelpos_y,
    _apply_highlight_and_sort,
    _apply_percentage_mode,
    _expand_axis_for_labels,
)


def build_bar_figure(
    df: pd.DataFrame,
    x_col: str,
    y_cols: List[str],
    *,
    stack_mode: str,
    bar_width: float,
    preview_w: int,
    preview_h: int,
    session_state: Optional[SessionStateLike] = None,
) -> go.Figure:
    """
    ページ側から呼び出すメイン関数。
    - df, x_col, y_cols：プロット対象データ（既に列選択済み & スケーリング済み）
    - stack_mode       ：「なし」「積み上げ」「割合(%)」
    - bar_width        ：棒 1 本あたりの幅（auto_bar_width などで計算済み）
    - preview_w, preview_h：レイアウトの width/height
    - session_state    ：省略時は st.session_state を利用

    戻り値：
        構築済みの go.Figure
    """
    state = _get_state(session_state)
    work_df = df.copy()

    # ---- デバッグ用（必要ならコメントアウトを外す）----
    # st.write("DEBUG bar_width in builder =", bar_width)
    # ------------------------------------------------

    # ========= セッション状態からのパラメータ取得 =========
    # タイトル関連
    chart_title = state["m_k_chart_title"]
    title_bold = state["m_k_title_bold"]
    title_size = state["m_k_title_size"]
    title_align = state["m_k_title_align"]

    # ---
    show_grid = state["m_k_show_grid"]
    palette_name = state["m_k_palette_name"]
    color_alpha = float(state["m_k_color_alpha"])
    font_family = state["m_k_font_family"]

    # 枠線関連
    frame_style_inner = state["m_k_frame_style"]
    frame_dash_inner = dash_value(state["m_k_frame_dash"])

    # 軸タイトル
    x_title_in = state["m_k_x_title"].strip()
    y_title_in = state["m_k_y_title"].strip()
    use_auto_axis_title = bool(state["m_k_use_headers_as_axis_title"])

    # 凡例関連
    show_legend = state["m_k_show_legend"]
    legend_loc = state["m_k_legend_location"]
    legend_orient_sel = state["m_k_legend_orientation"]
    legend_font_size = int(state["m_k_legend_font_size"])
    legend_bg = state["m_k_legend_bg"]
    legend_bcol = state["m_k_legend_bordercolor"]
    legend_bwid = int(state["m_k_legend_borderwidth"])

    orientation = state["m_k_orientation"]

    # annotation 系設定
    use_anno_labels = bool(state.get("m_k_use_annotation_labels", False))
    anno_horizontal_only = bool(state.get("m_k_anno_horizontal_only", True))
    if anno_horizontal_only:
        use_anno_now = use_anno_labels and (orientation == "横")
    else:
        use_anno_now = use_anno_labels

    # カラー（パレット）
    base_colors = PALETTES[palette_name]
    plotly_colors_rgba = [hex_to_rgba(c, color_alpha) for c in base_colors]

    # ── ハイライト設定 ──
    enable_highlight: bool = bool(state.get("m_k_enable_highlight", False))
    highlight_top_k: int = int(state.get("m_k_highlight_top_k", 3))
    highlight_top_k = max(1, highlight_top_k)

    highlight_color_hex = state["m_k_highlight_color"]
    highlight_rgba = hex_to_rgba(highlight_color_hex, color_alpha)

    nonhighlight_color_hex = state["m_k_nonhighlight_color"]
    nonhighlight_rgba = hex_to_rgba(nonhighlight_color_hex, color_alpha)

    # 上位カテゴリのハイライト対象を決める & ソート
    work_df, top_k_cats = _apply_highlight_and_sort(
        work_df,
        x_col,
        y_cols,
        enable_highlight=enable_highlight,
        highlight_top_k=highlight_top_k,
    )

    # ── 割合(%) モードなら正規化 ──
    if stack_mode == "割合(%)":
        work_df = _apply_percentage_mode(work_df, y_cols)

    # ========= Figure 構築 =========
    fig = go.Figure()

    # 棒の値ラベル表示モード
    bar_label_mode = state.get("m_k_bar_label_mode", "非表示")
    show_bar_label = bar_label_mode == "表示"

    # ラベル書式用設定
    value_format_mode = state.get("m_k_value_format_mode", "そのまま")
    decimals = int(state.get("m_k_label_decimals", 0))

    cats_series = work_df[x_col].astype(str)

    # トレース（グループ化なし）
    color_idx = 0
    for yc in y_cols:
        base_col = plotly_colors_rgba[color_idx % len(plotly_colors_rgba)]
        color_idx += 1

        values = work_df[yc]
        labels = _make_value_labels(
            values,
            stack_mode=stack_mode,
            value_format_mode=value_format_mode,
            decimals=decimals,
        )

        # ハイライトONなら「ハイライト色 / 非ハイライト色」で塗り分け
        if enable_highlight:
            marker_colors = [
                highlight_rgba if (c in top_k_cats) else nonhighlight_rgba
                for c in cats_series
            ]
        else:
            marker_colors = [base_col for _ in cats_series]

        if orientation == "縦":
            bar_kwargs = dict(
                x=work_df[x_col],
                y=values,
                name=yc,
                width=bar_width,
                marker=dict(color=marker_colors, line=dict(width=0)),
            )

            if show_bar_label:
                bar_kwargs["text"] = labels
                bar_kwargs["textposition"] = "outside"
                bar_kwargs["textfont"] = dict(
                    size=int(state["m_k_label_font_size"]),
                    family=(
                        None
                        if state["m_k_label_font_family"]
                        == "(グラフ全体と同じ)"
                        else state["m_k_label_font_family"]
                    ),
                )

            fig.add_trace(go.Bar(**bar_kwargs))

        else:
            # 横棒
            bar_kwargs = dict(
                y=work_df[x_col],
                x=values,
                name=yc,
                orientation="h",
                width=bar_width,
                marker=dict(color=marker_colors, line=dict(width=0)),
            )

            if show_bar_label:
                bar_kwargs["text"] = labels
                bar_kwargs["textposition"] = "outside"
                bar_kwargs["textfont"] = dict(
                    size=int(state["m_k_label_font_size"]),
                    family=(
                        None
                        if state["m_k_label_font_family"]
                        == "(グラフ全体と同じ)"
                        else state["m_k_label_font_family"]
                    ),
                )

            fig.add_trace(go.Bar(**bar_kwargs))

    # 積み上げモード
    fig.update_layout(
        barmode=(
            "group"
            if stack_mode == "なし"
            else "stack"
            if stack_mode == "積み上げ"
            else "relative"
        )
    )

    # 凡例レイアウト
    legend_cfg = (
        legend_config(
            loc=legend_loc,
            legend_orient_sel=legend_orient_sel,
            legend_bg=legend_bg,
            legend_bcol=legend_bcol,
            legend_bwid=legend_bwid,
            legend_font_size=legend_font_size,
        )
        if show_legend
        else {}
    )

    # 余白
    margins = dict(
        l=int(state["m_k_margin_l"]),
        r=int(state["m_k_margin_r"]),
        t=int(state["m_k_margin_t"]),
        b=int(state["m_k_margin_b"]),
    )

    # annotation 用に左余白を拡大（横棒グラフのみ）
    if use_anno_now and orientation == "横":
        anno_margin_left = int(state.get("m_k_anno_margin_left", 260))
        if margins["l"] < anno_margin_left:
            margins["l"] = anno_margin_left

    # レイアウト（タイトルなど）
    fig.update_layout(
        title=dict(
            text=f"<b>{chart_title}</b>" if title_bold else chart_title,
            x=0.5 if title_align == "中央" else 0.0,
            xanchor="center" if title_align == "中央" else "left",
            y=0.95,
            font=dict(
                size=title_size,
                family=None if font_family == "(system default)" else font_family,
            ),
        ),
        legend=legend_cfg,
        showlegend=bool(show_legend),
        template="plotly_white",
        margin=margins,
        width=int(preview_w),
        height=int(preview_h),
        autosize=False,
        font=dict(
            family=None if font_family == "(system default)" else font_family
        ),
        uniformtext_minsize=6,
        uniformtext_mode="hide",
        plot_bgcolor=state.get("m_k_plot_bgcolor", "white"),
        paper_bgcolor=state.get("m_k_paper_bgcolor", "white"),
    )

    # 軸タイトル（未入力なら自動）
    x_title_eff = (x_title_in or None) if use_auto_axis_title else None
    y_title_eff = (y_title_in or None) if use_auto_axis_title else None

    # 軸フォント
    tick_family = state.get("m_k_tick_font_family", "(グラフ全体と同じ)")
    if tick_family in [None, "", "(グラフ全体と同じ)"]:
        tick_family = None
    axis_title_family = state.get(
        "m_k_axis_title_family", "(グラフ全体と同じ)"
    )
    if axis_title_family in [None, "", "(グラフ全体と同じ)"]:
        axis_title_family = None

    fig.update_xaxes(
        title_text=x_title_eff,
        title_font=dict(
            size=int(state.get("m_k_axis_title_size", 14)),
            family=axis_title_family,
        ),
        tickfont=dict(
            size=int(state.get("m_k_tick_font_size", 12)),
            family=tick_family,
        ),
        title_standoff=int(state.get("m_k_x_title_standoff", 12)),
        ticks=_ticks_val(state.get("m_k_ticks_x", "outside")),
        ticklen=int(state.get("m_k_ticklen_x", 6)),
        ticklabelposition=_ticklabelpos_x(
            state.get("m_k_ticklabelpos_x", "自動")
        ),
        tickangle=int(state.get("m_k_tickangle_x", 0)),
        automargin=True,
        showgrid=bool(show_grid),
        gridwidth=1,
        gridcolor="rgba(0,0,0,0.08)" if show_grid else None,
    )
    fig.update_yaxes(
        title_text=y_title_eff,
        title_font=dict(
            size=int(state.get("m_k_axis_title_size", 14)),
            family=axis_title_family,
        ),
        tickfont=dict(
            size=int(state.get("m_k_tick_font_size", 12)),
            family=tick_family,
        ),
        title_standoff=int(state.get("m_k_y_title_standoff", 12)),
        ticks=_ticks_val(state.get("m_k_ticks_y", "outside")),
        ticklen=int(state.get("m_k_ticklen_y", 6)),
        ticklabelposition=_ticklabelpos_y(
            state.get("m_k_ticklabelpos_y", "自動")
        ),
        tickangle=int(state.get("m_k_tickangle_y", 0)),
        automargin=True,
        showgrid=bool(show_grid),
        gridwidth=1,
        gridcolor="rgba(0,0,0,0.08)" if show_grid else None,
    )


    # ★ 横棒グラフではカテゴリの順番を上から下に揃える
    if orientation == "横":
        fig.update_yaxes(autorange="reversed")

    # ==== 軸のカンマ区切り設定 ====
    value_format_mode_for_axis = value_format_mode
    decimals_for_axis = decimals
    axis_tickformat = _build_axis_tickformat(
        value_format_mode_for_axis, decimals_for_axis
    )

    if axis_tickformat is not None:
        if orientation == "縦":
            # 縦棒 → Y 軸が数値
            fig.update_yaxes(
                tickformat=axis_tickformat,
                separatethousands=True,
            )
        else:
            # 横棒 → X 軸が数値
            fig.update_xaxes(
                tickformat=axis_tickformat,
                separatethousands=True,
            )

    # 値ラベル表示時に上下左右の余白を少し拡げる
    if show_bar_label:
        _expand_axis_for_labels(
            fig,
            orientation=orientation,
            df=work_df,
            y_cols=y_cols,
            stack_mode=stack_mode,
            margin_ratio=1.1,
        )

    # 内側枠
    add_inner_frame(
        fig,
        kind=frame_style_inner,
        line_width=2,
        line_dash=frame_dash_inner,
        use_domain=bool(state.get("m_k_frame_ref_domain", True)),
    )

    # ラベル非表示なら text を消す
    if not show_bar_label:
        fig.update_traces(text=None, texttemplate=None)

    # ==============================
    # カテゴリラベル annotation 追加（横棒グラフ）
    # ==============================
    if use_anno_now and orientation == "横":
        # Y 軸 tick ラベルは消す
        fig.update_yaxes(showticklabels=False)

        # annotation 用フォントなど
        anno_font_family = state.get("m_k_anno_font_family", "(グラフ全体と同じ)")
        if anno_font_family in [None, "", "(グラフ全体と同じ)"]:
            anno_font_family = None
        anno_font_size = int(state.get("m_k_anno_font_size", 12))
        anno_color = state.get("m_k_anno_color", "#000000")
        anno_x = float(state.get("m_k_anno_x", 0.0))
        anno_align = state.get("m_k_anno_align", "left")
        anno_xanchor = state.get("m_k_anno_xanchor", "right")
        anno_yanchor = state.get("m_k_anno_valign", "middle")

        # カテゴリは重複なしで順序維持
        cats_unique = list(dict.fromkeys(cats_series.tolist()))

        for cat in cats_unique:
            fig.add_annotation(
                xref="paper",
                yref="y",
                x=anno_x,
                y=cat,
                text=str(cat),
                showarrow=False,
                xanchor=anno_xanchor,
                yanchor=anno_yanchor,
                align=anno_align,
                font=dict(
                    size=anno_font_size,
                    family=anno_font_family,
                    color=anno_color,
                ),
            )

    return fig
