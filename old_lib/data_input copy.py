# -*- coding: utf-8 -*-
# lib/graph/bar/data_input.py
#
# 「1) データ貼り付け」パネル
# - Excel貼り付け → DataFrame 化
# - タイトル候補の表示
# - パース診断エクスパンダ
#
# 呼び出し側:
#   df, title_default = render_data_input(sample_hint, mini_toggle)

from __future__ import annotations
from typing import Tuple

import streamlit as st
import pandas as pd

from lib.graph.parsing_utils import parse_pasted_robust


def render_data_input(sample_hint: str, mini_toggle) -> Tuple[pd.DataFrame, str]:
    """
    「1) データ貼り付け」UI を描画し、解析済み DataFrame と
    タイトル候補（1 行目）を返す。
    """
    # 見出し
    st.subheader("1) データ貼り付け")

    # ---- 内部コールバック：貼り付けテキストを解析 ----
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

        st.session_state["m_k_chart_title"] = title or ""

        cols = list(new_df.columns)
        # X 軸タイトル（1列目）
        if cols:
            st.session_state["m_k_x_title"] = cols[0]

        # Y 軸タイトル（2列目以降）
        y_cols = cols[1:]
        if y_cols:
            st.session_state["m_k_y_title"] = (
                " / ".join(y_cols) if len(y_cols) <= 3 else f"{len(y_cols)}系列"
            )

    # ---- テキストエリア & ボタン ----
    st.text_area(
        "Excelの表を貼り付け（1行目=タイトル、2行目=ヘッダー）",
        sample_hint,
        height=180,
        key="raw_text",
    )
    st.button(
        "▶️ グラフ作成（解析を実行）",
        type="primary",
        on_click=_ingest_text,
        use_container_width=True,
    )

    # ---- 解析済みかどうか確認 ----
    if "__df" not in st.session_state or not st.session_state.get("__confirmed", False):
        st.info("表を貼り付けたら『グラフ作成（解析を実行）』を押してください。")
        st.stop()

    df = st.session_state["__df"]
    title_default = st.session_state.get("__title", "")

    # 貼り付け内容の変更検知
    current_hash = hash(st.session_state.get("raw_text", ""))
    if current_hash != st.session_state.get("__raw_hash"):
        st.warning("貼り付け内容が前回の解析後に変更されています。必要なら再度『グラフ作成』を押してください。")

    # タイトル候補と先頭 50 行プレビュー
    st.success(f"タイトル候補：**{title_default or '(未設定)'}**")
    st.dataframe(df.head(50), use_container_width=True)

    # ---- パース診断（上にミニトグル → 本体エクスパンダ）----
    st.markdown('<div class="mini-toggle-row"></div>', unsafe_allow_html=True)
    mini_toggle("🩺 パース診断を開く（状態を保持）", key="exp_diag_open")
    with st.expander("🩺 パース診断（必要時のみ）", expanded=st.session_state["exp_diag_open"]):
        st.json(st.session_state.get("__diag", {}))

    return df, title_default
