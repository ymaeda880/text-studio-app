# -*- coding: utf-8 -*-
# lib/graph/gantt/builder.py
#
# DataFrame からガントチャート (Plotly) を生成する関数群

from __future__ import annotations

from typing import List, Dict

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from .utils import first_non_empty


def build_gantt(
    df: pd.DataFrame,
    *,
    label_font_size: int = 12,
    row_height: int = 40,
) -> go.Figure:
    """
    タスク DataFrame からガントチャート（Plotly）を作る。

    Parameters
    ----------
    df : DataFrame
        列: タスク / 開始 / 終了 / タイプ / 備考
        ※ parse_tasks() で前処理済みを想定
    label_font_size : int
        軸ラベル・タスク名・凡例などのフォントサイズ
    row_height : int
        1 行あたりの高さ（px）。行間の調整用。
    """
    fig = go.Figure()

    if df.empty:
        return fig

    # -----------------------------
    # 1) タスク順（入力順）を確定
    # -----------------------------
    base_tasks: List[str] = df["タスク"].tolist()
    seen: Dict[str, bool] = {}
    tasks_order: List[str] = []
    for t in base_tasks:
        if t not in seen:
            seen[t] = True
            tasks_order.append(t)

    # -----------------------------
    # 2) 計画／実績で行を分けるための YID
    # -----------------------------
    # 計画行: "<タスク>__PLAN"
    # 実績行: "<タスク>__ACT"
    df = df.copy()
    df["YID"] = df.apply(
        lambda r: f"{r['タスク']}__ACT" if str(r["タイプ"]) == "実績" else f"{r['タスク']}__PLAN",
        axis=1,
    )

    # y 軸の行順（上→下）:
    #   タスク1 PLAN
    #   タスク1 ACT
    #   タスク2 PLAN
    #   タスク2 ACT
    y_ids_order: List[str] = []
    y_labels: List[str] = []
    for task in tasks_order:
        plan_id = f"{task}__PLAN"
        act_id = f"{task}__ACT"

        # PLAN 行は常に用意（ラベル = タスク名）
        y_ids_order.append(plan_id)
        y_labels.append(task)

        # 実績が存在するタスクなら ACT 行も用意（ラベル = 空）
        if (df["YID"] == act_id).any():
            y_ids_order.append(act_id)
            y_labels.append("")

    # Plotly は categoryarray を下→上に並べるので反転して渡す
    y_ids_order_rev = list(reversed(y_ids_order))
    # タスクラベルは <br> をそのまま HTML 改行として使う
    y_labels_rev = [
        lab.replace("\n", "<br>") if isinstance(lab, str) else lab
        for lab in reversed(y_labels)
    ]

    # -----------------------------
    # 3) マイルストーン判定
    # -----------------------------
    has_end = df["終了"].notna()
    same_day = has_end & (df["開始"].dt.date == df["終了"].dt.date)
    milestone_mask = df["終了"].isna() | same_day

    bar_df = df[~milestone_mask].copy()
    ms_df = df[milestone_mask].copy()

    # -----------------------------
    # 4) 期間バー（px.timeline）
    # -----------------------------
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
            y="YID",
            color="タイプ",
            category_orders={"YID": y_ids_order_rev},
            color_discrete_map={
                "計画": "rgba(0, 0, 0, 0.35)",  # 薄いグレー
                "実績": "rgba(0, 0, 0, 0.9)",   # 黒
            },
        )
        for tr in fig_bar.data:
            # 枠線は邪魔なので消す
            if hasattr(tr, "marker") and hasattr(tr.marker, "line"):
                tr.marker.line.width = 0
            fig.add_trace(tr)

    # -----------------------------
    # 5) マイルストーン（●）
    # -----------------------------
    if not ms_df.empty:
        for t_type, sub in ms_df.groupby("タイプ"):
            color = "rgba(0, 0, 0, 0.6)" if t_type == "計画" else "rgba(0, 0, 0, 0.9)"
            fig.add_trace(
                go.Scatter(
                    x=sub["開始"],
                    y=sub["YID"],
                    mode="markers",
                    marker=dict(symbol="circle", size=10, color=color),
                    name=f"{t_type}（マイルストーン）",
                )
            )

    # -----------------------------
    # 6) 日付レンジ & 月ごとの情報
    # -----------------------------
    date_candidates = pd.concat(
        [df["開始"].dropna(), df["終了"].dropna()],
        ignore_index=True,
    )
    if not date_candidates.empty:
        min_date = date_candidates.min()
        max_date = date_candidates.max()
    else:
        min_date = max_date = pd.Timestamp.today()

    # 月初（境界）のリスト：最初の月〜「最後の月の翌月」の月初
    first_month_start = pd.Timestamp(min_date.year, min_date.month, 1)
    last_month_start = pd.Timestamp(max_date.year, max_date.month, 1)
    month_starts = pd.date_range(
        first_month_start,
        last_month_start + pd.offsets.MonthBegin(1),
        freq="MS",
    )

    # ラベル用：最後の月まで（境界の「翌月」はラベル不要）
    label_month_starts = month_starts[:-1]
    month_centers = label_month_starts + pd.Timedelta(days=14)  # 月の真ん中あたり
    month_labels = [f"{d.month}月" for d in month_centers]

    # x 軸の表示範囲：最初の月初〜最後の月の翌月（＝末尾の境界）
    x_min_range = first_month_start
    x_max_range = month_starts[-1]

    # -----------------------------
    # 7) レイアウト（高さ・軸・凡例）
    # -----------------------------
    height = max(420, row_height * len(y_ids_order))

    fig.update_layout(
        height=height,
        margin=dict(l=220, r=220, t=70, b=50),
        xaxis_title="",
        yaxis_title="",
        xaxis=dict(
            type="date",
            range=[x_min_range, x_max_range],
            showgrid=False,  # グリッドは vline で描画
            tickmode="array",
            tickvals=month_centers,
            ticktext=month_labels,
            tickfont=dict(size=label_font_size),
        ),
        yaxis=dict(
            categoryorder="array",
            categoryarray=y_ids_order_rev,
            tickmode="array",
            tickvals=y_ids_order_rev,
            ticktext=y_labels_rev,
            tickfont=dict(size=label_font_size),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1.0,
            font=dict(size=max(8, label_font_size - 1)),
        ),
    )

    # -----------------------------
    # 8) 月ごとの縦罫線（月初）
    # -----------------------------
    for d in month_starts:
        fig.add_vline(
            x=d,
            line_width=1,
            line_dash="dot",
            line_color="rgba(0, 0, 0, 0.3)",
            layer="below",
        )

    # -----------------------------
    # 9) 備考（右端・paper 座標で表示）
    # -----------------------------
    notes_by_yid: Dict[str, str] = (
        df.groupby("YID")["備考"].apply(first_non_empty).to_dict()
    )

    for yid in y_ids_order:
        note = notes_by_yid.get(yid, "")
        if not note:
            continue
        # 改行は <br> に変換（ユーザーが <br> を直接書いた場合はそのまま）
        note = str(note).replace("\r\n", "\n").replace("\r", "\n")
        note = note.replace("\n", "<br>")
        fig.add_annotation(
            xref="paper",
            x=1.02,          # プロット領域の少し右
            yref="y",
            y=yid,
            text=note,
            showarrow=False,
            xanchor="left",
            align="left",
            font=dict(size=max(8, label_font_size - 1)),
        )

    # 備考タイトル
    if y_ids_order:
        top_yid = y_ids_order[0]
        fig.add_annotation(
            xref="paper",
            x=1.02,
            yref="y",
            y=top_yid,
            text="備考",
            showarrow=False,
            xanchor="left",
            yshift=24,
            font=dict(size=label_font_size, color="black"),
        )

    return fig
