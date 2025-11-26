# -*- coding: utf-8 -*-
# pages/27_グラフ作成.py
# 棒グラフ作成（Plotly）— 軸ラベル調整 & 凡例詳細配置 + エクスパンダ直上トグル
# 仕様ハイライト：
#  - 軸タイトル（文言/フォント/サイズ/タイトル↔目盛の距離 title_standoff）
#  - 目盛（tick）フォント/サイズ、ticks（外/内/なし）、ticklen、ticklabelposition、tickangle
#  - 余白（margin）手動調整
#  - 凡例：枠内/枠外、上下左右・四隅、横向き/縦向き、背景と枠線、フォントサイズ
#  - 内側枠（プロット領域）/外側枠（図全体）
#  - エクスパンダは初期閉。手動で開閉した状態を保持（再描画後も維持）。
#  - エクスパンダの「上」に小さなトグル（チェックボックス）を配置（本体領域は圧迫しない）
#  - 初期化ボタンはウィジェット生成前で安全に実装
#  - 棒の右側への値表示（横棒の場合は右端／縦棒の場合は棒の上）
#  - 値の大きいカテゴリから順にハイライト色で塗り分け（上位K本を指定可能）
#  - ※ グループ化機能は削除（シンプルな単純棒グラフ専用）

from __future__ import annotations
import json
from typing import List, Optional, Dict, Set

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

# プリセット関連（デフォルト値・パレット・フォント候補・サンプルテキスト含む）
from lib.graph.bar.presets import (
    DEFAULTS,
    PRESETS,
    PALETTES,
    sample_hint,
    sample_hint2,
    sample_hint3,
    FONT_CANDS,
    HIGHLIGHT_COLOR_CHOICES,
    NON_HIGHLIGHT_COLOR_CHOICES,  # ★ 非ハイライト色候補を追加
)

# 棒グラフ共通ヘルパ
from lib.graph.bar.helpers import (
    hex_to_rgba,
    auto_bar_width,
    dash_value,
    add_inner_frame,
    # add_outer_frame,
    legend_config,
)

# スタイルパネル UI・データ入力・ダウンロード
from lib.graph.bar.style_panel import render_style_panel
from lib.graph.bar.data_input import render_data_input
from lib.graph.bar.download_panel import render_download_panel

from lib.graph.bar.jsonc_presets import (
    export_jsonc_from_session,
    load_preset_from_jsonc,
    apply_preset_to_session,
)


# =========================
# ページ設定
# =========================
st.set_page_config(page_title="📊 棒グラフ作成（軸・凡例フル調整版）", page_icon="📊", layout="wide")
st.title("📊 棒グラフ作成（Word貼り付け用｜軸・凡例フル調整版）")
st.caption("1行目=タイトル、2行目=ヘッダー、3行目以降=データ。Excelからそのまま貼り付けてください。")


# =========================
# セッション初期化
# =========================
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


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
        # データは保存（解析結果と生テキスト）
        keep_df = st.session_state.get("data_df")
        keep_title = st.session_state.get("data_title", "")
        keep_diag = st.session_state.get("data_diag", {})
        keep_raw = st.session_state.get("raw_text", "")

        # パラメータをデフォルトに戻す
        st.session_state.clear()
        for k, v in DEFAULTS.items():
            st.session_state[k] = v

        # 保存データの再設定（データだけ維持）
        if keep_df is not None:
            st.session_state["data_df"] = keep_df
            st.session_state["data_title"] = keep_title
            st.session_state["data_diag"] = keep_diag
            st.session_state["raw_text"] = keep_raw

        st.rerun()

    
    st.markdown("### 🎛 プリセット")
    preset_name = st.selectbox("レイアウトプリセットを選択", list(PRESETS.keys()), index=0)
    #cps1, cps2 = st.columns(2)

    # 既存のプリセット適用（その場で即反映 & rerun）
    #with cps1:
    if st.button("適用", use_container_width=True):
        apply_preset(PRESETS[preset_name])
        st.success(f"プリセット「{preset_name}」を適用しました。")
        st.rerun()

    # JSONC ダウンロード（常に最新 state を反映）
    #with cps2:
    jsonc_text = export_jsonc_from_session(st.session_state)
    st.download_button(
        "⬇️ JSONCで現在の設定を保存",
        data=jsonc_text.encode("utf-8"),
        file_name="current_preset.jsonc",
        mime="application/json",
        use_container_width=True,
    )


  
    # --- JSONC プリセットのアップロード＆適用 ---
    st.markdown("### 📥 JSONCプリセットの読み込み")
    st.caption("※ プリセットを読み込んだ後は、メイン画面の『🔁 再描画を実行』ボタンを押してグラフを更新してください。")

    # 1) ファイルを選ぶ（選ぶだけではまだ適用しない）
    uploaded = st.file_uploader(
        "JSONC形式のプリセットファイル（.json / .jsonc）を選択",
        type=["json", "jsonc"],
        key="preset_upload",
    )

    # 2) 「このファイルを適用する」ボタン
    if st.button("⬆️ アップロードしたプリセットを適用", use_container_width=True):
        if uploaded is None:
            st.warning("先にJSONCファイルを選択してください。")
        else:
            try:
                raw = uploaded.getvalue().decode("utf-8")
                preset_dict = load_preset_from_jsonc(raw)
                apply_preset_to_session(preset_dict, st.session_state)
                # ここでは st.success も st.rerun も使わない
            except Exception as e:
                st.warning(f"プリセットの読み込みに失敗しました: {e}")



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
st.subheader("1) データ貼り付け")

