# -*- coding: utf-8 -*-
# lib/word_analysis/blocks.py
#
# Word 文書のブロック（段落 / 表）を扱う共通ヘルパー

from __future__ import annotations

from typing import Union, List
import re

from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table


Block = Union[Paragraph, Table]


def iter_block_items(doc: Document):
    """
    document.element.body の子要素を順番通りにたどり、
    Paragraph / Table を順番に返すユーティリティ。

    python-docx の定番レシピを少しだけ簡略化したもの。
    """
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, doc)
        elif child.tag.endswith("}tbl"):
            yield Table(child, doc)


def paragraph_has_image(p: Paragraph) -> bool:
    """
    Paragraph 内に画像(drawing)が含まれているかどうかをざっくり判定。
    """
    for run in p.runs:
        try:
            if run._element.xpath(".//w:drawing"):
                return True
        except Exception:
            continue
    return False


def classify_paragraph(p: Paragraph) -> str:
    """
    見出し以外の段落を簡易的に分類する:
    - "toc" : 目次候補
    - "figure" : 図のキャプション or 図を含む段落
    - "table_caption" : 表のキャプション
    - "body" : 上記以外（本文扱い）

    ※ 完全ではなく「そこそこ当たる」程度の簡易ルール。
    """
    text = (p.text or "").strip()
    style_name = (p.style.name if p.style is not None else "") or ""

    # ---- 目次候補 ----
    if (
        style_name.startswith("TOC")
        or "目次" in style_name
        or text.startswith("目次")
    ):
        return "toc"

    # ---- 図キャプション候補 / 図を含む段落 ----
    if re.match(r"^(図|Figure|Fig\.?)\s*\d", text):
        return "figure"
    if any(k in style_name for k in ["図", "Figure", "キャプション", "Caption"]):
        return "figure"
    if paragraph_has_image(p):
        return "figure"

    # ---- 表キャプション候補 ----
    if re.match(r"^表\s*\d", text) or re.match(r"^Table\s*\d", text, re.IGNORECASE):
        return "table_caption"
    if any(k in style_name for k in ["表", "Table"]):
        return "table_caption"

    return "body"


def classify_block(block: Block, prev_block: Block | None) -> str:
    """
    Paragraph / Table をまとめて分類するためのラッパー。
    - Paragraph は classify_paragraph に委譲
    - Table は基本的に "table" 扱い（直前が表キャプションなら "table"）
    """
    if isinstance(block, Paragraph):
        return classify_paragraph(block)

    if isinstance(block, Table):
        if isinstance(prev_block, Paragraph) and classify_paragraph(prev_block) == "table_caption":
            return "table"
        # とりあえず Word 上の Table はすべて「表」扱い
        return "table"

    return "body"
