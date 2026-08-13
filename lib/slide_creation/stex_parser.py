# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/stex_parser.py
# ============================================================
# SlideTex（.stex）構文解析
#
# 機能：
# - \set{...}から資料全体の設定を取得する
# - \begin{frame, type=..., style=...}を解析する
# - frame内のtitle，subtitle，itemize，画像指定などを取得する
# - PresentationSettingsとSlideDefinitionへ変換する
#
# 方針：
# - LaTeXやBeamerではなく独自記法として解析する
# - typeはスライドの役割を表す
# - styleはスライドのデザインを表す
# - UTF-8またはUTF-8 BOM付きファイルを受け付ける
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import re
from dataclasses import dataclass, field

from lib.slide_creation.models import (
    ContentDefinition,
    PresentationSettings,
    RegionDefinition,
    SlideDefinition,
)
from lib.slide_creation.content_layouts.registry import (
    CONTENT_LAYOUT_REGIONS,
)

from lib.slide_creation.table.parser import (
    extract_table_definition,
    remove_table_environment,
)
from lib.slide_creation.table.validator import (
    validate_table_definition,
)

from lib.slide_creation.themes import (
    DEFAULT_FOOTER_KEY,
    DEFAULT_HEADER_KEY,
    DEFAULT_THEME_KEY,
    FOOTER_STYLES,
    HEADER_STYLES,
    SLIDE_STYLE_MAP,
    SLIDE_THEMES,
    SLIDE_TYPES,
    get_default_style_key,
)


# ============================================================
# 解析結果
# ============================================================
@dataclass
class StexParseResult:
    settings: PresentationSettings
    slides: list[SlideDefinition]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors and bool(self.slides)


# ============================================================
# 正規表現
# ============================================================
_SET_PATTERN = re.compile(
    r"\\set\s*\{(?P<body>.*?)\}",
    re.DOTALL,
)

_FRAME_PATTERN = re.compile(
    r"\\begin\s*\{\s*frame\s*,(?P<attributes>.*?)\}"
    r"(?P<body>.*?)"
    r"\\end\s*\{\s*frame\s*\}",
    re.DOTALL,
)

_ITEMIZE_PATTERN = re.compile(
    r"\\begin\s*\{\s*itemize\b.*?\}"
    r"(?P<body>.*?)"
    r"\\end\s*\{\s*itemize\s*\}",
    re.DOTALL,
)


# ============================================================
# コメント除去
# ============================================================
def _remove_comments(text: str) -> str:
    lines: list[str] = []

    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            continue

        lines.append(line)

    return "\n".join(lines)


# ============================================================
# 値の整形
# ============================================================
def _clean_value(value: str) -> str:
    cleaned = value.strip()

    if len(cleaned) >= 2:
        if (
            cleaned.startswith('"')
            and cleaned.endswith('"')
        ):
            cleaned = cleaned[1:-1]

        elif (
            cleaned.startswith("'")
            and cleaned.endswith("'")
        ):
            cleaned = cleaned[1:-1]

    return cleaned.strip()


# ============================================================
# key=value解析
# ============================================================
def _parse_key_value_block(
    text: str,
) -> dict[str, str]:
    values: dict[str, str] = {}
    parts: list[str] = []
    current: list[str] = []
    quote_char: str | None = None

    for char in text:
        if char in {'"', "'"}:
            if quote_char is None:
                quote_char = char

            elif quote_char == char:
                quote_char = None

            current.append(char)
            continue

        if char == "," and quote_char is None:
            part = "".join(current).strip()

            if part:
                parts.append(part)

            current = []
            continue

        current.append(char)

    last_part = "".join(current).strip()

    if last_part:
        parts.append(last_part)

    for part in parts:
        if "=" not in part:
            continue

        key, value = part.split("=", 1)
        normalized_key = key.strip().lower()

        if normalized_key:
            values[normalized_key] = _clean_value(value)

    return values


