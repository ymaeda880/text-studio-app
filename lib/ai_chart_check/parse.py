# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_chart_check/parse.py
# ============================================================
# AI図表チェック：AI応答解析・出力変換
#
# 機能：
# - AI応答からJSONを取り出す
# - list[dict] を DataFrame に変換する
# - checks を表示用 DataFrame に変換する
# - XLSX bytes を生成する
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
# code fence remove
# ============================================================
def strip_code_fence(text: str) -> str:
    # ------------------------------------------------------------
    # ```json ... ``` を除去
    # ------------------------------------------------------------
    s = str(text or "").strip()

    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)

    return s.strip()


# ============================================================
# json extraction
# ============================================================
def extract_json_object(text: str) -> Dict[str, Any]:
    # ------------------------------------------------------------
    # AI応答からJSON objectを取り出す（壊れたJSONも救う）
    # ------------------------------------------------------------
    s = strip_code_fence(text)

    # ------------------------------------------------------------
    # ① まずそのまま
    # ------------------------------------------------------------
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # ------------------------------------------------------------
    # ② 最初と最後の {} を切り出し
    # ------------------------------------------------------------
    start = s.find("{")
    end = s.rfind("}")

    if start >= 0 and end > start:
        candidate = s[start : end + 1]

        # --------------------------------------------------------
        # ★ ここが今回の修正ポイント
        # JSON崩れを補正
        # --------------------------------------------------------

        # 1. 改行を除去
        candidate = candidate.replace("\n", " ")

        # 2. 連続スペース整理
        candidate = re.sub(r"\s+", " ", candidate)

        # 3. 不正な末尾カンマ削除
        candidate = re.sub(r",\s*}", "}", candidate)
        candidate = re.sub(r",\s*]", "]", candidate)

        # 4. 文字列内の改行っぽいものを除去
        candidate = candidate.replace("\r", "")

        # --------------------------------------------------------
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception as e:
            # ★ デバッグ用：壊れている箇所を表示
            error_pos = getattr(e, "pos", None)

            if error_pos is not None:
                start_dbg = max(0, error_pos - 50)
                end_dbg = min(len(candidate), error_pos + 50)

                print("=== JSON ERROR CONTEXT ===")
                print(candidate[start_dbg:end_dbg])
                print("==========================")

    raise RuntimeError("AI応答をJSONとして読み取れませんでした。")


# ============================================================
# dataframe helpers
# ============================================================
def df_from_list(obj: Any) -> pd.DataFrame:
    # ------------------------------------------------------------
    # list[dict] を DataFrame 化
    # ------------------------------------------------------------
    if isinstance(obj, list):
        rows = [x for x in obj if isinstance(x, dict)]
        return pd.DataFrame(rows)

    return pd.DataFrame()


# ============================================================
# checks dataframe
# ============================================================
def checks_to_df(checks: Any) -> pd.DataFrame:
    # ------------------------------------------------------------
    # checks を表示用DataFrameに変換
    # ------------------------------------------------------------
    if not isinstance(checks, list):
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []

    for c in checks:
        if not isinstance(c, dict):
            continue

        refs = c.get("reference_texts")
        ref_text_joined = ""
        ref_page_joined = ""

        if isinstance(refs, list):
            ref_texts: List[str] = []
            ref_pages: List[str] = []

            for r in refs:
                if not isinstance(r, dict):
                    continue

                rt = str(r.get("reference_text") or "").strip()
                rp = r.get("reference_pdf_page")

                if rt:
                    ref_texts.append(rt)

                if rp is not None:
                    ref_pages.append(str(rp))

            ref_text_joined = " / ".join(ref_texts)
            ref_page_joined = ", ".join(ref_pages)

        rows.append(
            {
                "図表キー": c.get("figure_key", ""),
                "種別": c.get("kind", ""),
                "判定": c.get("judgment", ""),
                "重要度": c.get("severity", ""),
                "タイトル": c.get("title_text", ""),
                "タイトルpdf頁": c.get("title_pdf_page", ""),
                "タイトル頁ラベル": c.get("title_page_label", ""),
                "参照pdf頁": ref_page_joined,
                "参照テキスト": ref_text_joined,
                "理由": c.get("reason", ""),
                "title_item_id": c.get("title_item_id", ""),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# xlsx
# ============================================================
def make_xlsx_bytes(
    *,
    df_input_items: pd.DataFrame,
    df_checks: pd.DataFrame,
    df_titles: pd.DataFrame,
    df_refs: pd.DataFrame,
    df_unclassified: pd.DataFrame,
    summary_obj: Dict[str, Any],
) -> bytes:
    # ------------------------------------------------------------
    # XLSX bytes 作成
    # ------------------------------------------------------------
    output = BytesIO()

    df_summary = pd.DataFrame(
        [
            {
                "num_titles": summary_obj.get("num_titles", ""),
                "num_references": summary_obj.get("num_references", ""),
                "num_matches": summary_obj.get("num_matches", ""),
                "num_warnings": summary_obj.get("num_warnings", ""),
                "overall_comment": summary_obj.get("overall_comment", ""),
            }
        ]
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="サマリー", index=False)
        df_checks.to_excel(writer, sheet_name="AI照合結果", index=False)
        df_titles.to_excel(writer, sheet_name="AI分類_タイトル", index=False)
        df_refs.to_excel(writer, sheet_name="AI分類_参照", index=False)
        df_unclassified.to_excel(writer, sheet_name="AI分類_未分類", index=False)
        df_input_items.to_excel(writer, sheet_name="AI入力_items", index=False)

    return output.getvalue()