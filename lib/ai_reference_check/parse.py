# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/parse.py
# ============================================================
# AI参照チェック：AI応答parse / xlsx生成
#
# 機能：
# - AI応答からJSON objectを抽出する
# - checksをDataFrame化する
# - 元データとAI判定を結合する
# - 表示用の列順を整える
# - xlsx bytesを生成する
# - AI判定セルを共通ステータス色で表示する
# - 判定結果シートの下部に列説明を追加する
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

from common_lib.excel.status_formats import (
    STATUS_BLUE_BG,
    create_status_formats,
)


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

    m = re.search(
        r"\{.*\}",
        s,
        flags=re.DOTALL,
    )

    if not m:
        raise ValueError(
            "JSON objectが見つかりません。"
        )

    obj = json.loads(
        m.group(0)
    )

    if not isinstance(obj, dict):
        raise ValueError(
            "JSON objectではありません。"
        )

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
        return pd.DataFrame(
            columns=columns
        )

    df = pd.DataFrame(
        checks
    )

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    return df[
        columns
    ]

# ============================================================
# 結果表示用の列を整える
#
# 方針：
# - 内部処理では row_id / _source_line_no / chunk_index を保持する
# - 利用者向け表示では row_id を「No」に変更する
# - _source_line_no / chunk_index は表示しない
# - No → AI判定 → AI確信度 の順にする
# ============================================================
def reorder_result_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    df2 = df.copy()

    # --------------------------------------------------------
    # 利用者向けには不要な内部管理列を削除
    # --------------------------------------------------------
    drop_columns = [
        "_source_line_no",
        "chunk_index",
    ]

    df2 = df2.drop(
        columns=[
            col
            for col in drop_columns
            if col in df2.columns
        ]
    )

    # --------------------------------------------------------
    # row_id → No
    # --------------------------------------------------------
    if (
        "row_id" in df2.columns
        and "No" not in df2.columns
    ):
        df2 = df2.rename(
            columns={
                "row_id": "No",
            }
        )

    # --------------------------------------------------------
    # 先頭列
    # --------------------------------------------------------
    priority_columns = [
        "No",
        "AI判定",
        "AI確信度",
    ]

    existing_priority_columns = [
        col
        for col in priority_columns
        if col in df2.columns
    ]

    # --------------------------------------------------------
    # その他の列
    # --------------------------------------------------------
    other_columns = [
        col
        for col in df2.columns
        if col not in priority_columns
    ]

    return df2[
        existing_priority_columns
        + other_columns
    ].copy()

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

    # --------------------------------------------------------
    # AI判定がない場合
    # --------------------------------------------------------
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

        return reorder_result_columns(
            df_left
        )

    # --------------------------------------------------------
    # AI判定がある場合
    # --------------------------------------------------------
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

    df_result = df_left.merge(
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

    return reorder_result_columns(
        df_result
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

    # --------------------------------------------------------
    # 判定結果
    # --------------------------------------------------------
    df_result_x = reorder_result_columns(
        df_result
    )

    # --------------------------------------------------------
    # 要確認
    # --------------------------------------------------------
    df_review = pd.DataFrame()

    if (
        not df_result_x.empty
        and "AI判定" in df_result_x.columns
    ):
        df_review = df_result_x[
            df_result_x["AI判定"].isin(
                [
                    "CHECK",
                    "NG",
                ]
            )
        ].copy()

    # --------------------------------------------------------
    # usage
    # --------------------------------------------------------
    df_usage = pd.DataFrame(
        usage_rows
    )

    # ========================================================
    # Excel生成
    # ========================================================
    with pd.ExcelWriter(
        output,
        engine="xlsxwriter",
    ) as writer:

        # ----------------------------------------------------
        # 各シート出力
        # ----------------------------------------------------
        df_result_x.to_excel(
            writer,
            sheet_name="判定結果",
            index=False,
        )

        df_review.to_excel(
            writer,
            sheet_name="要確認",
            index=False,
        )

        df_input.to_excel(
            writer,
            sheet_name="入力",
            index=False,
        )

        df_checks.to_excel(
            writer,
            sheet_name="AI応答checks",
            index=False,
        )

        df_usage.to_excel(
            writer,
            sheet_name="usage",
            index=False,
        )

        # ====================================================
        # 判定結果シートの書式
        # ====================================================
        wb = writer.book
        ws = writer.sheets["判定結果"]

        # ----------------------------------------------------
        # common_lib 共通ステータス書式
        # ----------------------------------------------------
        status_formats = create_status_formats(
            wb
        )

        judgment_ok_fmt = (
            status_formats["green"]
        )

        judgment_ng_fmt = (
            status_formats["red"]
        )

        judgment_check_fmt = (
            status_formats["yellow"]
        )

        judgment_skip_fmt = (
            status_formats["blue"]
        )

        # ----------------------------------------------------
        # ヘッダー
        # ----------------------------------------------------
        header_fmt = wb.add_format(
            {
                "bold": True,
            }
        )

        # ----------------------------------------------------
        # 通常文字列
        # ----------------------------------------------------
        text_fmt = wb.add_format(
            {
                "num_format": "@",
                "valign": "top",
            }
        )

        # ----------------------------------------------------
        # 折り返し
        # ----------------------------------------------------
        wrap_fmt = wb.add_format(
            {
                "text_wrap": True,
                "valign": "top",
            }
        )

        # ----------------------------------------------------
        # 説明見出し
        # ----------------------------------------------------
        explanation_title_fmt = wb.add_format(
            {
                "bold": True,
                "bg_color": STATUS_BLUE_BG,
                "valign": "top",
            }
        )

        # ----------------------------------------------------
        # 説明本文
        # ----------------------------------------------------
        explanation_fmt = wb.add_format(
            {
                "text_wrap": True,
                "valign": "top",
            }
        )

        # ====================================================
        # 列情報
        # ====================================================
        cols = list(
            df_result_x.columns
        )

        col_idx = {
            name: i
            for i, name in enumerate(cols)
        }

        # ====================================================
        # 列幅
        # ====================================================
        widths = {
            "row_id": 10,
            "AI判定": 12,
            "AI確信度": 12,
            "sheet": 18,
            "図表キー": 16,
            "結果": 16,
            "図表タイトル": 34,
            "頁ラベル": 14,
            "pdf頁": 10,
            "参照頁ラベル": 18,
            "参照pdf頁": 14,
            "前テキスト": 44,
            "参照テキスト": 44,
            "後テキスト": 44,
            "AI理由": 44,
            "AI修正候補": 18,
            "AI補足": 36,
            "chunk_index": 12,
        }

        wrap_columns = {
            "図表タイトル",
            "前テキスト",
            "参照テキスト",
            "後テキスト",
            "AI理由",
            "AI補足",
        }

        for name, width in widths.items():
            if name not in col_idx:
                continue

            fmt = (
                wrap_fmt
                if name in wrap_columns
                else text_fmt
            )

            ws.set_column(
                col_idx[name],
                col_idx[name],
                width,
                fmt,
            )

        # ====================================================
        # ヘッダー
        # ====================================================
        for j, name in enumerate(cols):
            ws.write(
                0,
                j,
                name,
                header_fmt,
            )

        # ====================================================
        # AI判定セルの色
        #
        # OK    ：緑
        # NG    ：赤
        # CHECK ：黄色
        # SKIP  ：青
        # ====================================================
        if (
            "AI判定" in col_idx
            and len(df_result_x) > 0
        ):
            judgment_col = col_idx[
                "AI判定"
            ]

            for row_no, value in enumerate(
                df_result_x["AI判定"],
                start=1,
            ):
                judgment = (
                    ""
                    if pd.isna(value)
                    else str(value).strip().upper()
                )

                if judgment == "OK":
                    fmt = judgment_ok_fmt

                elif judgment == "NG":
                    fmt = judgment_ng_fmt

                elif judgment == "CHECK":
                    fmt = judgment_check_fmt

                elif judgment == "SKIP":
                    fmt = judgment_skip_fmt

                else:
                    fmt = text_fmt

                ws.write(
                    row_no,
                    judgment_col,
                    judgment,
                    fmt,
                )

        # ====================================================
        # 結果表の下に説明を追加
        #
        # 0行目                 ：ヘッダー
        # 1～len(df_result_x)   ：データ
        # +1行                  ：空行
        # +2行目                ：説明見出し
        # ====================================================
        explanation_start_row = (
            len(df_result_x) + 2
        )

        explanation_last_col = max(
            len(cols) - 1,
            0,
        )

        # ----------------------------------------------------
        # 説明見出し
        # ----------------------------------------------------
        ws.merge_range(
            explanation_start_row,
            0,
            explanation_start_row,
            explanation_last_col,
            "【結果の列について】",
            explanation_title_fmt,
        )

        # ----------------------------------------------------
        # 1. AI判定
        # ----------------------------------------------------
        ws.merge_range(
            explanation_start_row + 1,
            0,
            explanation_start_row + 1,
            explanation_last_col,
            (
                "1.「AI判定」は，AIによる図表参照の"
                "意味的な判定結果です．"
                "「OK」は図表タイトルと本文中の参照内容が"
                "自然に対応しているもの，"
                "「CHECK」は判断材料が不足しているなど"
                "人による確認が必要なもの，"
                "「NG」は本文中の参照内容と図表タイトルが"
                "対応していない可能性が高いもの，"
                "「SKIP」は未引用または対応図表なしなど"
                "AIによる意味判定の対象外となったものです．"
            ),
            explanation_fmt,
        )

        # ----------------------------------------------------
        # 2. AI確信度
        # ----------------------------------------------------
        ws.merge_range(
            explanation_start_row + 2,
            0,
            explanation_start_row + 2,
            explanation_last_col,
            (
                "2.「AI確信度」は，"
                "AIが判定結果に対して示した確信度です．"
                "0から1までの値で，"
                "1に近いほど判定に対する確信度が"
                "高いことを示します．"
            ),
            explanation_fmt,
        )

        # ----------------------------------------------------
        # 3. 頁ラベル
        # ----------------------------------------------------
        ws.merge_range(
            explanation_start_row + 3,
            0,
            explanation_start_row + 3,
            explanation_last_col,
            (
                "3.「頁ラベル」は，"
                "図表見出しが記載されている"
                "文書上のページ番号です．"
                "「1-1」「2-1」「資料1」などの"
                "形式の場合もあります．"
                "表紙や目次などがあるため，"
                "PDFファイル上のページ番号とは"
                "一致しない場合があります．"
            ),
            explanation_fmt,
        )

        # ----------------------------------------------------
        # 4. pdf頁
        # ----------------------------------------------------
        ws.merge_range(
            explanation_start_row + 4,
            0,
            explanation_start_row + 4,
            explanation_last_col,
            (
                "4.「pdf頁」は，"
                "図表見出しがPDFファイルそのものの"
                "何ページ目にあるかを示します．"
                "文書に記載された「頁ラベル」と"
                "「pdf頁」は一致しない場合があります．"
            ),
            explanation_fmt,
        )

        # ----------------------------------------------------
        # 5. 参照頁ラベル
        # ----------------------------------------------------
        ws.merge_range(
            explanation_start_row + 5,
            0,
            explanation_start_row + 5,
            explanation_last_col,
            (
                "5.「参照頁ラベル」は，"
                "その図表を本文中で参照している箇所の"
                "文書上のページ番号です．"
                "複数のページで参照されている場合は，"
                "複数のページ番号が記録されます．"
            ),
            explanation_fmt,
        )

        # ----------------------------------------------------
        # 6. 参照pdf頁
        # ----------------------------------------------------
        ws.merge_range(
            explanation_start_row + 6,
            0,
            explanation_start_row + 6,
            explanation_last_col,
            (
                "6.「参照pdf頁」は，"
                "その図表を本文中で参照している箇所が"
                "PDFファイルそのものの何ページ目に"
                "あるかを示します．"
                "複数のページで参照されている場合は，"
                "複数のページ番号が記録されます．"
            ),
            explanation_fmt,
        )

        # ====================================================
        # 説明行の高さ
        #
        # 09_図表チェック.py と同様に，
        # 不必要に高くならないよう調整する
        # ====================================================
        ws.set_row(
            explanation_start_row + 1,
            32,
        )

        ws.set_row(
            explanation_start_row + 2,
            26,
        )

        ws.set_row(
            explanation_start_row + 3,
            32,
        )

        ws.set_row(
            explanation_start_row + 4,
            28,
        )

        ws.set_row(
            explanation_start_row + 5,
            28,
        )

        ws.set_row(
            explanation_start_row + 6,
            28,
        )

        # ====================================================
        # ヘッダー固定
        # ====================================================
        ws.freeze_panes(
            1,
            0,
        )

    return output.getvalue()