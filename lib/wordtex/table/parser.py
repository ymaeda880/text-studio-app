# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/table/parser.py
# ============================================================
# wordTex table parser
#
# - 1行 begin と複数行 begin の両方に対応する
# - \begin{table,...} ～ \end{table} を解析する
# ============================================================

from __future__ import annotations

import re
from typing import Any

from lib.wordtex.blocks import TableBlock
from lib.wordtex.figuretable.parser import parse_attrs
from lib.table.helpers import _parse_table as parse_table_text


TABLE_BEGIN_START_RE = re.compile(
    r"^\s*\\begin\{table(?=,|\})",
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
    return bool(TABLE_BEGIN_START_RE.match(str(line or "")))


def is_table_end_line(line: str) -> bool:
    return bool(TABLE_END_RE.match(str(line or "")))


def extract_table_begin_attrs_from_lines(
    *,
    lines: list[str],
    start_index: int,
) -> tuple[dict[str, str], int, list[str], list[str]]:
    """
    table の begin 属性を取得する。

    対応:
    - 1行 begin
      \begin{table,style="simple"}

    - 複数行 begin
      \begin{table,
      style="simple",
      header_rows=1}
    """
    warnings: list[str] = []
    raw_begin_lines: list[str] = []

    i = start_index

    while i < len(lines):
        line = str(lines[i] or "")
        raw_begin_lines.append(line)

        joined = "\n".join(raw_begin_lines)

        if "}" in line:
            begin_text = joined
            prefix = "\\begin{table"

            pos = begin_text.find(prefix)
            if pos < 0:
                return {}, i + 1, raw_begin_lines, [
                    f"table開始タグを解析できません: {begin_text}"
                ]

            attr_text = begin_text[pos + len(prefix):]

            close_pos = attr_text.rfind("}")
            if close_pos >= 0:
                attr_text = attr_text[:close_pos]

            attrs = parse_attrs(attr_text)

            return attrs, i + 1, raw_begin_lines, warnings

        i += 1

    warnings.append("\\begin{table} の開始タグが閉じていません。")
    return {}, i, raw_begin_lines, warnings


def _to_int(value: object, default: int) -> int:
    text = str(value or "").strip()

    if not text:
        return default

    try:
        return int(text)
    except ValueError:
        return default

def _to_bool(value: object, default: bool = False) -> bool:
    text = str(value or "").strip().lower()

    if not text:
        return default

    if text in {"true", "1", "yes", "y", "on"}:
        return True

    if text in {"false", "0", "no", "n", "off"}:
        return False

    return default

def _parse_float_list(value: object) -> tuple[list[float], str]:
    """
    [1,2,3] 形式の数値リストを読む。
    """
    text = str(value or "").strip()

    if not text:
        return [], ""

    if not (text.startswith("[") and text.endswith("]")):
        return [], f"リスト指定が不正です: {text}"

    inner = text[1:-1].strip()

    if not inner:
        return [], ""

    values: list[float] = []

    for part in inner.split(","):
        p = part.strip()

        if not p:
            return [], f"空の値があります: {text}"

        try:
            v = float(p)
        except ValueError:
            return [], f"数値ではない値があります: {text}"

        if v <= 0:
            return [], f"0以下の値があります: {text}"

        values.append(v)

    return values, ""


def _parse_string_list(value: object) -> tuple[list[str], str]:
    """
    ["file.xlsx","sheet1"] 形式の文字列リストを読む。
    """
    text = str(value or "").strip()

    if not text:
        return [], ""

    if not (text.startswith("[") and text.endswith("]")):
        return [], f"リスト指定が不正です: {text}"

    inner = text[1:-1].strip()

    if not inner:
        return [], ""

    values: list[str] = []

    for part in inner.split(","):
        p = part.strip()

        if len(p) >= 2:
            if p.startswith('"') and p.endswith('"'):
                p = p[1:-1]
            elif p.startswith("'") and p.endswith("'"):
                p = p[1:-1]

        p = p.strip()

        if p:
            values.append(p)

    return values, ""

def _parse_table_width_attrs(
    attrs: dict[str, Any],
    warnings: list[str],
) -> tuple[str, list[float], list[float]]:
    """
    table の width / col_ratio / col_widths を読む。
    """
    width = str(attrs.get("width") or "100%").strip() or "100%"

    col_ratio, warning = _parse_float_list(attrs.get("col_ratio"))
    if warning:
        warnings.append(f"col_ratio が不正です: {warning}")
        col_ratio = []

    col_widths, warning = _parse_float_list(attrs.get("col_widths"))
    if warning:
        warnings.append(f"col_widths が不正です: {warning}")
        col_widths = []

    return width, col_ratio, col_widths


def normalize_wordtex_table_text(text: str) -> str:
    """
    WordTex table 本文を lib.table.helpers._parse_table 用に正規化する。

    対応:
    - & を Tab に変換する
    - LaTeX風の \\ を実改行に変換する
    - Excel貼り付けの Tab / 改行はそのまま使える
    """
    text = str(text or "")

    text = text.replace("\\\\", "\n")
    text = text.replace("&", "\t")

    return text.strip()


def build_table_block(
    *,
    attrs: dict[str, str],
    rows: list[list[str]],
    note_lines: list[str],
    raw: str,
    warnings: list[str],
) -> TableBlock:
    width, col_ratio, col_widths = _parse_table_width_attrs(
        attrs=attrs,
        warnings=warnings,
    )

    src_values, src_warning = _parse_string_list(attrs.get("src"))
    if src_warning:
        warnings.append(f"src が不正です: {src_warning}")
        src_values = []

    src_file = src_values[0] if len(src_values) >= 1 else ""
    src_sheet = src_values[1] if len(src_values) >= 2 else ""

    return TableBlock(
        title=str(attrs.get("title") or "").strip(),
        caption=str(attrs.get("caption") or "").strip(),
        label=str(attrs.get("label") or "").strip(),
        style=str(attrs.get("style") or "simple").strip() or "simple",
        header_rows=_to_int(attrs.get("header_rows"), 1),
        header_cols=_to_int(attrs.get("header_cols"), 0),
        width=width,
        col_ratio=col_ratio,
        col_widths=col_widths,
        compact=str(attrs.get("compact") or "none").strip().lower(),
        fontsize=str(attrs.get("fontsize") or "normal").strip().lower(),
        rows=rows,
        note="\n".join(note_lines).strip(),
        raw=raw,
        src_file=src_file,
        src_sheet=src_sheet,
    )


def parse_table_block(
    *,
    lines: list[str],
    start_index: int,
) -> tuple[TableBlock | None, int, list[str]]:
    r"""
    \begin{table,...} ... \end{table} を読む。

    - 複数行 begin に対応
    - 表本体は table_lines に入れる
    - \note{...} は note_lines に分離する
    """
    warnings: list[str] = []

    attrs, body_start_index, begin_raw_lines, begin_warnings = (
        extract_table_begin_attrs_from_lines(
            lines=lines,
            start_index=start_index,
        )
    )

    warnings.extend(begin_warnings)

    raw_lines: list[str] = list(begin_raw_lines)
    table_lines: list[str] = []
    note_lines: list[str] = []

    in_note = False
    i = body_start_index

    while i < len(lines):
        line = str(lines[i] or "")
        raw_lines.append(line)

        if is_table_end_line(line):
            table_text = normalize_wordtex_table_text(
                "\n".join(table_lines)
            )
            rows = parse_table_text(table_text)

            block = build_table_block(
                attrs=attrs,
                rows=rows,
                note_lines=note_lines,
                raw="\n".join(raw_lines),
                warnings=warnings,
            )

            if not rows and not str(getattr(block, "src_file", "") or "").strip():
                warnings.append(
                    f"tableの表データが空です: {raw_lines[0]}"
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

    table_text = normalize_wordtex_table_text(
        "\n".join(table_lines)
    )
    rows = parse_table_text(table_text)

    block = build_table_block(
        attrs=attrs,
        rows=rows,
        note_lines=note_lines,
        raw="\n".join(raw_lines),
        warnings=warnings,
    )

    warnings.append(
        f"tableが閉じられていません: {raw_lines[0] if raw_lines else ''}"
    )

    return block, i, warnings