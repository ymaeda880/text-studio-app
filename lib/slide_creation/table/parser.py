# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/table/parser.py
# ============================================================
# SlideTex 表構文解析
#
# 機能：
# - frame本文からtable環境を取得する
# - table環境のstyle・headerを解析する
# - 表題captionを取得する
# - 「//」で行を分割する
# - 「,」でセルを分割する
# - {...}で囲まれたセル内の区切り文字を保護する
# - <改行>をセル内改行へ変換する
# - <同上>・<同左>をセル結合指定へ変換する
#
# 方針：
# - PowerPoint描画処理には依存しない
# - 構文解析結果をTableDefinitionとして返す
# - 表の妥当性確認はvalidator.pyへ分離する
# - 1つのframe内では表を1つまで扱う
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import re
from dataclasses import dataclass

from lib.slide_creation.table.models import (
    TABLE_MERGE_LEFT,
    TABLE_MERGE_UP,
    TableCell,
    TableDefinition,
    TableHeaderSpec,
)
from lib.slide_creation.table.styles import (
    DEFAULT_TABLE_STYLE_KEY,
    TABLE_STYLE_KEYS,
)


# ============================================================
# 定数
# ============================================================
TABLE_LINE_SEPARATOR = "//"
TABLE_CELL_SEPARATOR = ","
TABLE_CELL_LINE_BREAK = "<改行>"


# ============================================================
# table環境解析結果
# ============================================================
@dataclass(frozen=True)
class TableEnvironmentMatch:
    # --------------------------------------------------------
    # table属性
    #
    # 例：
    #     style=grid,
    #     header={1,1}
    # --------------------------------------------------------
    attributes: str

    # --------------------------------------------------------
    # table本文
    # --------------------------------------------------------
    body: str

    # --------------------------------------------------------
    # frame本文内の開始・終了位置
    # --------------------------------------------------------
    start: int
    end: int

# ============================================================
# table環境取得
# ============================================================
def _find_matching_brace(
    text: str,
    *,
    opening_index: int,
) -> int | None:
    # ------------------------------------------------------------
    # opening_indexにある「{」と対応する「}」を取得する
    #
    # 中括弧の入れ子に対応する．
    # エスケープされた \{ と \} は構文括弧として扱わない．
    # ------------------------------------------------------------
    if (
        opening_index < 0
        or opening_index >= len(text)
        or text[opening_index] != "{"
    ):
        return None

    depth = 0
    escaped = False

    for index in range(
        opening_index,
        len(text),
    ):
        char = text[index]

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == "{":
            depth += 1
            continue

        if char == "}":
            depth -= 1

            if depth == 0:
                return index

            if depth < 0:
                return None

    return None


def _find_table_environments(
    frame_body: str,
) -> list[TableEnvironmentMatch]:
    # ------------------------------------------------------------
    # frame本文内のtable環境をすべて取得する
    #
    # 次のような属性内の中括弧にも対応する．
    #
    # \begin{table,
    #     style=grid,
    #     header={1,1}
    # }
    # ------------------------------------------------------------
    source = str(
        frame_body or ""
    )

    begin_pattern = re.compile(
        r"\\begin\s*\{\s*table\b",
        re.IGNORECASE,
    )

    end_pattern = re.compile(
        r"\\end\s*\{\s*table\s*\}",
        re.IGNORECASE,
    )

    matches: list[TableEnvironmentMatch] = []
    search_position = 0

    while True:
        begin_match = begin_pattern.search(
            source,
            search_position,
        )

        if begin_match is None:
            break

        # --------------------------------------------------------
        # \begin{table の後ろから，
        # 外側の属性終了「}」を探す
        # --------------------------------------------------------
        attribute_opening_index = source.find(
            "{",
            begin_match.start(),
        )

        if attribute_opening_index < 0:
            break

        attribute_closing_index = _find_matching_brace(
            source,
            opening_index=attribute_opening_index,
        )

        if attribute_closing_index is None:
            break

        # --------------------------------------------------------
        # \begin{table,...} の中身
        #
        # 「table」より後ろを属性として取得する
        # --------------------------------------------------------
        begin_inner_text = source[
            attribute_opening_index + 1:
            attribute_closing_index
        ]

        table_name_match = re.match(
            r"\s*table\b",
            begin_inner_text,
            flags=re.IGNORECASE,
        )

        if table_name_match is None:
            search_position = begin_match.end()
            continue

        attributes = begin_inner_text[
            table_name_match.end():
        ].strip()

        if attributes.startswith(","):
            attributes = attributes[1:].strip()

        # --------------------------------------------------------
        # 対応する \end{table} を探す
        # --------------------------------------------------------
        end_match = end_pattern.search(
            source,
            attribute_closing_index + 1,
        )

        if end_match is None:
            break

        body = source[
            attribute_closing_index + 1:
            end_match.start()
        ]

        matches.append(
            TableEnvironmentMatch(
                attributes=attributes,
                body=body,
                start=begin_match.start(),
                end=end_match.end(),
            )
        )

        search_position = end_match.end()

    return matches


