# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/parse.py
# ============================================================
# AI参照チェック：AI応答parse / xlsx生成
#
# 機能：
# - AI応答からJSON objectを抽出する
# - checksをDataFrame化する
# - 元データとAI判定を結合する
# - xlsx bytesを生成する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import json
import re
from io import BytesIO
from typing import Any, Dict, List

import pandas as pd


# ============================================================
# AI応答からJSON object抽出
# ============================================================
def extract_json_object(text: str) -> Dict[str, Any]:
    s = str(text or "").strip()

    if not s:
        raise ValueError("AI応答が空です。")

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        raise ValueError("JSON objectが見つかりません。")

    obj = json.loads(m.group(0))

    if not isinstance(obj, dict):
        raise ValueError("JSON objectではありません。")

    return obj


# ============================================================
# checks抽出
# ============================================================
def checks_from_result_objects(
    *,
    result_objects: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []

    for obj in result_objects:
        if not isinstance(obj, dict):
            continue

        arr = obj.get("checks")

        if not isinstance(arr, list):
            continue

        for item in arr:
            if isinstance(item, dict):
                checks.append(item)

    return checks


# ============================================================
# checks DataFrame化
# ============================================================
def checks_to_df(
    *,
    checks: List[Dict[str, Any]],
) -> pd.DataFrame:
    columns = [
        "row_id",
        "figure_key",
        "judgment",
        "confidence",
        "reason",
        "suspected_correct_key",
        "note",
        "chunk_index",
    ]

    if not checks:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(checks)

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    return df[columns]


# ============================================================
# 元データとAI判定を結合
# ============================================================
def merge_input_and_checks(
    *,
    df_input: pd.DataFrame,
    df_checks: pd.DataFrame,
) -> pd.DataFrame:
    if df_input.empty:
        return pd.DataFrame()

    df_left = df_input.copy()

    if df_checks.empty:
        for col in [
            "AI判定",
            "AI確信度",
            "AI理由",
            "AI修正候補",
            "AI補足",
            "chunk_index",
        ]:
            df_left[col] = ""
        return df_left

    df_right = df_checks.copy()
    df_right = df_right.rename(
        columns={
            "judgment": "AI判定",
            "confidence": "AI確信度",
            "reason": "AI理由",
            "suspected_correct_key": "AI修正候補",
            "note": "AI補足",
        }
    )

    return df_left.merge(
        df_right[
            [
                "row_id",
                "AI判定",
                "AI確信度",
                "AI理由",
                "AI修正候補",
                "AI補足",
                "chunk_index",
            ]
        ],
        on="row_id",
        how="left",
    )


# ============================================================
# xlsx bytes生成
# ============================================================
def make_reference_check_xlsx_bytes(
    *,
    df_result: pd.DataFrame,
    df_input: pd.DataFrame,
    df_checks: pd.DataFrame,
    usage_rows: List[Dict[str, Any]],
) -> bytes:
    output = BytesIO()

    df_review = pd.DataFrame()
    if not df_result.empty and "AI判定" in df_result.columns:
        df_review = df_result[df_result["AI判定"].isin(["CHECK", "NG"])].copy()

    df_usage = pd.DataFrame(usage_rows)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_result.to_excel(writer, sheet_name="判定結果", index=False)
        df_review.to_excel(writer, sheet_name="要確認", index=False)
        df_input.to_excel(writer, sheet_name="入力", index=False)
        df_checks.to_excel(writer, sheet_name="AI応答checks", index=False)
        df_usage.to_excel(writer, sheet_name="usage", index=False)

    return output.getvalue()