# -*- coding: utf-8 -*-
# pages/57_棒グラフ作成_simple.py
#
# 「貼り付け → 列を選ぶ → ボタン押す」と
# ただの棒グラフ（matplotlib）が出るだけの超シンプル版。

from __future__ import annotations
from typing import Optional
import io

import streamlit as st
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

# 日本語フォントだけ最低限設定（それ以外は matplotlib デフォルト）
plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["text.usetex"] = False
matplotlib.rcParams["mathtext.default"] = "regular"

# データ貼り付け用ユーティリティ
from lib.graph.bar.data_input import render_data_input
from lib.graph.bar.presets import (
    sample_hint,
    sample_hint2,
    sample_hint3,
    DEFAULTS,
)

# =========================
# ページ設定
# =========================
st.set_page_config(
    page_title="📊 棒グラフ作成（シンプル版 / matplotlib）",
    page_icon="📊",
    layout="wide",
)
st.title("📊 棒グラフ作成（シンプル版｜matplotlib）")
st.caption("1行目=タイトル、2行目=ヘッダー、3行目以降=データを貼り付けてください。設定は最小限です。")

# =========================
# session_state の最低限初期化
# =========================
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.session_state.setdefault("exp_diag_open", False)

# =========================
# 1) データ貼り付け
# =========================

def dummy_mini_toggle(label: str, key: str) -> None:
    """simple版では何もしないダミー関数（render_data_inputとの互換用）"""
    return

# --- サンプルデータの選択 ---
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
    current_hint = ""  # 完全に空にしたい場合

df, title_default = render_data_input(
    sample_hint=current_hint,
    mini_toggle=dummy_mini_toggle,
)

if df.empty:
    st.info("データを貼り付けると、ここから棒グラフを作成できます。")
    st.stop()

st.subheader("2) 列の指定（最低限）")

all_cols = list(df.columns)
if not all_cols:
    st.error("列が見つかりません。貼り付けデータをご確認ください。")
    st.stop()

# カテゴリ列：1列
cat_col = st.selectbox("カテゴリ列（X軸/ラベル）", all_cols, index=0)

# 値の列：1列だけ（Xと同じ列は除外）
value_candidates = [c for c in all_cols if c != cat_col] or all_cols
val_col = st.selectbox("値の列（Y軸）", value_candidates, index=0)

# グラフ向きだけは選べるように
orientation = st.radio(
    "棒グラフの向き",
    ["縦（デフォルト）", "横"],
    horizontal=True,
)

# =========================
# 3) グラフ作成
# =========================
st.subheader("3) グラフを作成")

fig: Optional[plt.Figure] = None

if st.button("📊 グラフを作成", type="primary", use_container_width=True):
    # ラベル文字列（<br> が来たら改行に）
    cats_raw = df[cat_col].astype(str)
    labels = [s.replace("<br>", "\n") for s in cats_raw]
    values = pd.to_numeric(df[val_col], errors="coerce").fillna(0.0)

    idx = list(range(len(labels)))

    fig, ax = plt.subplots()  # デフォルトサイズ

    if orientation.startswith("縦"):
        # 縦棒グラフ
        ax.bar(idx, values)
        ax.set_xticks(idx)
        ax.set_xticklabels(
            labels,
            rotation=0,
            ha="center",
            va="center",
            linespacing=1.2,
        )
        for tl in ax.get_xticklabels():
            tl.set_multialignment("center")

        ax.set_xlabel(cat_col)
        ax.set_ylabel(val_col)

    else:
        # 横棒グラフ
        ax.barh(idx, values)

        # ラベルが長いので左マージンを少し広げるとバランスが良い
        fig.subplots_adjust(left=0.40)

        ax.set_yticks(idx)
        ax.set_yticklabels(
            labels,
            rotation=0,
            ha="center",
            va="center",
            linespacing=1.2,
        )
        for tl in ax.get_yticklabels():
            tl.set_multialignment("center")

        ax.invert_yaxis()  # 上に最初の項目が来るように
        ax.set_ylabel(cat_col)
        ax.set_xlabel(val_col)

    # タイトル（1行目をそのまま）
    if isinstance(title_default, str) and title_default.strip():
        ax.set_title(title_default.strip())

    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)

# =========================
# 4) ダウンロード（PNG / SVG）
# =========================
st.subheader("4) ダウンロード（PNG / SVG）")

if "fig" not in locals() or fig is None:
    st.info("まず上の「📊 グラフを作成」ボタンを押してください。")
else:
    col_png, col_svg = st.columns(2)

    with col_png:
        st.markdown("**📥 PNG 画像で保存**")
        buf_png = io.BytesIO()
        fig.savefig(buf_png, format="png", dpi=300, bbox_inches="tight")
        png_bytes = buf_png.getvalue()

        st.download_button(
            "PNG をダウンロード",
            data=png_bytes,
            file_name="bar_chart_simple.png",
            mime="image/png",
            use_container_width=True,
        )

    with col_svg:
        st.markdown("**📥 SVG 画像で保存（ベクター形式）**")
        buf_svg = io.BytesIO()
        fig.savefig(buf_svg, format="svg", dpi=300, bbox_inches="tight")
        svg_bytes = buf_svg.getvalue()

        st.download_button(
            "SVG をダウンロード",
            data=svg_bytes,
            file_name="bar_chart_simple.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )
