# -*- coding: utf-8 -*-
# pages/32_ガントチャート.py
#
# タスク表（タスク / 開始 / 終了 / タイプ / 備考）をテキストエリアに貼り付けて
# ガントチャートを作成するページ。

from __future__ import annotations

import streamlit as st
import pandas as pd

from lib.graph.gantt.sample_data import SAMPLE_TEXT
from lib.graph.gantt.parser import parse_tasks
from lib.graph.gantt.builder import build_gantt


# ------------------------------------------------------------
# ページ設定
# ------------------------------------------------------------
st.set_page_config(
    page_title="32 ガントチャート",
    page_icon="📊",
    layout="wide",
)

st.title("📊 ガントチャート作成")
st.caption(
    "タスク一覧（タスク / 開始 / 終了 / タイプ / 備考）を貼り付けて、"
    "ガントチャートと備考欄付きの図を作成します。"
)


# ------------------------------------------------------------
# SessionState 初期化
# ------------------------------------------------------------
if "gantt_raw_text" not in st.session_state:
    st.session_state["gantt_raw_text"] = ""

if "gantt_sample_choice" not in st.session_state:
    st.session_state["gantt_sample_choice"] = "なし"


# ------------------------------------------------------------
# サイドバー：サンプル選択 + 適用ボタン
# ------------------------------------------------------------
with st.sidebar:
    st.markdown("### サンプルデータ")

    sample_choice = st.radio(
        "サンプルを選択",
        ("なし", "サンプル1"),
        key="gantt_sample_choice",
    )

    if st.button("このサンプルを貼り付ける"):
        if sample_choice == "サンプル1":
            st.session_state["gantt_raw_text"] = SAMPLE_TEXT
        else:
            st.session_state["gantt_raw_text"] = ""

        st.success(f"「{sample_choice}」を貼り付けました。")


# ------------------------------------------------------------
# 入力フォーマット説明
# ------------------------------------------------------------
with st.expander("📥 入力方法（フォーマット）", expanded=False):
    st.markdown(
        """
- 1行目はヘッダーとして **タスク / 開始 / 終了 / タイプ** を必ず含めてください。  
  （任意で **備考** 列を追加できます）  
- 区切りは **タブ**（Excel からコピー）または **カンマ**（CSV）を想定しています。  
- 終了が空欄の行、または開始と終了が同じ日の行は **マイルストーン（●）** として表示されます。  
- 行の順番どおりに、上からタスクが並びます。  
- 備考の折り返しを細かく調整したい場合は、テキスト内に `<br>` を入れてください。  
- `タスク` 列に `<続き>` とある行は、1つ上のタスクの **2本目・3本目…のバー** として同じ行に追加されます。
        """
    )


# ------------------------------------------------------------
# 入力テキストエリア
# ------------------------------------------------------------
st.markdown("### 1) タスク表をここに貼り付け")

raw_text = st.text_area(
    "タスク / 開始 / 終了 / タイプ（＋任意で備考）の列を貼り付けてください",
    key="gantt_raw_text",
    height=260,
    placeholder="例：Excel で範囲をコピーしてそのまま貼り付け（1行目は列名）",
)


# ------------------------------------------------------------
# 実行ボタン
# ------------------------------------------------------------
run_gantt = st.button(
    "📐 ガントチャートを作成",
    type="primary",
)


# ------------------------------------------------------------
# ボタン押下後だけパース & 表示
# ------------------------------------------------------------
if run_gantt:
    if not raw_text.strip():
        st.warning("タスク表を貼り付けてください。")
        st.stop()

    try:
        df = parse_tasks(raw_text)
    except Exception as e:
        st.error(f"タスク表の読み込みに失敗しました: {e}")
        st.stop()

    st.success(f"タスク {len(df)} 行を読み込みました。")
    st.dataframe(df, use_container_width=True)

    with st.expander("🛠️ グラフの表示調整（文字サイズ・行間）", expanded=False):
        label_font_size = st.slider(
            "文字サイズ（タスク名・軸目盛・凡例など）",
            min_value=8,
            max_value=20,
            value=12,
            step=1,
        )
        row_height = st.slider(
            "行の高さ（行間：ピクセル）",
            min_value=30,
            max_value=80,
            value=40,
            step=2,
        )

    st.markdown("### 2) ガントチャート")

    fig = build_gantt(
        df,
        label_font_size=label_font_size,
        row_height=row_height,
    )

    if fig.data:
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 3) 図の保存")

        col_png, col_html = st.columns(2)

        with col_png:
            try:
                fig_png = fig.full_figure_for_development(warn=False)

                date_candidates = pd.concat(
                    [df["開始"].dropna(), df["終了"].dropna()],
                    ignore_index=True,
                )

                if not date_candidates.empty:
                    min_date = date_candidates.min()
                    max_date = date_candidates.max()
                else:
                    min_date = max_date = pd.Timestamp.today()

                x_min_png = min_date - pd.Timedelta(days=20)
                x_max_png = max_date + pd.Timedelta(days=60)

                fig_height = fig.layout.height or 600

                fig_png.update_layout(
                    width=1200,
                    height=fig_height,
                    margin=dict(l=300, r=300, t=120, b=100),
                )
                fig_png.update_xaxes(
                    range=[x_min_png, x_max_png],
                )

                png_bytes = fig_png.to_image(format="png", scale=2)

                st.download_button(
                    label="📥 PNG 画像としてダウンロード",
                    data=png_bytes,
                    file_name="gantt_chart.png",
                    mime="image/png",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(
                    "PNG 出力に失敗しました（`kaleido` がインストールされていない可能性があります）。\n"
                    "ターミナルで `pip install -U kaleido` を実行してから再度お試しください。\n\n"
                    f"詳細: {e}"
                )

        with col_html:
            html_str = fig.to_html(
                full_html=False,
                include_plotlyjs="cdn",
            )
            st.download_button(
                label="📥 HTML としてダウンロード（インタラクティブ）",
                data=html_str.encode("utf-8"),
                file_name="gantt_chart.html",
                mime="text/html",
                use_container_width=True,
            )

    else:
        st.info("有効なタスクがありません（開始日が空欄の行は無視されます）。")

else:
    st.info("タスク表を貼り付けて、「📐 ガントチャートを作成」を押してください。")