# -*- coding: utf-8 -*-
# lib/word_analysis/tables.py
#
# 表キャプションの番号抽出・JSON 化

from __future__ import annotations

from typing import List, Tuple, Dict, Any
import re

from docx.text.paragraph import Paragraph
from docx.table import Table
from docx.oxml.ns import qn


def extract_seq_result_text(paragraph: Paragraph) -> str:
    """
    フィールド（SEQ など）が使われているキャプション段落から、
    <w:fldChar w:fldCharType="separate"/>〜<w:fldChar w:fldCharType="end"/>
    の間に表示される文字列を復元する。

    - <w:t> のテキスト
    - <w:noBreakHyphen/> は "-" に置き換える

    戻り値の例: "表3.1.1-2"
    """
    p_el = paragraph._element
    texts: List[str] = []
    in_result = False

    for node in p_el.iter():
        tag = node.tag

        # フィールド境界
        if tag.endswith("}fldChar"):
            fld_type = node.get(qn("w:fldCharType"))
            if fld_type == "separate":
                in_result = True
                continue
            if fld_type == "end":
                in_result = False
                break
        elif in_result and tag.endswith("}t"):
            if node.text:
                texts.append(node.text)
        elif in_result and tag.endswith("}noBreakHyphen"):
            texts.append("-")

    return "".join(texts)


def parse_table_number_and_title(paragraph: Paragraph) -> Tuple[str | None, str]:
    """
    表キャプション段落から「表番号」と「タイトル」を推定する。

    - まずフィールドから復元した表示文字列（例: "表3.1.1-2"）を使う
    - うまく取れない場合は paragraph.text から正規表現で推定
    - 戻り値: ( "3.1.1-2" or None, タイトル文字列 )
    """
    raw_text = (paragraph.text or "").strip()

    # 1) フィールド結果テキストを試す
    seq_text = extract_seq_result_text(paragraph)
    candidate = seq_text if seq_text else raw_text

    # "表3.1.1-2", "Table 3.1.1-2" などを想定
    m = re.search(
        r"(表|Table)\s*([0-9.]+)(?:[-−―‐-–—]\s*([0-9]+))?",
        candidate,
        re.IGNORECASE,
    )
    table_number: str | None = None
    if m:
        base = m.group(2)
        sub = m.group(3) or "1"
        table_number = f"{base}-{sub}"

    # タイトル部分: paragraph.text から番号部分を削った残りを使う
    title = raw_text
    if table_number:
        num_pattern = re.escape(table_number)
        title = re.sub(
            rf"(表|Table)\s*{num_pattern}",
            "",
            raw_text,
            flags=re.IGNORECASE,
        ).lstrip(" 　:：-―–—")

    return table_number, title or raw_text


def table_to_json(tbl: Table, caption_para: Paragraph | None) -> Dict[str, Any]:
    """
    python-docx の Table を、GPT に投げやすい JSON に変換する。

    戻り値の例:
    {
      "table_number": "3.1.1-2",
      "title": "最寄りの地域気象観測所の所在地等",
      "cells": [
        ["名称", "遠野", "釜石", "大槌"],
        ["所在地", "...", "...", "..."],
        ...
      ]
    }
    """
    table_number = None
    title = ""

    if caption_para is not None:
        table_number, title = parse_table_number_and_title(caption_para)

    if table_number is None:
        table_number = "unknown"
    if title is None:
        title = ""

    cells: List[List[str]] = []
    for row in tbl.rows:
        row_values: List[str] = []
        for cell in row.cells:
            text = (cell.text or "").strip()
            row_values.append(text)
        cells.append(row_values)

    return {
        "table_number": table_number,
        "title": title,
        "cells": cells,
    }
