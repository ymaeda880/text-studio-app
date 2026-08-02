# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/stex_parser.py
# ============================================================
# SlideTex（.stex）構文解析
#
# 機能：
# - \set{...}から資料全体の設定を取得する
# - \begin{frame, type=..., style=...}を解析する
# - frame内のtitle，subtitle，itemizeなどを取得する
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
    PresentationSettings,
    SlideDefinition,
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
    r"\\begin\s*\{\s*itemize\s*\}"
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
# itemize取得
# ============================================================
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


def _extract_itemize_lines(
    frame_body: str,
) -> list[str]:
    match = _ITEMIZE_PATTERN.search(frame_body)

    if not match:
        return []

    return _extract_items(match.group("body"))


# ============================================================
# left・right取得
# ============================================================
def _extract_environment_items(
    frame_body: str,
    environment_name: str,
) -> list[str]:
    pattern = re.compile(
        rf"\\begin\s*\{{\s*"
        rf"{re.escape(environment_name)}"
        rf"\s*\}}"
        rf"(?P<body>.*?)"
        rf"\\end\s*\{{\s*"
        rf"{re.escape(environment_name)}"
        rf"\s*\}}",
        re.DOTALL,
    )

    match = pattern.search(frame_body)

    if not match:
        return []

    return _extract_items(match.group("body"))


# ============================================================
# 未処理本文取得
# ============================================================
def _extract_plain_body(
    frame_body: str,
) -> str:
    text = frame_body

    text = _ITEMIZE_PATTERN.sub("", text)

    for environment_name in ("left", "right"):
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

    if not style_key:
        style_key = get_default_style_key(slide_type)

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

    title = _extract_command_value(
        frame_body,
        "title",
    )
    subtitle = _extract_command_value(
        frame_body,
        "subtitle",
    )
    section_number = _extract_command_value(
        frame_body,
        "sectionnumber",
    )
    presenter_name = _extract_command_value(
        frame_body,
        "presenter",
    )
    contact_text = _extract_command_value(
        frame_body,
        "contact",
    )
    message = _extract_command_value(
        frame_body,
        "message",
    )
    left_heading = _extract_command_value(
        frame_body,
        "lefttitle",
    )
    right_heading = _extract_command_value(
        frame_body,
        "righttitle",
    )

    itemize_lines = _extract_itemize_lines(
        frame_body
    )
    left_lines = _extract_environment_items(
        frame_body,
        "left",
    )
    right_lines = _extract_environment_items(
        frame_body,
        "right",
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