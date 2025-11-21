# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
from pathlib import Path
import textwrap
from typing import Optional, List

import streamlit as st
import pandas as pd
import numpy as np

# ====== lib パス追加（プロジェクト直下の lib を import 可能に）======
PROJECTS_ROOT = Path(__file__).resolve().parents[2]  # adjust if needed
LIB_DIR = PROJECTS_ROOT / "text_studio_app" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from graph import (
    PALETTES, DEFAULT_PRESETS,
    parse_pasted_robust, setup_japanese_font,
    make_plotly_fig, export_png
)

st.set_page_config(page_title="📊 グラフ作成（Word貼り付け用）", page_icon="📊", layout="wide")
st.title("📊 グラフ作成（Word貼り付け用）")
st.caption("1行目=タイトル、2行目=ヘッダー、3行目以降=データをExcelから貼り付け。")

# ===== サイドバー：プリセット & 枠 =====
with st.sidebar:
    st.header("🎛️ スタイル・設定")
    if "__user_presets" not in st.session_state:
        st.session_state["__user_presets"] = {}

    def _current_settings() -> dict:
        return {
            "title_bold": st.session_state.get("k_title_bold", True),
            "title_size": st.session_state.get("k_title_size", 22),
            "title_align": st.session_state.get("k_title_align", "中央"),
            "show_legend": st.session_state.get("k_show_legend", True),
            "show_grid": st.session_state.get("k_show_grid", True),
            "markers_on": st.session_state.get("k_markers_on", True),
            "line_width": st.session_state.get("k_line_width", 2.4),
            "palette_name": st.session_state.get("k_palette_name", "Minimal"),
            "out_w": st.session_state.get("k_out_w", 1200),
            "out_h": st.session_state.get("k_out_h", 700),
            "out_dpi": st.session_state.get("k_out_dpi", 220),
            "frame_style": st.session_state.get("k_frame_style", "なし"),
            "corner_radius": st.session_state.get("k_corner_radius", 20),
        }

    def _apply_preset(preset_dict: dict):
        keymap = {
            "title_bold":"k_title_bold", "title_size":"k_title_size", "title_align":"k_title_align",
            "show_legend":"k_show_legend", "show_grid":"k_show_grid", "markers_on":"k_markers_on",
            "line_width":"k_line_width", "palette_name":"k_palette_name",
            "out_w":"k_out_w", "out_h":"k_out_h", "out_dpi":"k_out_dpi",
            "frame_style":"k_frame_style", "corner_radius":"k_corner_radius",
        }
        for k, v in preset_dict.items():
            st.session_state[keymap[k]] = v
        st.rerun()

    preset_names = list(DEFAULT_PRESETS.keys()) + list(st.session_state["__user_presets"].keys())
    sel_preset = st.selectbox("プリセットを選択", preset_names, index=0, key="k_selected_preset")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("適用", use_container_width=True):
            src = DEFAULT_PRESETS.get(sel_preset) or st.session_state["__user_presets"].get(sel_preset)
            if src: _apply_preset(src)
    with c2:
        if st.button("上書き保存", use_container_width=True):
            st.session_state["__user_presets"][sel_preset] = _current_settings()
            st.success(f"「{sel_preset}」を上書き保存しました。")
    with c3:
        if sel_preset in st.session_state["__user_presets"]:
            if st.button("削除", use_container_width=True):
                del st.session_state["__user_presets"][sel_preset]
                st.success(f"「{sel_preset}」を削除しました。")
                st.rerun()

    with st.expander("💾 新規プリセットを保存", expanded=False):
        new_name = st.text_input("プリセット名", value="")
        if st.button("この設定で保存", use_container_width=True, disabled=(new_name.strip()=="")):
            st.session_state["__user_presets"][new_name.strip()] = _current_settings()
            st.success(f"「{new_name.strip()}」を保存しました。")
            st.rerun()

    st.divider()
    st.radio("枠線スタイル（PNG）", ["なし","四角","角丸"], key="k_frame_style", index=0)
    if st.session_state.get("k_frame_style","なし") == "角丸":
        st.slider("角丸半径（px）", 6, 60, 20, step=2, key="k_corner_radius")
    st.caption("※ Word へは PNG を貼り付けてください。")