# ============================================================
# 本文レイアウト比率解析
# ============================================================
def _parse_layout_ratio(
    raw_value: str,
    *,
    layout_key: str,
    frame_number: int,
    errors: list[str],
) -> tuple[float, ...]:
    ratio_text = str(raw_value or "").strip()
    if not ratio_text:
        return ()
    expected_counts = {
        "full": 1,
        "two_column": 2,
        "three_column": 3,
        "two_row": 2,
        "sidebar": 2,
    }
    expected_count = expected_counts.get(layout_key)
    parts = [part.strip() for part in ratio_text.split(":")]
    if expected_count is None or len(parts) != expected_count:
        errors.append(
            f"フレーム{frame_number}：layout={layout_key}のratioは，"
            f"{expected_count or 0}個の正の数を「:」で区切って指定してください．"
        )
        return ()
    values: list[float] = []
    for part in parts:
        try:
            value = float(part)
        except ValueError:
            errors.append(f"フレーム{frame_number}：ratioは数値で指定してください：{ratio_text}")
            return ()
        if value <= 0:
            errors.append(f"フレーム{frame_number}：ratioは0より大きい数で指定してください：{ratio_text}")
            return ()
        values.append(value)
    return tuple(values)

# ============================================================
# フォント属性解析
# ============================================================
def _parse_optional_positive_int(
    raw_value: str,
    *,
    attribute_name: str,
    frame_number: int,
    errors: list[str],
) -> int | None:
    value_text = str(raw_value or "").strip()
    if not value_text:
        return None
    try:
        value = int(value_text)
    except ValueError:
        errors.append(
            f"フレーム{frame_number}：{attribute_name}は"
            f"正の整数で指定してください：{value_text}"
        )
        return None
    if value <= 0:
        errors.append(
            f"フレーム{frame_number}：{attribute_name}は"
            "0より大きい整数で指定してください．"
        )
        return None
    return value

# ============================================================
# 単一コマンド取得
# ============================================================
def _extract_command_value(
    frame_body: str,
    command: str,
) -> str:
    pattern = re.compile(
        rf"\\{re.escape(command)}\s*"
        rf"\{{(?P<value>.*?)\}}",
        re.DOTALL,
    )

    match = pattern.search(frame_body)

    if not match:
        return ""

    return match.group("value").strip()


# ============================================================
# Region内コンテンツ解析
# ============================================================
_TEXT_ENVIRONMENT_NAMES = {
    "text",
    "itemize",
    "image",
    "imagecaption",
    "description",
    "note",
}


@dataclass(frozen=True)
class _EnvironmentMatch:
    name: str
    attributes: str
    body: str
    start: int
    end: int


def _find_matching_brace(
    text: str,
    *,
    opening_index: int,
) -> int | None:
    if (
        opening_index < 0
        or opening_index >= len(text)
        or text[opening_index] != "{"
    ):
        return None

    depth = 0
    escaped = False

    for index in range(opening_index, len(text)):
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


def _normalize_content_text(value: str) -> str:
    return "\n".join(
        line.strip()
        for line in str(value or "").splitlines()
        if line.strip()
    )


def _extract_items(text: str) -> list[str]:
    item_matches = re.findall(
        r"\\item\s+(.*?)(?=\\item|\Z)",
        text,
        flags=re.DOTALL,
    )

    items: list[str] = []

    for item in item_matches:
        cleaned = " ".join(
            line.strip()
            for line in item.splitlines()
            if line.strip()
        )
        if cleaned:
            items.append(cleaned)

    return items


