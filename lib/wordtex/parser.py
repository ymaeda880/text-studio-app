# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/parser.py

from __future__ import annotations

import re

from lib.wordtex.blocks import (
    ParsedWordTex,
    ParagraphBlock,
    HeadingBlock,
    ParagraphHeadingBlock,
    SetBlock,
    NewPageBlock,
    VSkipBlock,
    TitleBlock,
    AuthorBlock,
    DateBlock,
    TableOfContentsBlock,
)
from lib.wordtex.figuretable.parser import (
    is_figure_table_begin_line,
    parse_figure_table_block,
)

from lib.wordtex.figure.parser import (
    is_figure_begin_line,
    parse_figure_block,
)

from lib.wordtex.itemize.parser import (
    is_itemize_begin_line,
    parse_itemize_block,
)

from lib.wordtex.table.parser import (
    is_table_begin_line,
    parse_table_block,
)

SET_LINE_RE = re.compile(
    r"^\s*\\set\{(?P<body>.*?)\}\s*$",
    re.DOTALL,
)

SECTION_LINE_RE = re.compile(
    r"^\s*\\(?P<cmd>section|subsection|subsubsection)\{(?P<body>.*?)\}\s*$",
    re.DOTALL,
)

PARAGRAPH_HEADING_LINE_RE = re.compile(
    r"^\s*\\paragraph\{(?P<body>.*?)\}\s*$",
    re.DOTALL,
)

COMMENT_LINE_RE = re.compile(
    r"^\s*%.*$",
)

TABLE_OF_CONTENTS_RE = re.compile(
    r"^\s*\\tableofcontents\s*$",
)

VSKIP_LINE_RE = re.compile(
    r"^\s*\\vskip\{(?P<amount>.*?)\}\s*$",
    re.DOTALL,
)

NOINDENT_LINE_RE = re.compile(
    r"^\s*\\noindent\s*$",
)


def is_comment_line(line: str) -> bool:
    return bool(COMMENT_LINE_RE.match(str(line or "")))


def is_table_of_contents_line(line: str) -> bool:
    return bool(TABLE_OF_CONTENTS_RE.match(str(line or "")))

def is_set_line(line: str) -> bool:
    return bool(SET_LINE_RE.match(str(line or "")))


def is_newpage_line(line: str) -> bool:
    """
    \newpage の判定
    """
    return str(line or "").strip() == "\\newpage"

def is_vskip_line(line: str) -> bool:
    """
    \vskip{...} の判定
    """
    return bool(VSKIP_LINE_RE.match(str(line or "")))

def is_noindent_line(line: str) -> bool:
    """
    \noindent の判定
    """
    return bool(NOINDENT_LINE_RE.match(str(line or "")))

def is_section_line(line: str) -> bool:
    return bool(SECTION_LINE_RE.match(str(line or "")))

def is_paragraph_heading_line(line: str) -> bool:
    return bool(PARAGRAPH_HEADING_LINE_RE.match(str(line or "")))

def strip_outer_quotes(value: str) -> str:
    text = str(value or "").strip()

    if len(text) >= 2:
        if text.startswith('"') and text.endswith('"'):
            return text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            return text[1:-1]

    return text

def split_wordtex_attrs(attr_text: str) -> list[str]:
    """
    wordTex共通の属性文字列をカンマで分割する。

    - "..." / '...' の中のカンマは分割しない
    - [...] の中のカンマは分割しない
    - {...} の中のカンマは分割しない
    """
    text = str(attr_text or "")
    parts: list[str] = []

    buf: list[str] = []
    quote: str | None = None
    escape = False
    bracket_depth = 0
    brace_depth = 0

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

        if ch == "[":
            bracket_depth += 1
            buf.append(ch)
            continue

        if ch == "]":
            if bracket_depth > 0:
                bracket_depth -= 1
            buf.append(ch)
            continue

        if ch == "{":
            brace_depth += 1
            buf.append(ch)
            continue

        if ch == "}":
            if brace_depth > 0:
                brace_depth -= 1
            buf.append(ch)
            continue

        if ch == "," and bracket_depth == 0 and brace_depth == 0:
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


def parse_wordtex_attrs(attr_text: str) -> dict[str, str]:
    """
    section / set 用の属性解析。

    figureTable専用 parser の parse_attrs は使わない。
    末尾の } を勝手に削らないため，
    section_title_format=第{num}章 {title}
    を正しく保持できる。
    """
    text = str(attr_text or "").strip()
    result: dict[str, str] = {}

    if not text:
        return result

    for part in split_wordtex_attrs(text):
        if "=" not in part:
            key = part.strip()
            if key:
                result[key] = ""
            continue

        key, value = part.split("=", 1)
        key = str(key or "").strip()
        value = strip_outer_quotes(str(value or "").strip())

        if key:
            result[key] = value

    return result

