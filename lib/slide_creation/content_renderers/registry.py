# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/content_renderers/registry.py
# ============================================================
# 本文コンテンツ 共通描画
# ============================================================
from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from lib.slide_creation.components import (
    add_bullet_text,
    add_slide_image,
    add_textbox,
)
from lib.slide_creation.content_layouts.models import RegionBounds
from lib.slide_creation.font_settings import (
    resolve_font_name,
    resolve_font_size,
)
from lib.slide_creation.models import (
    ContentDefinition,
    PresentationSettings,
    RegionDefinition,
    SlideDefinition,
    SlideTheme,
)
from lib.slide_creation.table.renderer import render_table


# ============================================================
# 定数
# ============================================================
_INNER_MARGIN = 0.30
_CONTENT_GAP = 0.14
_MIN_CONTENT_HEIGHT = 0.34
_MIN_FLEX_HEIGHT = 0.80


# ============================================================
# 共通処理
# ============================================================
def _inner_bounds(bounds: RegionBounds) -> RegionBounds:
    return RegionBounds(
        bounds.left + _INNER_MARGIN,
        bounds.top + 0.22,
        max(bounds.width - _INNER_MARGIN * 2, 0.20),
        max(bounds.height - 0.44, 0.20),
    )


def _content_font_name(
    *,
    content: ContentDefinition,
    theme: SlideTheme,
    slide_def: SlideDefinition,
    region: RegionDefinition,
    layout_defaults: Mapping[str, Any],
) -> str:
    return (
        content.font_name
        or resolve_font_name(
            theme=theme,
            slide_def=slide_def,
            region=region,
            layout_defaults=layout_defaults,
        )
    )


def _content_font_size(
    *,
    content: ContentDefinition,
    role: str,
    theme: SlideTheme,
    slide_def: SlideDefinition,
    region: RegionDefinition,
    layout_defaults: Mapping[str, Any],
) -> int:
    if content.font_size is not None:
        return int(content.font_size)

    return resolve_font_size(
        role=role,
        theme=theme,
        slide_def=slide_def,
        region=region,
        layout_defaults=layout_defaults,
    )


def _line_count(text: str) -> int:
    return max(
        len([
            line
            for line in str(text or "").splitlines()
            if line.strip()
        ]),
        1,
    )


def _preferred_fixed_height(content: ContentDefinition) -> float | None:
    if content.content_type == "description":
        return min(0.34 + 0.20 * _line_count(content.text), 1.05)

    if content.content_type == "note":
        return min(0.28 + 0.18 * _line_count(content.text), 0.86)

    if content.content_type == "imagecaption":
        return min(0.30 + 0.18 * _line_count(content.text), 0.90)

    if content.content_type == "text":
        return min(0.40 + 0.24 * _line_count(content.text), 1.80)

    if content.content_type == "itemize":
        return min(0.40 + 0.42 * _line_count(content.text), 3.60)

    return None


def _allocate_content_heights(
    contents: list[ContentDefinition],
    *,
    available_height: float,
) -> list[float]:
    if not contents:
        return []

    gaps = _CONTENT_GAP * max(len(contents) - 1, 0)
    usable_height = max(available_height - gaps, _MIN_CONTENT_HEIGHT)

    preferred = [
        _preferred_fixed_height(content)
        for content in contents
    ]
    flexible_indexes = [
        index
        for index, value in enumerate(preferred)
        if value is None
    ]
    fixed_total = sum(
        value
        for value in preferred
        if value is not None
    )

    if not flexible_indexes:
        if fixed_total <= usable_height:
            extra = (usable_height - fixed_total) / len(contents)
            return [
                float(value or _MIN_CONTENT_HEIGHT) + extra
                for value in preferred
            ]

        scale = usable_height / max(fixed_total, 0.01)
        return [
            max(float(value or _MIN_CONTENT_HEIGHT) * scale, _MIN_CONTENT_HEIGHT)
            for value in preferred
        ]

    minimum_flexible_total = _MIN_FLEX_HEIGHT * len(flexible_indexes)
    if fixed_total + minimum_flexible_total > usable_height:
        fixed_available = max(
            usable_height - minimum_flexible_total,
            _MIN_CONTENT_HEIGHT * (len(contents) - len(flexible_indexes)),
        )
        fixed_scale = fixed_available / max(fixed_total, 0.01)
    else:
        fixed_scale = 1.0

    heights = [0.0] * len(contents)
    used_fixed = 0.0

    for index, value in enumerate(preferred):
        if value is None:
            continue
        heights[index] = max(value * fixed_scale, _MIN_CONTENT_HEIGHT)
        used_fixed += heights[index]

    flexible_height = max(
        (usable_height - used_fixed) / len(flexible_indexes),
        _MIN_FLEX_HEIGHT,
    )

    for index in flexible_indexes:
        heights[index] = flexible_height

    total = sum(heights)
    if total > usable_height:
        scale = usable_height / total
        heights = [
            max(height * scale, _MIN_CONTENT_HEIGHT)
            for height in heights
        ]

    return heights


