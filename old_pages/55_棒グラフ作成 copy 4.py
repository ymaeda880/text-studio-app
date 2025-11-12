# -*- coding: utf-8 -*-
# pages/56_グラフ作成.py
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

from __future__ import annotations
import json
from typing import List, Optional, Dict

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

# 解析ユーティリティ
from lib.graph.parsing_utils import parse_pasted_robust

# =========================
# ページ設定
# =========================
st.set_page_config(page_title="📊 棒グラフ作成（軸・凡例フル調整版）", page_icon="📊", layout="wide")
st.title("📊 棒グラフ作成（Word貼り付け用｜Plotly｜軸・凡例フル調整版）")
st.caption("1行目=タイトル、2行目=ヘッダー、3行目以降=データ。Excelからそのまま貼り付けてください。")

# =========================
# デフォルト値
# =========================
DEFAULTS = {
    # 表示・スタイル
    "m_k_chart_title": "",
    "m_k_title_bold": True,
    "m_k_title_size": 22,
    "m_k_title_align": "中央",
    "m_k_show_legend": True,
    "m_k_show_grid": True,
    "m_k_palette_name": "Minimal",
    "m_k_color_alpha": 0.6,
    "m_k_font_family": "(system default)",

    # 凡例（詳細）
    "m_k_legend_location": "外-上",     # 外-上/外-下/外-左/外-右/ 内-右上/内-右下/内-左上/内-左下
    "m_k_legend_orientation": "自動",    # 自動/横(h)/縦(v)
    "m_k_legend_font_size": 16,
    "m_k_legend_bg": "rgba(255,255,255,0.0)",
    "m_k_legend_bordercolor": "rgba(0,0,0,0.3)",
    "m_k_legend_borderwidth": 0,

    # 枠線（内側 / プロット領域）
    "m_k_frame_style": "四角",           # なし/四角/角丸
    "m_k_frame_dash": "実線",            # 実線/破線/点線
    "m_k_corner_radius_frac": 0.025,
    "m_k_frame_ref_domain": True,        # True: x/y domain, False: paper

    # 枠線（外側 / 図全体）
    "m_k_outerframe_style": "なし",
    "m_k_outerframe_dash": "実線",
    "m_k_outer_radius_px": 16,

    # 軸タイトル・目盛（共通）
    "m_k_x_title": "",
    "m_k_y_title": "",
    "m_k_axis_title_size": 16,
    "m_k_axis_title_family": "(グラフ全体と同じ)",
    "m_k_tick_font_size": 16,
    "m_k_tick_font_family": "(グラフ全体と同じ)",
    "m_k_use_headers_as_axis_title": True,

    # 目盛（位置/長さ/ラベル位置/角度）
    "m_k_ticks_x": "outside",           # outside / inside / (なし)
    "m_k_ticks_y": "outside",
    "m_k_ticklen_x": 3,                 # px
    "m_k_ticklen_y": 3,
    "m_k_ticklabelpos_x": "自動",       # 自動/外-下/外-上/内-下/内-上
    "m_k_ticklabelpos_y": "自動",       # 自動/外-左/外-右/内-左/内-右
    "m_k_tickangle_x": 0,               # 度
    "m_k_tickangle_y": 0,

    # 余白
    "m_k_margin_l": 60, "m_k_margin_r": 20, "m_k_margin_t": 60, "m_k_margin_b": 60,

    # 軸タイトル ↔ 目盛の距離
    "m_k_x_title_standoff": 12,
    "m_k_y_title_standoff": 12,

    # プレビューサイズ + アスペクト
    "m_k_preview_width": 820,
    "m_k_preview_aspect": 0.58,      # 高さ = 幅 * 0.58
    "m_k_preview_min_h": 320,
    "m_k_preview_max_h": 800,

    # エクスパンダ初期開閉（初期=閉）
    "exp_style_open": False,
    "exp_group_open": False,
    "exp_diag_open": False,

    # 出力サイズ（PNG/SVG）
    "m_k_out_w": None,   # 初回にプレビューから決定
    "m_k_out_h": None,
    "m_k_out_dpi": 220,
    "sync_export_to_preview": True,
    "lock_export_square": False,

    # 棒の太さ
    "k_bar_mode": "自動",
    "m_manual_bar_width": 0.60,
}

# 初期化
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# プレビュー寸法（ウィジェット生成前に確定）
pw = int(st.session_state["m_k_preview_width"])
aspect = float(st.session_state["m_k_preview_aspect"])
ph = int(max(st.session_state["m_k_preview_min_h"],
             min(st.session_state["m_k_preview_max_h"], pw * aspect)))

