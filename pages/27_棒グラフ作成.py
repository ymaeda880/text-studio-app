# -*- coding: utf-8 -*-
# pages/27_グラフ作成.py
# 棒グラフ作成（Plotly）— 軸ラベル調整 & 凡例詳細配置 + エクスパンダ直上トグル

from __future__ import annotations
import json
from typing import List, Optional, Dict, Set

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

# プリセット関連（デフォルト値・パレット・フォント候補）
from lib.graph.bar.presets import (
    DEFAULTS,
    PALETTES,
    FONT_CANDS,
)

# セッション状態・サイドバー・ミニトグル
from lib.graph.bar.state import init_session_state_from_defaults
from lib.graph.bar.sidebar import (
    render_sample_sidebar,
    render_reset_and_preset_sidebar,
)
from lib.graph.bar.mini_toggle import inject_mini_toggle_css, mini_toggle

# 棒グラフ共通ヘルパ
from lib.graph.bar.helpers import (
    auto_bar_width,
)

# 図のビルダー
from lib.graph.bar.builder import build_bar_figure

# スタイルパネル UI・データ入力・ダウンロード
from lib.graph.bar.style_panel import render_style_panel
from lib.graph.bar.data_input import render_data_input
from lib.graph.bar.download_panel import render_download_panel


# =========================
# ページ設定
# =========================
st.set_page_config(
    page_title="📊 棒グラフ作成（軸・凡例フル調整版）",
    page_icon="📊",
    layout="wide",
)
st.title("📊 棒グラフ作成")
st.caption(
    "1行目=タイトル、2行目=ヘッダー、3行目以降=データ（※『タイトルなし』も選べます）。"
    "Excelからそのまま貼り付けてください。"
)

# =========================
# セッション初期化
# =========================
init_session_state_from_defaults(DEFAULTS)

# =========================
# ミニトグル用 CSS 注入
# =========================
inject_mini_toggle_css()

# =========================
# サイドバー：サンプル選択
# =========================
with st.sidebar:
    current_hint = render_sample_sidebar()

# =========================
# サイドバー：リセット & プリセット
# =========================
with st.sidebar:
    render_reset_and_preset_sidebar()


# =========================
# 1) データ貼り付け（モジュール化）
# =========================
st.subheader("1) データ貼り付け")

# --- ★ タイトル行の有無ラジオボタン（ここだけで定義） ---
st.radio(
    "タイトル行の指定",
    ("1行目はタイトル", "タイトルなし（1行目からヘッダー）"),
    horizontal=True,
    key="m_k_title_row_mode",
)

# lib/graph/bar/data_input.py 側で m_k_title_row_mode を参照してパース
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

# ★ df は data_input 側ですでに「スケーリング後 df」になっている
work_df = df[[x_col] + y_cols].copy()
work_df[x_col] = work_df[x_col].astype(str)

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
        horizontal=True,
        key="m_k_orientation",
    )
with cset2:
    stack_mode = st.radio(
        "積み上げ",
        ["なし", "積み上げ", "割合(%)"],
        index=0,
        horizontal=True,
    )

with cset3:
    st.radio(
        "値表示",
        ["非表示", "表示"],
        horizontal=True,
        key="m_k_bar_label_mode",
    )

# —— スタイル（上にミニトグル → 本体エクスパンダ）
render_style_panel(
    palettes=PALETTES,
    font_candidates=FONT_CANDS,
    mini_toggle=mini_toggle,
)

# スタイルパネル内で設定されたプレビュー幅・高さを session_state から取得
preview_w = int(
    st.session_state.get("m_k_preview_width", DEFAULTS["m_k_preview_width"])
)
preview_h = int(
    st.session_state.get("m_k_preview_height", DEFAULTS["m_k_preview_height"])
)

# ==== 棒幅 ====
cats = work_df[x_col].astype(str).tolist()
num_series = len(y_cols)
is_stacked = stack_mode != "なし"
bars_per_cat = 1 if is_stacked else max(1, num_series)

# まず「自動幅」を一度だけ求める
base_bar_width = auto_bar_width(
    int(st.session_state["m_k_preview_width"]),
    len(cats),
    bars_per_cat,
)

mode = st.session_state.get("m_k_bar_mode", "自動")
manual_factor = float(
    st.session_state.get("m_k_bar_width", 0.60)
)  # 0.10〜1.00

if mode == "自動":
    # 自動モード：そのまま
    bar_width = base_bar_width
else:
    # 手動モード：自動幅 × 相対係数（0〜1）
    bar_width = base_bar_width * manual_factor

if not is_stacked:
    slots = len(y_cols)
    if bar_width * slots > 0.98:
        st.info("棒が重なり気味です。『棒の太さ』を少し下げると見やすくなります。")


# =========================
# 4) プレビュー
# =========================
st.subheader("4) プレビュー")

st.markdown("### 🔄 プレビュー再描画")
if st.button(
    "🔁 再描画を実行",
    type="primary",
    use_container_width=True,
    key="rerender_button",
):
    st.session_state["__force_rerender"] = not st.session_state.get(
        "__force_rerender", False
    )
    st.rerun()

try:
    # === 図の構築はビルダーに委譲 ===
    fig = build_bar_figure(
        df=work_df,
        x_col=x_col,
        y_cols=y_cols,
        stack_mode=stack_mode,
        bar_width=bar_width,
        preview_w=preview_w,
        preview_h=preview_h,
    )

    st.plotly_chart(
        fig,
        use_container_width=False,
        theme=None,
        config={
            "responsive": False,
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": "bar_chart",
                "scale": 2,
            },
        },
    )

except Exception as e:
    st.error(f"プレビュー生成エラー: {e}")
    st.stop()

# =========================
# 5) ダウンロード（モジュール化）
# =========================
render_download_panel(fig=fig, preview_h=preview_h)
