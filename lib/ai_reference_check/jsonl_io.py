# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/jsonl_io.py
# ============================================================
# AI参照チェック：JSONL入出力
#
# 機能：
# - 09_図表チェック.py が出力した AI用サマリーJSONL を読み込む
# - 必須列を検証する
# - row_id を付与する
# - DataFrame / records に変換する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import json
from typing import Any, Dict, List, Tuple

import pandas as pd


# ============================================================
# constants
# ============================================================
REQUIRED_COLUMNS = [
    "図表キー",
    "図表タイトル",
    "前テキスト",
    "参照テキスト",
    "後テキスト",
]


# ============================================================
# JSONL bytes 読み込み
# ============================================================
def load_ai_summary_jsonl_bytes(
    *,
    data: bytes,
) -> Tuple[pd.DataFrame, List[str]]:
    errors: List[str] = []
    rows: List[Dict[str, Any]] = []

    text = data.decode("utf-8-sig", errors="replace")

    for line_no, line in enumerate(text.splitlines(), start=1):
        s = line.strip()

        if not s:
            continue

        try:
            obj = json.loads(s)
        except Exception as e:
            errors.append(f"{line_no}行目: JSONとして読めません: {e}")
            continue

        if not isinstance(obj, dict):
            errors.append(f"{line_no}行目: JSON objectではありません。")
            continue

        obj["_source_line_no"] = line_no
        rows.append(obj)

    df = pd.DataFrame(rows)

    if df.empty:
        return df, errors

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            errors.append(f"必須列がありません: {col}")

    if "row_id" not in df.columns:
        df.insert(0, "row_id", range(1, len(df) + 1))

    return df, errors


# ============================================================
# AI送信用 records 生成
# ============================================================
def df_to_ai_records(
    *,
    df: pd.DataFrame,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    if df.empty:
        return records

    for _, row in df.iterrows():
        records.append(
            {
                "row_id": int(row.get("row_id")),
                "sheet": str(row.get("sheet", "") or ""),
                "図表キー": str(row.get("図表キー", "") or ""),
                "結果": str(row.get("結果", "") or ""),
                "図表タイトル": str(row.get("図表タイトル", "") or ""),
                "頁": str(row.get("頁", "") or ""),
                "pdf頁": str(row.get("pdf頁", "") or ""),
                "参照頁ラベル": str(row.get("参照頁ラベル", "") or ""),
                "参照pdf頁": str(row.get("参照pdf頁", "") or ""),
                "前テキスト": str(row.get("前テキスト", "") or ""),
                "参照テキスト": str(row.get("参照テキスト", "") or ""),
                "後テキスト": str(row.get("後テキスト", "") or ""),
            }
        )

    return records