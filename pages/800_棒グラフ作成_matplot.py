# -*- coding: utf-8 -*-
# pages/56_棒グラフ作成_matplot.py
# 棒グラフ作成（matplotlib）— 軸ラベル調整 & 凡例詳細配置 + エクスパンダ直上トグル
# 仕様ハイライト：
#  - 軸タイトル（文言/フォント/サイズ/タイトル↔目盛の距離 labelpad）
#  - 目盛（tick）フォント/サイズ、ticks（外/内）、ticklen、tickangle
#  - 余白（margin）手動調整
#  - 凡例：枠内/枠外、上下左右・四隅、フォントサイズ
#  - 内側フレーム（プロット領域）/外側フレーム（図全体っぽい枠）
#  - エクスパンダは初期閉。手動で開閉した状態を保持（再描画後も維持）
#  - エクスパンダの「上」に小さなトグル（チェックボックス）を配置
#  - 棒の右側への値表示（横棒の場合は右端／縦棒の場合は棒の上）
#  - 値の大きいカテゴリから順にハイライト色で塗り分け（上位K本を指定可能）
#  - グループ化機能は削除（シンプルな単純棒グラフ専用）

from __future__ import annotations
import json
from typing import List, Optional, Dict, Set

import io
import streamlit as st
import pandas as pd
import numpy as np

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ------- matplotlib 全体設定（日本語 + 改行を素直に扱う）-------
plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["figure.autolayout"] = False
matplotlib.rcParams["text.usetex"] = False
matplotlib.rcParams["mathtext.default"] = "regular"

# 解析ユーティリティ
from lib.graph.parsing_utils import parse_pasted_robust

# プリセット関連（デフォルト値・パレット・フォント候補・サンプルテキスト含む）
from lib.graph.bar.presets import (
    DEFAULTS,
    PRESETS,
    PALETTES,
    sample_hint,
    FONT_CANDS,
    HIGHLIGHT_COLOR_CHOICES,
    NON_HIGHLIGHT_COLOR_CHOICES,
)

# 棒グラフ共通ヘルパ
from lib.graph.bar.helpers import auto_bar_width

# スタイルパネル UI
from lib.graph.bar.style_panel import render_style_panel
from lib.graph.bar.data_input import render_data_input


# =========================
# ページ設定
# =========================
st.set_page_config(
    page_title="📊 棒グラフ作成（軸・凡例フル調整版 / matplotlib）",
    page_icon="📊",
    layout="wide",
)
st.title("📊 棒グラフ作成（Word貼り付け用｜matplotlib｜軸・凡例フル調整版）")
st.caption("1行目=タイトル、2行目=ヘッダー、3行目以降=データ。Excelからそのまま貼り付けてください。")


# =========================
# セッション初期化
# =========================
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# 値ラベル・ハイライト関連の初期値（DEFAULTS に無い場合の保険）
st.session_state.setdefault("m_k_bar_label_mode", "非表示")
st.session_state.setdefault("m_k_enable_highlight", False)
st.session_state.setdefault("m_k_highlight_top_k", 3)

_default_hl_label = next(iter(HIGHLIGHT_COLOR_CHOICES.keys()))
st.session_state.setdefault("m_k_highlight_color_label", _default_hl_label)
st.session_state.setdefault("m_k_highlight_color", HIGHLIGHT_COLOR_CHOICES[_default_hl_label])

# 非ハイライト色の初期値（DEFAULTS に無い場合の保険）
_default_nhl_label = next(iter(NON_HIGHLIGHT_COLOR_CHOICES.keys()))
st.session_state.setdefault("m_k_nonhighlight_color_label", _default_nhl_label)
st.session_state.setdefault("m_k_nonhighlight_color", NON_HIGHLIGHT_COLOR_CHOICES[_default_nhl_label])

