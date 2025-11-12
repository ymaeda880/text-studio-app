# -*- coding: utf-8 -*-
# pages/56_グラフ作成.py
# （棒グラフ専用・簡潔版）
# - Excel 1行目: タイトル / 2行目: ヘッダー / 3行目〜: データ
# - プレビュー: Plotly
# - エクスポート: PNG / SVG（kaleido）
# - 追加:
#   * ヘッダー名を軸タイトルへ自動適用（未入力のとき）
#   * 目盛（tick）フォントファミリー選択
#   * expanderの開閉“記憶”（チェックボックス固定方式）
#   * 設定JSON（var_names付き）出力
#   * 「初期値に戻す」はフラグ→次回冒頭で一括適用（ウィジェット生成後の直接代入を避ける）

from __future__ import annotations
import json
from typing import List, Optional, Dict

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

# 解析ユーティリティ（別ファイル）
from lib.graph.parsing_utils import parse_pasted_robust

# =========================
# ページ設定
# =========================
st.set_page_config(page_title="📊 棒グラフ作成（Word貼り付け用｜Plotly版）", page_icon="📊", layout="wide")
st.title("📊 棒グラフ作成（Word貼り付け用｜Plotly版）")
st.caption("1行目=タイトル、2行目=ヘッダー、3行目以降=データ。Excelからそのまま貼り付けてください。")

# =========================
# カラーパレット（最小セット）
# =========================
PALETTES: Dict[str, List[str]] = {
    "Minimal":   ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"],
    "Corporate": ["#2E86AB", "#F6AA1C", "#A23E48", "#33658A", "#55DDE0", "#758E4F"],
    "Playful":   ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6A4C93", "#1A8FE3", "#95D02B"],
}

# =========================
# ヘルパ
# =========================
def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def _auto_bar_width(preview_px: int, num_cats: int, bars_per_cat: int) -> float:
    """プレビュー幅から「棒の太さ（相対）」のみを自動算出（0..1）。"""
    preview_px = max(600.0, float(preview_px))
    num_cats = max(1, int(num_cats))
    bars_per_cat = max(1, int(bars_per_cat))
    slot_px = max(24.0, (preview_px - 120.0) / num_cats)
    target_px_per_bar = slot_px * 0.70 / bars_per_cat
    target_px_per_bar = float(np.clip(target_px_per_bar, 6.0, 48.0))
    width_norm = float(np.clip(target_px_per_bar / slot_px, 0.10, 0.95))
    return width_norm

