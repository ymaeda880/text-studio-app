# -*- coding: utf-8 -*-
# lib/translate/prompts.py
# ============================================================
# 翻訳プロンプト
#
# 機能：
# - 翻訳先言語の選択肢を定義する
# - 固定言語と任意入力言語の表示名を解決する
# - system prompt / user prompt を生成する
#
# 方針：
# - 翻訳方向は日本語の表示名で保持する
# - プロンプト生成時に翻訳先言語名へ変換する
# - 「その他の言語」はpage側で具体的な言語名へ解決してから渡す
# ============================================================

from __future__ import annotations


# ============================================================
# 翻訳方向
# ============================================================
TRANSLATE_TO_JA = "日本語に翻訳"
TRANSLATE_TO_EN = "英語に翻訳"
TRANSLATE_TO_FR = "フランス語に翻訳"
TRANSLATE_TO_DE = "ドイツ語に翻訳"
TRANSLATE_TO_ES = "スペイン語に翻訳"
TRANSLATE_TO_OTHER = "その他の言語"

TRANSLATION_DIRECTIONS = [
    TRANSLATE_TO_JA,
    TRANSLATE_TO_EN,
    TRANSLATE_TO_FR,
    TRANSLATE_TO_DE,
    TRANSLATE_TO_ES,
    TRANSLATE_TO_OTHER,
]

DEFAULT_TRANSLATION_DIRECTION = TRANSLATE_TO_JA


# ============================================================
# 翻訳先言語定義
# ============================================================
_TRANSLATION_TARGETS = {
    TRANSLATE_TO_JA: {
        "system_name": "Japanese",
        "user_name": "日本語",
    },
    TRANSLATE_TO_EN: {
        "system_name": "English",
        "user_name": "英語",
    },
    TRANSLATE_TO_FR: {
        "system_name": "French",
        "user_name": "フランス語",
    },
    TRANSLATE_TO_DE: {
        "system_name": "German",
        "user_name": "ドイツ語",
    },
    TRANSLATE_TO_ES: {
        "system_name": "Spanish",
        "user_name": "スペイン語",
    },
}


# ============================================================
# helper：翻訳先言語を解決
# ============================================================
def _resolve_target_language(
    direction: str,
) -> tuple[str, str]:
    """
    翻訳方向から，system prompt用とuser prompt用の
    翻訳先言語名を返す．

    固定選択肢に存在しない値は，
    「○○語に翻訳」の形式から言語名を取り出して使用する．
    """

    normalized_direction = str(direction or "").strip()

    # --------------------------------------------------------
    # 固定言語
    # --------------------------------------------------------
    target = _TRANSLATION_TARGETS.get(normalized_direction)

    if target is not None:
        return (
            str(target["system_name"]),
            str(target["user_name"]),
        )

    # --------------------------------------------------------
    # その他の言語
    # 例：
    # - イタリア語に翻訳
    # - 中国語に翻訳
    # --------------------------------------------------------
    target_language = normalized_direction

    if target_language.endswith("に翻訳"):
        target_language = target_language[:-4].strip()

    if not target_language:
        target_language = "指定された言語"

    return (
        target_language,
        target_language,
    )


# ============================================================
# system prompt 生成
# ============================================================
def build_translation_system_prompt(
    *,
    direction: str,
    extra: str = "",
) -> str:

    # --------------------------------------------------------
    # 翻訳先言語
    # --------------------------------------------------------
    target_lang, _ = _resolve_target_language(direction)

    # --------------------------------------------------------
    # 追加指示
    # --------------------------------------------------------
    extra_block = ""

    if str(extra or "").strip():
        extra_block = f"""

Additional user instruction:
{str(extra or "").strip()}
"""

    # --------------------------------------------------------
    # system prompt
    # --------------------------------------------------------
    return f"""
You are a careful professional translator.

Task:

- Translate the input text into {target_lang}.

Rules:

- Translate literally and faithfully.
- Do not summarize.
- Do not merge sentences.
- Do not omit sentences.
- Do not add explanations.
- Preserve the original order.
- Keep numbers, dates, names, headings, and technical terms as faithfully as possible.
- If the source contains a sentence number such as [0001], keep that number.
- Output only the translated text.
- Do not output commentary before or after the translation.
{extra_block}
""".strip()


# ============================================================
# user prompt 生成
# ============================================================
def build_translation_user_prompt(
    *,
    numbered_preview: str,
    direction: str,
    extra: str = "",
) -> str:

    # --------------------------------------------------------
    # 翻訳先言語
    # --------------------------------------------------------
    _, target_lang = _resolve_target_language(direction)

    # --------------------------------------------------------
    # 追加指示
    # --------------------------------------------------------
    extra_block = ""

    if str(extra or "").strip():
        extra_block = f"""

【追加指示】
{str(extra or "").strip()}
"""

    # --------------------------------------------------------
    # user prompt
    # --------------------------------------------------------
    return f"""
次の文章を{target_lang}に翻訳してください．

【翻訳ルール】

- 直訳してください．
- 要約しないでください．
- 複数の文をまとめないでください．
- 文を省略しないでください．
- 原文の順序を維持してください．
- [0001] のような番号がある場合は，番号を維持してください．
- 翻訳結果だけを出力してください．
{extra_block}

【原文】
{numbered_preview}
""".strip()