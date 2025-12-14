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
from .images import paragraph_has_image
import re

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
    段落を簡易的に分類する:

    - "toc"            : 目次候補
    - "figure_caption" : 図のキャプション
    - "table_caption"  : 表のキャプション
    - "figure_body"    : 図本体（画像を含む段落）
    - "body"           : 上記以外（本文・見出しなど）

    ※ 完全ではなく「そこそこ当たる」程度の簡易ルール。
    """
    text = (p.text or "").strip()
    style_name = (p.style.name if getattr(p, "style", None) is not None else "") or ""

    # ---- 目次候補 ----
    if (
        style_name.startswith("TOC")
        or "目次" in style_name
        or text.startswith("目次")
    ):
        return "toc"

    # ---- 表キャプション（優先）----
    #   ・先頭が「表...」 / "Table..." で始まる
    #   ・またはスタイル名に「表」「Table」が含まれる
    if (
        re.match(r"^表\s*[\d０-９]", text)
        or re.match(r"^Table\s*[\d０-９]", text, re.IGNORECASE)
        or ("表" in style_name)
        or ("Table" in style_name)
    ):
        return "table_caption"

    # ---- 図キャプション ----
    #   ・先頭が「図...」 / "Figure 1" / "Fig. 1" で始まる
    #   ・またはスタイル名に「図」「Figure」「Caption」「キャプション」が含まれる
    if (
        re.match(r"^図\s*[\d０-９]", text)
        or re.match(r"^Figure\s*[\d０-９]", text, re.IGNORECASE)
        or re.match(r"^Fig\.?\s*[\d０-９]", text, re.IGNORECASE)
        or ("図" in style_name)
        or ("Figure" in style_name)
        or ("Caption" in style_name)
        or ("キャプション" in style_name)
    ):
        return "figure_caption"

    # ---- 図本体（画像を含む段落）----
    if paragraph_has_image(p):
        return "figure_body"

    # ---- それ以外 ----
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
