# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/figure/parser.py

from __future__ import annotations

import re
from typing import Any

from lib.wordtex.blocks import FigureBlock, FigureItem
from lib.wordtex.figuretable.parser import (
    parse_attrs,
    find_matching_brace,
    parse_bool_value,
)


BEGIN_FIGURE_START_RE = re.compile(
    r"^\s*\\begin\{figure(?=,|\})",
)

END_FIGURE_RE = re.compile(
    r"^\s*\\end\{figure\}\s*$",
)

ITEM_START_RE = re.compile(
    r"\\item\s*\{",
)

NOTE_START_RE = re.compile(
    r"\\note\s*\{",
)


def is_figure_begin_line(line: str) -> bool:
    return bool(BEGIN_FIGURE_START_RE.match(str(line or "")))


def is_figure_end_line(line: str) -> bool:
    return bool(END_FIGURE_RE.match(str(line or "")))


def extract_begin_attrs_from_lines(
    *,
    lines: list[str],
    start_index: int,
) -> tuple[dict[str, str], int, list[str], list[str]]:
    warnings: list[str] = []
    raw_begin_lines: list[str] = []

    i = start_index

    while i < len(lines):
        line = lines[i]
        raw_begin_lines.append(line)

        joined = "\n".join(raw_begin_lines)

        if "}" in line:
            begin_text = joined
            prefix = "\\begin{figure"

            pos = begin_text.find(prefix)
            if pos < 0:
                return {}, i + 1, raw_begin_lines, [
                    f"figure開始タグを解析できません: {begin_text}"
                ]

            attr_text = begin_text[pos + len(prefix):]

            close_pos = attr_text.rfind("}")
            if close_pos >= 0:
                attr_text = attr_text[:close_pos]

            attrs = parse_attrs(attr_text)
            return attrs, i + 1, raw_begin_lines, warnings

        i += 1

    warnings.append("\\begin{figure} の開始タグが閉じていません。")
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
        close_pos = find_matching_brace(
            text,
            open_pos=open_pos,
        )

        if close_pos < 0:
            warnings.append("item の終了 } が見つかりません。")
            break

        item_texts.append(
            text[open_pos + 1:close_pos].strip()
        )

        pos = close_pos + 1

    return item_texts, warnings


def extract_note_text(block_body: str) -> tuple[str, list[str]]:
    text = str(block_body or "")
    warnings: list[str] = []

    m = NOTE_START_RE.search(text)
    if not m:
        return "", warnings

    open_pos = text.find("{", m.start())
    close_pos = find_matching_brace(
        text,
        open_pos=open_pos,
    )

    if close_pos < 0:
        warnings.append("note の終了 } が見つかりません。")
        return "", warnings

    note = text[open_pos + 1:close_pos].strip()

    # 空行は削除し、改行だけを保持する
    lines = [
        line.strip()
        for line in note.splitlines()
        if line.strip()
    ]

    return "\n".join(lines), warnings


def parse_figure_item(
    item_text: str,
) -> tuple[FigureItem | None, list[str]]:
    warnings: list[str] = []
    attrs = parse_attrs(item_text)

    file_name = str(attrs.get("file") or "").strip()

    if not file_name:
        warnings.append(f"figure item に file 属性がありません: {item_text}")
        return None, warnings

    item = FigureItem(
        file=file_name,
        title=str(attrs.get("title") or "").strip(),
        desp=str(
            attrs.get("desp")
            if attrs.get("desp") is not None
            else attrs.get("desc") or ""
        ).strip(),
        raw=str(item_text or ""),
    )

    return item, warnings


def build_figure_block_from_attrs(
    *,
    attrs: dict[str, Any],
    raw: str,
    item: FigureItem | None,
    note: str,
) -> FigureBlock:
    return FigureBlock(
        title=str(attrs.get("title") or "").strip(),
        caption=str(attrs.get("caption") or "").strip(),
        label=str(attrs.get("label") or "").strip(),
        width=str(attrs.get("width") or "100%").strip(),
        numbering=parse_bool_value(
            attrs.get("numbering", True),
            default=True,
        ),
        item=item,
        note=str(note or "").strip(),
        raw=raw,
    )


def parse_figure_block(
    *,
    lines: list[str],
    start_index: int,
) -> tuple[FigureBlock | None, int, list[str]]:
    warnings: list[str] = []

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

        if is_figure_end_line(line):
            found_end = True
            i += 1
            break

        body_lines.append(line)
        i += 1

    if not found_end:
        warnings.append(
            "\\begin{figure} に対応する \\end{figure} がありません。"
        )

    raw = "\n".join(raw_lines)
    body = "\n".join(body_lines)

    item_texts, item_warnings = extract_item_texts(body)
    warnings.extend(item_warnings)

    if len(item_texts) > 1:
        warnings.append("figure の item は1つだけ有効です。先頭のみ使用します。")

    item: FigureItem | None = None

    if item_texts:
        item, parse_warnings = parse_figure_item(item_texts[0])
        warnings.extend(parse_warnings)
    else:
        warnings.append("figure に item がありません。")

    note, note_warnings = extract_note_text(body)
    warnings.extend(note_warnings)

    block = build_figure_block_from_attrs(
        attrs=attrs,
        raw=raw,
        item=item,
        note=note,
    )

    return block, i, warnings