# ===== 1) データ貼り付け =====
st.subheader("1) データ貼り付け")
sample = textwrap.dedent("""\
    売上推移
    期間\tA社\tB社\tC社
    2024-01\t120\t98\t101
    2024-02\t140\t110\t96
    2024-03\t135\t115\t108
""")
text = st.text_area("Excelの表を貼り付け（1行目=タイトル、2行目=ヘッダー）", sample, height=180)

title, df, diag = ("", pd.DataFrame(), {})
if text.strip():
    title, df, diag = parse_pasted_robust(text)

with st.expander("🩺 パース診断", expanded=False):
    st.json(diag)

if df.empty:
    st.error("データを貼り付けてください。（パースに失敗）")
    st.stop()

st.success(f"タイトル候補：**{title or '(未設定)'}**")
st.dataframe(df.head(50), use_container_width=True)

if "__confirmed" not in st.session_state:
    st.session_state["__confirmed"] = False

if not st.session_state["__confirmed"]:
    st.markdown("---"); st.markdown("### ▶ 次に進む")
    if st.button("▶ グラフ作成を開始", type="primary", use_container_width=True):
        st.session_state["__df"] = df
        st.session_state["__title"] = title
        st.session_state["__confirmed"] = True
        st.rerun()
    st.stop()
else:
    df = st.session_state["__df"]
    title_default = st.session_state["__title"]

# ===== 2) データの種類と列の選択 =====
st.subheader("2) データの種類と列の選択")
data_kind = st.radio("データの種類", ["時系列", "クロスセクション"], index=0, horizontal=True)
all_cols = list(df.columns)
x_col = st.selectbox("X軸（時系列なら日付/期間、CSならカテゴリ）", all_cols, index=0)
y_cols: List[str] = st.multiselect("Y（系列）列（複数可）", [c for c in all_cols if c != x_col],
                                   default=[c for c in all_cols if c != x_col][:1])

if not y_cols:
    st.warning("Y 列を1つ以上選んでください。"); st.stop()

group_col: Optional[str] = None
agg_func = "sum"
stack_mode = "none"
if data_kind == "クロスセクション":
    with st.expander("🔧 グループ化（任意）", expanded=False):
        gc = st.selectbox("グループ化列（例：性別/クラス 等）", ["(なし)"] + all_cols, index=0)
        group_col = None if gc == "(なし)" else gc
        agg_func = st.selectbox("集計方法", ["sum", "mean", "median", "max", "min"], index=0)
        stack_mode = st.radio("積み上げモード", ["none", "stack", "percent"], index=0, horizontal=True)

# 整形
work_df = df.copy()
ts_is_datetime = False
if data_kind == "時系列":
    dt = pd.to_datetime(work_df[x_col], errors="coerce", infer_datetime_format=True)
    if dt.notna().mean() >= 0.5:
        work_df[x_col] = dt; ts_is_datetime = True
        work_df = work_df.dropna(subset=[x_col]).sort_values(x_col)
    else:
        work_df[x_col] = work_df[x_col].astype(str)

use_cols = [x_col] + y_cols + ([group_col] if group_col else [])
work_df = work_df[use_cols].copy()

if data_kind == "クロスセクション" and group_col:
    import numpy as np
    agg_map = {c: getattr(np, agg_func) for c in y_cols}
    work_df = work_df.groupby([x_col, group_col], dropna=False).agg(agg_map).reset_index()

if work_df.empty:
    st.warning("プロット対象データが空です。X 列の形式をご確認ください。"); st.stop()

# ===== 3) グラフ設定 =====
st.subheader("3) グラフ設定")
chart_type = st.radio("グラフ種類",
    ["折れ線", "面", "棒", "積み上げ棒", "散布"] if data_kind=="時系列" else ["棒","横棒","積み上げ棒","円"],
    index=0, horizontal=True)

if data_kind == "クロスセクション" and chart_type == "円" and len(y_cols) != 1:
    st.warning("円グラフは Y 列を1つにしてください。"); st.stop()