def read_braced_command_block(
    *,
    lines: list[str],
    start_index: int,
    command: str,
) -> tuple[str, int, str]:
    """
    \\title{...} / \\author{...} / \\date{...} を読む。
    複数行と空行を保持する。
    """
    line = str(lines[start_index] or "")
    prefix = f"\\{command}" + "{"

    stripped = line.strip()

    if not stripped.startswith(prefix):
        return "", start_index + 1, line

    first_body = stripped[len(prefix):]
    raw_lines = [line]
    body_lines: list[str] = []

    if "}" in first_body:
        body = first_body.rsplit("}", 1)[0]
        return body, start_index + 1, "\n".join(raw_lines)

    body_lines.append(first_body)

    i = start_index + 1

    while i < len(lines):
        current = str(lines[i] or "")
        raw_lines.append(current)

        if current.strip() == "}":
            return "\n".join(body_lines), i + 1, "\n".join(raw_lines)

        if "}" in current:
            body_lines.append(current.rsplit("}", 1)[0])
            return "\n".join(body_lines), i + 1, "\n".join(raw_lines)

        body_lines.append(current)
        i += 1

    return "\n".join(body_lines), i, "\n".join(raw_lines)

def parse_vskip_line(line: str) -> VSkipBlock | None:
    """
    \vskip{...} を VSkipBlock に変換する。
    """
    m = VSKIP_LINE_RE.match(str(line or ""))

    if not m:
        return None

    amount = str(m.group("amount") or "").strip()

    return VSkipBlock(
        amount=amount,
        raw=str(line or ""),
    )

def parse_set_line(
    line: str,
) -> tuple[SetBlock | None, list[str]]:
    warnings: list[str] = []

    m = SET_LINE_RE.match(str(line or ""))
    if not m:
        return None, warnings

    body = str(m.group("body") or "").strip()

    if not body:
        warnings.append(f"set設定が空です: {line}")
        return None, warnings

    # ------------------------------------------------------------
    # \set{font="report",size=11} のような
    # カンマ区切り key=value を読む。
    #
    # parse_attrs は section / figureTable などでも使っている
    # 既存の属性解析処理なので、ここでも流用する。
    # ------------------------------------------------------------
    values = parse_wordtex_attrs(body)

    cleaned_values: dict[str, str] = {}

    for key, value in values.items():
        key_text = str(key or "").strip()
        value_text = strip_outer_quotes(str(value or "").strip())

        if not key_text:
            continue

        cleaned_values[key_text] = value_text

    if not cleaned_values:
        warnings.append(f"set設定が不正です: {line}")
        return None, warnings

    return SetBlock(
        values=cleaned_values,
        raw=str(line or ""),
    ), warnings


def parse_heading_body(body: str) -> tuple[str, dict[str, str]]:
    """
    \\section{タイトル,label="sec:x"} を解析する。

    最初の key=value ではない要素を title とみなす。
    """
    text = str(body or "").strip()

    attrs = parse_wordtex_attrs(text)

    title = ""

    for key, value in attrs.items():
        if value == "":
            title = key
            break

    if not title:
        title = str(attrs.get("title") or "").strip()

    cleaned_attrs = {
        k: v
        for k, v in attrs.items()
        if not (k == title and v == "")
    }

    return title, cleaned_attrs


def parse_section_line(line: str) -> HeadingBlock | None:
    m = SECTION_LINE_RE.match(str(line or ""))

    if not m:
        return None

    cmd = str(m.group("cmd") or "").strip()
    body = str(m.group("body") or "").strip()

    level_map = {
        "section": 1,
        "subsection": 2,
        "subsubsection": 3,
    }

    title, attrs = parse_heading_body(body)

    return HeadingBlock(
        level=level_map.get(cmd, 1),
        title=title,
        label=str(attrs.get("label") or "").strip(),
        raw=str(line or ""),
    )

def parse_paragraph_heading_line(line: str) -> ParagraphHeadingBlock | None:
    m = PARAGRAPH_HEADING_LINE_RE.match(str(line or ""))

    if not m:
        return None

    body = str(m.group("body") or "").strip()

    title, attrs = parse_heading_body(body)

    return ParagraphHeadingBlock(
        title=title,
        label=str(attrs.get("label") or "").strip(),
        raw=str(line or ""),
    )

def flush_paragraph(
    *,
    parsed: ParsedWordTex,
    paragraph_lines: list[str],
    noindent: bool = False,
) -> None:
    if not paragraph_lines:
        return

    text = "\n".join(paragraph_lines).strip()

    if text:
        parsed.blocks.append(
            ParagraphBlock(
                text=text,
                noindent=bool(noindent),
            )
        )

    paragraph_lines.clear()


