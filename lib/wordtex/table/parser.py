# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/table/parser.py
# ============================================================
# wordTex table parser
# ============================================================

from __future__ import annotations

import re

from lib.wordtex.blocks import TableBlock
from lib.wordtex.figuretable.parser import parse_attrs
from lib.table.helpers import _parse_table as parse_table_text


TABLE_BEGIN_RE = re.compile(
    r"^\s*\\begin\{table(?P<body>.*?)\}\s*$"
)

TABLE_END_RE = re.compile(
    r"^\s*\\end\{table\}\s*$"
)

NOTE_BEGIN_RE = re.compile(
    r"^\s*\\note\{\s*$"
)

NOTE_END_RE = re.compile(
    r"^\s*\}\s*$"
)


def is_table_begin_line(line: str) -> bool:
    return bool(TABLE_BEGIN_RE.match(str(line or "")))


def is_table_end_line(line: str) -> bool:
    return bool(TABLE_END_RE.match(str(line or "")))


def parse_table_begin_attrs(line: str) -> dict[str, str]:
    m = TABLE_BEGIN_RE.match(str(line or ""))

    if not m:
        return {}

    body = str(m.group("body") or "").strip()

    if body.startswith(","):
        body = body[1:].strip()

    if not body:
        return {}

    return parse_attrs(body)


def _to_int(value: object, default: int) -> int:
    text = str(value or "").strip()

    if not text:
        return default

    try:
        return int(text)
    except ValueError:
        return default

def normalize_wordtex_table_text(text: str) -> str:
    """
    WordTex table 本文を lib.table.helpers._parse_table 用に正規化する。

    対応：
    - & を Tab に変換する
    - LaTeX風の \\ を実改行に変換する
    - Excel貼り付けの Tab / 改行はそのまま使える
    """
    text = str(text or "")

    # ------------------------------------------------------------
    # LaTeX の行区切り \\ を実改行へ変換する。
    # ------------------------------------------------------------
    text = text.replace("\\\\", "\n")

    # ------------------------------------------------------------
    # WordTex table の列区切り & を Tab へ変換する。
    # これで既存の _parse_table() をそのまま再利用できる。
    # ------------------------------------------------------------
    text = text.replace("&", "\t")

    return text.strip()

def parse_table_block(
    *,
    lines: list[str],
    start_index: int,
) -> tuple[TableBlock | None, int, list[str]]:
    """
    \\begin{table,...} ... \\end{table} を読む。

    - 表本体は table_lines に入れる
    - \\note{...} は note_lines に分離する
    """
    warnings: list[str] = []

    start_line = str(lines[start_index] or "")
    attrs = parse_table_begin_attrs(start_line)

    table_lines: list[str] = []
    note_lines: list[str] = []

    in_note = False
    i = start_index + 1

    while i < len(lines):
        line = str(lines[i] or "")

        if is_table_end_line(line):

            table_text = normalize_wordtex_table_text(
                "\n".join(table_lines)
            )
            rows = parse_table_text(table_text)

            block = TableBlock(
                title=str(attrs.get("title") or "").strip(),
                caption=str(attrs.get("caption") or "").strip(),
                label=str(attrs.get("label") or "").strip(),
                style=str(attrs.get("style") or "simple").strip() or "simple",
                header_rows=_to_int(attrs.get("header_rows"), 1),
                header_cols=_to_int(attrs.get("header_cols"), 0),
                rows=rows,
                note="\n".join(note_lines).strip(),
                raw="\n".join(lines[start_index:i + 1]),
            )

            if not rows:
                warnings.append(
                    f"tableの表データが空です: {start_line}"
                )

            return block, i + 1, warnings

        if NOTE_BEGIN_RE.match(line):
            in_note = True
            i += 1
            continue

        if in_note:
            if NOTE_END_RE.match(line):
                in_note = False
                i += 1
                continue

            note_lines.append(line)
            i += 1
            continue

        table_lines.append(line)
        i += 1

    rows = parse_table_text("\n".join(table_lines).strip())

    block = TableBlock(
        title=str(attrs.get("title") or "").strip(),
        caption=str(attrs.get("caption") or "").strip(),
        label=str(attrs.get("label") or "").strip(),
        style=str(attrs.get("style") or "simple").strip() or "simple",
        header_rows=_to_int(attrs.get("header_rows"), 1),
        header_cols=_to_int(attrs.get("header_cols"), 0),
        rows=rows,
        note="\n".join(note_lines).strip(),
        raw="\n".join(lines[start_index:i]),
    )

    warnings.append(
        f"tableが閉じられていません: {start_line}"
    )

    return block, i, warnings