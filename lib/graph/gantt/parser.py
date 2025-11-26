# -*- coding: utf-8 -*-
# lib/graph/gantt/parser.py

from __future__ import annotations

from io import StringIO
from typing import List

import pandas as pd


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


def parse_tasks(raw: str) -> pd.DataFrame:
    """
    貼り付けテキストから DataFrame を生成。

    - 必須列: タスク / 開始 / 終了 / タイプ
    - 任意列: 備考
    - 「タスク」列が `<続き>` / `＜続き＞` の行は直前のタスク名を引き継ぐ
      （タイプが空欄なら直前のタイプも引き継ぐ）
    """
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

    # NaN の備考は空文字に
    df["備考"] = df["備考"].fillna("")

    # ----------------------------------------------------
    # ここから <続き> の処理
    # ----------------------------------------------------
    prev_task: str | None = None
    prev_type: str | None = None

    for idx, row in df.iterrows():
        t_raw = row["タスク"]
        t = str(t_raw).strip()

        typ_raw = row["タイプ"]
        typ = str(typ_raw).strip() if not pd.isna(typ_raw) else ""

        # 通常のタスク名行 → そのまま記憶
        if t and t not in ("<続き>", "＜続き＞"):
            prev_task = t
            # タイプが空でない場合だけ更新
            if typ:
                prev_type = typ

        # <続き> / ＜続き＞ → 直前のタスク名・タイプを引き継ぐ
        elif t in ("<続き>", "＜続き＞"):
            if prev_task is not None:
                # タスク名を直前タスクに差し替え
                df.at[idx, "タスク"] = prev_task

                # タイプが空欄なら直前のタイプを引き継ぎ
                if not typ and prev_type:
                    df.at[idx, "タイプ"] = prev_type
            else:
                # 先頭行が <続き> の場合など、前がなければそのまま（もしくは Warning を出しても良い）
                pass

    # ----------------------------------------------------
    # 日付に変換（最後に実施）
    # ----------------------------------------------------
    df["開始"] = pd.to_datetime(df["開始"], errors="coerce")
    df["終了"] = pd.to_datetime(df["終了"], errors="coerce")

    return df