def _find_named_environments(text: str) -> list[_EnvironmentMatch]:
    source = str(text or "")
    begin_pattern = re.compile(
        r"\\begin\s*\{\s*"
        r"(?P<name>text|itemize|image|imagecaption|description|note|table)\b",
        re.IGNORECASE,
    )
    matches: list[_EnvironmentMatch] = []
    search_position = 0

    while True:
        begin_match = begin_pattern.search(source, search_position)
        if begin_match is None:
            break

        name = begin_match.group("name").lower()
        opening_index = source.find("{", begin_match.start())
        closing_index = _find_matching_brace(
            source,
            opening_index=opening_index,
        )
        if closing_index is None:
            break

        begin_inner = source[opening_index + 1:closing_index]
        name_match = re.match(
            rf"\s*{re.escape(name)}\b",
            begin_inner,
            flags=re.IGNORECASE,
        )
        if name_match is None:
            search_position = begin_match.end()
            continue

        attributes = begin_inner[name_match.end():].strip()
        if attributes.startswith(","):
            attributes = attributes[1:].strip()

        end_pattern = re.compile(
            rf"\\end\s*\{{\s*{re.escape(name)}\s*\}}",
            re.IGNORECASE,
        )
        end_match = end_pattern.search(source, closing_index + 1)
        if end_match is None:
            break

        matches.append(
            _EnvironmentMatch(
                name=name,
                attributes=attributes,
                body=source[closing_index + 1:end_match.start()],
                start=begin_match.start(),
                end=end_match.end(),
            )
        )
        search_position = end_match.end()

    return matches


def _find_legacy_commands(text: str) -> list[_EnvironmentMatch]:
    pattern = re.compile(
        r"\\(?P<name>image|imagecaption|description|note)\s*\{",
        re.IGNORECASE,
    )
    source = str(text or "")
    matches: list[_EnvironmentMatch] = []

    for match in pattern.finditer(source):
        opening_index = source.find("{", match.start())
        closing_index = _find_matching_brace(
            source,
            opening_index=opening_index,
        )
        if closing_index is None:
            continue

        matches.append(
            _EnvironmentMatch(
                name=match.group("name").lower(),
                attributes="",
                body=source[opening_index + 1:closing_index],
                start=match.start(),
                end=closing_index + 1,
            )
        )

    return matches


def _parse_content_font_attributes(
    attributes_text: str,
    *,
    content_name: str,
    frame_number: int,
    errors: list[str],
) -> tuple[str, int | None]:
    attributes = _parse_key_value_block(attributes_text)
    allowed_attributes = {"font_name", "font_size"}

    for attribute_name in attributes:
        if attribute_name not in allowed_attributes:
            errors.append(
                f"フレーム{frame_number}：{content_name}では"
                f"{attribute_name}属性を使用できません．"
            )

    font_size = _parse_optional_positive_int(
        attributes.get("font_size", ""),
        attribute_name=f"{content_name}のfont_size",
        frame_number=frame_number,
        errors=errors,
    )
    return (
        attributes.get("font_name", "").strip(),
        font_size,
    )

# ============================================================
# Region内コンテンツ生成
# ============================================================
def _content_from_match(
    match: _EnvironmentMatch,
    *,
    frame_number: int,
    errors: list[str],
    warnings: list[str],
) -> ContentDefinition | None:
    # --------------------------------------------------------
    # table
    #
    # tableは，
    # style・header・font_sizeなどの専用属性を持つため，
    # 共通フォント属性解析を通さず，
    # table.parserへ解析を委譲する．
    # --------------------------------------------------------
    if match.name == "table":
        table_source = (
            "\\begin{table,"
            + match.attributes
            + "}\n"
            + match.body
            + "\n\\end{table}"
            if match.attributes
            else (
                "\\begin{table}\n"
                + match.body
                + "\n\\end{table}"
            )
        )

        table = extract_table_definition(
            table_source,
            frame_number=frame_number,
            errors=errors,
            warnings=warnings,
        )

        if table is None:
            return None

        errors.extend(
            validate_table_definition(
                table,
                frame_number=frame_number,
            )
        )

        return ContentDefinition(
            content_type="table",
            table=table,
        )

    # --------------------------------------------------------
    # table以外の共通フォント属性
    #
    # text・itemize・image・imagecaption・description・noteは，
    # font_name・font_sizeを共通属性として扱う．
    # --------------------------------------------------------
    font_name, font_size = _parse_content_font_attributes(
        match.attributes,
        content_name=match.name,
        frame_number=frame_number,
        errors=errors,
    )

    # --------------------------------------------------------
    # itemize
    # --------------------------------------------------------
    if match.name == "itemize":
        items = _extract_items(
            match.body,
        )

        if not items:
            warnings.append(
                f"フレーム{frame_number}："
                "itemizeに\\itemがありません．"
            )

        return ContentDefinition(
            content_type="itemize",
            text="\n".join(
                items,
            ),
            font_name=font_name,
            font_size=font_size,
        )

    # --------------------------------------------------------
    # 本文整形
    # --------------------------------------------------------
    normalized_text = _normalize_content_text(
        match.body,
    )

    if not normalized_text:
        warnings.append(
            f"フレーム{frame_number}："
            f"{match.name}の内容が空です．"
        )

    # --------------------------------------------------------
    # image
    # --------------------------------------------------------
    if match.name == "image":
        return ContentDefinition(
            content_type="image",
            image_file=normalized_text,
            font_name=font_name,
            font_size=font_size,
        )

    # --------------------------------------------------------
    # text・imagecaption・description・note
    # --------------------------------------------------------
    return ContentDefinition(
        content_type=match.name,
        text=normalized_text,
        font_name=font_name,
        font_size=font_size,
    )