if st.session_state.get("m_k_out_w") is None or st.session_state.get("__sizes_initialized") is not True:
    st.session_state["m_k_out_w"] = pw
    st.session_state["m_k_out_h"] = ph
    st.session_state["__sizes_initialized"] = True

PREVIEW_W = pw
PREVIEW_H = ph

# 初期化ボタン（安全）
with st.sidebar:
    st.markdown("### 🧼 パラメータのリセット")
    if st.button("🔄 すべて初期値に戻す（安全）", use_container_width=True):
        keep_df = st.session_state.get("__df")
        keep_title = st.session_state.get("__title", "")
        keep_diag = st.session_state.get("__diag", {})
        st.session_state.clear()
        for k, v in DEFAULTS.items():
            st.session_state[k] = v
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

# ミニトグル用の小さめスタイル（エクスパンダ「上」に置く）
st.markdown("""
<style>
.mini-toggle-row { margin-top: -10px; margin-bottom: -6px; }
.mini-toggle-row .stCheckbox { transform: scale(0.9); transform-origin: left center; }
.mini-toggle-hint { font-size: 0.8rem; color: #666; margin-left: 6px; }
</style>
""", unsafe_allow_html=True)

def mini_toggle(label: str, key: str):
    """エクスパンダの直前に置く小さめトグル（チェックボックス + ヒント）"""
    c1, c2 = st.columns([0.08, 0.92])
    with c1:
        st.checkbox("", key=key)
    with c2:
        st.markdown(f'<div class="mini-toggle-hint">{label}</div>', unsafe_allow_html=True)

# パレット
PALETTES: Dict[str, List[str]] = {
    "Minimal":   ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"],
    "Corporate": ["#2E86AB", "#F6AA1C", "#A23E48", "#33658A", "#55DDE0", "#758E4F"],
    "Playful":   ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6A4C93", "#1A8FE3", "#95D02B"],
}

# ヘルパ
def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def _auto_bar_width(preview_px: int, num_cats: int, bars_per_cat: int) -> float:
    preview_px = max(600.0, float(preview_px))
    num_cats = max(1, int(num_cats))
    bars_per_cat = max(1, int(bars_per_cat))
    slot_px = max(24.0, (preview_px - 120.0) / num_cats)
    target_px_per_bar = slot_px * 0.70 / bars_per_cat
    target_px_per_bar = float(np.clip(target_px_per_bar, 6.0, 48.0))
    width_norm = float(np.clip(target_px_per_bar / slot_px, 0.10, 0.95))
    return width_norm

