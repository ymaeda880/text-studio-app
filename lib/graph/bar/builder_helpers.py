# -*- coding: utf-8 -*-
# lib/graph/bar/builder_helpers.py
#
# builder.py から切り出したヘルパ関数群
# - セッション状態取得
# - 値ラベル文字列生成
# - 軸 tickformat / tick オプション
# - ハイライト＆ソート
# - 割合(%) モード変換
# - 値ラベル用の軸拡張

from __future__ import annotations

from typing import List, Optional, Set, MutableMapping, Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


SessionStateLike = MutableMapping[str, Any]


def _get_state(session_state: Optional[SessionStateLike] = None) -> SessionStateLike:
    """
    session_state 引数があればそれを使い，
    なければ st.session_state を返すヘルパ。
    """
    return session_state if session_state is not None else st.session_state


def _make_value_labels(
    series: pd.Series,
    *,
    stack_mode: str,
    value_format_mode: str,
    decimals: int,
) -> List[str]:
    """
    棒に表示するラベル文字列を生成する。
    - stack_mode が 「割合(%)」 のときは末尾に % を付ける
    - value_format_mode が「カンマ区切り」のときは 1,234.5 のように , を入れる
    - decimals で小数点以下桁数を指定
    """
    labels: List[str] = []
    for v in series.values:
        try:
            fv = float(v)
        except Exception:
            # 数値に変換できないときはそのまま文字列で
            labels.append(str(v))
            continue

        # 割合モード（すでに値は % 単位に変換済み）
        if stack_mode == "割合(%)":
            if value_format_mode == "カンマ区切り":
                labels.append(f"{fv:,.{decimals}f}%")
            else:
                labels.append(f"{fv:.{decimals}f}%")
        else:
            if value_format_mode == "カンマ区切り":
                labels.append(f"{fv:,.{decimals}f}")
            else:
                labels.append(f"{fv:.{decimals}f}")
    return labels


def _build_axis_tickformat(
    value_format_mode: str,
    decimals: int,
) -> Optional[str]:
    """
    軸の tickformat 文字列を決定する。
    カンマ区切りモードのときだけ Plotly 用 tickformat を返し，
    それ以外は None を返す。
    """
    if value_format_mode != "カンマ区切り":
        return None
    # 例: , .0f → 1,234 / , .1f → 1,234.5
    return f",.{decimals}f"


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


def _apply_highlight_and_sort(
    df: pd.DataFrame,
    x_col: str,
    y_cols: List[str],
    *,
    enable_highlight: bool,
    highlight_top_k: int,
) -> tuple[pd.DataFrame, Set[str]]:
    """
    上位カテゴリのハイライト対象を決める & 表示順を「大きい順」に並べ替える。

    戻り値：
        (並べ替え後の DataFrame, ハイライト対象カテゴリ名の集合)
    """
    top_k_cats: Set[str] = set()
    if not enable_highlight or df.empty:
        return df, top_k_cats

    work_df = df.copy()
    num_block = work_df[y_cols].apply(pd.to_numeric, errors="coerce")
    work_df["_total_"] = num_block.sum(axis=1).fillna(0)

    # 大きい順にソートして上位Kカテゴリを選ぶ
    work_df = work_df.sort_values("_total_", ascending=False)
    top_k_cats = set(
        work_df.head(highlight_top_k)[x_col].astype(str).tolist()
    )

    # 表示順も「大きい順」に入れ替えた DataFrame を返す
    work_df_out = (
        df.assign(_total_=work_df["_total_"].values)
        .sort_values("_total_", ascending=False)
        .drop(columns=["_total_"])
    )
    return work_df_out, top_k_cats


def _apply_percentage_mode(
    df: pd.DataFrame,
    y_cols: List[str],
) -> pd.DataFrame:
    """
    割合(%) モード用に，行ごとに 100% に正規化する。
    元の df は変更せず，新しい DataFrame を返す。
    """
    work_df = df.copy()
    num_block = work_df[y_cols].apply(pd.to_numeric, errors="coerce")
    row_sum = num_block.sum(axis=1)
    safe_sum = row_sum.replace(0, np.nan)
    pct_block = num_block.div(safe_sum, axis=0) * 100.0
    pct_block = pct_block.fillna(0)
    for col in y_cols:
        work_df[col] = pct_block[col]
    return work_df


def _expand_axis_for_labels(
    fig: go.Figure,
    *,
    orientation: str,
    df: pd.DataFrame,
    y_cols: List[str],
    stack_mode: str,
    margin_ratio: float = 1.1,
) -> None:
    """
    値ラベル表示時に，棒の最大値より少し余白をとるために軸範囲を拡張する。
    """
    num_block = df[y_cols].apply(pd.to_numeric, errors="coerce")

    if stack_mode == "なし":
        max_val = num_block.max().max()
    else:
        max_val = num_block.sum(axis=1).max()

    if pd.notna(max_val) and max_val > 0:
        if orientation == "縦":
            fig.update_yaxes(range=[0, max_val * margin_ratio])
        else:
            fig.update_xaxes(range=[0, max_val * margin_ratio])