def _append_plain_text_content(
    contents: list[tuple[int, ContentDefinition]],
    *,
    text: str,
    start: int,
) -> None:
    normalized = _normalize_content_text(text)
    if normalized:
        contents.append(
            (
                start,
                ContentDefinition(
                    content_type="text",
                    text=normalized,
                ),
            )
        )


def _parse_region_contents(
    region_body: str,
    *,
    region_name: str,
    frame_number: int,
    errors: list[str],
    warnings: list[str],
) -> list[ContentDefinition]:
    source = str(region_body or "")
    environment_matches = _find_named_environments(source)
    occupied_ranges = [
        (match.start, match.end)
        for match in environment_matches
    ]

    legacy_matches = [
        match
        for match in _find_legacy_commands(source)
        if not any(
            start <= match.start < end
            for start, end in occupied_ranges
        )
    ]

    all_matches = sorted(
        environment_matches + legacy_matches,
        key=lambda value: value.start,
    )

    parsed_contents: list[tuple[int, ContentDefinition]] = []
    cursor = 0

    for match in all_matches:
        if match.start < cursor:
            continue

        _append_plain_text_content(
            parsed_contents,
            text=source[cursor:match.start],
            start=cursor,
        )

        error_count_before = len(errors)
        content = _content_from_match(
            match,
            frame_number=frame_number,
            errors=errors,
            warnings=warnings,
        )
        if len(errors) == error_count_before and content is not None:
            parsed_contents.append((match.start, content))

        cursor = match.end

    _append_plain_text_content(
        parsed_contents,
        text=source[cursor:],
        start=cursor,
    )

    return [
        content
        for _position, content in sorted(
            parsed_contents,
            key=lambda value: value[0],
        )
    ]


def _extract_itemize_lines(frame_body: str) -> list[str]:
    for match in _find_named_environments(frame_body):
        if match.name == "itemize":
            return _extract_items(match.body)
    return []


def _extract_environment_items(
    frame_body: str,
    environment_name: str,
) -> list[str]:
    pattern = re.compile(
        rf"\\begin\s*\{{\s*{re.escape(environment_name)}\s*\}}"
        rf"(?P<body>.*?)"
        rf"\\end\s*\{{\s*{re.escape(environment_name)}\s*\}}",
        re.DOTALL,
    )
    match = pattern.search(frame_body)
    return _extract_items(match.group("body")) if match else []


