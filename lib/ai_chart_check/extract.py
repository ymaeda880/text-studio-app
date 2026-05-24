# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_chart_check/extract.py
# ============================================================
# AI図表チェック：抽出ロジック
#
# 機能：
# - PDFページ別テキストから文を抽出する
# - 「図」「表」を含む文だけを抽出する
# - AIへ渡す items 形式に整形する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import re
from typing import Any, Dict, List, Optional


# ============================================================
# text normalize
# ============================================================
def normalize_text_for_sentence_split(text: str) -> str:
    # ------------------------------------------------------------
    # PDF抽出テキストの軽い正規化
    # ------------------------------------------------------------
    s = str(text or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t\u3000]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ============================================================
# sentence split
# ============================================================
def split_sentences_keep_japanese(text: str) -> List[str]:
    # ------------------------------------------------------------
    # 日本語文を簡易分割
    # ------------------------------------------------------------
    src = normalize_text_for_sentence_split(text)

    if not src:
        return []

    rough_parts: List[str] = []

    for line in src.split("\n"):
        line = line.strip()

        if not line:
            continue

        parts = re.split(r"(?<=[。！？!?])", line)

        for p in parts:
            p = p.strip()

            if p:
                rough_parts.append(p)

    return rough_parts


# ============================================================
# target detection
# ============================================================
def contains_figure_or_table(text: str) -> bool:
    # ------------------------------------------------------------
    # 「図」「表」を含む文を対象にする
    # ------------------------------------------------------------
    s = str(text or "")
    return ("図" in s) or ("表" in s)


# ============================================================
# clip
# ============================================================
def safe_text_clip(text: str, max_chars: int) -> str:
    # ------------------------------------------------------------
    # AI入力肥大化防止
    # ------------------------------------------------------------
    s = str(text or "").strip()

    if len(s) <= max_chars:
        return s

    return s[:max_chars] + "…"


# ============================================================
# main extractor
# ============================================================
def extract_figure_table_sentences(
    *,
    pages_text: List[str],
    page_labels: List[Optional[str]],
    include_context: bool,
    max_sentence_chars: int,
    max_context_chars: int,
) -> List[Dict[str, Any]]:
    # ------------------------------------------------------------
    # ページ別テキストから「図」「表」を含む文を抽出
    # ------------------------------------------------------------
    items: List[Dict[str, Any]] = []

    for page_index, page_text in enumerate(pages_text, start=1):
        sentences = split_sentences_keep_japanese(page_text)

        page_label = None
        if page_index - 1 < len(page_labels):
            page_label = page_labels[page_index - 1]

        for sent_index, sent in enumerate(sentences, start=1):
            if not contains_figure_or_table(sent):
                continue

            context_before = ""
            context_after = ""

            if include_context:
                if sent_index - 2 >= 0:
                    context_before = sentences[sent_index - 2]

                if sent_index < len(sentences):
                    context_after = sentences[sent_index]

            item_id = f"p{page_index:04d}_s{sent_index:04d}"

            items.append(
                {
                    "id": item_id,
                    "pdf_page": page_index,
                    "page_label": page_label,
                    "sentence_index": sent_index,
                    "text": safe_text_clip(sent, max_sentence_chars),
                    "context_before": safe_text_clip(context_before, max_context_chars),
                    "context_after": safe_text_clip(context_after, max_context_chars),
                }
            )

    return items