# -*- coding: utf-8 -*-
# pages/33_フローチャート.py
#
# Excel から 2 列（タイトル / 説明）をコピペして
# 簡易フローチャートを描くページ。

from __future__ import annotations

import re
import textwrap
from typing import List, Dict

import streamlit as st
import plotly.graph_objects as go

from lib.graph.flowchart.lowlevel import (
    init_flowchart_defaults,
    add_rect_shape,
    add_text_annotation,
)

from lib.graph.flowchart.step_shapes import (
    add_step_box,
    add_vertical_arrow,
)


# ============================
# サンプルテキスト定義
# ============================
SAMPLE1_TEXT = """業務計画の作成\t事前調査の報告内容を踏まえ、実施方針と計画を整理する。
基礎データ・指標に関する調査\t基礎指標および応用的な分析手順について外部の有識者の意見を得ながら整理する。
データ解析と整備効果の評価\t事前調査との比較を基準として整備効果を評価し、分析結果をまとめる。
対外向け資料の作成\t市民向けに分かりやすく整理したPR資料を作成し、成果とあわせてまとめる。"""

SAMPLE2_TEXT = """企画案の整理\t関連資料を収集し、目的と背景を整理したうえで企画案の骨子を作成する。
関係者ヒアリング\t関係部署や外部有識者へのヒアリングを行い、企画案の妥当性や懸念点を確認する。
実施計画の詳細化\tスケジュール・体制・コストなどを整理し、実施可能な計画として具体化する。
成果報告のとりまとめ\t実施結果を整理して課題・今後の展開を含めた報告資料を作成する。"""


# ============================
# ヘルパー：テキスト→ステップ
# ============================
def parse_steps_from_paste(raw: str) -> List[Dict[str, str]]:
    """
    Excel からの 2 列コピーを想定：
    1列目=タイトル, 2列目=説明（TAB 区切り）
    """
    steps: List[Dict[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        if "\t" in line:
            title, desc = line.split("\t", 1)
        else:
            # TAB が無い場合は「2個以上のスペース」で区切る
            parts = re.split(r"\s{2,}", line, 1)
            if len(parts) == 2:
                title, desc = parts
            else:
                title, desc = line, ""

        steps.append({"title": title.strip(), "desc": desc.strip()})
    return steps



# ============================
# steps → Plotly 図
# ============================
def build_flow_chart(steps: List[Dict[str, str]]) -> go.Figure:
    fig = go.Figure()
    n = len(steps)
    if n == 0:
        return fig

    # 縦位置の自動配置
    top, bottom = 0.88, 0.12
    total_height = top - bottom
    box_h = total_height / (n * 1.3)
    gap = (total_height - n * box_h) / max(n - 1, 1)
    ys = [top - (box_h / 2) - i * (box_h + gap) for i in range(n)]

    x0, x1 = 0.08, 0.92
    arrow_color = "rgb(0,176,80)"

    for i, (step, y) in enumerate(zip(steps, ys)):
        add_step_box(
            fig,
            x0=x0,
            x1=x1,
            y_center=y,
            height=box_h,
            title=step["title"],
            desc=step["desc"],
        )

        # 下の箱との間に矢印
        if i < n - 1:
            y_next = ys[i + 1]
            add_vertical_arrow(
                fig,
                x=0.5,
                y_from=y - box_h / 2 - gap * 0.25,
                y_to=y_next + box_h / 2 + gap * 0.25,
                color=arrow_color,
                width=2,
            )

    # 外枠（lowlevel の add_rect_shape を利用）
    add_rect_shape(
        fig,
        (0.05, 0.05),
        (0.95, 0.95),
        line_color="black",
        fill_color="rgba(0,0,0,0)",
        line_width=st.session_state["outer_frame_line_width"],
    )

    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 1])

    fig.update_layout(
        width=800,
        height=max(450, 150 * n),
        margin=dict(l=40, r=40, t=80, b=40),
        plot_bgcolor="white",
        paper_bgcolor="white",
        title=dict(
            text="📊 フローチャート（Excel貼り付け）",
            x=0.5,
            xanchor="center",
        ),
    )
    return fig


# ============================
# Streamlit UI
# ============================
st.set_page_config(page_title="📊 フローチャート", layout="centered")
st.title("📊 フローチャート（簡易版）")

# ---- 初期化：DEFAULTS → session_state ----
init_flowchart_defaults()

# ---- SessionState 初期化（テキストは空 / サンプル=なし）----
if "flow_raw_text" not in st.session_state:
    st.session_state["flow_raw_text"] = ""
if "flow_sample_choice" not in st.session_state:
    st.session_state["flow_sample_choice"] = "なし"

# ---- サイドバー：サンプル選択 + 適用ボタン ----
with st.sidebar:
    st.markdown("### サンプルデータ")

    sample_choice = st.radio(
        "サンプルを選択",
        ("なし", "サンプル1", "サンプル2"),
        key="flow_sample_choice",
    )

    if st.button("このサンプルを貼り付ける", use_container_width=True):
        if sample_choice == "サンプル1":
            st.session_state["flow_raw_text"] = SAMPLE1_TEXT
        elif sample_choice == "サンプル2":
            st.session_state["flow_raw_text"] = SAMPLE2_TEXT
        else:  # なし
            st.session_state["flow_raw_text"] = ""
        st.success(f"「{sample_choice}」を貼り付けました。")

st.markdown(
    """
Excel で作成した **2列の表（「タイトル」「説明」）** を  
そのままコピーして、下のテキスト欄に貼り付けてください。

- 1列目：ステップ名（タイトル）  
- 2列目：説明文  
- 区切りは **TAB**（通常の Excel コピー）を想定しています。
"""
)

# ★ 初期値は SessionState のみを使う（value= は渡さない）
raw_text = st.text_area(
    "Excel からコピーして貼り付け",
    key="flow_raw_text",
    height=180,
)

if st.button("📐 フローチャートを作成", type="primary"):
    steps = parse_steps_from_paste(raw_text)

    if not steps:
        st.warning("有効な行が見つかりませんでした。タイトルと説明の2列を貼り付けてください。")
    else:
        fig = build_flow_chart(steps)
        st.plotly_chart(fig, use_container_width=True)