# ============================================================
# Region環境取得・解析
# ============================================================
def _parse_regions(
    frame_body: str,
    *,
    layout_key: str,
    frame_number: int,
    errors: list[str],
    warnings: list[str],
) -> list[RegionDefinition]:
    allowed_names = CONTENT_LAYOUT_REGIONS[layout_key]
    all_region_names = {
        name
        for names in CONTENT_LAYOUT_REGIONS.values()
        for name in names
    }
    regions: list[RegionDefinition] = []

    for region_name in sorted(all_region_names):
        pattern = re.compile(
            rf"\\begin\s*\{{\s*{re.escape(region_name)}\s*"
            rf"(?P<attributes>,.*?)?\}}"
            rf"(?P<body>.*?)"
            rf"\\end\s*\{{\s*{re.escape(region_name)}\s*\}}",
            re.DOTALL,
        )
        matches = list(pattern.finditer(frame_body))

        if len(matches) > 1:
            errors.append(
                f"フレーム{frame_number}：{region_name}領域が重複しています．"
            )
            continue
        if not matches:
            continue

        match = matches[0]
        if region_name not in allowed_names:
            errors.append(
                f"フレーム{frame_number}：layout={layout_key}では"
                f"{region_name}領域を使用できません．使用可能："
                + "，".join(allowed_names)
            )
            continue

        raw_attributes = str(match.group("attributes") or "").lstrip(",")
        region_attributes = _parse_key_value_block(raw_attributes)
        error_count_before = len(errors)
        region_font_size = _parse_optional_positive_int(
            region_attributes.get("font_size", ""),
            attribute_name=f"{region_name}領域のfont_size",
            frame_number=frame_number,
            errors=errors,
        )
        if len(errors) > error_count_before:
            continue

        regions.append(
            RegionDefinition(
                name=region_name,
                font_name=region_attributes.get("font_name", "").strip(),
                font_size=region_font_size,
                contents=_parse_region_contents(
                    match.group("body"),
                    region_name=region_name,
                    frame_number=frame_number,
                    errors=errors,
                    warnings=warnings,
                ),
            )
        )

    if not regions:
        errors.append(
            f"フレーム{frame_number}：layout={layout_key}ですが，領域がありません．"
            "使用可能：" + "，".join(allowed_names)
        )

    return regions


# ============================================================
# 未処理本文取得
# ============================================================
def _extract_plain_body(
    frame_body: str,
) -> str:
    text = frame_body

    # --------------------------------------------------------
    # table環境を通常本文から除外する
    # --------------------------------------------------------
    text = remove_table_environment(
        text,
    )

    text = _ITEMIZE_PATTERN.sub("", text)

    for environment_name in (
        "left", "center", "right",
        "top", "bottom", "full",
        "sidebar", "main",
    ):
        text = re.sub(
            rf"\\begin\s*\{{\s*"
            rf"{environment_name}"
            rf"\s*\}}"
            rf".*?"
            rf"\\end\s*\{{\s*"
            rf"{environment_name}"
            rf"\s*\}}",
            "",
            text,
            flags=re.DOTALL,
        )

    known_commands = (
        "title",
        "subtitle",
        "sectionnumber",
        "presenter",
        "contact",
        "message",
        "lefttitle",
        "righttitle",
        "image",
        "imagecaption",
        "description",
        "note",
    )

    for command in known_commands:
        text = re.sub(
            rf"\\{command}\s*\{{.*?\}}",
            "",
            text,
            flags=re.DOTALL,
        )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return "\n".join(lines)


# ============================================================
# 資料全体設定
# ============================================================
def _parse_settings(
    text: str,
    *,
    errors: list[str],
    warnings: list[str],
) -> PresentationSettings:
    match = _SET_PATTERN.search(text)

    if match:
        values = _parse_key_value_block(
            match.group("body")
        )

    else:
        values = {}
        warnings.append(
            "\\set{...}がないため，"
            "既定の設定を使用します．"
        )

    theme_key = values.get(
        "theme",
        DEFAULT_THEME_KEY,
    )
    header_key = values.get(
        "header",
        DEFAULT_HEADER_KEY,
    )
    footer_key = values.get(
        "footer",
        DEFAULT_FOOTER_KEY,
    )

    if theme_key not in SLIDE_THEMES:
        errors.append(
            f"未登録のテーマです：theme={theme_key}"
        )

    if header_key not in HEADER_STYLES:
        errors.append(
            f"未登録のヘッダーです：header={header_key}"
        )

    if footer_key not in FOOTER_STYLES:
        errors.append(
            f"未登録のフッターです：footer={footer_key}"
        )

    return PresentationSettings(
        presentation_title=values.get(
            "title",
            "SlideTex資料",
        ),
        company_name=values.get("company", ""),
        presenter_name=values.get("presenter", ""),
        presentation_date=values.get("date", ""),
        theme_key=theme_key,
        header_key=header_key,
        footer_key=footer_key,
        image_path=values.get(
            "image_path",
            "inbox",
        ),
    )