def _rounded_rect_path(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
    """(x0,y0)-(x1,y1) の長方形を半径 r（paper座標）で角丸にしたSVGパス。"""
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

def add_inner_frame(fig, *, kind: str, line_width: int, line_dash: str, radius_frac: float):
    if kind == "なし":
        return
    if kind == "四角":
        fig.add_shape(
            type="rect", xref="paper", yref="paper",
            x0=0, y0=0, x1=1, y1=1,
            line=dict(color="rgba(0,0,0,0.8)", width=line_width, dash=line_dash),
            fillcolor="rgba(0,0,0,0)", layer="above",
        )
    elif kind == "角丸":
        path = _rounded_rect_path(0.0, 0.0, 1.0, 1.0, max(0.0, float(radius_frac)))
        fig.add_shape(
            type="path", path=path, xref="paper", yref="paper",
            line=dict(color="rgba(0,0,0,0.8)", width=line_width, dash=line_dash),
            fillcolor="rgba(0,0,0,0)", layer="above",
        )

def add_outer_frame(fig, *, kind: str, line_width: int, line_dash: str, radius_px: int):
    if kind == "なし":
        return
    w = int(fig.layout.width or 800)
    h = int(fig.layout.height or 600)
    m = fig.layout.margin or dict(l=20, r=20, t=60, b=40)
    l = int(getattr(m, "l", 20) or 0); r = int(getattr(m, "r", 20) or 0)
    t = int(getattr(m, "t", 60) or 0); b = int(getattr(m, "b", 40) or 0)
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

def _ensure_default(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default

# =========================
# 0) デフォルト（ウィジェット生成前に必ずセット）
# =========================
DEFAULTS = {
    # グラフ全般
    "m_k_chart_title": "",
    "m_k_title_bold": True,
    "m_k_title_size": 22,
    "m_k_title_align": "中央",
    "m_k_show_legend": True,
    "m_k_show_grid": True,
    "m_k_palette_name": "Minimal",
    "m_k_color_alpha": 0.6,
    "m_k_font_family": "(system default)",

    # 内側枠
    "m_k_frame_style": "四角",
    "m_k_frame_dash": "実線",
    "m_k_corner_radius_frac": 0.025,

    # 外枠
    "m_k_outerframe_style": "なし",
    "m_k_outerframe_dash": "実線",
    "m_k_outer_radius_px": 16,

    # 軸と目盛
    "m_k_x_title": "",
    "m_k_y_title": "",
    "m_k_axis_title_size": 14,
    "m_k_tick_font_size": 12,
    "m_k_tick_font_family": "(グラフ全体と同じ)",

    # 出力サイズ
    "m_k_out_w": 1200,
    "m_k_out_h": 700,
    "m_k_out_dpi": 220,

    # 棒の太さ
    "k_bar_mode": "自動",
    "m_manual_bar_width": 0.60,

    # エクスポート補助
    "sync_export_to_preview": False,
    "lock_export_square": False,

    # プレビュー
    "m_k_preview_width": 820,

    # expander開閉の記憶（初期＝閉じている）
    "exp_style_open": False,
    "exp_group_open": False,
    "exp_diag_open": False,

    # 一度だけ適用する系のフラグ
    "__apply_title_default_once__": True,
}

# 初期化
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- リセットの遅延適用（ボタンでフラグ→次回最初に実行） ---
if st.session_state.get("__pending_reset__", False):
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    st.session_state["__pending_reset__"] = False

# =========================
# 1) データ貼り付け（ボタン式）
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
    # 次回描画で貼り付けタイトルを初期値として一度だけ適用
    st.session_state["__apply_title_default_once__"] = True

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

# タイトル初期値を1回だけ適用（ウィジェット作成前）
if st.session_state.get("__apply_title_default_once__", False):
    if not st.session_state.get("m_k_chart_title"):
        st.session_state["m_k_chart_title"] = (title_default or "")
    st.session_state["__apply_title_default_once__"] = False

st.success(f"タイトル候補：**{title_default or '(未設定)'}**")
st.dataframe(df.head(50), use_container_width=True)

# 🧷 expanderの開閉を記憶（チェックで固定）
st.markdown("#### 🧷 セクションの展開設定（固定）")
cols_mem = st.columns(3)
with cols_mem[0]:
    st.checkbox("🎨 スタイルを展開したままにする", key="exp_style_open", value=st.session_state["exp_style_open"])
with cols_mem[1]:
    st.checkbox("🔧 グループ化を展開したままにする", key="exp_group_open", value=st.session_state["exp_group_open"])
with cols_mem[2]:
    st.checkbox("🩺 パース診断を展開したままにする", key="exp_diag_open", value=st.session_state["exp_diag_open"])

with st.expander("🩺 パース診断（必要時のみ）", expanded=st.session_state["exp_diag_open"]):
    st.json(st.session_state.get("__diag", {}))

# =========================
# 2) 列選択・整形（棒グラフ専用）
# =========================
st.subheader("2) 列選択・整形")
all_cols = list(df.columns)
x_col = st.selectbox("カテゴリ列（X軸/ラベル）", all_cols, index=0)
y_cols = st.multiselect("Y（系列）列（複数可）", [c for c in all_cols if c != x_col], default=[c for c in all_cols if c != x_col][:1])
if not y_cols:
    st.warning("Y 列を1つ以上選んでください。"); st.stop()

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

preview_w = st.slider("プレビューの幅（px）", 300, 1200, st.session_state["m_k_preview_width"], 20, key="m_k_preview_width")

with st.expander("🎨 スタイル（クイック調整）", expanded=st.session_state["exp_style_open"]):
    # フォント（Plotlyはシステムフォント準拠）
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
        "フォントファミリー",
        options=FONT_CANDS,
        index=FONT_CANDS.index(st.session_state["m_k_font_family"]) if st.session_state["m_k_font_family"] in FONT_CANDS else FONT_CANDS.index("(system default)"),
        key="m_k_font_family",
    )

    st.divider()
    c1, c2, c3 = st.columns([1.2,1,1])
    with c1:
        st.text_input("タイトル", key="m_k_chart_title")
        st.checkbox("タイトル太字", key="m_k_title_bold")
        st.slider("タイトル文字サイズ", 10, 36, st.session_state["m_k_title_size"], step=1, key="m_k_title_size")
        st.radio("タイトル位置", ["左","中央"], index=0 if st.session_state["m_k_title_align"] == "左" else 1, horizontal=True, key="m_k_title_align")
    with c2:
        st.checkbox("凡例を表示", key="m_k_show_legend")
        st.checkbox("グリッド表示", key="m_k_show_grid")
        st.selectbox("色パレット", list(PALETTES.keys()), index=list(PALETTES.keys()).index(st.session_state["m_k_palette_name"]), key="m_k_palette_name")
        st.slider("色の透明度（0=透明〜1=不透明）", 0.0, 1.0, st.session_state["m_k_color_alpha"], 0.05, key="m_k_color_alpha")
    with c3:
        st.number_input("出力 幅(px)",  min_value=300, max_value=4000, value=st.session_state["m_k_out_w"], step=100, key="m_k_out_w")
        dpi_val = st.session_state["m_k_out_dpi"]
        st.caption(f"約 **{st.session_state['m_k_out_w'] / dpi_val * 2.54:.2f} cm**（DPI={dpi_val}）")
        st.number_input("出力 高さ(px)", min_value=300, max_value=4000, value=st.session_state["m_k_out_h"], step=50,  key="m_k_out_h")
        st.number_input("PNG DPI相当（scale換算）", min_value=72,  max_value=600,  value=st.session_state["m_k_out_dpi"], step=10, key="m_k_out_dpi")

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
    st.checkbox("🔗 エクスポートサイズをプレビューに同期する（幅=プレビュー幅／高さ=プレビュー高さ）",
                key="sync_export_to_preview", value=st.session_state.get("sync_export_to_preview", True))
    st.checkbox("🟦 出力を正方形にする（幅=高さ、同期ONでも適用）",
                key="lock_export_square", value=st.session_state.get("lock_export_square", False))

    st.divider()
    # === 軸ラベル ===
    st.markdown("**📐 軸ラベル設定**")
    st.checkbox("ヘッダー名を軸タイトルに自動適用（未入力のとき）",
                key="m_k_use_headers_as_axis_title", value=st.session_state.get("m_k_use_headers_as_axis_title", True))
    ax1, ax2 = st.columns(2)
    with ax1:
        st.text_input("X軸タイトル", key="m_k_x_title", value=st.session_state.get("m_k_x_title", ""))
        st.slider("軸タイトルのフォントサイズ", 8, 36, int(st.session_state.get("m_k_axis_title_size", 14)), 1, key="m_k_axis_title_size")
    with ax2:
        st.text_input("Y軸タイトル", key="m_k_y_title", value=st.session_state.get("m_k_y_title", ""))
        st.slider("目盛（tick）のフォントサイズ", 6, 30, int(st.session_state.get("m_k_tick_font_size", 12)), 1, key="m_k_tick_font_size")

    st.divider()
    st.markdown("**🖋️ 目盛（tick）フォント設定**")
    TICK_FONTS = ["(グラフ全体と同じ)"] + [f for f in FONT_CANDS if f != "(system default)"]
    st.selectbox(
        "目盛フォントファミリー",
        TICK_FONTS,
        index=TICK_FONTS.index(st.session_state.get("m_k_tick_font_family", "(グラフ全体と同じ)")) if st.session_state.get("m_k_tick_font_family") in TICK_FONTS else 0,
        key="m_k_tick_font_family",
    )

# —— スタイル値（以後参照）
chart_title   = st.session_state["m_k_chart_title"]
title_bold    = st.session_state["m_k_title_bold"]
title_size    = st.session_state["m_k_title_size"]
title_align   = st.session_state["m_k_title_align"]
show_legend   = st.session_state["m_k_show_legend"]
show_grid     = st.session_state["m_k_show_grid"]
palette_name  = st.session_state["m_k_palette_name"]
color_alpha   = float(st.session_state["m_k_color_alpha"])
font_family   = st.session_state["m_k_font_family"]

# 枠
frame_style_inner = st.session_state.get("m_k_frame_style", "四角")
frame_dash_inner  = _dash_value(st.session_state.get("m_k_frame_dash", "実線"))
corner_frac_inner = float(st.session_state.get("m_k_corner_radius_frac", 0.025))
outer_style = st.session_state.get("m_k_outerframe_style", "なし")
outer_dash  = _dash_value(st.session_state.get("m_k_outerframe_dash", "実線"))
outer_radius_px = int(st.session_state.get("m_k_outer_radius_px", 16))

# 軸ラベル入力
x_title_in = st.session_state.get("m_k_x_title", "").strip()
y_title_in = st.session_state.get("m_k_y_title", "").strip()
use_auto_axis_title = bool(st.session_state.get("m_k_use_headers_as_axis_title", True))

# ==== 棒幅決定 ====
cats = work_df[x_col].astype(str).tolist()
groups_list = work_df[group_col].astype(str).unique().tolist() if ("group_col" in locals() and group_col) else []
num_series = len(y_cols)
is_stacked = (stack_mode != "なし")
bars_per_cat = 1 if is_stacked else max(1, num_series * (len(groups_list) if groups_list else 1))
bar_width = _auto_bar_width(st.session_state["m_k_preview_width"], len(cats), bars_per_cat) if st.session_state["k_bar_mode"] == "自動" else float(st.session_state["m_manual_bar_width"])

if not is_stacked:
    slots = (len(groups_list) if group_col else 1) * len(y_cols)
    if bar_width * slots > 0.98:
        st.info("棒が重なり気味です。『棒の太さ』を少し下げると見やすくなります。")

# Plotly カラー
base_colors = PALETTES[palette_name]
plotly_colors_rgba = [_hex_to_rgba(c, color_alpha) for c in base_colors]

# =========================
# 4) Plotly プレビュー
# =========================
st.subheader("4) プレビュー")
st.markdown("### 🔄 プレビュー再描画")
if st.button("🔁 再描画を実行", type="primary", use_container_width=True, key="rerender_button"):
    st.session_state["__force_rerender"] = not st.session_state.get("__force_rerender", False)
    st.rerun()

preview_h = int(max(320, min(800, st.session_state["m_k_preview_width"] * 0.58)))

try:
    fig = go.Figure()
    # 棒トレース
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

    # 積み上げ
    fig.update_layout(barmode=("group" if stack_mode=="なし" else "stack" if stack_mode=="積み上げ" else "relative"))

    # レジェンド
    legend_cfg = (dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0) if show_legend else dict(visible=False))

    # レイアウト
    fig.update_layout(
        title=dict(
            text=f"<b>{chart_title}</b>" if title_bold else chart_title,
            x=0.5 if title_align=="中央" else 0.0,
            xanchor="center" if title_align=="中央" else "left",
            y=0.95,
            font=dict(size=title_size, family=None if font_family=="(system default)" else font_family)
        ),
        legend=legend_cfg,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=40),
        width=st.session_state["m_k_preview_width"],
        height=preview_h,
        autosize=False
    )

    # === 軸タイトル（未入力ならヘッダー適用） ===
    x_title_eff = (x_title_in if x_title_in else (x_col if use_auto_axis_title else ""))
    y_title_auto = " / ".join(y_cols) if len(y_cols) <= 3 else f"{len(y_cols)}系列"
    y_title_eff = (y_title_in if y_title_in else (y_title_auto if use_auto_axis_title else ""))

    # === 目盛フォント ===
    tick_family = st.session_state.get("m_k_tick_font_family", "(グラフ全体と同じ)")
    if tick_family in [None, "", "(グラフ全体と同じ)"]:
        tick_family = None  # レイアウト全体のフォント設定に従う

    fig.update_xaxes(
        title_text=(x_title_eff or None),
        title_font=dict(size=int(st.session_state.get("m_k_axis_title_size", 14))),
        tickfont=dict(size=int(st.session_state.get("m_k_tick_font_size", 12)), family=tick_family),
        automargin=True,
    )
    fig.update_yaxes(
        title_text=(y_title_eff or None),
        title_font=dict(size=int(st.session_state.get("m_k_axis_title_size", 14))),
        tickfont=dict(size=int(st.session_state.get("m_k_tick_font_size", 12)), family=tick_family),
        automargin=True,
    )

    # ===== 設定JSON出力（fig確定後） =====
    # 実際のエクスポート寸法（セッションは変えない）
    if st.session_state.get("sync_export_to_preview", False):
        out_w_export = int(st.session_state["m_k_preview_width"])
        out_h_export = int(preview_h)
    else:
        out_w_export = int(st.session_state.get("m_k_out_w", 1200))
        out_h_export = int(st.session_state.get("m_k_out_h", 700))
    if st.session_state.get("lock_export_square", False):
        out_h_export = int(out_w_export)

    with st.sidebar:
        # ---- パラメータのリセット（フラグのみ立てて再実行）----
        st.markdown("### 🧼 パラメータのリセット")
        if st.button("🔄 すべて初期値に戻す", use_container_width=True):
            st.session_state["__pending_reset__"] = True
            st.rerun()

        st.markdown("### ⚙️ 現在の設定（JSON出力）")
        include_var_names = st.checkbox("🔍 変数名（var_names）も出力する", value=True)

        _m = fig.layout.margin
        marg = {
            "l": int(getattr(_m, "l", 20) or 20),
            "r": int(getattr(_m, "r", 20) or 20),
            "t": int(getattr(_m, "t", 60) or 60),
            "b": int(getattr(_m, "b", 40) or 40),
        }

        cfg = {
            "data": {
                "x_col": x_col,
                "y_cols": y_cols,
                "group_col": group_col if 'group_col' in locals() else None,
                "rows": int(len(work_df)),
                "var_names": {"x_col": "x_col", "y_cols": "y_cols", "group_col": "group_col", "rows": "len(work_df)"},
            },
            "chart": {
                "orientation": orientation,
                "stack_mode": stack_mode,
                "bar_width_relative": float(bar_width),
                "palette": st.session_state.get("m_k_palette_name"),
                "color_alpha": float(st.session_state.get("m_k_color_alpha", 0.6)),
                "show_grid": bool(st.session_state.get("m_k_show_grid", True)),
                "show_legend": bool(st.session_state.get("m_k_show_legend", True)),
                "var_names": {
                    "orientation": "orientation",
                    "stack_mode": "stack_mode",
                    "bar_width_relative": "bar_width",
                    "palette": 'st.session_state["m_k_palette_name"]',
                    "color_alpha": 'st.session_state["m_k_color_alpha"]',
                    "show_grid": 'st.session_state["m_k_show_grid"]',
                    "show_legend": 'st.session_state["m_k_show_legend"]'
                }
            },
            "layout": {
                "preview_width": int(st.session_state["m_k_preview_width"]),
                "preview_height": int(preview_h),
                "margin": marg,
                "font_family": st.session_state.get("m_k_font_family", "(system default)"),
                "figure_width": int(fig.layout.width or st.session_state["m_k_preview_width"]),
                "figure_height": int(fig.layout.height or preview_h),
                "var_names": {
                    "preview_width": "m_k_preview_width",
                    "preview_height": "preview_h",
                    "margin": "fig.layout.margin (marg)",
                    "font_family": 'st.session_state["m_k_font_family"]',
                    "figure_width": "fig.layout.width",
                    "figure_height": "fig.layout.height"
                }
            },
            "title": {
                "text": st.session_state.get("m_k_chart_title", ""),
                "bold": bool(st.session_state.get("m_k_title_bold", True)),
                "size": int(st.session_state.get("m_k_title_size", 22)),
                "align": st.session_state.get("m_k_title_align", "中央"),
                "var_names": {
                    "text": 'st.session_state["m_k_chart_title"]',
                    "bold": 'st.session_state["m_k_title_bold"]',
                    "size": 'st.session_state["m_k_title_size"]',
                    "align": 'st.session_state["m_k_title_align"]'
                }
            },
            "axes": {
                "x_title": x_title_eff,
                "y_title": y_title_eff,
                "axis_title_size": int(st.session_state.get("m_k_axis_title_size", 14)),
                "tick_font_size": int(st.session_state.get("m_k_tick_font_size", 12)),
                "tick_font_family": st.session_state.get("m_k_tick_font_family", "(グラフ全体と同じ)"),
                "var_names": {
                    "x_title": 'x_title_eff',
                    "y_title": 'y_title_eff',
                    "axis_title_size": 'st.session_state["m_k_axis_title_size"]',
                    "tick_font_size": 'st.session_state["m_k_tick_font_size"]',
                    "tick_font_family": 'st.session_state["m_k_tick_font_family"]'
                }
            },
            "inner_frame": {
                "style": st.session_state.get("m_k_frame_style", "四角"),
                "dash": st.session_state.get("m_k_frame_dash", "実線"),
                "corner_radius_frac": float(st.session_state.get("m_k_corner_radius_frac", 0.025)),
                "var_names": {
                    "style": 'st.session_state["m_k_frame_style"]',
                    "dash": 'st.session_state["m_k_frame_dash"]',
                    "corner_radius_frac": 'st.session_state["m_k_corner_radius_frac"]'
                }
            },
            "outer_frame": {
                "style": st.session_state.get("m_k_outerframe_style", "なし"),
                "dash": st.session_state.get("m_k_outerframe_dash", "実線"),
                "corner_radius_px": int(st.session_state.get("m_k_outer_radius_px", 16)),
                "var_names": {
                    "style": 'st.session_state["m_k_outerframe_style"]',
                    "dash": 'st.session_state["m_k_outerframe_dash"]',
                    "corner_radius_px": 'st.session_state["m_k_outer_radius_px"]'
                }
            },
            "export": {
                "out_width_px": int(st.session_state.get("m_k_out_w", 1200)),
                "out_height_px": int(st.session_state.get("m_k_out_h", 700)),
                "out_dpi_equiv": int(st.session_state.get("m_k_out_dpi", 220)),
                "used_out_width_px": int(out_w_export),
                "used_out_height_px": int(out_h_export),
                "var_names": {
                    "out_width_px": 'st.session_state["m_k_out_w"]',
                    "out_height_px": 'st.session_state["m_k_out_h"]',
                    "out_dpi_equiv": 'st.session_state["m_k_out_dpi"]',
                    "used_out_width_px": "out_w_export",
                    "used_out_height_px": "out_h_export"
                }
            },
            "mode": {
                "bar_width_mode": st.session_state.get("k_bar_mode", "自動"),
                "manual_bar_width": float(st.session_state.get("m_manual_bar_width", 0.60)),
                "var_names": {
                    "bar_width_mode": 'st.session_state["k_bar_mode"]',
                    "manual_bar_width": 'st.session_state["m_manual_bar_width"]'
                }
            },
            "ui": {
                "exp_style_open": bool(st.session_state.get("exp_style_open", False)),
                "exp_group_open": bool(st.session_state.get("exp_group_open", False)),
                "exp_diag_open": bool(st.session_state.get("exp_diag_open", False)),
                "var_names": {
                    "exp_style_open": 'st.session_state["exp_style_open"]',
                    "exp_group_open": 'st.session_state["exp_group_open"]',
                    "exp_diag_open": 'st.session_state["exp_diag_open"]'
                }
            },
        }

        if not include_var_names:
            def _strip_var_names(d):
                if isinstance(d, dict):
                    return {k: _strip_var_names(v) for k, v in d.items() if k != "var_names"}
                if isinstance(d, list):
                    return [_strip_var_names(x) for x in d]
                return d
            cfg = _strip_var_names(cfg)

        json_text = json.dumps(cfg, ensure_ascii=False, indent=2)
        if st.button("📤 現在の設定をJSONで出す", use_container_width=True):
            st.code(json_text, language="json")
        st.download_button("💾 設定JSONをダウンロード", data=json_text.encode("utf-8"),
                           file_name="bar_chart_settings.json", mime="application/json", use_container_width=True)

    # グリッド微調整
    if show_grid:
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.08)")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.08)")
    else:
        fig.update_xaxes(showgrid=False); fig.update_yaxes(showgrid=False)

    # 枠
    add_inner_frame(fig, kind=frame_style_inner, line_width=2, line_dash=frame_dash_inner, radius_frac=corner_frac_inner)
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
# 4.5) Plotly 図を直接ダウンロード（PNG / SVG）
# =========================
st.markdown("### 📥 Plotly 図のダウンロード")

# 実際の書き出し寸法（セッションは変えない）
if st.session_state.get("sync_export_to_preview", False):
    out_w_export = int(st.session_state["m_k_preview_width"])
    out_h_export = int(preview_h)
else:
    out_w_export = int(st.session_state.get("m_k_out_w", 1200))
    out_h_export = int(st.session_state.get("m_k_out_h", 700))
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