def _rounded_rect_path(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
    w = x1 - x0; h = y1 - y0
    rr = max(0.0, min(r, min(w, h) / 2.0))
    x0r, x1r = x0 + rr, x1 - rr
    y0r, y1r = y0 + rr, y1 - rr
    return (
        f"M {x0r},{y0} H {x1r} A {rr},{rr} 0 0 1 {x1},{y0r} "
        f"V {y1r} A {rr},{rr} 0 0 1 {x1r},{y1} H {x0r} "
        f"A {rr},{rr} 0 0 1 {x0},{y1r} V {y0r} A {rr},{rr} 0 0 1 {x0r},{y0} Z"
    )

def _dash_value(jp: str) -> str:
    return {"実線": "solid", "破線": "dash", "点線": "dot"}.get(jp, "solid")

def add_inner_frame(fig, *, kind: str, line_width: int, line_dash: str, radius_frac: float, use_domain: bool):
    if kind == "なし":
        return
    xr = "x domain" if use_domain else "paper"
    yr = "y domain" if use_domain else "paper"
    if kind == "四角":
        fig.add_shape(
            type="rect", xref=xr, yref=yr,
            x0=0, y0=0, x1=1, y1=1,
            line=dict(color="rgba(0,0,0,0.8)", width=line_width, dash=line_dash),
            fillcolor="rgba(0,0,0,0)", layer="above",
        )
    elif kind == "角丸":
        path = _rounded_rect_path(0.0, 0.0, 1.0, 1.0, max(0.0, float(radius_frac)))
        fig.add_shape(
            type="path", path=path, xref=xr, yref=yr,
            line=dict(color="rgba(0,0,0,0.8)", width=line_width, dash=line_dash),
            fillcolor="rgba(0,0,0,0)", layer="above",
        )

def add_outer_frame(fig, *, kind: str, line_width: int, line_dash: str, radius_px: int):
    if kind == "なし":
        return
    w = int(fig.layout.width or 800)
    h = int(fig.layout.height or 600)
    m = fig.layout.margin or dict(l=20, r=20, t=60, b=40)
    l = int(getattr(m, "l", 20) or 0)
    r = int(getattr(m, "r", 20) or 0)
    t = int(getattr(m, "t", 60) or 0)
    b = int(getattr(m, "b", 40) or 0)
    x0 = - l / w; y0 = - b / h; x1 = 1 + r / w; y1 = 1 + t / h
    if kind == "四角":
        fig.add_shape(
            type="rect", xref="paper", yref="paper",
            x0=x0, y0=y0, x1=x1, y1=y1,
            line=dict(color="rgba(0,0,0,0.8)", width=line_width, dash=line_dash),
            fillcolor="rgba(0,0,0,0)", layer="above",
        )
    elif kind == "角丸":
        r_frac = max(0.0, float(radius_px) / float(min(w, h)))
        path = _rounded_rect_path(x0, y0, x1, y1, r_frac)
        fig.add_shape(
            type="path", path=path, xref="paper", yref="paper",
            line=dict(color="rgba(0,0,0,0.8)", width=line_width, dash=line_dash),
            fillcolor="rgba(0,0,0,0)", layer="above",
        )

# =========================
# 1) データ貼り付け
# =========================
st.subheader("1) データ貼り付け")

def _ingest_text():
    raw = st.session_state.get("raw_text", "")
    title, new_df, diag = parse_pasted_robust(raw)
    if new_df.empty:
        st.warning("貼り付けを認識できませんでした。タイトル1行 + 表形式にしてください。")
        st.session_state["__confirmed"] = False
        return
    st.session_state["__df"] = new_df
    st.session_state["__title"] = title
    st.session_state["__diag"] = diag
    st.session_state["__confirmed"] = True
    st.session_state["__raw_hash"] = hash(raw)
    st.session_state["__df_version"] = st.session_state.get("__df_version", 0) + 1
    if not st.session_state.get("__title_applied", False):
        st.session_state["m_k_chart_title"] = title or ""
        st.session_state["__title_applied"] = True

sample_hint = """クラス別成績
クラス\t国語\t数学\t英語
A\t68\t72\t81
B\t75\t65\t78
C\t80\t70\t88
"""
st.text_area("Excelの表を貼り付け（1行目=タイトル、2行目=ヘッダー）", sample_hint, height=180, key="raw_text")
st.button("▶️ グラフ作成（解析を実行）", type="primary", on_click=_ingest_text, use_container_width=True)

if "__df" not in st.session_state or not st.session_state.get("__confirmed", False):
    st.info("表を貼り付けたら『グラフ作成（解析を実行）』を押してください。")
    st.stop()

df = st.session_state["__df"]
title_default = st.session_state.get("__title", "")
current_hash = hash(st.session_state.get("raw_text", ""))
if current_hash != st.session_state.get("__raw_hash"):
    st.warning("貼り付け内容が前回の解析後に変更されています。必要なら再度『グラフ作成』を押してください。")

st.success(f"タイトル候補：**{title_default or '(未設定)'}**")
st.dataframe(df.head(50), use_container_width=True)

# —— パース診断（上にミニトグル → 本体エクスパンダ）
st.markdown('<div class="mini-toggle-row"></div>', unsafe_allow_html=True)
mini_toggle("🩺 パース診断を開く（状態を保持）", key="exp_diag_open")
with st.expander("🩺 パース診断（必要時のみ）", expanded=st.session_state["exp_diag_open"]):
    st.json(st.session_state.get("__diag", {}))

# =========================
# 2) 列選択・整形
# =========================
st.subheader("2) 列選択・整形")
all_cols = list(df.columns)
x_col = st.selectbox("カテゴリ列（X軸/ラベル）", all_cols, index=0)
y_cols = st.multiselect("Y（系列）列（複数可）", [c for c in all_cols if c != x_col], default=[c for c in all_cols if c != x_col][:1])
if not y_cols:
    st.warning("Y 列を1つ以上選んでください。"); st.stop()

# —— グループ化（上にミニトグル → 本体エクスパンダ）
st.markdown('<div class="mini-toggle-row"></div>', unsafe_allow_html=True)
mini_toggle("🔧 グループ化設定を開く（状態を保持）", key="exp_group_open")
with st.expander("🔧 グループ化（任意）", expanded=st.session_state["exp_group_open"]):
    gc = st.selectbox("グループ化列（例：性別/クラス 等）", ["(なし)"] + all_cols, index=0)
    group_col: Optional[str] = None if gc == "(なし)" else gc
    agg_func = st.selectbox("集計方法", ["sum", "mean", "median", "max", "min"], index=0)

work_df = df[[x_col] + y_cols + ([group_col] if group_col else [])].copy()
if group_col:
    agg_map = {c: getattr(np, agg_func) for c in y_cols}
    work_df = work_df.groupby([x_col, group_col], dropna=False).agg(agg_map).reset_index()
work_df[x_col] = work_df[x_col].astype(str)
if work_df.empty:
    st.warning("プロット対象データが空です。列の選択をご確認ください。"); st.stop()

# =========================
# 3) 棒グラフ設定
# =========================
st.subheader("3) 棒グラフ設定")
cset1, cset2 = st.columns([1,2])
with cset1:
    orientation = st.radio("向き", ["縦", "横"], index=0, horizontal=True)
with cset2:
    stack_mode  = st.radio("積み上げ", ["なし", "積み上げ", "割合(%)"], index=0, horizontal=True)

# プレビュー幅
preview_w = st.slider("プレビューの幅（px）", 300, 1400, st.session_state["m_k_preview_width"], 20, key="m_k_preview_width")
preview_h = int(max(st.session_state["m_k_preview_min_h"],
                    min(st.session_state["m_k_preview_max_h"],
                        st.session_state["m_k_preview_width"] * float(st.session_state["m_k_preview_aspect"]))))

# —— スタイル（上にミニトグル → 本体エクスパンダ）
st.markdown('<div class="mini-toggle-row"></div>', unsafe_allow_html=True)
mini_toggle("🎨 スタイル設定を開く（状態を保持）", key="exp_style_open")
with st.expander("🎨 スタイル（クイック調整）", expanded=st.session_state["exp_style_open"]):
    # フォント
    st.markdown("**🈺 フォント（Plotly表示/書き出し）**")
    FONT_CANDS = [
        "IPAexGothic", "IPAGothic",
        "Noto Sans CJK JP", "Noto Sans JP",
        "Hiragino Sans", "Hiragino Kaku Gothic ProN",
        "Yu Gothic", "Yu Gothic UI",
        "Meiryo", "Meiryo UI",
        "MS Gothic", "MS PGothic",
        "(system default)",
    ]
    st.selectbox(
        "フォントファミリー（全体）",
        options=FONT_CANDS,
        index=FONT_CANDS.index(st.session_state["m_k_font_family"]) if st.session_state["m_k_font_family"] in FONT_CANDS else FONT_CANDS.index("(system default)"),
        key="m_k_font_family",
    )

    st.divider()
    c1, c2, c3 = st.columns([1.3,1.2,1.2])
    with c1:
        st.text_input("タイトル", key="m_k_chart_title")
        st.checkbox("タイトル太字", key="m_k_title_bold")
        st.slider("タイトル文字サイズ", 10, 36, st.session_state["m_k_title_size"], step=1, key="m_k_title_size")
        st.radio("タイトル位置", ["左","中央"], index=0 if st.session_state["m_k_title_align"] == "左" else 1, horizontal=True, key="m_k_title_align")
        st.selectbox("色パレット", list(PALETTES.keys()), index=list(PALETTES.keys()).index(st.session_state["m_k_palette_name"]), key="m_k_palette_name")
        st.slider("色の透明度（0=透明〜1=不透明）", 0.0, 1.0, st.session_state["m_k_color_alpha"], 0.05, key="m_k_color_alpha")
    with c2:
        # —— 軸ラベル & 目盛 ——（復活＋拡張）
        st.markdown("**📐 軸ラベル**")
        st.checkbox("ヘッダー名を軸タイトルに自動適用（未入力のとき）",
                    key="m_k_use_headers_as_axis_title", value=st.session_state.get("m_k_use_headers_as_axis_title", True))
        ax1, ax2 = st.columns(2)
        with ax1:
            st.text_input("X軸タイトル", key="m_k_x_title", value=st.session_state.get("m_k_x_title", ""))
            st.number_input("X軸 title_standoff（px）", 0, 80, value=int(st.session_state.get("m_k_x_title_standoff", 12)), step=1, key="m_k_x_title_standoff")
        with ax2:
            st.text_input("Y軸タイトル", key="m_k_y_title", value=st.session_state.get("m_k_y_title", ""))
            st.number_input("Y軸 title_standoff（px）", 0, 80, value=int(st.session_state.get("m_k_y_title_standoff", 12)), step=1, key="m_k_y_title_standoff")
        st.number_input("軸タイトルのフォントサイズ", 8, 36, value=int(st.session_state.get("m_k_axis_title_size", 14)), step=1, key="m_k_axis_title_size")
        AXIS_FONTS = ["(グラフ全体と同じ)"] + [f for f in FONT_CANDS if f != "(system default)"]
        st.selectbox("軸タイトルのフォント", AXIS_FONTS,
                     index=AXIS_FONTS.index(st.session_state.get("m_k_axis_title_family", "(グラフ全体と同じ)")) if st.session_state.get("m_k_axis_title_family") in AXIS_FONTS else 0,
                     key="m_k_axis_title_family")
        st.number_input("目盛（tick）のフォントサイズ", 6, 30, value=int(st.session_state.get("m_k_tick_font_size", 12)), step=1, key="m_k_tick_font_size")
        TICK_FONTS = ["(グラフ全体と同じ)"] + [f for f in FONT_CANDS if f != "(system default)"]
        st.selectbox("目盛（tick）フォント", TICK_FONTS,
                     index=TICK_FONTS.index(st.session_state.get("m_k_tick_font_family", "(グラフ全体と同じ)")) if st.session_state.get("m_k_tick_font_family") in TICK_FONTS else 0,
                     key="m_k_tick_font_family")

        st.markdown("**📏 目盛（ticks / 長さ / ラベル配置 / 角度）**")
        tx1, tx2 = st.columns(2)
        with tx1:
            st.selectbox("X軸 ticks", ["outside","inside","(なし)"], key="m_k_ticks_x",
                         index={"outside":0,"inside":1,"(なし)":2}[st.session_state.get("m_k_ticks_x","outside")])
            st.number_input("X軸 ticklen(px)", 0, 40, value=int(st.session_state.get("m_k_ticklen_x", 6)), step=1, key="m_k_ticklen_x")
            st.selectbox("X軸 ラベル位置", ["自動","外-下","外-上","内-下","内-上"], key="m_k_ticklabelpos_x",
                         index=["自動","外-下","外-上","内-下","内-上"].index(st.session_state.get("m_k_ticklabelpos_x","自動")))
            st.number_input("X軸 ラベル角度(°)", -90, 90, value=int(st.session_state.get("m_k_tickangle_x", 0)), step=5, key="m_k_tickangle_x")
        with tx2:
            st.selectbox("Y軸 ticks", ["outside","inside","(なし)"], key="m_k_ticks_y",
                         index={"outside":0,"inside":1,"(なし)":2}[st.session_state.get("m_k_ticks_y","outside")])
            st.number_input("Y軸 ticklen(px)", 0, 40, value=int(st.session_state.get("m_k_ticklen_y", 6)), step=1, key="m_k_ticklen_y")
            st.selectbox("Y軸 ラベル位置", ["自動","外-左","外-右","内-左","内-右"], key="m_k_ticklabelpos_y",
                         index=["自動","外-左","外-右","内-左","内-右"].index(st.session_state.get("m_k_ticklabelpos_y","自動")))
            st.number_input("Y軸 ラベル角度(°)", -90, 90, value=int(st.session_state.get("m_k_tickangle_y", 0)), step=5, key="m_k_tickangle_y")

    with c3:
        st.markdown("**🏷️ 凡例**")
        st.checkbox("凡例を表示", key="m_k_show_legend")
        st.selectbox("凡例の位置", ["外-上","外-下","外-左","外-右","内-右上","内-右下","内-左上","内-左下"], key="m_k_legend_location")
        st.selectbox("凡例の向き", ["自動","横(h)","縦(v)"], key="m_k_legend_orientation")
        st.number_input("凡例フォントサイズ", 8, 30, value=int(st.session_state.get("m_k_legend_font_size", 12)), step=1, key="m_k_legend_font_size")
        st.text_input("凡例 背景色（rgba）", key="m_k_legend_bg", value=st.session_state.get("m_k_legend_bg","rgba(255,255,255,0.0)"))
        st.text_input("凡例 枠線色（rgba）", key="m_k_legend_bordercolor", value=st.session_state.get("m_k_legend_bordercolor","rgba(0,0,0,0.3)"))
        st.number_input("凡例 枠線幅(px)", 0, 5, value=int(st.session_state.get("m_k_legend_borderwidth",0)), step=1, key="m_k_legend_borderwidth")

    st.divider()
    st.markdown("**📏 余白（margin）**")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.number_input("左余白 l(px)", 0, 300, value=st.session_state.get("m_k_margin_l", 60), step=2, key="m_k_margin_l")
    with m2:
        st.number_input("右余白 r(px)", 0, 300, value=st.session_state.get("m_k_margin_r", 20), step=2, key="m_k_margin_r")
    with m3:
        st.number_input("上余白 t(px)", 0, 300, value=st.session_state.get("m_k_margin_t", 60), step=2, key="m_k_margin_t")
    with m4:
        st.number_input("下余白 b(px)", 0, 300, value=st.session_state.get("m_k_margin_b", 60), step=2, key="m_k_margin_b")

    st.divider()
    st.markdown("**🧱 棒の太さ（相対・0〜1）**")
    st.radio("モード", ["自動", "手動"], index=0 if st.session_state["k_bar_mode"] == "自動" else 1, horizontal=True, key="k_bar_mode")
    if st.session_state["k_bar_mode"] == "手動":
        st.slider("棒の太さ（相対）", 0.10, 1.00, value=float(st.session_state["m_manual_bar_width"]), step=0.01, key="m_manual_bar_width")
    else:
        st.slider("棒の太さ（相対）", 0.10, 1.00, value=0.60, step=0.01, disabled=True)

    st.divider()
    st.markdown("**🖼️ 枠線（プロット領域 内側）**")
    st.radio("枠の種類（内側）", ["なし", "四角", "角丸"],
             index=["なし","四角","角丸"].index(st.session_state["m_k_frame_style"]) if st.session_state.get("m_k_frame_style") in ["なし","四角","角丸"] else 1,
             key="m_k_frame_style", horizontal=True)
    st.radio("枠の線種（内側）", ["実線", "破線", "点線"],
             index=["実線","破線","点線"].index(st.session_state.get("m_k_frame_dash","実線")),
             key="m_k_frame_dash", horizontal=True)
    if st.session_state["m_k_frame_style"] == "角丸":
        st.slider("角丸の半径（比率）", 0.0, 0.08, float(st.session_state["m_k_corner_radius_frac"]), 0.005, key="m_k_corner_radius_frac")
    st.checkbox("内側枠をプロット領域（x/y domain）に合わせる", key="m_k_frame_ref_domain",
                value=st.session_state.get("m_k_frame_ref_domain", True))

    st.divider()
    st.markdown("**🖼️ 外枠（図全体：タイトル・凡例・余白を含む）**")
    st.radio("外枠の種類（全体）", ["なし", "四角", "角丸"],
             index=["なし","四角","角丸"].index(st.session_state.get("m_k_outerframe_style","なし")),
             key="m_k_outerframe_style", horizontal=True)
    st.radio("外枠の線種（全体）", ["実線", "破線", "点線"],
             index=["実線","破線","点線"].index(st.session_state.get("m_k_outerframe_dash","実線")),
             key="m_k_outerframe_dash", horizontal=True)
    if st.session_state["m_k_outerframe_style"] == "角丸":
        st.slider("外枠の角丸（px）", 0, 100, int(st.session_state.get("m_k_outer_radius_px",16)), 1, key="m_k_outer_radius_px")

    st.divider()
    st.markdown("**📤 エクスポート補助**")
    st.checkbox("エクスポートサイズをプレビューに同期する（幅=プレビュー幅/高さ=プレビュー高さ）",
                key="sync_export_to_preview", value=st.session_state.get("sync_export_to_preview", True))
    st.checkbox("出力を正方形にする（幅=高さ）", key="lock_export_square", value=st.session_state.get("lock_export_square", False))
    cexp1, cexp2 = st.columns(2)
    with cexp1:
        st.number_input("出力 幅(px)",  min_value=300, max_value=4000,
                        value=int(st.session_state.get("m_k_out_w", preview_w)), step=100, key="m_k_out_w")
    with cexp2:
        st.number_input("出力 高さ(px)", min_value=300, max_value=4000,
                        value=int(st.session_state.get("m_k_out_h", preview_h)), step=50,  key="m_k_out_h")
    st.number_input("PNG DPI相当（scale換算）", min_value=72,  max_value=600,
                    value=int(st.session_state.get("m_k_out_dpi", 220)), step=10, key="m_k_out_dpi")

# —— 値の参照
chart_title   = st.session_state["m_k_chart_title"]
title_bold    = st.session_state["m_k_title_bold"]
title_size    = st.session_state["m_k_title_size"]
title_align   = st.session_state["m_k_title_align"]
show_legend   = st.session_state["m_k_show_legend"]
show_grid     = st.session_state["m_k_show_grid"]
palette_name  = st.session_state["m_k_palette_name"]
color_alpha   = float(st.session_state["m_k_color_alpha"])
font_family   = st.session_state["m_k_font_family"]

frame_style_inner = st.session_state.get("m_k_frame_style", "四角")
frame_dash_inner  = _dash_value(st.session_state.get("m_k_frame_dash", "実線"))
corner_frac_inner = float(st.session_state.get("m_k_corner_radius_frac", 0.025))
outer_style = st.session_state.get("m_k_outerframe_style", "なし")
outer_dash  = _dash_value(st.session_state.get("m_k_outerframe_dash", "実線"))
outer_radius_px = int(st.session_state.get("m_k_outer_radius_px", 16))

x_title_in = st.session_state.get("m_k_x_title", "").strip()
y_title_in = st.session_state.get("m_k_y_title", "").strip()
use_auto_axis_title = bool(st.session_state.get("m_k_use_headers_as_axis_title", True))

# 凡例関連
legend_loc   = st.session_state.get("m_k_legend_location", "外-上")
legend_orient_sel = st.session_state.get("m_k_legend_orientation", "自動")
legend_font_size  = int(st.session_state.get("m_k_legend_font_size", 12))
legend_bg    = st.session_state.get("m_k_legend_bg", "rgba(255,255,255,0.0)")
legend_bcol  = st.session_state.get("m_k_legend_bordercolor", "rgba(0,0,0,0.3)")
legend_bwid  = int(st.session_state.get("m_k_legend_borderwidth", 0))

# ==== 棒幅 ====
cats = work_df[x_col].astype(str).tolist()
groups_list = work_df[group_col].astype(str).unique().tolist() if ("group_col" in locals() and group_col) else []
num_series = len(y_cols)
is_stacked = (stack_mode != "なし")
bars_per_cat = 1 if is_stacked else max(1, num_series * (len(groups_list) if groups_list else 1))
bar_width = _auto_bar_width(int(st.session_state["m_k_preview_width"]), len(cats), bars_per_cat) if st.session_state["k_bar_mode"] == "自動" else float(st.session_state["m_manual_bar_width"])
if not is_stacked:
    slots = (len(groups_list) if group_col else 1) * len(y_cols)
    if bar_width * slots > 0.98:
        st.info("棒が重なり気味です。『棒の太さ』を少し下げると見やすくなります。")

# カラー
base_colors = PALETTES[palette_name]
plotly_colors_rgba = [_hex_to_rgba(c, color_alpha) for c in base_colors]

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

    # トレース
    color_idx = 0
    if group_col:
        for g in groups_list:
            tmp = work_df[work_df[group_col].astype(str) == g]
            for yc in y_cols:
                col = plotly_colors_rgba[color_idx % len(plotly_colors_rgba)]; color_idx += 1
                name = f"{yc} ({g})" if len(y_cols)>1 else str(g)
                if orientation == "縦":
                    fig.add_trace(go.Bar(x=tmp[x_col], y=tmp[yc], name=name, width=bar_width,
                                         marker=dict(color=col, line=dict(width=0))))
                else:
                    fig.add_trace(go.Bar(y=tmp[x_col], x=tmp[yc], name=name, orientation="h", width=bar_width,
                                         marker=dict(color=col, line=dict(width=0))))
    else:
        for yc in y_cols:
            col = plotly_colors_rgba[color_idx % len(plotly_colors_rgba)]; color_idx += 1
            if orientation == "縦":
                fig.add_trace(go.Bar(x=work_df[x_col], y=work_df[yc], name=yc, width=bar_width,
                                     marker=dict(color=col, line=dict(width=0))))
            else:
                fig.add_trace(go.Bar(y=work_df[x_col], x=work_df[yc], name=yc, orientation="h", width=bar_width,
                                     marker=dict(color=col, line=dict(width=0))))

    # 積み上げモード
    fig.update_layout(barmode=("group" if stack_mode=="なし" else "stack" if stack_mode=="積み上げ" else "relative"))

    # 凡例レイアウト（詳細）
    def _legend_cfg(loc: str) -> dict:
        orient = {"自動": None, "横(h)": "h", "縦(v)": "v"}[legend_orient_sel]
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
            cfg = dict(orientation="h", x=1.0, y=1.02, xanchor="right", yanchor="bottom")

        cfg.update(dict(
            bgcolor=legend_bg,
            bordercolor=legend_bcol,
            borderwidth=legend_bwid,
            font=dict(size=legend_font_size),
            traceorder="normal",
        ))
        return cfg

    legend_cfg = _legend_cfg(legend_loc) if show_legend else {}

    # 余白
    margins = dict(
        l=int(st.session_state.get("m_k_margin_l", 60)),
        r=int(st.session_state.get("m_k_margin_r", 20)),
        t=int(st.session_state.get("m_k_margin_t", 60)),
        b=int(st.session_state.get("m_k_margin_b", 60)),
    )

    # レイアウト
    fig.update_layout(
        title=dict(
            text=f"<b>{chart_title}</b>" if title_bold else chart_title,
            x=0.5 if title_align=="中央" else 0.0,
            xanchor="center" if title_align=="中央" else "left",
            y=0.95,
            font=dict(size=title_size,
                      family=None if font_family=="(system default)" else font_family)
        ),
        legend=legend_cfg,
        showlegend=bool(show_legend),
        template="plotly_white",
        margin=margins,
        width=int(st.session_state["m_k_preview_width"]),
        height=int(preview_h),
        autosize=False,
        font=dict(family=None if font_family=="(system default)" else font_family),
    )

    # 軸タイトル（未入力なら自動）
    x_title_eff = (x_title_in or (x_col if use_auto_axis_title else "")) or None
    y_title_auto = " / ".join(y_cols) if len(y_cols) <= 3 else f"{len(y_cols)}系列"
    y_title_eff = (y_title_in or (y_title_auto if use_auto_axis_title else "")) or None

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

    # 軸適用（title_standoff / ticks / ticklen / ticklabelposition / tickangle）
    fig.update_xaxes(
        title_text=x_title_eff,
        title_font=dict(size=int(st.session_state.get("m_k_axis_title_size", 14)),
                        family=axis_title_family),
        tickfont=dict(size=int(st.session_state.get("m_k_tick_font_size", 12)),
                      family=tick_family),
        title_standoff=int(st.session_state.get("m_k_x_title_standoff", 12)),
        ticks=_ticks_val(st.session_state.get("m_k_ticks_x","outside")),
        ticklen=int(st.session_state.get("m_k_ticklen_x", 6)),
        ticklabelposition=_ticklabelpos_x(st.session_state.get("m_k_ticklabelpos_x","自動")),
        tickangle=int(st.session_state.get("m_k_tickangle_x", 0)),
        automargin=True,
        showgrid=bool(show_grid),
        gridwidth=1, gridcolor="rgba(0,0,0,0.08)" if show_grid else None,
    )
    fig.update_yaxes(
        title_text=y_title_eff,
        title_font=dict(size=int(st.session_state.get("m_k_axis_title_size", 14)),
                        family=axis_title_family),
        tickfont=dict(size=int(st.session_state.get("m_k_tick_font_size", 12)),
                      family=tick_family),
        title_standoff=int(st.session_state.get("m_k_y_title_standoff", 12)),
        ticks=_ticks_val(st.session_state.get("m_k_ticks_y","outside")),
        ticklen=int(st.session_state.get("m_k_ticklen_y", 6)),
        ticklabelposition=_ticklabelpos_y(st.session_state.get("m_k_ticklabelpos_y","自動")),
        tickangle=int(st.session_state.get("m_k_tickangle_y", 0)),
        automargin=True,
        showgrid=bool(show_grid),
        gridwidth=1, gridcolor="rgba(0,0,0,0.08)" if show_grid else None,

    )

    # 枠
    add_inner_frame(
        fig,
        kind=frame_style_inner,
        line_width=2,
        line_dash=frame_dash_inner,
        radius_frac=corner_frac_inner,
        use_domain=bool(st.session_state.get("m_k_frame_ref_domain", True)),
    )
    add_outer_frame(fig, kind=outer_style, line_width=2, line_dash=outer_dash, radius_px=outer_radius_px)

    # プレビュー描画
    st.plotly_chart(
        fig, use_container_width=False, theme=None,
        config={"responsive": False, "displaylogo": False,
                "toImageButtonOptions": {"format": "png", "filename": "bar_chart", "scale": 2}}
    )

except Exception as e:
    st.error(f"プレビュー生成エラー: {e}")
    st.stop()

# =========================
# 5) ダウンロード
# =========================
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
        fig, format="png",
        width=out_w_export, height=out_h_export,
        scale=int(max(1, round(int(st.session_state.get("m_k_out_dpi", 220)) / 96))),
    )
    st.download_button("📊 高解像PNGをダウンロード（Word向け）", data=png_bytes,
                       file_name="bar_chart.png", mime="image/png", use_container_width=True)
except Exception as e:
    st.warning(f"PNG生成エラー（kaleido未導入またはフォント未対応の可能性）: {e}")

# SVG
try:
    svg_bytes = pio.to_image(fig, format="svg", width=out_w_export, height=out_h_export, scale=1)
    st.download_button("🖋️ SVGをダウンロード（ベクター）", data=svg_bytes,
                       file_name="bar_chart.svg", mime="image/svg+xml", use_container_width=True)
except Exception as e:
    st.warning(f"SVG生成エラー: {e}")