# ============================================================
# caption
# ============================================================
_CAPTION_PATTERN = re.compile(
    r"\\caption\s*\{(?P<value>.*?)\}",
    re.DOTALL,
)


# ============================================================
# 文字列整形
# ============================================================
def _normalize_multiline_text(
    value: str,
) -> str:
    # ------------------------------------------------------------
    # 複数行記述を1つの文字列へ整える
    # ------------------------------------------------------------
    lines = [
        line.strip()
        for line in str(value or "").splitlines()
        if line.strip()
    ]

    return " ".join(
        lines,
    ).strip()


def _strip_outer_braces(
    value: str,
) -> str:
    # ------------------------------------------------------------
    # セル全体を囲む最外側の{...}だけを外す
    #
    # 例：
    # {3,000}
    #     -> 3,000
    #
    # {{A}}
    #     -> {A}
    # ------------------------------------------------------------
    text = str(value or "").strip()

    if (
        len(text) >= 2
        and text.startswith("{")
        and text.endswith("}")
    ):
        depth = 0

        for index, char in enumerate(text):
            if char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth < 0:
                    return text

                if (
                    depth == 0
                    and index < len(text) - 1
                ):
                    return text

        if depth == 0:
            return text[1:-1]

    return text


def _unescape_braces(
    value: str,
) -> str:
    # ------------------------------------------------------------
    # エスケープされた中括弧を通常文字へ戻す
    # ------------------------------------------------------------
    return (
        str(value or "")
        .replace(r"\{", "{")
        .replace(r"\}", "}")
    )


# ============================================================
# 属性分割
# ============================================================
def _split_attribute_parts(
    text: str,
) -> list[str]:
    # ------------------------------------------------------------
    # table属性をカンマで分割する
    #
    # header={1,1}のカンマは分割しない
    # 引用符内のカンマも分割しない
    # ------------------------------------------------------------
    parts: list[str] = []
    current: list[str] = []

    brace_depth = 0
    quote_char: str | None = None
    escaped = False

    for char in str(text or ""):
        if escaped:
            current.append(char)
            escaped = False
            continue

        if char == "\\":
            current.append(char)
            escaped = True
            continue

        if char in {'"', "'"}:
            if quote_char is None:
                quote_char = char

            elif quote_char == char:
                quote_char = None

            current.append(char)
            continue

        if quote_char is None:
            if char == "{":
                brace_depth += 1
                current.append(char)
                continue

            if char == "}":
                brace_depth = max(
                    0,
                    brace_depth - 1,
                )
                current.append(char)
                continue

            if (
                char == TABLE_CELL_SEPARATOR
                and brace_depth == 0
            ):
                part = "".join(
                    current,
                ).strip()

                if part:
                    parts.append(
                        part,
                    )

                current = []
                continue

        current.append(char)

    last_part = "".join(
        current,
    ).strip()

    if last_part:
        parts.append(
            last_part,
        )

    return parts


def _parse_table_attributes(
    attributes_text: str,
) -> dict[str, str]:
    # ------------------------------------------------------------
    # table環境のkey=valueを解析する
    # ------------------------------------------------------------
    text = str(
        attributes_text or ""
    ).strip()

    if text.startswith(","):
        text = text[1:]

    values: dict[str, str] = {}

    for part in _split_attribute_parts(
        text,
    ):
        if "=" not in part:
            continue

        key, raw_value = part.split(
            "=",
            1,
        )

        normalized_key = key.strip().lower()
        normalized_value = raw_value.strip()

        if (
            len(normalized_value) >= 2
            and (
                (
                    normalized_value.startswith('"')
                    and normalized_value.endswith('"')
                )
                or (
                    normalized_value.startswith("'")
                    and normalized_value.endswith("'")
                )
            )
        ):
            normalized_value = normalized_value[1:-1]

        if normalized_key:
            values[normalized_key] = (
                normalized_value.strip()
            )

    return values


