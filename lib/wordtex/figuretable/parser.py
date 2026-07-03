# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/figuretable/parser.py
# ============================================================
# figureTable parser
#
# - 1行 begin と複数行 begin の両方に対応する
# - \begin{figureTable,...} ～ \end{figureTable} を解析する
# ============================================================

from __future__ import annotations

import re
from typing import Any

from lib.wordtex.blocks import FigureTableBlock, FigureTableItem
from lib.wordtex.figuretable.constants import (
    DEFAULT_FIGURE_TABLE_BG_COLOR_KEY,
    DEFAULT_FIGURE_TABLE_ROW,
    normalize_figure_table_row,
)


BEGIN_FIGURE_TABLE_START_RE = re.compile(
    r"^\s*\\begin\{figureTable\b",
)

END_FIGURE_TABLE_RE = re.compile(
    r"^\s*\\end\{figureTable\}\s*$",
)

ITEM_START_RE = re.compile(
    r"\\item\s*\{",
)


def parse_bool_value(value: object, *, default: bool = True) -> bool:
    text = str(value or "").strip().lower()

    if not text:
        return default

    if text in {"true", "1", "yes", "y", "on"}:
        return True

    if text in {"false", "0", "no", "n", "off"}:
        return False

    return default


def strip_quote(value: object) -> str:
    text = str(value or "").strip()

    if len(text) >= 2:
        if text[0] == '"' and text[-1] == '"':
            return text[1:-1]
        if text[0] == "'" and text[-1] == "'":
            return text[1:-1]

    return text


def normalize_attr_text(attr_text: str) -> str:
    text = str(attr_text or "").strip()

    if text.startswith(","):
        text = text[1:].strip()

    if text.endswith("}"):
        text = text[:-1].strip()

    return text


def split_attrs(attr_text: str) -> list[str]:
    text = str(attr_text or "")
    parts: list[str] = []

    buf: list[str] = []
    quote: str | None = None
    escape = False
    bracket_depth = 0

    for ch in text:
        if escape:
            buf.append(ch)
            escape = False
            continue

        if ch == "\\":
            buf.append(ch)
            escape = True
            continue

        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue

        if ch in {'"', "'"}:
            buf.append(ch)
            quote = ch
            continue

        # ------------------------------------------------------------
        # リスト指定 [1,2,3] の中では，カンマを属性区切りにしない。
        # 例:
        #   col_ratio=[1,2,1]
        # ------------------------------------------------------------
        if ch == "[":
            bracket_depth += 1
            buf.append(ch)
            continue

        if ch == "]":
            if bracket_depth > 0:
                bracket_depth -= 1
            buf.append(ch)
            continue

        if ch == "," and bracket_depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue

        buf.append(ch)

    last = "".join(buf).strip()
    if last:
        parts.append(last)

    return parts


def parse_attrs(attr_text: str) -> dict[str, str]:
    text = normalize_attr_text(attr_text)
    result: dict[str, str] = {}

    if not text:
        return result

    for part in split_attrs(text):
        if "=" not in part:
            key = part.strip()
            if key:
                result[key] = ""
            continue

        key, value = part.split("=", 1)
        key = str(key or "").strip()
        value = strip_quote(value)

        if key:
            result[key] = value

    return result


def is_figure_table_begin_line(line: str) -> bool:
    return bool(BEGIN_FIGURE_TABLE_START_RE.match(str(line or "")))


def is_figure_table_end_line(line: str) -> bool:
    return bool(END_FIGURE_TABLE_RE.match(str(line or "")))


def find_matching_brace(text: str, *, open_pos: int) -> int:
    if open_pos < 0 or open_pos >= len(text):
        return -1

    if text[open_pos] != "{":
        return -1

    depth = 0
    quote: str | None = None
    escape = False

    for i in range(open_pos, len(text)):
        ch = text[i]

        if escape:
            escape = False
            continue

        if ch == "\\":
            escape = True
            continue

        if quote:
            if ch == quote:
                quote = None
            continue

        if ch in {'"', "'"}:
            quote = ch
            continue

        if ch == "{":
            depth += 1
            continue

        if ch == "}":
            depth -= 1
            if depth == 0:
                return i

    return -1


def extract_begin_attrs_from_lines(
    *,
    lines: list[str],
    start_index: int,
) -> tuple[dict[str, str], int, list[str], list[str]]:
    """
    複数行 begin に対応して begin 属性を取得する。

    戻り値:
        attrs
        body_start_index
        raw_begin_lines
        warnings
    """
    warnings: list[str] = []
    raw_begin_lines: list[str] = []

    if start_index < 0 or start_index >= len(lines):
        return {}, start_index, raw_begin_lines, ["figureTable開始位置が不正です。"]

    i = start_index

    while i < len(lines):
        line = lines[i]
        raw_begin_lines.append(line)

        joined = "\n".join(raw_begin_lines)

        # --------------------------------------------------------
        # beginタグとして閉じる } が見つかったら属性部分を切り出す
        # --------------------------------------------------------
        if "}" in line:
            begin_text = joined

            prefix = "\\begin{figureTable"
            pos = begin_text.find(prefix)

            if pos < 0:
                return {}, i + 1, raw_begin_lines, [
                    f"figureTable開始タグを解析できません: {begin_text}"
                ]

            attr_text = begin_text[pos + len(prefix) :]

            # 最後の } 以降は begin 属性ではない
            close_pos = attr_text.rfind("}")
            if close_pos >= 0:
                attr_text = attr_text[:close_pos]

            attrs = parse_attrs(attr_text)

            return attrs, i + 1, raw_begin_lines, warnings

        i += 1

    warnings.append("\\begin{figureTable} の開始タグが閉じていません。")
    return {}, i, raw_begin_lines, warnings


