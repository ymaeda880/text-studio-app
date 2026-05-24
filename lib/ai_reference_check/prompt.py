# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/prompt.py
# ============================================================
# AI参照チェック：プロンプト生成
#
# 機能：
# - 09_図表チェック.py のAI用サマリーJSONLを前提にする
# - AIには抽出ではなく、意味的な参照妥当性だけを判定させる
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import json
from typing import Any, Dict, List

from lib.ai_reference_check.normalize import normalize_ai_text


# ============================================================
# system prompt
# ============================================================
def build_reference_check_system_text() -> str:
    return """
あなたは日本語の環境影響評価書・報告書における図表参照の整合性を確認する専門家です。

あなたの役割は、本文中の図表参照が、指定された図表タイトルと意味的に対応しているかを判断することです。

重要な方針：
- 図表番号を新たに抽出しない。
- 入力済みの「図表キー」「図表タイトル」「前テキスト」「参照テキスト」「後テキスト」だけを根拠に判断する。
- 単なる番号の存在確認ではなく、本文の説明内容と図表タイトルの意味的対応を見る。
- 判断できない場合は無理にOKにせず、CHECKにする。
- 出力は必ずJSONのみとする。
""".strip()


# ============================================================
# AI送信用record整形
# ============================================================
def normalize_record_for_prompt(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "row_id": row.get("row_id"),
        "sheet": str(row.get("sheet", "") or ""),
        "figure_key": str(row.get("図表キー", "") or ""),
        "existing_result": str(row.get("結果", "") or ""),
        "figure_title": normalize_ai_text(str(row.get("図表タイトル", "") or "")),
        "page_label": str(row.get("頁", "") or ""),
        "pdf_page": str(row.get("pdf頁", "") or ""),
        "reference_page_label": str(row.get("参照頁ラベル", "") or ""),
        "reference_pdf_page": str(row.get("参照pdf頁", "") or ""),
        "previous_text": normalize_ai_text(str(row.get("前テキスト", "") or "")),
        "reference_text": normalize_ai_text(str(row.get("参照テキスト", "") or "")),
        "next_text": normalize_ai_text(str(row.get("後テキスト", "") or "")),
    }


# ============================================================
# payload生成
# ============================================================
def build_reference_check_payload(
    *,
    source_file: str,
    chunk_index: int,
    chunk_total: int,
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "schema": "ai_reference_check_input_v1",
        "source_file": str(source_file or ""),
        "chunk_index": int(chunk_index),
        "chunk_total": int(chunk_total),
        "task": "図表タイトルと本文参照文脈の意味的対応を判定する",
        "judgment_labels": {
            "OK": "図表タイトルと本文参照文脈が自然に対応している",
            "CHECK": "判断材料が不足、または少し怪しいため人間確認が必要",
            "NG": "本文参照文脈が図表タイトルと明らかに対応していない可能性が高い",
            "SKIP": "未引用など、意味判定の対象外",
        },
        "records": [
            normalize_record_for_prompt(row)
            for row in records
        ],
    }


# ============================================================
# prompt text生成
# ============================================================
def build_reference_check_prompt_text(payload: Dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    return f"""
以下のJSONには、図表参照チェック対象のレコードが入っています。

各recordについて、figure_key の図表が、reference_text および previous_text / next_text の文脈で正しく参照されているかを判断してください。

判断基準：
- 図表タイトルと参照文脈が意味的に対応していれば OK。
- 文脈が短すぎる、抽出ノイズが混ざっている、判断に迷う場合は CHECK。
- 図表タイトルと明らかに違う内容を本文が説明している場合は NG。
- existing_result が「未引用」のように参照文が空の場合は SKIP。

必ず次のJSON形式だけで返してください。説明文やMarkdownは不要です。

{{
  "schema": "ai_reference_check_output_v1",
  "chunk_index": <number>,
  "chunk_total": <number>,
  "checks": [
    {{
      "row_id": <number>,
      "figure_key": "<string>",
      "judgment": "OK | CHECK | NG | SKIP",
      "confidence": <0.0から1.0の数値>,
      "reason": "<判断理由>",
      "suspected_correct_key": "<別の図表キーが疑われる場合のみ。なければ空文字>",
      "note": "<抽出ノイズなど補足。なければ空文字>"
    }}
  ]
}}

入力JSON：
{payload_json}
""".strip()