def parse_wordtex_source(source_text: str) -> ParsedWordTex:
    parsed = ParsedWordTex()

    text = str(source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    paragraph_lines: list[str] = []
    next_paragraph_noindent = False

    i = 0

    while i < len(lines):
        line = lines[i]

        if is_comment_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False
            i += 1
            continue

        if not str(line or "").strip():
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False
            i += 1
            continue

        if str(line or "").lstrip().startswith("\\title{"):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
            )

            body, next_index, raw = read_braced_command_block(
                lines=lines,
                start_index=i,
                command="title",
            )

            parsed.blocks.append(
                TitleBlock(
                    text=body,
                    raw=raw,
                )
            )

            i = next_index
            continue

        if str(line or "").lstrip().startswith("\\author{"):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
            )

            body, next_index, raw = read_braced_command_block(
                lines=lines,
                start_index=i,
                command="author",
            )

            parsed.blocks.append(
                AuthorBlock(
                    text=body.strip(),
                    raw=raw,
                )
            )

            i = next_index
            continue

        if str(line or "").lstrip().startswith("\\date{"):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
            )

            body, next_index, raw = read_braced_command_block(
                lines=lines,
                start_index=i,
                command="date",
            )

            parsed.blocks.append(
                DateBlock(
                    text=body.strip(),
                    raw=raw,
                )
            )

            i = next_index
            continue

        if is_table_of_contents_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
            )

            parsed.blocks.append(
                TableOfContentsBlock(
                    raw=str(line or ""),
                )
            )

            i += 1
            continue


        if is_newpage_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
            )

            parsed.blocks.append(
                NewPageBlock(
                    raw=str(line or ""),
                )
            )

            i += 1
            continue

        if is_vskip_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False

            block = parse_vskip_line(line)
            if block is not None:
                parsed.blocks.append(block)

            i += 1
            continue


        if is_noindent_line(line):
            # ------------------------------------------------------------
            # \noindent
            #
            # この行自体はWordへ出力しない。
            # 次に作られる ParagraphBlock だけ noindent=True にする。
            # \vskip などの直後でも効くように，ここでは flush しない。
            # ------------------------------------------------------------
            next_paragraph_noindent = True

            i += 1
            continue


        if is_section_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False

            heading_block = parse_section_line(line)
            if heading_block is not None:
                parsed.blocks.append(heading_block)

            i += 1
            continue


        if is_paragraph_heading_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False

            paragraph_heading_block = parse_paragraph_heading_line(line)
            if paragraph_heading_block is not None:
                parsed.blocks.append(paragraph_heading_block)

            i += 1
            continue       


        if is_itemize_begin_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False

            block, next_index, warnings = parse_itemize_block(
                lines=lines,
                start_index=i,
            )

            parsed.warnings.extend(warnings)

            if block is not None:
                parsed.blocks.append(block)

            i = next_index if next_index > i else i + 1
            continue

        if is_figure_begin_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False

            block, next_index, warnings = parse_figure_block(
                lines=lines,
                start_index=i,
            )

            parsed.warnings.extend(warnings)

            if block is not None:
                parsed.blocks.append(block)

            i = next_index if next_index > i else i + 1
            continue      

        if is_figure_table_begin_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False

            block, next_index, warnings = parse_figure_table_block(
                lines=lines,
                start_index=i,
            )

            parsed.warnings.extend(warnings)

            if block is not None:
                parsed.blocks.append(block)

            i = next_index if next_index > i else i + 1
            continue

        # ------------------------------------------------------------
        # table
        # ------------------------------------------------------------
        if is_table_begin_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False

            table_block, next_index, table_warnings = parse_table_block(
                lines=lines,
                start_index=i,
            )

            parsed.warnings.extend(table_warnings)

            if table_block is not None:
                parsed.blocks.append(table_block)

            i = next_index if next_index > i else i + 1
            continue


        if is_set_line(line):
            flush_paragraph(
                parsed=parsed,
                paragraph_lines=paragraph_lines,
                noindent=next_paragraph_noindent,
            )
            next_paragraph_noindent = False

            block, warnings = parse_set_line(line)
            parsed.warnings.extend(warnings)

            if block is not None:
                parsed.blocks.append(block)

            i += 1
            continue

        paragraph_lines.append(line)
        i += 1

    flush_paragraph(
        parsed=parsed,
        paragraph_lines=paragraph_lines,
        noindent=next_paragraph_noindent,
    )
    next_paragraph_noindent = False

    return parsed