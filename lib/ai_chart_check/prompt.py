# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_chart_check/prompt.py
# ============================================================
# AI図表チェック：プロンプト生成
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import json
from typing import Any, Dict, List


# ============================================================
# input payload
# ============================================================
def build_ai_input_payload(
    *,
    source_file: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    # ------------------------------------------------------------
    # AIへ渡すJSON payload
    # ------------------------------------------------------------
    return {
        "schema": "figure_table_reference_check_input_v1",
        "source_file": source_file,
        "items": items,
    }


# ============================================================
# classify payload
# ============================================================
def build_classify_payload(
    *,
    source_file: str,
    chunk_index: int,
    chunk_total: int,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    # ------------------------------------------------------------
    # 分類AIへ渡すpayload
    # ------------------------------------------------------------
    return {
        "schema": "figure_table_classify_input_v1",
        "source_file": source_file,
        "chunk_index": chunk_index,
        "chunk_total": chunk_total,
        "items": items,
    }


# ============================================================
# check payload
# ============================================================
def build_check_payload(
    *,
    source_file: str,
    titles: List[Dict[str, Any]],
    references: List[Dict[str, Any]],
    unclassified_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    # ------------------------------------------------------------
    # 照合AIへ渡すpayload
    # ------------------------------------------------------------
    return {
        "schema": "figure_table_check_input_v1",
        "source_file": source_file,
        "titles": titles,
        "references": references,
        "unclassified_items": unclassified_items,
    }


# ============================================================
# system
# ============================================================
def build_system_text() -> str:
    # ------------------------------------------------------------
    # AI system text
    # ------------------------------------------------------------
    return (
        "あなたは大学・研究機関・官公庁向け文書の校閲者です。"
        "日本語の報告書における図表タイトルと本文参照の対応関係を厳密に確認してください。"
        "推測で断定せず、不明な場合は必ず『要確認』としてください。"
        "出力は必ずvalid JSONのみとし、Markdownや説明文をJSONの外に出してはいけません。"
        "JSON内の数値フィールドは必ず数字で出力してください。"
    )


# ============================================================
# classify prompt
# ============================================================
def build_classify_prompt_text(payload: Dict[str, Any]) -> str:
    # ------------------------------------------------------------
    # 図表タイトル / 本文参照 / 未分類を分類するprompt
    # ------------------------------------------------------------
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    return f"""
以下のJSONは、PDFから抽出した「図」または「表」を含む文の一覧です。

この段階では、照合判定は行わず、各文を次の3種類に分類してください。

1. 図表タイトル
2. 本文中の図表参照
3. 未分類

# 重要ルール

- この段階では「一致」「参照なし」「タイトルなし」などの最終判定はしないでください。
- items に存在しない文を創作してはいけません。
- source_item_id は必ず入力JSONの id を使ってください。
- figure_key は「図3-1」「表2.1」「図表4-2」など、読み取れる範囲で正規化してください。
- 番号が読めない場合は figure_key を空文字にしてください。
- JSON以外の文章は絶対に出力しないでください。
- Markdownの ```json は使わないでください。
- すべての文字列は1行にしてください。
- 文字列の途中に改行を入れないでください。
- reason は短くしてください。
- 出力は valid JSON として json.loads() で読み込める形式にしてください。

# 数値ルール

- summary.num_titles は必ず整数で出力してください。
- summary.num_references は必ず整数で出力してください。
- summary.num_unclassified は必ず整数で出力してください。
- twenty、nineteen、eleven などの英単語は禁止です。
- 二十、十九、十一 などの漢数字は禁止です。
- "20" のような文字列は禁止です。
- 必ず 20, 19, 11 のようなJSON数値で出力してください。

# 出力JSONスキーマ

{{
  "schema": "figure_table_classify_output_v1",
  "summary": {{
    "num_titles": 0,
    "num_references": 0,
    "num_unclassified": 0,
    "comment": ""
  }},
  "titles": [
    {{
      "figure_key": "図3-1",
      "kind": "図",
      "title_text": "",
      "source_item_id": "",
      "pdf_page": 1,
      "page_label": null,
      "confidence": "high"
    }}
  ],
  "references": [
    {{
      "figure_key": "図3-1",
      "kind": "図",
      "reference_text": "",
      "source_item_id": "",
      "pdf_page": 1,
      "page_label": null,
      "confidence": "high"
    }}
  ],
  "unclassified_items": [
    {{
      "source_item_id": "",
      "pdf_page": 1,
      "page_label": null,
      "text": "",
      "reason": ""
    }}
  ]
}}

# confidence の選択肢

- high
- medium
- low

# 入力JSON

{payload_json}
""".strip()


# ============================================================
# check prompt
# ============================================================
def build_check_prompt_text(payload: Dict[str, Any]) -> str:
    # ------------------------------------------------------------
    # 分類済みタイトル / 参照を照合するprompt
    # ------------------------------------------------------------
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    return f"""
以下のJSONは、前段のAI分類で得られた図表タイトル候補と本文参照候補です。

この段階では、分類済み結果をもとに、図表タイトルと本文参照の対応関係を照合してください。

# 目的

1. 図表タイトルごとに、対応する本文参照があるか確認する
2. 本文参照ごとに、対応する図表タイトルがあるか確認する
3. 図表キー単位で「一致」「参照なし」「タイトルなし」「不一致」「要確認」を判定する

# 注意

- 原則として figure_key が同じタイトルと参照を対応させてください。
- figure_key が空欄のものは要確認にしてください。
- タイトルだけあり、参照がない場合は「参照なし」にしてください。
- 参照だけあり、タイトルがない場合は「タイトルなし」にしてください。
- 同じfigure_keyでも文意が明らかに異なる場合は「要確認」または「不一致」にしてください。
- JSON以外の文章は絶対に出力しないでください。
- Markdownの ```json は使わないでください。
- すべての文字列は1行にしてください。
- 文字列の途中に改行を入れないでください。
- overall_comment や reason は短くしてください。
- 出力は valid JSON として json.loads() で読み込める形式にしてください。

# 数値ルール

- summary.num_titles は必ず整数で出力してください。
- summary.num_references は必ず整数で出力してください。
- summary.num_matches は必ず整数で出力してください。
- summary.num_warnings は必ず整数で出力してください。
- twenty、nineteen、eleven などの英単語は禁止です。
- 二十、十九、十一 などの漢数字は禁止です。
- "20" のような文字列は禁止です。
- 必ず 20, 19, 11 のようなJSON数値で出力してください。

# 出力JSONスキーマ

{{
  "schema": "figure_table_reference_check_output_v1",
  "summary": {{
    "num_titles": 0,
    "num_references": 0,
    "num_matches": 0,
    "num_warnings": 0,
    "overall_comment": ""
  }},
  "checks": [
    {{
      "figure_key": "図3-1",
      "kind": "図",
      "title_text": "",
      "title_item_id": "",
      "title_pdf_page": 1,
      "title_page_label": null,
      "reference_texts": [
        {{
          "reference_text": "",
          "reference_item_id": "",
          "reference_pdf_page": 1,
          "reference_page_label": null
        }}
      ],
      "judgment": "一致",
      "severity": "OK",
      "reason": ""
    }}
  ]
}}

# judgment の選択肢

- 一致
- 参照なし
- タイトルなし
- 不一致
- 要確認

# severity の選択肢

- OK
- WARN
- NG
- CHECK

# 入力JSON

{payload_json}
""".strip()


# ============================================================
# legacy prompt
# ============================================================
def build_prompt_text(payload: Dict[str, Any]) -> str:
    # ------------------------------------------------------------
    # 互換用：旧関数名
    # ------------------------------------------------------------
    return build_check_prompt_text(payload)