# ============================================================
# 各コンテンツ描画
# ============================================================
def _render_plain_text(
    slide: Any,
    *,
    content: ContentDefinition,
    bounds: RegionBounds,
    theme: SlideTheme,
    slide_def: SlideDefinition,
    region: RegionDefinition,
    layout_defaults: Mapping[str, Any],
) -> None:
    role = "content_narrow_body" if bounds.width < 4.2 else "content_body"
    add_textbox(
        slide,
        left=bounds.left,
        top=bounds.top,
        width=bounds.width,
        height=bounds.height,
        text=content.text,
        theme=theme,
        font_size=_content_font_size(
            content=content,
            role=role,
            theme=theme,
            slide_def=slide_def,
            region=region,
            layout_defaults=layout_defaults,
        ),
        font_name=_content_font_name(
            content=content,
            theme=theme,
            slide_def=slide_def,
            region=region,
            layout_defaults=layout_defaults,
        ),
        color=theme.body_text_color,
        vertical_anchor=MSO_ANCHOR.TOP,
    )


def _render_itemize(
    slide: Any,
    *,
    content: ContentDefinition,
    bounds: RegionBounds,
    theme: SlideTheme,
    slide_def: SlideDefinition,
    region: RegionDefinition,
    layout_defaults: Mapping[str, Any],
) -> None:
    lines = [
        line.strip()
        for line in content.text.splitlines()
        if line.strip()
    ]
    role = "content_narrow_body" if bounds.width < 4.2 else "content_body"
    add_bullet_text(
        slide,
        lines=lines,
        left=bounds.left,
        top=bounds.top,
        width=bounds.width,
        height=bounds.height,
        theme=theme,
        font_size=_content_font_size(
            content=content,
            role=role,
            theme=theme,
            slide_def=slide_def,
            region=region,
            layout_defaults=layout_defaults,
        ),
        font_name=_content_font_name(
            content=content,
            theme=theme,
            slide_def=slide_def,
            region=region,
            layout_defaults=layout_defaults,
        ),
    )


def _render_small_text(
    slide: Any,
    *,
    content: ContentDefinition,
    bounds: RegionBounds,
    role: str,
    color: Any,
    theme: SlideTheme,
    slide_def: SlideDefinition,
    region: RegionDefinition,
    layout_defaults: Mapping[str, Any],
    alignment: PP_ALIGN = PP_ALIGN.LEFT,
) -> None:
    add_textbox(
        slide,
        left=bounds.left,
        top=bounds.top,
        width=bounds.width,
        height=bounds.height,
        text=content.text,
        theme=theme,
        font_size=_content_font_size(
            content=content,
            role=role,
            theme=theme,
            slide_def=slide_def,
            region=region,
            layout_defaults=layout_defaults,
        ),
        font_name=_content_font_name(
            content=content,
            theme=theme,
            slide_def=slide_def,
            region=region,
            layout_defaults=layout_defaults,
        ),
        color=color,
        alignment=alignment,
        vertical_anchor=MSO_ANCHOR.TOP,
    )


