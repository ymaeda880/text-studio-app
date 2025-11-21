# -*- coding: utf-8 -*-
# pages/32_ガントチャート.py
#
# タスク表（タスク / 開始 / 終了 / タイプ / 備考）をテキストエリアに貼り付けて
# ガントチャートを作成するページ。
# - 入力の行順（上から）でタスクを並べる（1行目がグラフの一番上）
# - 終了が空欄 or 開始＝終了 はマイルストーン（●）
# - 「計画」「実績」はバーの色を変えて表示
# - x軸は月ごとの縦グリッド線を表示（6月, 7月, ...）
# - 備考は右端に Annotation で表示し、長文は自動改行する

from __future__ import annotations

from io import StringIO
from typing import List

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

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
# サンプルデータ
# ------------------------------------------------------------
sample_text = """タスク\t開始\t終了\tタイプ\t備考
業務計画の立案\t2025/6/10\t2025/7/2\t計画\t課題の再整理含む
業務計画の立案\t2025/6/10\t2025/7/15\t実績\t課題の再整理含む
保存（保存管理）の方向性と方法の検討\t2025/7/2\t2025/11/10\t計画\t本質的価値の再整理、保存管理の目標・将来像並びに課題の再整理含む
保存（保存管理）の方向性と方法の検討\t2025/7/5\t2025/11/20\t実績\t
活用の方向性と方法の検討\t2025/7/2\t2025/11/10\t計画\t課題の再整理含む
整備の方向性と方法の検討\t2025/8/10\t2025/11/10\t計画\t課題の再整理含む
運営・体制の方向性と方法の検討\t2025/11/10\t2026/6/10\t計画\t課題の再整理含む
経過観察の方向性と方法の検討\t2025/6/10\t2026/2/1\t計画\t課題の再整理含む
委員会運営補助\t2025/6/10\t2025/6/10\t計画\t議事要録作成含む
報告書の作成\t2025/8/10\t2026/2/10\t計画\t計画書の製本含む
打合せ協議\t2025/6/10\t\t計画\t必要に応じてメール、電話等での打合せを実施
打合せ協議\t2025/7/10\t\t計画\t
打合せ協議\t2025/8/10\t\t計画\t
打合せ協議\t2025/12/10\t\t計画\t
"""

# ------------------------------------------------------------
# ユーティリティ
# ------------------------------------------------------------
def detect_sep(text: str) -> str:
    """区切り文字を簡易判定（タブ優先 → カンマ）。"""
    head = ""
    for ln in text.splitlines():
        if ln.strip():
            head = ln
            break
    if "\t" in head:
        return "\t"
    if "," in head:
        return ","
    return "\t"


def wrap_text(text: str, width: int = 20) -> str:
    """備考を一定文字数で改行して <br> に変換（Plotly用）。"""
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if not text:
        return ""
    return "<br>".join(text[i : i + width] for i in range(0, len(text), width))


def parse_tasks(raw: str) -> pd.DataFrame:
    """貼り付けテキストから DataFrame を生成。"""
    raw = raw.strip()
    if not raw:
        return pd.DataFrame()

    sep = detect_sep(raw)
    df = pd.read_csv(StringIO(raw), sep=sep)

    expected_base = ["タスク", "開始", "終了", "タイプ"]
    missing = [c for c in expected_base if c not in df.columns]
    if missing:
        raise ValueError(
            f"列名が足りません: {missing}（タスク / 開始 / 終了 / タイプ は必須です。備考は任意です）"
        )

    # 備考列がない場合は空で作る
    if "備考" not in df.columns:
        df["備考"] = ""

    # 日付に変換（失敗したものは NaT）
    df["開始"] = pd.to_datetime(df["開始"], errors="coerce")
    df["終了"] = pd.to_datetime(df["終了"], errors="coerce")

    # 備考の折り返し版
    df["備考_wrapped"] = df["備考"].fillna("").apply(lambda x: wrap_text(x, 20))

    return df


