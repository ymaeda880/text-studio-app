# -*- coding: utf-8 -*-
# text_studio_app/lib/chart_check/summary_export.py
# ============================================================
# 図表チェック：通常サマリー出力
#
# 機能：
# - 引用見出し / 未引用見出しを統合
# - 図 / 表 / 図表 の3シートに分割
# - pdf頁順にソート
# - サマリーxlsx bytesを生成
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from io import BytesIO
from typing import Dict

import pandas as pd


# ============================================================
# constants
# ============================================================
SUMMARY_COLUMNS = [
    "図表キー",
    "結果",
    "図表タイトル",
    "頁",
    "pdf頁",
    "参照頁ラベル",
    "参照pdf頁",
    "参照テキスト",
    "参照テキスト(強調)",
]


# ============================================================
# kind 判定
# ============================================================
def summary_kind_from_key(key: str) -> str:
    s = str(key or "")

    if s.startswith("図表"):
        return "図表"

    if s.startswith("図"):
        return "図"

    if s.startswith("表"):
        return "表"

    return ""


# ============================================================
# 空サマリーdf
# ============================================================
def empty_summary_df() -> pd.DataFrame:
    return pd.DataFrame(columns=SUMMARY_COLUMNS)


# ============================================================
# pdf頁順ソート
# ============================================================
def sort_summary_by_pdf_page(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return empty_summary_df()

    df2 = df.copy()

    if "_summary_kind" in df2.columns:
        df2 = df2.drop(columns=["_summary_kind"])

    if "pdf頁" in df2.columns and "図表キー" in df2.columns:
        df2 = df2.sort_values(
            by=["pdf頁", "図表キー"],
            kind="mergesort",
        )

    return df2


# ============================================================
# 引用見出し + 未引用見出しを統合
# ============================================================
def build_summary_all_df(
    *,
    df_referenced_captions_x: pd.DataFrame,
    df_missing_caption_refs_x: pd.DataFrame,
) -> pd.DataFrame:
    summary_parts = []

    if not df_referenced_captions_x.empty:
        df_tmp = df_referenced_captions_x.copy()
        df_tmp.insert(1, "結果", "")
        summary_parts.append(df_tmp)

    if not df_missing_caption_refs_x.empty:
        df_tmp = df_missing_caption_refs_x.copy()
        df_tmp.insert(1, "結果", "未引用")
        summary_parts.append(df_tmp)

    if summary_parts:
        return pd.concat(summary_parts, ignore_index=True)

    return empty_summary_df()


# ============================================================
# 図 / 表 / 図表 に分割
# ============================================================
def split_summary_frames(df_summary_all_x: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    df_all = df_summary_all_x.copy()

    if "図表キー" in df_all.columns:
        df_all["_summary_kind"] = df_all["図表キー"].map(summary_kind_from_key)
    else:
        df_all["_summary_kind"] = ""

    df_fig = df_all[df_all["_summary_kind"] == "図"].copy()
    df_tbl = df_all[df_all["_summary_kind"] == "表"].copy()
    df_figtbl = df_all[df_all["_summary_kind"] == "図表"].copy()

    return {
        "図サマリー": sort_summary_by_pdf_page(df_fig),
        "表サマリー": sort_summary_by_pdf_page(df_tbl),
        "図表サマリー": sort_summary_by_pdf_page(df_figtbl),
    }


# ============================================================
# 通常サマリーxlsx bytes生成
# ============================================================
def build_summary_xlsx_bytes(
    *,
    df_referenced_captions_x: pd.DataFrame,
    df_missing_caption_refs_x: pd.DataFrame,
    df_orphan_refs_x: pd.DataFrame,
) -> bytes:
    df_summary_all_x = build_summary_all_df(
        df_referenced_captions_x=df_referenced_captions_x,
        df_missing_caption_refs_x=df_missing_caption_refs_x,
    )

    frames = split_summary_frames(df_summary_all_x)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frames["図サマリー"].to_excel(writer, sheet_name="図サマリー", index=False)
        frames["表サマリー"].to_excel(writer, sheet_name="表サマリー", index=False)
        frames["図表サマリー"].to_excel(writer, sheet_name="図表サマリー", index=False)
        df_orphan_refs_x.to_excel(writer, sheet_name="見出しなし参照", index=False)

    return output.getvalue()