# プレビュー寸法（ウィジェット生成前に確定）
pw = int(st.session_state["m_k_preview_width"])
aspect = float(st.session_state["m_k_preview_aspect"])
ph = int(
    max(
        st.session_state["m_k_preview_min_h"],
        min(st.session_state["m_k_preview_max_h"], pw * aspect),
    )
)

if st.session_state.get("m_k_out_w") is None or st.session_state.get("__sizes_initialized") is not True:
    st.session_state["m_k_out_w"] = pw
    st.session_state["m_k_out_h"] = ph
    st.session_state["__sizes_initialized"] = True

PREVIEW_W = pw
PREVIEW_H = ph


# ===== プリセット適用ヘルパ =====
def apply_preset(overrides: Dict[str, object]) -> None:
    """プリセットの値で session_state を上書き"""
    for k, v in overrides.items():
        st.session_state[k] = v


# =========================
# サイドバー（リセット & プリセット）
# =========================
with st.sidebar:
    st.markdown("### 🧼 パラメータのリセット")
    if st.button("🔄 すべて初期値に戻す（安全）", use_container_width=True):
        keep_df = st.session_state.get("__df")
        keep_title = st.session_state.get("__title", "")
        keep_diag = st.session_state.get("__diag", {})
        st.session_state.clear()
        for k, v in DEFAULTS.items():
            st.session_state[k] = v

        # 値ラベル・ハイライト関連も復元
        st.session_state["m_k_bar_label_mode"] = "非表示"
        st.session_state["m_k_enable_highlight"] = False
        st.session_state["m_k_highlight_top_k"] = 3
        st.session_state["m_k_highlight_color_label"] = _default_hl_label
        st.session_state["m_k_highlight_color"] = HIGHLIGHT_COLOR_CHOICES[_default_hl_label]

        # 非ハイライト色も復元
        st.session_state["m_k_nonhighlight_color_label"] = _default_nhl_label
        st.session_state["m_k_nonhighlight_color"] = NON_HIGHLIGHT_COLOR_CHOICES[_default_nhl_label]

        # 寸法再設定
        st.session_state["m_k_out_w"] = PREVIEW_W
        st.session_state["m_k_out_h"] = PREVIEW_H
        st.session_state["__sizes_initialized"] = True
        if keep_df is not None:
            st.session_state["__df"] = keep_df
            st.session_state["__title"] = keep_title
            st.session_state["__diag"] = keep_diag
            st.session_state["__confirmed"] = True
        st.rerun()

    st.markdown("### 🎛 プリセット")
    preset_name = st.selectbox("レイアウトプリセットを選択", list(PRESETS.keys()), index=0)
    cps1, cps2 = st.columns(2)
    with cps1:
        if st.button("適用", use_container_width=True):
            apply_preset(PRESETS[preset_name])
            st.rerun()
    with cps2:
        if st.button("現在の設定をJSONで保存", use_container_width=True):
            export_keys = [k for k in st.session_state.keys() if k.startswith(("m_k_", "k_bar_mode"))]
            export_dict = {k: st.session_state[k] for k in export_keys}
            st.download_button(
                "⬇️ ダウンロード：current_preset.json",
                data=json.dumps(export_dict, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name="current_preset.json",
                mime="application/json",
                use_container_width=True,
            )


# =========================
# ミニトグル用スタイル
# =========================
st.markdown(
    """
<style>
.mini-toggle-row { margin-top: -10px; margin-bottom: -6px; }
.mini-toggle-row .stCheckbox { transform: scale(0.9); transform-origin: left center; }
.mini-toggle-hint { font-size: 0.8rem; color: #666; margin-left: 6px; }
</style>
""",
    unsafe_allow_html=True,
)


def mini_toggle(label: str, key: str):
    """エクスパンダの直前に置く小さめトグル（チェックボックス + ヒント）"""
    c1, c2 = st.columns([0.08, 0.92])
    with c1:
        st.checkbox(" ", key=key)  # 空白ラベル（アクセシビリティ警告回避）
    with c2:
        st.markdown(f'<div class="mini-toggle-hint">{label}</div>', unsafe_allow_html=True)


# =========================
# 1) データ貼り付け（モジュール化）
# =========================
df, title_default = render_data_input(
    sample_hint=sample_hint,
    mini_toggle=mini_toggle,
)


# =========================
# 2) 列選択・整形（グループ化なしのシンプル版）
# =========================
st.subheader("2) 列選択・整形")
all_cols = list(df.columns)
x_col = st.selectbox("カテゴリ列（X軸/ラベル）", all_cols, index=0)

# Y列（初期状態ではX以外すべて選択）
default_y_cols = [c for c in all_cols if c != x_col]
y_cols = st.multiselect(
    "Y（系列）列（複数可）",
    [c for c in all_cols if c != x_col],
    default=default_y_cols,
)
if not y_cols:
    st.warning("Y 列を1つ以上選んでください。")
    st.stop()

# グループ化は行わない：x + y列だけを使用
work_df = df[[x_col] + y_cols].copy()
work_df[x_col] = (
    work_df[x_col]
    .astype(str)
    .str.replace("<br>", "\n")
)
if work_df.empty:
    st.warning("プロット対象データが空です。列の選択をご確認ください。")
    st.stop()


# =========================
# 3) 棒グラフ設定
# =========================
st.subheader("3) 棒グラフ設定")
cset1, cset2, cset3 = st.columns([1, 1, 1.6])
with cset1:
    st.radio(
        "向き",
        ["縦", "横"],
        index=0 if st.session_state.get("m_k_orientation", "縦") == "縦" else 1,
        horizontal=True,
        key="m_k_orientation",
    )
with cset2:
    stack_mode = st.radio("積み上げ", ["なし", "積み上げ", "割合(%)"], index=0, horizontal=True)

with cset3:
    st.radio(
        "棒の右側への値表示",
        ["非表示", "右側に表示"],
        index=0 if st.session_state.get("m_k_bar_label_mode", "非表示") == "非表示" else 1,
        horizontal=True,
        key="m_k_bar_label_mode",
    )

    st.markdown("**上位カテゴリのハイライト**")
    st.checkbox(
        "大きい値から順に色を変える",
        key="m_k_enable_highlight",
        value=bool(st.session_state.get("m_k_enable_highlight", False)),
    )

    if st.session_state["m_k_enable_highlight"]:
        st.number_input(
            "ハイライトする本数（大きい順）",
            min_value=1,
            max_value=50,
            value=int(st.session_state.get("m_k_highlight_top_k", 3)),
            step=1,
            key="m_k_highlight_top_k",
        )

        # セレクトボックスでハイライト色を選択
        hl_label_list = list(HIGHLIGHT_COLOR_CHOICES.keys())
        current_hl_label = st.session_state.get("m_k_highlight_color_label", _default_hl_label)
        try:
            hl_idx = hl_label_list.index(current_hl_label)
        except ValueError:
            hl_idx = 0

        selected_hl_label = st.selectbox(
            "ハイライト色を選択",
            hl_label_list,
            index=hl_idx,
            key="m_k_highlight_color_label",
        )
        st.session_state["m_k_highlight_color"] = HIGHLIGHT_COLOR_CHOICES[selected_hl_label]

        # 非ハイライト色（残りの棒の色）も選択
        nhl_label_list = list(NON_HIGHLIGHT_COLOR_CHOICES.keys())
        current_nhl_label = st.session_state.get("m_k_nonhighlight_color_label", _default_nhl_label)
        try:
            nhl_idx = nhl_label_list.index(current_nhl_label)
        except ValueError:
            nhl_idx = 0

        selected_nhl_label = st.selectbox(
            "ハイライトしていない棒の色",
            nhl_label_list,
            index=nhl_idx,
            key="m_k_nonhighlight_color_label",
        )
        st.session_state["m_k_nonhighlight_color"] = NON_HIGHLIGHT_COLOR_CHOICES[selected_nhl_label]

# プレビュー幅
preview_w = st.slider(
    "プレビューの幅（px）",
    300,
    1400,
    st.session_state["m_k_preview_width"],
    20,
    key="m_k_preview_width",
)
preview_h = int(
    max(
        st.session_state["m_k_preview_min_h"],
        min(
            st.session_state["m_k_preview_max_h"],
            st.session_state["m_k_preview_width"] * float(st.session_state["m_k_preview_aspect"]),
        ),
    )
)

# —— スタイル（上にミニトグル → 本体エクスパンダ）
render_style_panel(
    preview_w=preview_w,
    preview_h=preview_h,
    palettes=PALETTES,
    font_candidates=FONT_CANDS,
    mini_toggle=mini_toggle,
)

# —— 値の参照
chart_title = st.session_state["m_k_chart_title"]
title_bold = st.session_state["m_k_title_bold"]
title_size = st.session_state["m_k_title_size"]
title_align = st.session_state["m_k_title_align"]
show_legend = st.session_state["m_k_show_legend"]
show_grid = st.session_state["m_k_show_grid"]
palette_name = st.session_state["m_k_palette_name"]
color_alpha = float(st.session_state["m_k_color_alpha"])

frame_style_inner = st.session_state.get("m_k_frame_style", "四角")
frame_dash_inner = st.session_state.get("m_k_frame_dash", "実線")
outer_style = st.session_state.get("m_k_outerframe_style", "なし")
outer_dash = st.session_state.get("m_k_outerframe_dash", "実線")
outer_radius_px = int(st.session_state.get("m_k_outer_radius_px", 16))

x_title_in = st.session_state.get("m_k_x_title", "").strip()
y_title_in = st.session_state.get("m_k_y_title", "").strip()
use_auto_axis_title = bool(st.session_state.get("m_k_use_headers_as_axis_title", True))

# 凡例関連
legend_loc = st.session_state.get("m_k_legend_location", "外-上")
legend_font_size = int(st.session_state.get("m_k_legend_font_size", 12))

orientation = st.session_state.get("m_k_orientation", "縦")

# ==== 棒幅 ====
cats = work_df[x_col].astype(str).tolist()
num_series = len(y_cols)
is_stacked = stack_mode != "なし"
bars_per_cat = 1 if is_stacked else max(1, num_series)
bar_width = (
    auto_bar_width(int(st.session_state["m_k_preview_width"]), len(cats), bars_per_cat)
    if st.session_state["k_bar_mode"] == "自動"
    else float(st.session_state["m_manual_bar_width"])
)
if not is_stacked:
    slots = len(y_cols)
    if bar_width * slots > 0.98:
        st.info("棒が重なり気味です。『棒の太さ』を少し下げると見やすくなります。")

# ★ 値の最大値（ラベル用余白）
_num_vals = pd.to_numeric(work_df[y_cols].stack(), errors="coerce")
if _num_vals.notna().any():
    global_max_value = float(_num_vals.max())
else:
    global_max_value = None

# カラー（パレット）
base_colors = PALETTES[palette_name]

# ── 上位カテゴリのハイライト対象を決める ──
enable_highlight: bool = bool(st.session_state.get("m_k_enable_highlight", False))
highlight_top_k: int = int(st.session_state.get("m_k_highlight_top_k", 3))
highlight_top_k = max(1, highlight_top_k)

highlight_color_hex = st.session_state.get("m_k_highlight_color", HIGHLIGHT_COLOR_CHOICES[_default_hl_label])
nonhighlight_color_hex = st.session_state.get(
    "m_k_nonhighlight_color",
    NON_HIGHLIGHT_COLOR_CHOICES[_default_nhl_label],
)

top_k_cats: Set[str] = set()
if enable_highlight and len(work_df) > 0:
    rank_df = work_df.copy()
    num_block = rank_df[y_cols].apply(pd.to_numeric, errors="coerce")
    rank_df["_total_"] = num_block.sum(axis=1).fillna(0)

    rank_df = rank_df.sort_values("_total_", ascending=False)
    top_k_cats = set(rank_df.head(highlight_top_k)[x_col].astype(str).tolist())

    work_df = (
        work_df.assign(_total_=rank_df["_total_"].values)
        .sort_values("_total_", ascending=False)
        .drop(columns=["_total_"])
    )
    cats = work_df[x_col].astype(str).tolist()


# =========================
# 4) プレビュー
# =========================
st.subheader("4) プレビュー")
st.markdown("### 🔄 プレビュー再描画")
if st.button("🔁 再描画を実行", type="primary", use_container_width=True, key="rerender_button"):
    st.session_state["__force_rerender"] = not st.session_state.get("__force_rerender", False)
    st.rerun()


def _mpl_legend_loc(loc_key: str):
    """凡例位置キーを matplotlib の loc / bbox に変換"""
    loc = "upper right"
    bbox = None

    if "外-上" in loc_key:
        loc = "lower center"
        bbox = (0.5, 1.02)
    elif "外-右" in loc_key:
        loc = "center left"
        bbox = (1.02, 0.5)
    elif "内-右上" in loc_key:
        loc = "upper right"
    elif "内-左上" in loc_key:
        loc = "upper left"
    elif "内-右下" in loc_key:
        loc = "lower right"
    elif "内-左下" in loc_key:
        loc = "lower left"
    return loc, bbox


def _mpl_linestyle(dash_label: str) -> str:
    if dash_label == "点線":
        return "--"
    if dash_label == "破線":
        return "-."
    if dash_label == "点線(細)":
        return ":"
    return "-"  # 実線


def _add_outer_frame(fig, radius_px: int, dash_label: str, style: str):
    """図全体に外枠っぽい枠を描く"""
    if style == "なし":
        return

    linestyle = _mpl_linestyle(dash_label)
    ax_outer = fig.add_axes([0, 0, 1, 1], zorder=-1)
    ax_outer.set_axis_off()
    box = FancyBboxPatch(
        (0.01, 0.01),
        0.98,
        0.98,
        boxstyle=f"round,pad=0.01,rounding_size={radius_px}",
        transform=ax_outer.transAxes,
        linewidth=1.5,
        edgecolor="black",
        facecolor="none",
        linestyle=linestyle,
    )
    ax_outer.add_patch(box)


try:
    # =========================
    # 図のサイズ設定（px → inch）
    # =========================
    dpi = 100.0

    base_w_px = int(st.session_state["m_k_preview_width"])
    base_h_px = int(preview_h)

    orientation = st.session_state.get("m_k_orientation", "縦")
    if orientation == "横":
        # 横棒グラフは横幅を少し絞る
        fig_w_px = int(base_w_px * 0.65)
    else:
        fig_w_px = base_w_px

    fig_h_px = base_h_px

    fig_w_in = fig_w_px / dpi
    fig_h_in = fig_h_px / dpi

    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in), dpi=dpi)

    # 背景色
    plot_bg = st.session_state.get("m_k_plot_bgcolor", "white")
    paper_bg = st.session_state.get("m_k_paper_bgcolor", "white")
    fig.patch.set_facecolor(paper_bg)
    ax.set_facecolor(plot_bg)

    # 棒の値ラベル表示モード
    bar_label_mode = st.session_state.get("m_k_bar_label_mode", "非表示")
    show_bar_label = (bar_label_mode == "右側に表示")

    cats_series = work_df[x_col].astype(str)
    index = np.arange(len(cats_series))

    # データ（割合モードなら正規化）
    values_df = work_df[y_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    if stack_mode == "割合(%)":
        row_sums = values_df.sum(axis=1).replace(0, np.nan)
        values_df = values_df.div(row_sums, axis=0) * 100.0
        values_df = values_df.fillna(0.0)

    orientation = st.session_state.get("m_k_orientation", "縦")

    # 描画
    bar_containers: List = []
    total_bottom = np.zeros(len(index))

    if not is_stacked:
        # グループ棒グラフ
        for i, yc in enumerate(y_cols):
            offset = (i - (num_series - 1) / 2.0) * bar_width
            vals = values_df[yc].values

            if enable_highlight:
                colors = [
                    highlight_color_hex if (c in top_k_cats) else nonhighlight_color_hex
                    for c in cats_series
                ]
            else:
                base_color = base_colors[i % len(base_colors)]
                colors = [base_color] * len(cats_series)

            if orientation == "縦":
                rects = ax.bar(index + offset, vals, width=bar_width, label=yc, color=colors, alpha=color_alpha)
            else:
                rects = ax.barh(index + offset, vals, height=bar_width, label=yc, color=colors, alpha=color_alpha)
            bar_containers.append(rects)
    else:
        # 積み上げ棒グラフ
        for i, yc in enumerate(y_cols):
            vals = values_df[yc].values

            if enable_highlight:
                colors = [
                    highlight_color_hex if (c in top_k_cats) else nonhighlight_color_hex
                    for c in cats_series
                ]
            else:
                base_color = base_colors[i % len(base_colors)]
                colors = [base_color] * len(cats_series)

            if orientation == "縦":
                rects = ax.bar(index, vals, width=bar_width, bottom=total_bottom, label=yc, color=colors, alpha=color_alpha)
                total_bottom = total_bottom + vals
            else:
                rects = ax.barh(index, vals, height=bar_width, left=total_bottom, label=yc, color=colors, alpha=color_alpha)
                total_bottom = total_bottom + vals
            bar_containers.append(rects)

    # 軸タイトル（未入力なら自動）
    x_title_eff = (x_title_in or (x_col if use_auto_axis_title else "")) or None
    y_title_auto = " / ".join(y_cols) if len(y_cols) <= 3 else f"{len(y_cols)}系列"
    y_title_eff = (y_title_in or (y_title_auto if use_auto_axis_title else "")) or None

    # フォント系
    axis_title_size = int(st.session_state.get("m_k_axis_title_size", 14))
    tick_font_size = int(st.session_state.get("m_k_tick_font_size", 12))

    # タイトル
    title_text = chart_title or ""
    title_weight = "bold" if title_bold else "normal"
    if title_align == "中央":
        ax.set_title(title_text, fontsize=title_size, fontweight=title_weight, loc="center")
    else:
        ax.set_title(title_text, fontsize=title_size, fontweight=title_weight, loc="left")

    # 軸タイトル & labelpad
    ax.set_xlabel(
        x_title_eff or "",
        fontsize=axis_title_size,
        labelpad=int(st.session_state.get("m_k_x_title_standoff", 12)),
    )
    ax.set_ylabel(
        y_title_eff or "",
        fontsize=axis_title_size,
        labelpad=int(st.session_state.get("m_k_y_title_standoff", 12)),
    )

    # tick フォント & 角度
    tickangle_x = int(st.session_state.get("m_k_tickangle_x", 0))
    tickangle_y = int(st.session_state.get("m_k_tickangle_y", 0))
    ax.tick_params(axis="x", labelsize=tick_font_size)
    ax.tick_params(axis="y", labelsize=tick_font_size)

    # ======== 軸ラベル設定（<br> → 改行） ========
    if orientation == "縦":
        ax.set_xticks(index)
        x_labels = [str(s).replace("<br>", "\n") for s in cats_series]
        ax.set_xticklabels(x_labels, rotation=tickangle_x)
        for tl in ax.get_xticklabels():
            tl.set_multialignment("center")
    else:
        ax.set_yticks(index)
        y_labels = [str(s).replace("<br>", "\n") for s in cats_series]
        ax.set_yticklabels(y_labels, rotation=tickangle_y)
        for tl in ax.get_yticklabels():
            tl.set_multialignment("center")
        ax.invert_yaxis()  # 上が一番大きいカテゴリになるように

    # グリッド
    if show_grid:
        if orientation == "縦":
            ax.grid(True, axis="y", linestyle=":", linewidth=0.8, alpha=0.5)
        else:
            ax.grid(True, axis="x", linestyle=":", linewidth=0.8, alpha=0.5)

    # 軸の最大値を少し広げてラベル用余白を確保
    if global_max_value is not None and global_max_value > 0:
        if orientation == "縦":
            ymin, ymax = ax.get_ylim()
            ax.set_ylim(0, max(ymax, global_max_value * 1.15))
        else:
            xmin, xmax = ax.get_xlim()
            ax.set_xlim(0, max(xmax, global_max_value * 1.15))

    # 値ラベル
    if show_bar_label:
        for rects in bar_containers:
            for rect in rects:
                if orientation == "縦":
                    height = rect.get_height()
                    if height == 0:
                        continue
                    ax.text(
                        rect.get_x() + rect.get_width() / 2.0,
                        rect.get_y() + height,
                        f"{height:.1f}",
                        ha="center",
                        va="bottom",
                        fontsize=tick_font_size,
                    )
                else:
                    width = rect.get_width()
                    if width == 0:
                        continue
                    ax.text(
                        rect.get_x() + width,
                        rect.get_y() + rect.get_height() / 2.0,
                        f"{width:.1f}",
                        ha="left",
                        va="center",
                        fontsize=tick_font_size,
                    )

    # 凡例
    if show_legend:
        loc, bbox = _mpl_legend_loc(legend_loc)
        if bbox is None:
            ax.legend(fontsize=legend_font_size, loc=loc)
        else:
            ax.legend(fontsize=legend_font_size, loc=loc, bbox_to_anchor=bbox)

    # 内側フレーム（axes.spines）
    if frame_style_inner == "なし":
        for spine in ax.spines.values():
            spine.set_visible(False)
    else:
        ls = _mpl_linestyle(frame_dash_inner)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.5)
            spine.set_linestyle(ls)

    # 余白（margin）設定：px → figure fraction
    margin_l = int(st.session_state.get("m_k_margin_l", 60))
    margin_r = int(st.session_state.get("m_k_margin_r", 20))
    margin_t = int(st.session_state.get("m_k_margin_t", 60))
    margin_b = int(st.session_state.get("m_k_margin_b", 60))

    left = margin_l / fig_w_px
    right = 1 - margin_r / fig_w_px
    bottom = margin_b / fig_h_px
    top = 1 - margin_t / fig_h_px
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top)

    # 外枠
    _add_outer_frame(fig, radius_px=outer_radius_px, dash_label=outer_dash, style=outer_style)

    # プレビュー用にPNGを生成して表示（横幅500px固定）
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    st.image(buf, width=500)

except Exception as e:
    st.error(f"プレビュー生成エラー: {e}")
    st.stop()


# =========================
# 5) ダウンロード（matplotlib版）
# =========================
st.subheader("5) ダウンロード")

col_png, col_svg = st.columns(2)

# PNG 出力
with col_png:
    st.markdown("**📥 PNG 画像で保存（Word 貼り付け向き）**")
    buf_png = io.BytesIO()
    fig.savefig(buf_png, format="png", dpi=300, bbox_inches="tight")
    png_bytes = buf_png.getvalue()

    st.download_button(
        "PNG をダウンロード",
        data=png_bytes,
        file_name="bar_chart.png",
        mime="image/png",
        use_container_width=True,
    )

# SVG 出力
with col_svg:
    st.markdown("**📥 SVG 画像で保存（ベクター形式）**")
    buf_svg = io.BytesIO()
    fig.savefig(buf_svg, format="svg", dpi=300, bbox_inches="tight")
    svg_bytes = buf_svg.getvalue()

    st.download_button(
        "SVG をダウンロード",
        data=svg_bytes,
        file_name="bar_chart.svg",
        mime="image/svg+xml",
        use_container_width=True,
    )