sample_choice = st.radio(
    "サンプルデータの種類（貼り付け欄が空のときに表示）",
    ("なし", "サンプル1", "サンプル2", "サンプル3"),
    horizontal=True,
)

if sample_choice == "サンプル1":
    current_hint = sample_hint
elif sample_choice == "サンプル2":
    current_hint = sample_hint2
elif sample_choice == "サンプル3":
    current_hint = sample_hint3
else:
    current_hint = ""  # 完全に空

# lib/graph/bar/data_input.py 側で：
# - テキスト貼り付け
# - 解析（parse_pasted_robust）
# - m_k_chart_title / m_k_x_title / m_k_y_title の上書き
# を行い、ここでは DataFrame だけ受け取る
df = render_data_input(
    sample_hint=current_hint,
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
work_df[x_col] = work_df[x_col].astype(str)
if work_df.empty:
    st.warning("プロット対象データが空です。列の選択をご確認ください。")
    st.stop()

# ★ 軸ラベルのデフォルトをここで設定（空のときだけ）
# if st.session_state["m_k_x_title"] == "":
#     st.session_state["m_k_x_title"] = x_col

# if st.session_state["m_k_y_title"] == "":
#     st.session_state["m_k_y_title"] = (
#         " / ".join(y_cols) if len(y_cols) <= 3 else f"{len(y_cols)}系列"
#     )


# =========================
# 3) 棒グラフ設定
# =========================
st.subheader("3) 棒グラフ設定")
cset1, cset2, cset3 = st.columns([1, 1, 1.6])
with cset1:
    st.radio(
        "向き",
        ["縦", "横"],
        horizontal=True,
        key="m_k_orientation",
    )
with cset2:
    stack_mode = st.radio("積み上げ", ["なし", "積み上げ", "割合(%)"], index=0, horizontal=True)

with cset3:
    st.radio(
        "棒の上側（右側）への値表示",
        ["非表示", "右側に表示"],
        horizontal=True,
        key="m_k_bar_label_mode",
    )


# =========================
# プレビュー幅・高さ（黄金比ボタン）
# =========================
col_w, col_h, col_auto = st.columns([1, 1, 1])

# 黄金比（高さ = 幅 × 0.618... とする）
GOLDEN_RATIO = (5 ** 0.5 - 1) / 2  # ≒ 0.618

with col_w:
    preview_w = st.slider(
        "プレビューの幅（px）",
        min_value=300,
        max_value=1400,
        value=st.session_state["m_k_preview_width"],
        step=20,
        key="m_k_preview_width",
    )

with col_auto:
    if st.button("高さを自動に計算"):
        auto_h = int(preview_w * GOLDEN_RATIO)
        st.session_state["m_k_preview_height"] = auto_h

with col_h:
    preview_h = st.slider(
        "プレビューの高さ（px）",
        min_value=100,
        max_value=2000,
        value=st.session_state["m_k_preview_height"],
        step=20,
        key="m_k_preview_height",
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
# タイトル関連
chart_title = st.session_state["m_k_chart_title"]
title_bold = st.session_state["m_k_title_bold"]
title_size = st.session_state["m_k_title_size"]
title_align = st.session_state["m_k_title_align"]

# ---
show_grid = st.session_state["m_k_show_grid"]
palette_name = st.session_state["m_k_palette_name"]
color_alpha = float(st.session_state["m_k_color_alpha"])
font_family = st.session_state["m_k_font_family"]

# 枠線関連
frame_style_inner = st.session_state["m_k_frame_style"]
frame_dash_inner = dash_value(st.session_state["m_k_frame_dash"])

# 軸タイトル
x_title_in = st.session_state["m_k_x_title"].strip()
y_title_in = st.session_state["m_k_y_title"].strip()
use_auto_axis_title = bool(st.session_state["m_k_use_headers_as_axis_title"])

# 凡例関連
show_legend = st.session_state["m_k_show_legend"]
legend_loc = st.session_state["m_k_legend_location"]
legend_orient_sel = st.session_state["m_k_legend_orientation"]
legend_font_size = int(st.session_state["m_k_legend_font_size"])
legend_bg = st.session_state["m_k_legend_bg"]
legend_bcol = st.session_state["m_k_legend_bordercolor"]
legend_bwid = int(st.session_state["m_k_legend_borderwidth"])

orientation = st.session_state["m_k_orientation"]

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

# ★ 横棒用の最大値（X軸の余白用）
_num_vals = pd.to_numeric(work_df[y_cols].stack(), errors="coerce")
if _num_vals.notna().any():
    global_max_value = float(_num_vals.max())
else:
    global_max_value = None

# カラー（パレット）
base_colors = PALETTES[palette_name]
plotly_colors_rgba = [hex_to_rgba(c, color_alpha) for c in base_colors]

# ── 上位カテゴリのハイライト対象を決める（グループ化なし前提） ──
enable_highlight: bool = bool(st.session_state.get("m_k_enable_highlight", False))
highlight_top_k: int = int(st.session_state.get("m_k_highlight_top_k", 3))
highlight_top_k = max(1, highlight_top_k)

highlight_color_hex = st.session_state["m_k_highlight_color"]
highlight_rgba = hex_to_rgba(highlight_color_hex, color_alpha)

nonhighlight_color_hex = st.session_state["m_k_nonhighlight_color"]
nonhighlight_rgba = hex_to_rgba(nonhighlight_color_hex, color_alpha)

top_k_cats: Set[str] = set()
if enable_highlight and len(work_df) > 0:
    rank_df = work_df.copy()
    num_block = rank_df[y_cols].apply(pd.to_numeric, errors="coerce")
    rank_df["_total_"] = num_block.sum(axis=1).fillna(0)

    # 大きい順にソートして上位Kカテゴリを選ぶ
    rank_df = rank_df.sort_values("_total_", ascending=False)
    top_k_cats = set(rank_df.head(highlight_top_k)[x_col].astype(str).tolist())

    # 表示順も「大きい順」に入れ替える
    work_df = (
        work_df.assign(_total_=rank_df["_total_"].values)
        .sort_values("_total_", ascending=False)
        .drop(columns=["_total_"])
    )


# =========================
# 割合(%) モード：行ごとに 100% に正規化
# =========================
if stack_mode == "割合(%)":
    # 数値部分だけ取り出し
    num_block = work_df[y_cols].apply(pd.to_numeric, errors="coerce")

    # 行ごとの合計（カテゴリごとの合計）
    row_sum = num_block.sum(axis=1)

    # 0 で割らないように 0 は NaN に置換
    safe_sum = row_sum.replace(0, np.nan)

    # 各セル / 行合計 × 100 → %
    pct_block = num_block.div(safe_sum, axis=0) * 100.0

    # NaN は 0 にしておく（合計0行など）
    pct_block = pct_block.fillna(0)

    # 正規化した値で work_df を上書き
    for col in y_cols:
        work_df[col] = pct_block[col]





# =========================
# 4) プレビュー
# =========================
st.subheader("4) プレビュー")
st.markdown("### 🔄 プレビュー再描画")
if st.button("🔁 再描画を実行", type="primary", use_container_width=True, key="rerender_button"):
    st.session_state["__force_rerender"] = not st.session_state.get("__force_rerender", False)
    st.rerun()

try:
    fig = go.Figure()

    # 棒の値ラベル表示モード
    bar_label_mode = st.session_state.get("m_k_bar_label_mode", "非表示")
    show_bar_label = (bar_label_mode == "右側に表示")

    # 値ラベルを作る小ヘルパ
    # def make_labels(series: pd.Series) -> List[str]:
    #     vals = series.values
    #     labels: List[str] = []
    #     for v in vals:
    #         try:
    #             fv = float(v)
    #             labels.append(f"{fv:.1f}")
    #         except Exception:
    #             labels.append(str(v))
    #     return labels
    
    def make_labels(series: pd.Series) -> List[str]:
        vals = series.values
        labels: List[str] = []
        for v in vals:
            try:
                fv = float(v)
                if stack_mode == "割合(%)":
                    labels.append(f"{fv:.1f}%")
                else:
                    labels.append(f"{fv:.1f}")
            except Exception:
                labels.append(str(v))
        return labels


    cats_series = work_df[x_col].astype(str)

    # トレース（グループ化なし）
    color_idx = 0
    for yc in y_cols:
        base_col = plotly_colors_rgba[color_idx % len(plotly_colors_rgba)]
        color_idx += 1

        values = work_df[yc]
        labels = make_labels(values)

        # ハイライトONなら「ハイライト色 / 非ハイライト色」で塗り分け
        # ハイライトOFFなら従来通りパレット色を使用
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
            fig.add_trace(go.Bar(**bar_kwargs))
        else:
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
            fig.add_trace(go.Bar(**bar_kwargs))

    # 積み上げモード
    fig.update_layout(
        barmode=("group" if stack_mode == "なし" else "stack" if stack_mode == "積み上げ" else "relative")
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
        l=int(st.session_state["m_k_margin_l"]),
        r=int(st.session_state["m_k_margin_r"]),
        t=int(st.session_state["m_k_margin_t"]),
        b=int(st.session_state["m_k_margin_b"]),
    )

    # レイアウト
    fig.update_layout(
        # --- タイトル設定 ---
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

        # --- 凡例設定 ---
        legend=legend_cfg,
        showlegend=bool(show_legend),

        # --- 全体テンプレート ---
        template="plotly_white",

        # --- マージン ---
        margin=margins,

        # --- プレビューの幅・高さ ---
        width=int(preview_w),
        height=int(preview_h),
        autosize=False,

        # --- 図全体のフォント ---
        font=dict(
            family=None if font_family == "(system default)" else font_family
        ),

        # --- テキストが小さすぎるとき非表示にするルール ---
        uniformtext_minsize=6,
        uniformtext_mode="hide",

        # --- 背景色設定 ---
        plot_bgcolor=st.session_state.get("m_k_plot_bgcolor", "white"),
        paper_bgcolor=st.session_state.get("m_k_paper_bgcolor", "white"),
    )

    # 軸タイトル（未入力なら自動）
    x_title_eff = (x_title_in or None) if use_auto_axis_title else None
    y_title_eff = (y_title_in or None) if use_auto_axis_title else None

    # 軸フォント
    tick_family = st.session_state.get("m_k_tick_font_family", "(グラフ全体と同じ)")
    if tick_family in [None, "", "(グラフ全体と同じ)"]:
        tick_family = None
    axis_title_family = st.session_state.get("m_k_axis_title_family", "(グラフ全体と同じ)")
    if axis_title_family in [None, "", "(グラフ全体と同じ)"]:
        axis_title_family = None

    # ticks/labelpos の整形
    def _ticks_val(v: str) -> str:
        return "" if v == "(なし)" else v

    def _ticklabelpos_x(v: str) -> Optional[str]:
        return {
            "自動": None,
            "外-下": "outside bottom",
            "外-上": "outside top",
            "内-下": "inside bottom",
            "内-上": "inside top",
        }.get(v, None)

    def _ticklabelpos_y(v: str) -> Optional[str]:
        return {
            "自動": None,
            "外-左": "outside left",
            "外-右": "outside right",
            "内-左": "inside left",
            "内-右": "inside right",
        }.get(v, None)

    # 軸適用
    fig.update_xaxes(
        title_text=x_title_eff,
        title_font=dict(
            size=int(st.session_state.get("m_k_axis_title_size", 14)),
            family=axis_title_family,
        ),
        tickfont=dict(
            size=int(st.session_state.get("m_k_tick_font_size", 12)),
            family=tick_family,
        ),
        title_standoff=int(st.session_state.get("m_k_x_title_standoff", 12)),
        ticks=_ticks_val(st.session_state.get("m_k_ticks_x", "outside")),
        ticklen=int(st.session_state.get("m_k_ticklen_x", 6)),
        ticklabelposition=_ticklabelpos_x(st.session_state.get("m_k_ticklabelpos_x", "自動")),
        tickangle=int(st.session_state.get("m_k_tickangle_x", 0)),
        automargin=True,
        showgrid=bool(show_grid),
        gridwidth=1,
        gridcolor="rgba(0,0,0,0.08)" if show_grid else None,
    )
    fig.update_yaxes(
        title_text=y_title_eff,
        title_font=dict(
            size=int(st.session_state.get("m_k_axis_title_size", 14)),
            family=axis_title_family,
        ),
        tickfont=dict(
            size=int(st.session_state.get("m_k_tick_font_size", 12)),
            family=tick_family,
        ),
        title_standoff=int(st.session_state.get("m_k_y_title_standoff", 12)),
        ticks=_ticks_val(st.session_state.get("m_k_ticks_y", "outside")),
        ticklen=int(st.session_state.get("m_k_ticklen_y", 6)),
        ticklabelposition=_ticklabelpos_y(st.session_state.get("m_k_ticklabelpos_y", "自動")),
        tickangle=int(st.session_state.get("m_k_tickangle_y", 0)),
        automargin=True,
        showgrid=bool(show_grid),
        gridwidth=1,
        gridcolor="rgba(0,0,0,0.08)" if show_grid else None,
    )


    if orientation == "横":
        # Y軸は上が一番上になるよう反転
        fig.update_yaxes(autorange="reversed")

        # 値表示モード（右側に表示）のときだけ余白を付ける
        show_bar_label = (st.session_state.get("m_k_bar_label_mode") == "右側に表示")

        if show_bar_label:
            # ---- 横棒のときの最大値（stackモードを考慮） ----
            num_block = work_df[y_cols].apply(pd.to_numeric, errors="coerce")

            if stack_mode == "なし":
                # 非積み上げ → 各科目の最大値
                max_val = num_block.max().max()
            else:
                # 積み上げ → 合計値の最大
                max_val = num_block.sum(axis=1).max()

            # ---- 右側に15%余白を加えた range を設定 ----
            if pd.notna(max_val) and max_val > 0:
                fig.update_xaxes(range=[0, max_val * 1.1])

    if orientation == "縦":
        # 値表示モード（右側に表示 = 棒の上に表示）のときだけ余白を付ける
        show_bar_label = (st.session_state.get("m_k_bar_label_mode") == "右側に表示")

        if show_bar_label:
            # ---- 縦棒のときの最大値（stackモードを考慮）----
            num_block = work_df[y_cols].apply(pd.to_numeric, errors="coerce")

            if stack_mode == "なし":
                # 非積み上げ → 単独最大値
                max_val = num_block.max().max()
            else:
                # 積み上げ → 合計値の最大
                max_val = num_block.sum(axis=1).max()

            # ---- 上に15%余白を加えた range を設定 ----
            if pd.notna(max_val) and max_val > 0:
                fig.update_yaxes(range=[0, max_val * 1.1])


    # 枠
    add_inner_frame(
        fig,
        kind=frame_style_inner,
        line_width=2,
        line_dash=frame_dash_inner,
        use_domain=bool(st.session_state.get("m_k_frame_ref_domain", True)),
    )

    # ラベル非表示モードのときは念のため text 系をクリア
    if not show_bar_label:
        fig.update_traces(text=None, texttemplate=None)

    # プレビュー描画
    st.plotly_chart(
        fig,
        use_container_width=False,
        theme=None,
        config={
            "responsive": False,
            "displaylogo": False,
            "toImageButtonOptions": {"format": "png", "filename": "bar_chart", "scale": 2},
        },
    )

except Exception as e:
    st.error(f"プレビュー生成エラー: {e}")
    st.stop()


# =========================
# 5) ダウンロード（モジュール化）
# =========================
render_download_panel(fig=fig, preview_h=preview_h)