# ============================================================
# 1フレーム解析
# ============================================================
def _parse_frame(
    *,
    frame_number: int,
    attributes_text: str,
    frame_body: str,
    errors: list[str],
    warnings: list[str],
) -> SlideDefinition | None:
    attributes = _parse_key_value_block(
        attributes_text
    )

    slide_type = attributes.get("type", "").strip()
    style_key = attributes.get("style", "").strip()
    layout_key = attributes.get("layout", "").strip()
    ratio_text = attributes.get("ratio", "").strip()
    frame_font_name = attributes.get("font_name", "").strip()
    error_count_before_fonts = len(errors)
    title_font_size = _parse_optional_positive_int(
        attributes.get("title_font_size", ""),
        attribute_name="title_font_size",
        frame_number=frame_number,
        errors=errors,
    )
    body_font_size = _parse_optional_positive_int(
        attributes.get("body_font_size", ""),
        attribute_name="body_font_size",
        frame_number=frame_number,
        errors=errors,
    )
    if len(errors) > error_count_before_fonts:
        return None

    if not slide_type:
        errors.append(
            f"フレーム{frame_number}："
            "typeが指定されていません．"
        )
        return None

    if slide_type not in SLIDE_TYPES:
        errors.append(
            f"フレーム{frame_number}："
            f"未登録のtypeです：{slide_type}"
        )
        return None

    if layout_key:
        if slide_type != "content":
            errors.append(
                f"フレーム{frame_number}："
                "layoutはtype=contentで指定してください．"
            )
            return None

        if layout_key not in CONTENT_LAYOUT_REGIONS:
            errors.append(
                f"フレーム{frame_number}："
                f"未登録のlayoutです：{layout_key}．"
                "使用可能："
                + "，".join(sorted(CONTENT_LAYOUT_REGIONS))
            )
            return None

    if ratio_text and not layout_key:
        errors.append(
            f"フレーム{frame_number}：ratioを指定する場合はlayoutも指定してください．"
        )
        return None

    layout_ratio = (
        _parse_layout_ratio(
            ratio_text,
            layout_key=layout_key,
            frame_number=frame_number,
            errors=errors,
        )
        if layout_key
        else ()
    )
    if ratio_text and not layout_ratio:
        return None

    if not style_key:
        style_key = (
            "default"
            if layout_key
            else get_default_style_key(slide_type)
        )

        warnings.append(
            f"フレーム{frame_number}："
            f"styleが未指定のため，"
            f"style={style_key}を使用します．"
        )

    available_styles = SLIDE_STYLE_MAP.get(
        slide_type,
        {},
    )

    if style_key not in available_styles:
        errors.append(
            f"フレーム{frame_number}："
            f"type={slide_type}では"
            f"style={style_key}を使用できません．"
        )
        return None

    title = _extract_command_value(frame_body, "title")
    subtitle = _extract_command_value(frame_body, "subtitle")
    section_number = _extract_command_value(frame_body, "sectionnumber")
    presenter_name = _extract_command_value(frame_body, "presenter")
    contact_text = _extract_command_value(frame_body, "contact")
    message = _extract_command_value(frame_body, "message")
    left_heading = _extract_command_value(frame_body, "lefttitle")
    right_heading = _extract_command_value(frame_body, "righttitle")

    # --------------------------------------------------------
    # 新しいlayout・Region構文
    # --------------------------------------------------------
    if layout_key:
        error_count_before_regions = len(errors)

        regions = _parse_regions(
            frame_body,
            layout_key=layout_key,
            frame_number=frame_number,
            errors=errors,
            warnings=warnings,
        )

        if len(errors) > error_count_before_regions:
            return None

        body = ""
        image_file = ""
        image_caption = ""
        description = ""
        note = ""
        table = None

    # --------------------------------------------------------
    # 従来構文
    # --------------------------------------------------------
    else:
        image_file = _extract_command_value(frame_body, "image")
        image_caption = _extract_command_value(frame_body, "imagecaption")
        description = _extract_command_value(frame_body, "description")
        note = _extract_command_value(frame_body, "note")

        itemize_lines = _extract_itemize_lines(frame_body)
        left_lines = _extract_environment_items(frame_body, "left")
        right_lines = _extract_environment_items(frame_body, "right")

        table = extract_table_definition(
            frame_body,
            frame_number=frame_number,
            errors=errors,
            warnings=warnings,
        )

        if table is not None:
            errors.extend(
                validate_table_definition(
                    table,
                    frame_number=frame_number,
                )
            )

        if style_key in {"two_column", "comparison"}:
            body_lines: list[str] = []
            body_lines.extend(left_lines)
            body_lines.extend(right_lines)

            if not body_lines:
                body_lines = itemize_lines

            body = "\n".join(body_lines)

        elif itemize_lines:
            body = "\n".join(itemize_lines)

        elif message:
            body = message

        else:
            body = _extract_plain_body(frame_body)

        regions = []

        if (
            slide_type == "content"
            and style_key == "text_image"
            and not image_file
        ):
            errors.append(
                f"フレーム{frame_number}："
                "style=text_imageでは"
                "\\image{...}を指定してください．"
            )
            return None

        if (
            slide_type == "content"
            and style_key in {"table", "text_table"}
            and table is None
        ):
            errors.append(
                f"フレーム{frame_number}："
                f"style={style_key}では"
                "\\begin{table,...}から"
                "\\end{table}までを指定してください．"
            )
            return None

        if table is not None and slide_type != "content":
            errors.append(
                f"フレーム{frame_number}："
                "tableはtype=contentの"
                "フレーム内で使用してください．"
            )
            return None

    if not title:
        warnings.append(
            f"フレーム{frame_number}："
            "\\title{...}がありません．"
        )

    return SlideDefinition(
        slide_type=slide_type,
        style_key=style_key,
        title=title,
        subtitle=subtitle,
        body=body,
        section_number=section_number,
        left_heading=left_heading,
        right_heading=right_heading,
        presenter_name=presenter_name,
        contact_text=contact_text,
        layout_key=layout_key,
        layout_ratio=layout_ratio,
        font_name=frame_font_name,
        title_font_size=title_font_size,
        body_font_size=body_font_size,
        regions=regions,
        description=description,
        note=note,
        image_file=image_file,
        image_caption=image_caption,
        table=table,
    )