def build_gantt(df: pd.DataFrame) -> go.Figure:
    """タスク DataFrame からガントチャート（Plotly）を作る。"""
    fig = go.Figure()

    if df.empty:
        return fig

    # 入力順を保持したタスク順（1行目が一番上）
    tasks_order: List[str] = df["タスク"].drop_duplicates(keep="first").tolist()
    # Plotly は categoryarray を下→上に使うので反転して渡す
    tasks_order_rev = list(reversed(tasks_order))

    # マイルストーン判定：終了が NaT または 開始＝終了 の行
    has_end = df["終了"].notna()
    same_day = has_end & (df["開始"].dt.date == df["終了"].dt.date)
    milestone_mask = df["終了"].isna() | same_day

    bar_df = df[~milestone_mask].copy()
    ms_df = df[milestone_mask].copy()

    # ---- 期間バー：px.timeline を利用 ----
    if not bar_df.empty:
        # 終了 < 開始 の場合は入れ替え（入力ミス対策）
        swap_mask = bar_df["終了"] < bar_df["開始"]
        bar_df.loc[swap_mask, ["開始", "終了"]] = bar_df.loc[
            swap_mask, ["終了", "開始"]
        ].values

        fig_bar = px.timeline(
            bar_df,
            x_start="開始",
            x_end="終了",
            y="タスク",
            color="タイプ",
            category_orders={"タスク": tasks_order_rev},
            color_discrete_map={
                "計画": "rgba(0, 0, 0, 0.35)",  # 薄いグレー
                "実績": "rgba(0, 0, 0, 0.9)",   # 黒
            },
        )
        # 実績が計画の上に乗るよう、計画→実績の順で並ぶことを保証
        # （px.timeline は元の行順を保つので、元の df の並びを尊重）
        for tr in fig_bar.data:
            # 枠線は邪魔なので消す
            if hasattr(tr, "marker") and hasattr(tr.marker, "line"):
                tr.marker.line.width = 0
            fig.add_trace(tr)

    # ---- マイルストーン（●） ----
    if not ms_df.empty:
        for t_type, sub in ms_df.groupby("タイプ"):
            color = "rgba(0, 0, 0, 0.6)" if t_type == "計画" else "rgba(0, 0, 0, 0.9)"
            fig.add_trace(
                go.Scatter(
                    x=sub["開始"],
                    y=sub["タスク"],
                    mode="markers",
                    marker=dict(symbol="circle", size=10, color=color),
                    name=f"{t_type}（マイルストーン）",
                )
            )

    # ---- 日付レンジ算出 ----
    date_candidates = pd.concat(
        [df["開始"].dropna(), df["終了"].dropna()], ignore_index=True
    )
    if not date_candidates.empty:
        min_date = date_candidates.min()
        max_date = date_candidates.max()
    else:
        min_date = max_date = pd.Timestamp.today()

    # 備考を右端に置くためにレンジを少し延長
    note_offset_days = 40   # 備考を置く位置
    range_offset_days = 60  # x範囲の右余白
    note_x = max_date + pd.Timedelta(days=note_offset_days)
    x_max_range = max_date + pd.Timedelta(days=range_offset_days)

    height = max(420, 40 * len(tasks_order))

    fig.update_layout(
        height=height,
        margin=dict(l=220, r=200, t=70, b=50),
        xaxis_title="日付",
        yaxis_title="タスク",
        yaxis=dict(
            categoryorder="array",
            categoryarray=tasks_order_rev,  # ← 上から入力順になるよう反転
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1.0,
        ),
    )

    # x軸：日付＋月ごと縦グリッド（スクショの「6月, 7月, ...」イメージ）
    # tickformat "%-m月" は環境によって効かないことがあるので "%b %Y" も検討可。
    fig.update_xaxes(
        type="date",
        range=[min_date, x_max_range],
        showgrid=True,
        dtick="M1",          # 1か月刻みでグリッド
        gridwidth=1,
        griddash="dot",
        tickformat="%Y-%m",  # 例: 2025-06, 2025-07 ...
    )

    # ---- 備考（右端に表示：Annotation） ----
    # タスクごとに「最初の非空備考」を採用
    def first_non_empty(values: pd.Series) -> str:
        for v in values:
            if isinstance(v, str) and v.strip():
                return v
        return ""

    notes_by_task = (
        df.groupby("タスク")["備考_wrapped"].apply(first_non_empty).to_dict()
    )

    for task in tasks_order:
        note = notes_by_task.get(task, "")
        if not note:
            continue
        fig.add_annotation(
            x=note_x,
            y=task,
            text=note,
            showarrow=False,
            xanchor="left",
            align="left",
            font=dict(size=11),
            # 背景の白ボックスを付けたい場合は以下をコメント解除
            # bordercolor="black",
            # borderwidth=0,
            # bgcolor="white",
        )

    # 備考のタイトル（上部に「備考」ラベル）を追加
    fig.add_annotation(
        x=note_x,
        y=tasks_order[0],  # 一番上のタスクの少し上に
        text="備考",
        showarrow=False,
        xanchor="left",
        yshift=24,
        font=dict(size=12, color="black", family="Meiryo"),
    )

    return fig


# ------------------------------------------------------------
# 入力 UI
# ------------------------------------------------------------
with st.expander("📥 入力方法（フォーマット）", expanded=False):
    st.markdown(
        """
- 1行目はヘッダーとして **タスク / 開始 / 終了 / タイプ** を必ず含めてください。  
  （任意で **備考** 列を追加できます）  
- 区切りは **タブ**（Excel からコピー）または **カンマ**（CSV）を想定しています。  
- 終了が空欄の行、または開始と終了が同じ日の行は **マイルストーン（●）** として表示されます。  
- 行の順番どおりに、上からタスクが並びます。
        """
    )
    st.text("サンプル（Excel からコピーした想定）")
    st.code(sample_text, language="text")

st.markdown("### 1) タスク表をここに貼り付け（またはドラッグ＆ドロップでテキストを投入）")

raw_text = st.text_area(
    "タスク / 開始 / 終了 / タイプ（＋任意で備考）の列を貼り付けてください",
    value="",
    height=260,
    placeholder="例：Excel で範囲をコピーしてそのまま貼り付け（1行目は列名）",
)

use_sample = st.checkbox("サンプルデータを使う（上を書き換えずに動作確認したいとき）", value=False)
if use_sample and not raw_text.strip():
    raw_text = sample_text

# ------------------------------------------------------------
# パース & 表示
# ------------------------------------------------------------
if raw_text.strip():
    try:
        df = parse_tasks(raw_text)
    except Exception as e:
        st.error(f"タスク表の読み込みに失敗しました: {e}")
        st.stop()

    st.success(f"タスク {len(df)} 行を読み込みました。")
    st.dataframe(df, use_container_width=True)

    st.markdown("### 2) ガントチャート")

    fig = build_gantt(df)
    if fig.data:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("有効なタスクがありません（開始日が空欄の行は無視されます）。")
else:
    st.info("タスク表を貼り付けると、ここにガントチャートが表示されます。")