def extract_item_texts(block_body: str) -> tuple[list[str], list[str]]:
    text = str(block_body or "")
    item_texts: list[str] = []
    warnings: list[str] = []

    pos = 0

    while True:
        m = ITEM_START_RE.search(text, pos)
        if not m:
            break

        open_pos = text.find("{", m.start())
        if open_pos < 0:
            warnings.append("itemの開始 { が見つかりません。")
            break

        close_pos = find_matching_brace(
            text,
            open_pos=open_pos,
        )

        if close_pos < 0:
            warnings.append("itemの終了 } が見つかりません。")
            break

        inner = text[open_pos + 1 : close_pos].strip()
        item_texts.append(inner)

        pos = close_pos + 1

    return item_texts, warnings


def parse_figure_table_item(
    item_text: str,
) -> tuple[FigureTableItem | None, list[str]]:
    warnings: list[str] = []
    attrs = parse_attrs(item_text)

    file_name = str(attrs.get("file") or "").strip()

    if not file_name:
        warnings.append(f"itemにfile属性がありません: {item_text}")
        return None, warnings

    title = str(attrs.get("title") or "").strip()

    desp = str(
        attrs.get("desp")
        if attrs.get("desp") is not None
        else attrs.get("desc") or ""
    ).strip()

    item = FigureTableItem(
        file=file_name,
        title=title,
        desp=desp,
        raw=str(item_text or ""),
    )

    return item, warnings


def build_figure_table_block_from_attrs(
    *,
    attrs: dict[str, Any],
    raw: str,
) -> FigureTableBlock:
    title = str(attrs.get("title") or "").strip()
    caption = str(attrs.get("caption") or "").strip()
    label = str(attrs.get("label") or "").strip()

    row = normalize_figure_table_row(
        attrs.get("row", DEFAULT_FIGURE_TABLE_ROW)
    )

    bc = str(
        attrs.get("bc")
        or attrs.get("background")
        or DEFAULT_FIGURE_TABLE_BG_COLOR_KEY
    ).strip()

    numbering = parse_bool_value(
        attrs.get("numbering", True),
        default=True,
    )

    return FigureTableBlock(
        title=title,
        caption=caption,
        label=label,
        row=row,
        width=str(attrs.get("width") or "100%").strip(),
        col_ratio=str(attrs.get("col_ratio") or "").strip(),
        bc=bc,
        numbering=numbering,
        items=[],
        raw=raw,
    )


def parse_figure_table_body(
    body: str,
) -> tuple[list[FigureTableItem], list[str]]:
    item_texts, warnings = extract_item_texts(body)

    items: list[FigureTableItem] = []

    for item_text in item_texts:
        item, item_warnings = parse_figure_table_item(item_text)
        warnings.extend(item_warnings)

        if item is not None:
            items.append(item)

    if not items:
        warnings.append("figureTable内に有効なitemがありません。")

    return items, warnings


def parse_figure_table_block(
    *,
    lines: list[str],
    start_index: int,
) -> tuple[FigureTableBlock | None, int, list[str]]:
    warnings: list[str] = []

    if start_index < 0 or start_index >= len(lines):
        return None, start_index, ["figureTableの開始位置が不正です。"]

    if not is_figure_table_begin_line(lines[start_index]):
        return None, start_index, [
            f"figureTable開始行ではありません: {lines[start_index]}"
        ]

    attrs, body_start_index, begin_raw_lines, begin_warnings = (
        extract_begin_attrs_from_lines(
            lines=lines,
            start_index=start_index,
        )
    )

    warnings.extend(begin_warnings)

    raw_lines: list[str] = list(begin_raw_lines)
    body_lines: list[str] = []

    i = body_start_index
    found_end = False

    while i < len(lines):
        line = lines[i]
        raw_lines.append(line)

        if is_figure_table_end_line(line):
            found_end = True
            i += 1
            break

        body_lines.append(line)
        i += 1

    if not found_end:
        warnings.append(
            "\\begin{figureTable} に対応する \\end{figureTable} がありません。"
        )

    raw = "\n".join(raw_lines)
    body = "\n".join(body_lines)

    block = build_figure_table_block_from_attrs(
        attrs=attrs,
        raw=raw,
    )

    items, body_warnings = parse_figure_table_body(body)
    block.items = items
    warnings.extend(body_warnings)

    return block, i, warnings