# ============================================================
# header解析
# ============================================================
def _parse_non_negative_int(
    value: str,
    *,
    field_name: str,
    frame_number: int,
    errors: list[str],
) -> int | None:
    # ------------------------------------------------------------
    # 0以上の整数を解析する
    # ------------------------------------------------------------
    try:
        parsed = int(
            str(value or "").strip(),
        )

    except ValueError:
        errors.append(
            f"フレーム{frame_number}："
            f"tableの{field_name}は"
            "0以上の整数で指定してください："
            f"{value}"
        )
        return None

    if parsed < 0:
        errors.append(
            f"フレーム{frame_number}："
            f"tableの{field_name}は"
            "0以上で指定してください："
            f"{value}"
        )
        return None

    return parsed


def _parse_header_spec(
    raw_value: str,
    *,
    frame_number: int,
    errors: list[str],
) -> TableHeaderSpec:
    # ------------------------------------------------------------
    # header指定を解析する
    #
    # header={1}
    #     -> 1行，0列
    #
    # header={2}
    #     -> 2行，0列
    #
    # header={0,1}
    #     -> 0行，1列
    #
    # header={1,1}
    #     -> 1行，1列
    # ------------------------------------------------------------
    text = _strip_outer_braces(
        str(raw_value or "").strip(),
    )

    if not text:
        return TableHeaderSpec()

    parts = [
        part.strip()
        for part in text.split(",")
    ]

    if len(parts) == 1:
        row_count = _parse_non_negative_int(
            parts[0],
            field_name="header行数",
            frame_number=frame_number,
            errors=errors,
        )

        if row_count is None:
            return TableHeaderSpec()

        return TableHeaderSpec(
            row_count=row_count,
            column_count=0,
        )

    if len(parts) == 2:
        row_count = _parse_non_negative_int(
            parts[0],
            field_name="header行数",
            frame_number=frame_number,
            errors=errors,
        )

        column_count = _parse_non_negative_int(
            parts[1],
            field_name="header列数",
            frame_number=frame_number,
            errors=errors,
        )

        if (
            row_count is None
            or column_count is None
        ):
            return TableHeaderSpec()

        return TableHeaderSpec(
            row_count=row_count,
            column_count=column_count,
        )

    errors.append(
        f"フレーム{frame_number}："
        "tableのheaderは"
        "header={行数}または"
        "header={行数,列数}で指定してください："
        f"{raw_value}"
    )

    return TableHeaderSpec()


# ============================================================
# 区切り文字による分割
# ============================================================
def _split_outside_braces(
    text: str,
    *,
    separator: str,
) -> list[str]:
    # ------------------------------------------------------------
    # 中括弧の外側にある区切り文字だけで分割する
    #
    # separatorは「,」または「//」を想定する
    # ------------------------------------------------------------
    source = str(text or "")

    parts: list[str] = []
    current: list[str] = []

    brace_depth = 0
    quote_char: str | None = None
    escaped = False

    index = 0

    while index < len(source):
        char = source[index]

        if escaped:
            current.append(char)
            escaped = False
            index += 1
            continue

        if char == "\\":
            current.append(char)
            escaped = True
            index += 1
            continue

        if char in {'"', "'"}:
            if quote_char is None:
                quote_char = char

            elif quote_char == char:
                quote_char = None

            current.append(char)
            index += 1
            continue

        if quote_char is None:
            if char == "{":
                brace_depth += 1
                current.append(char)
                index += 1
                continue

            if char == "}":
                brace_depth = max(
                    0,
                    brace_depth - 1,
                )
                current.append(char)
                index += 1
                continue

            if (
                brace_depth == 0
                and source.startswith(
                    separator,
                    index,
                )
            ):
                parts.append(
                    "".join(current),
                )
                current = []
                index += len(separator)
                continue

        current.append(char)
        index += 1

    parts.append(
        "".join(current),
    )

    return parts


# ============================================================
# セル解析
# ============================================================
def _parse_cell(
    raw_value: str,
) -> TableCell:
    # ------------------------------------------------------------
    # 1セルをTableCellへ変換する
    # ------------------------------------------------------------
    text = _strip_outer_braces(
        str(raw_value or "").strip(),
    )

    text = _unescape_braces(
        text,
    )

    text = text.replace(
        TABLE_CELL_LINE_BREAK,
        "\n",
    )

    normalized = text.strip()

    if normalized == TABLE_MERGE_UP:
        return TableCell(
            text="",
            merge_direction="up",
        )

    if normalized == TABLE_MERGE_LEFT:
        return TableCell(
            text="",
            merge_direction="left",
        )

    return TableCell(
        text=normalized,
        merge_direction="",
    )