with st.expander("🎨 タイトル・装飾", expanded=False):
    st.text_input("タイトル", value=title_default or "", key="k_chart_title")
    st.checkbox("タイトルを太字", value=DEFAULT_PRESETS["Minimal"]["title_bold"], key="k_title_bold")
    st.slider("タイトル文字サイズ", 10, 36, DEFAULT_PRESETS["Minimal"]["title_size"], step=1, key="k_title_size")
    st.radio("タイトル位置", ["左","中央"], index=1, horizontal=True, key="k_title_align")
    st.checkbox("凡例を表示", value=True, key="k_show_legend")
    st.checkbox("グリッド表示", value=True, key="k_show_grid")
    st.checkbox("マーカー表示（線・散布）", value=True, key="k_markers_on")
    st.slider("線の太さ", 1.0, 6.0, 2.4, step=0.2, key="k_line_width")
    st.selectbox("色パレット", list(PALETTES.keys()), index=0, key="k_palette_name")

with st.expander("🖨️ 出力（PNG）", expanded=False):
    st.number_input("幅(px)",    min_value=600, max_value=4000, value=1200, step=100, key="k_out_w")
    st.number_input("高さ(px)",  min_value=400, max_value=3000, value=700, step=50,   key="k_out_h")
    st.number_input("DPI",       min_value=72,  max_value=600,  value=220, step=10,   key="k_out_dpi")

# 値取り出し
title_bold   = st.session_state["k_title_bold"]
title_size   = st.session_state["k_title_size"]
title_align  = st.session_state["k_title_align"]
show_legend  = st.session_state["k_show_legend"]
show_grid    = st.session_state["k_show_grid"]
markers_on   = st.session_state["k_markers_on"]
line_width   = st.session_state["k_line_width"]
palette_name = st.session_state["k_palette_name"]
out_w        = st.session_state["k_out_w"]
out_h        = st.session_state["k_out_h"]
out_dpi      = st.session_state["k_out_dpi"]
frame_style  = st.session_state.get("k_frame_style","なし")
corner_radius= st.session_state.get("k_corner_radius", 20)
chart_title  = st.session_state.get("k_chart_title", title_default or "")

# ===== 4) プレビュー =====
st.subheader("4) プレビュー")
fig = make_plotly_fig(
    data_kind=data_kind, chart_type=chart_type, work_df=work_df,
    x_col=x_col, y_cols=y_cols, group_col=group_col,
    chart_title=chart_title, title_bold=title_bold, title_size=title_size, title_align=title_align,
    show_legend=show_legend, show_grid=show_grid, markers_on=markers_on, line_width=line_width
)
st.plotly_chart(fig, use_container_width=True)

# ===== 5) 生成・ダウンロード =====
st.subheader("5) 生成・ダウンロード")
if "__png_bytes" not in st.session_state:
    st.session_state["__png_bytes"] = None

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📊 グラフを作成（PNG生成）", use_container_width=True):
        setup_japanese_font()  # 一応ここで確実に適用
        try:
            png_bytes = export_png(
                data_kind=data_kind, chart_type=chart_type, work_df=work_df,
                x_col=x_col, y_cols=y_cols, group_col=group_col, stack_mode="none",
                chart_title=chart_title, title_bold=title_bold, title_size=title_size, title_align=title_align,
                show_legend=show_legend, show_grid=show_grid, markers_on=markers_on, line_width=line_width,
                palette_name=palette_name, out_w=out_w, out_h=out_h, out_dpi=out_dpi,
                frame_style=frame_style, corner_radius=corner_radius, ts_is_datetime=ts_is_datetime
            )
            st.session_state["__png_bytes"] = png_bytes
            st.success("PNG を生成しました。右のボタンからダウンロードできます。下にプレビューも表示します。")
        except Exception as e:
            st.session_state["__png_bytes"] = None
            st.error(f"PNG 生成エラー: {e}")

with c2:
    if st.session_state["__png_bytes"]:
        st.download_button("📥 PNG をダウンロード（Word用）",
                           data=st.session_state["__png_bytes"],
                           file_name="chart.png", mime="image/png",
                           use_container_width=True)
    else:
        st.info("まず左のボタンで PNG を生成してください。")

with c3:
    if st.button("🧹 生成結果をクリア", use_container_width=True):
        st.session_state["__png_bytes"] = None
        st.rerun()

if st.session_state["__png_bytes"]:
    st.image(st.session_state["__png_bytes"], caption="Word貼り付け用 PNG", use_column_width=True)