def _render_image(
    slide: Any,
    *,
    content: ContentDefinition,
    bounds: RegionBounds,
    settings: PresentationSettings,
    inbox_root: Path,
    sub: str,
) -> None:
    add_slide_image(
        slide,
        image_file=content.image_file,
        image_path=settings.image_path,
        inbox_root=inbox_root,
        sub=sub,
        left=bounds.left,
        top=bounds.top,
        width=bounds.width,
        height=bounds.height,
    )


def _render_table_content(
    slide: Any,
    *,
    content: ContentDefinition,
    bounds: RegionBounds,
    theme: SlideTheme,
    slide_def: SlideDefinition,
    region: RegionDefinition,
    layout_defaults: Mapping[str, Any],
) -> None:
    if content.table is None:
        raise ValueError("tableコンテンツですが，表データがありません．")

    render_table(
        slide,
        table_definition=content.table,
        theme=theme,
        left=bounds.left,
        top=bounds.top,
        width=bounds.width,
        height=bounds.height,
        font_name=_content_font_name(
            content=content,
            theme=theme,
            slide_def=slide_def,
            region=region,
            layout_defaults=layout_defaults,
        ),
        layout_font_defaults=layout_defaults,
    )


# ============================================================
# 公開描画
# ============================================================
def render_region_contents(
    slide: Any,
    *,
    contents: list[ContentDefinition],
    bounds: RegionBounds,
    settings: PresentationSettings,
    inbox_root: Path,
    sub: str,
    theme: SlideTheme,
    slide_def: SlideDefinition,
    region: RegionDefinition,
    layout_defaults: Mapping[str, Any],
) -> None:
    if not contents:
        return

    inner = _inner_bounds(bounds)
    heights = _allocate_content_heights(
        contents,
        available_height=inner.height,
    )
    current_top = inner.top

    for content, content_height in zip(contents, heights):
        content_bounds = RegionBounds(
            inner.left,
            current_top,
            inner.width,
            content_height,
        )

        if content.content_type == "text":
            _render_plain_text(
                slide,
                content=content,
                bounds=content_bounds,
                theme=theme,
                slide_def=slide_def,
                region=region,
                layout_defaults=layout_defaults,
            )

        elif content.content_type == "itemize":
            _render_itemize(
                slide,
                content=content,
                bounds=content_bounds,
                theme=theme,
                slide_def=slide_def,
                region=region,
                layout_defaults=layout_defaults,
            )

        elif content.content_type == "image":
            _render_image(
                slide,
                content=content,
                bounds=content_bounds,
                settings=settings,
                inbox_root=inbox_root,
                sub=sub,
            )

        elif content.content_type == "imagecaption":
            _render_small_text(
                slide,
                content=content,
                bounds=content_bounds,
                role="image_caption",
                color=theme.sub_text_color,
                theme=theme,
                slide_def=slide_def,
                region=region,
                layout_defaults=layout_defaults,
                alignment=PP_ALIGN.CENTER,
            )

        elif content.content_type == "description":
            _render_small_text(
                slide,
                content=content,
                bounds=content_bounds,
                role="table_description",
                color=theme.body_text_color,
                theme=theme,
                slide_def=slide_def,
                region=region,
                layout_defaults=layout_defaults,
            )

        elif content.content_type == "note":
            _render_small_text(
                slide,
                content=content,
                bounds=content_bounds,
                role="table_note",
                color=theme.sub_text_color,
                theme=theme,
                slide_def=slide_def,
                region=region,
                layout_defaults=layout_defaults,
            )

        elif content.content_type == "table":
            _render_table_content(
                slide,
                content=content,
                bounds=content_bounds,
                theme=theme,
                slide_def=slide_def,
                region=region,
                layout_defaults=layout_defaults,
            )

        else:
            raise ValueError(
                "未対応の本文コンテンツです："
                + content.content_type
            )

        current_top += content_height + _CONTENT_GAP