def _parse_table_rows(
    body_text: str,
) -> tuple[tuple[TableCell, ...], ...]:
    # ------------------------------------------------------------
    # 表本文を行・セルへ分割する
    # ------------------------------------------------------------
    raw_rows = _split_outside_braces(
        body_text,
        separator=TABLE_LINE_SEPARATOR,
    )

    rows: list[tuple[TableCell, ...]] = []

    for raw_row in raw_rows:
        normalized_row = str(
            raw_row or ""
        ).strip()

        if not normalized_row:
            continue

        raw_cells = _split_outside_braces(
            normalized_row,
            separator=TABLE_CELL_SEPARATOR,
        )

        cells = tuple(
            _parse_cell(
                raw_cell,
            )
            for raw_cell in raw_cells
        )

        rows.append(
            cells,
        )

    return tuple(
        rows,
    )


# ============================================================
# caption取得
# ============================================================
def _extract_caption(
    table_body: str,
) -> tuple[str, str]:
    # ------------------------------------------------------------
    # captionとcaption除去後の本文を返す
    # ------------------------------------------------------------
    match = _CAPTION_PATTERN.search(
        table_body,
    )

    if match is None:
        return (
            "",
            table_body,
        )

    caption = _normalize_multiline_text(
        match.group("value"),
    )

    body_without_caption = (
        table_body[:match.start()]
        + table_body[match.end():]
    )

    return (
        caption,
        body_without_caption,
    )


# ============================================================
# 公開関数
# ============================================================
def extract_table_definition(
    frame_body: str,
    *,
    frame_number: int,
    errors: list[str],
    warnings: list[str],
) -> TableDefinition | None:
    # ------------------------------------------------------------
    # frame本文から表定義を取得する
    #
    # 表がない場合はNoneを返す
    # ------------------------------------------------------------
    matches = _find_table_environments(
        frame_body,
    )

    if not matches:
        return None

    if len(matches) > 1:
        errors.append(
            f"フレーム{frame_number}："
            "1つのframe内にtableを"
            "複数指定することはできません．"
        )
        return None

    match = matches[0]

    attributes = _parse_table_attributes(
        match.attributes,
    )

    # ------------------------------------------------------------
    # style
    # ------------------------------------------------------------
    style_key = (
        attributes.get(
            "style",
            DEFAULT_TABLE_STYLE_KEY,
        )
        .strip()
        .lower()
    )

    if not style_key:
        style_key = DEFAULT_TABLE_STYLE_KEY

    if style_key not in TABLE_STYLE_KEYS:
        errors.append(
            f"フレーム{frame_number}："
            "未対応のtableスタイルです："
            f"{style_key}．"
            "使用可能："
            + "，".join(
                sorted(
                    TABLE_STYLE_KEYS,
                )
            )
        )

    # ------------------------------------------------------------
    # header
    # ------------------------------------------------------------
    header = _parse_header_spec(
        attributes.get(
            "header",
            "",
        ),
        frame_number=frame_number,
        errors=errors,
    )

    # ------------------------------------------------------------
    # font_size
    # ------------------------------------------------------------
    font_size: int | None = None

    raw_font_size = str(
        attributes.get(
            "font_size",
            "",
        )
        or ""
    ).strip()

    if raw_font_size:
        try:
            parsed_font_size = int(
                raw_font_size
            )

        except ValueError:
            errors.append(
                f"フレーム{frame_number}："
                "tableのfont_sizeは"
                "整数で指定してください："
                f"{raw_font_size}"
            )

        else:
            if parsed_font_size <= 0:
                errors.append(
                    f"フレーム{frame_number}："
                    "tableのfont_sizeは"
                    "1以上で指定してください："
                    f"{raw_font_size}"
                )

            else:
                font_size = parsed_font_size

    # ------------------------------------------------------------
    # caption・表本文
    # ------------------------------------------------------------
    caption, table_data_text = _extract_caption(
        match.body,
    )

    rows = _parse_table_rows(
        table_data_text,
    )

    if not rows:
        errors.append(
            f"フレーム{frame_number}："
            "tableに行データがありません．"
        )
        return None

    if not caption:
        warnings.append(
            f"フレーム{frame_number}："
            "tableに\\caption{...}がありません．"
        )

    return TableDefinition(
        style_key=style_key,
        font_size=font_size,
        caption=caption,
        header=header,
        rows=rows,
    )

def remove_table_environment(
    frame_body: str,
) -> str:
    # ------------------------------------------------------------
    # frame本文からtable環境をすべて除去する
    #
    # 後ろから削除することで，
    # 先に取得した文字位置がずれないようにする
    # ------------------------------------------------------------
    source = str(
        frame_body or ""
    )

    matches = _find_table_environments(
        source,
    )

    if not matches:
        return source

    result = source

    for match in reversed(
        matches,
    ):
        result = (
            result[:match.start]
            + result[match.end:]
        )

    return result