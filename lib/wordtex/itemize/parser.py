# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/itemize/parser.py
# ============================================================
# wordTex itemize parser
# ============================================================

from __future__ import annotations

import re

from lib.wordtex.blocks import ItemizeBlock, ItemizeItem
from lib.wordtex.figuretable.parser import parse_attrs


ITEMIZE_BEGIN_RE = re.compile(
    r"^\s*\\begin\{itemize(?P<body>.*?)\}\s*$"
)

ITEMIZE_END_RE = re.compile(
    r"^\s*\\end\{itemize\}\s*$"
)

ITEM_LINE_RE = re.compile(
    r"^\s*\\item(?:\[(?P<label>.*?)\])?\s*(?P<text>.*)$"
)


def is_itemize_begin_line(line: str) -> bool:
    return bool(ITEMIZE_BEGIN_RE.match(str(line or "")))


def is_itemize_end_line(line: str) -> bool:
    return bool(ITEMIZE_END_RE.match(str(line or "")))


def parse_itemize_begin_attrs(line: str) -> dict[str, str]:
    m = ITEMIZE_BEGIN_RE.match(str(line or ""))

    if not m:
        return {}

    body = str(m.group("body") or "").strip()

    if body.startswith(","):
        body = body[1:].strip()

    if not body:
        return {}

    return parse_attrs(body)


def parse_item_line(line: str) -> tuple[str, str] | None:
    m = ITEM_LINE_RE.match(str(line or ""))

    if not m:
        return None

    label = str(m.group("label") or "").strip()
    text = str(m.group("text") or "").strip()

    return label, text


def parse_itemize_block(
    *,
    lines: list[str],
    start_index: int,
) -> tuple[ItemizeBlock | None, int, list[str]]:
    """
    \\begin{itemize} ... \\end{itemize} を読む。

    入れ子 itemize に対応する。
    """
    warnings: list[str] = []

    start_line = str(lines[start_index] or "")
    attrs = parse_itemize_begin_attrs(start_line)

    block = ItemizeBlock(
        style=str(attrs.get("style") or "").strip(),
        raw=start_line,
    )

    current_item: ItemizeItem | None = None
    item_text_lines: list[str] = []

    def flush_current_item() -> None:
        nonlocal current_item, item_text_lines

        if current_item is None:
            return

        extra_text = "\n".join(
            line
            for line in item_text_lines
            if str(line or "").strip()
        ).strip()

        if extra_text:
            if current_item.text:
                current_item.text = current_item.text + "\n" + extra_text
            else:
                current_item.text = extra_text

        block.items.append(current_item)
        current_item = None
        item_text_lines = []

    i = start_index + 1

    while i < len(lines):
        line = str(lines[i] or "")

        if is_itemize_end_line(line):
            flush_current_item()
            block.raw = "\n".join(lines[start_index:i + 1])
            return block, i + 1, warnings

        if is_itemize_begin_line(line):
            if current_item is None:
                warnings.append(
                    f"itemizeの入れ子が\\itemの前にあります: {line}"
                )
                child, next_index, child_warnings = parse_itemize_block(
                    lines=lines,
                    start_index=i,
                )
                warnings.extend(child_warnings)
                i = next_index if next_index > i else i + 1
                continue

            child, next_index, child_warnings = parse_itemize_block(
                lines=lines,
                start_index=i,
            )

            warnings.extend(child_warnings)

            if child is not None:
                current_item.children.append(child)

            i = next_index if next_index > i else i + 1
            continue

        parsed_item = parse_item_line(line)

        if parsed_item is not None:
            flush_current_item()

            label, text = parsed_item

            current_item = ItemizeItem(
                label=label,
                text=text,
                raw=line,
            )

            i += 1
            continue

        if current_item is not None:
            item_text_lines.append(line)

        i += 1

    flush_current_item()

    warnings.append(
        f"itemizeが閉じられていません: {start_line}"
    )

    block.raw = "\n".join(lines[start_index:i])
    return block, i, warnings