# -*- coding: utf-8 -*-
# lib/translate/prompts.py
# ============================================================
# 翻訳プロンプト
# ============================================================

from __future__ import annotations


# ============================================================
# 翻訳方向
# ============================================================
TRANSLATE_TO_JA = "日本語に翻訳"
TRANSLATE_TO_EN = "英語に翻訳"

TRANSLATION_DIRECTIONS = [
    TRANSLATE_TO_JA,
    TRANSLATE_TO_EN,
]

DEFAULT_TRANSLATION_DIRECTION = TRANSLATE_TO_JA


# ============================================================
# system prompt 生成
# ============================================================
def build_translation_system_prompt(
    *,
    direction: str,
    extra: str = "",
) -> str:

    # ------------------------------------------------------------
    # 翻訳先言語
    # ------------------------------------------------------------
    if direction == TRANSLATE_TO_EN:
        target_lang = "English"
        source_note = "Japanese to English"
    else:
        target_lang = "Japanese"
        source_note = "English to Japanese"

    # ------------------------------------------------------------
    # 追加指示
    # ------------------------------------------------------------
    extra_block = ""
    if str(extra or "").strip():
        extra_block = f"""

Additional user instruction:
{str(extra or "").strip()}
"""

    # ------------------------------------------------------------
    # system prompt
    # ------------------------------------------------------------
    return f"""
You are a careful professional translator.

Task:
- Translate the input text into {target_lang}.
- Translation direction: {source_note}.

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

    # ------------------------------------------------------------
    # 翻訳先言語
    # ------------------------------------------------------------
    if direction == TRANSLATE_TO_EN:
        target_lang = "英語"
    else:
        target_lang = "日本語"

    # ------------------------------------------------------------
    # 追加指示
    # ------------------------------------------------------------
    extra_block = ""
    if str(extra or "").strip():
        extra_block = f"""

【追加指示】
{str(extra or "").strip()}
"""

    # ------------------------------------------------------------
    # user prompt
    # ------------------------------------------------------------
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