# ============================================================
# 公開関数
# ============================================================
def parse_stex_text(
    text: str,
) -> StexParseResult:
    errors: list[str] = []
    warnings: list[str] = []

    default_settings = PresentationSettings(
        presentation_title="SlideTex資料",
    )

    if not text.strip():
        return StexParseResult(
            settings=default_settings,
            slides=[],
            errors=[".stexファイルが空です．"],
        )

    cleaned_text = _remove_comments(text)

    settings = _parse_settings(
        cleaned_text,
        errors=errors,
        warnings=warnings,
    )

    frame_matches = list(
        _FRAME_PATTERN.finditer(cleaned_text)
    )

    slides: list[SlideDefinition] = []

    if not frame_matches:
        errors.append(
            "\\begin{frame, type=...}から"
            "\\end{frame}までのフレームがありません．"
        )

    for frame_number, match in enumerate(
        frame_matches,
        start=1,
    ):
        slide = _parse_frame(
            frame_number=frame_number,
            attributes_text=match.group(
                "attributes"
            ),
            frame_body=match.group("body"),
            errors=errors,
            warnings=warnings,
        )

        if slide is not None:
            slides.append(slide)

    return StexParseResult(
        settings=settings,
        slides=slides,
        errors=errors,
        warnings=warnings,
    )


def parse_stex_bytes(
    data: bytes,
) -> StexParseResult:
    try:
        text = data.decode("utf-8-sig")

    except UnicodeDecodeError as exc:
        return StexParseResult(
            settings=PresentationSettings(
                presentation_title="SlideTex資料",
            ),
            slides=[],
            errors=[
                "UTF-8で.stexファイルを"
                f"読み込めませんでした：{exc}"
            ],
        )

    return parse_stex_text(text)