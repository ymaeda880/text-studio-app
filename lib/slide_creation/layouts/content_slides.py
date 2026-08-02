# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/layouts/content_slides.py
# ============================================================
# 本文ページ描画
# ============================================================

from __future__ import annotations

from typing import Any

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from lib.slide_creation.components import (
    add_bullet_text,
    add_footer,
    add_header,
    add_panel,
    add_textbox,
    set_slide_background,
    split_body_lines,
)
from lib.slide_creation.models import (
    PresentationSettings,
    SlideDefinition,
    SlideTheme,
)


def add_content_slide(
    prs: Any,
    *,
    slide_def: SlideDefinition,
    settings: PresentationSettings,
    page_number: int,
    theme: SlideTheme,
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    set_slide_background(
        slide,
        color=theme.background_color,
    )

    add_header(
        slide,
        slide_width=prs.slide_width,
        slide_title=slide_def.title,
        header_key=settings.header_key,
        theme=theme,
    )

    lines = split_body_lines(slide_def.body)

    if slide_def.style_key == "two_column":
        split_index = (len(lines) + 1) // 2
        left_lines = lines[:split_index]
        right_lines = lines[split_index:]

        add_panel(
            slide,
            left=0.75,
            top=1.4,
            width=5.85,
            height=4.85,
            theme=theme,
        )
        add_panel(
            slide,
            left=6.75,
            top=1.4,
            width=5.85,
            height=4.85,
            theme=theme,
        )

        add_bullet_text(
            slide,
            lines=left_lines,
            left=1.05,
            top=1.75,
            width=5.2,
            height=4.0,
            theme=theme,
        )
        add_bullet_text(
            slide,
            lines=right_lines,
            left=7.05,
            top=1.75,
            width=5.2,
            height=4.0,
            theme=theme,
        )

    elif slide_def.style_key == "comparison":
        left_lines = lines[0::2]
        right_lines = lines[1::2]

        add_textbox(
            slide,
            left=0.9,
            top=1.25,
            width=5.5,
            height=0.35,
            text=slide_def.left_heading or "項目A",
            theme=theme,
            font_size=16,
            color=theme.accent_color,
            bold=True,
            alignment=PP_ALIGN.CENTER,
        )
        add_textbox(
            slide,
            left=6.9,
            top=1.25,
            width=5.5,
            height=0.35,
            text=slide_def.right_heading or "項目B",
            theme=theme,
            font_size=16,
            color=theme.accent_color,
            bold=True,
            alignment=PP_ALIGN.CENTER,
        )

        add_panel(
            slide,
            left=0.75,
            top=1.65,
            width=5.85,
            height=4.6,
            theme=theme,
        )
        add_panel(
            slide,
            left=6.75,
            top=1.65,
            width=5.85,
            height=4.6,
            theme=theme,
        )

        add_bullet_text(
            slide,
            lines=left_lines,
            left=1.05,
            top=1.95,
            width=5.2,
            height=3.9,
            theme=theme,
        )
        add_bullet_text(
            slide,
            lines=right_lines,
            left=7.05,
            top=1.95,
            width=5.2,
            height=3.9,
            theme=theme,
        )

    elif slide_def.style_key == "message":
        add_panel(
            slide,
            left=1.0,
            top=1.65,
            width=11.3,
            height=4.4,
            theme=theme,
        )

        add_textbox(
            slide,
            left=1.5,
            top=2.2,
            width=10.3,
            height=3.0,
            text=slide_def.body,
            theme=theme,
            font_size=30,
            color=theme.body_text_color,
            bold=True,
            alignment=PP_ALIGN.CENTER,
            vertical_anchor=MSO_ANCHOR.MIDDLE,
        )

    else:
        add_panel(
            slide,
            left=0.8,
            top=1.4,
            width=11.7,
            height=4.85,
            theme=theme,
        )

        add_bullet_text(
            slide,
            lines=lines,
            left=1.15,
            top=1.75,
            width=10.9,
            height=4.1,
            theme=theme,
        )

    add_footer(
        slide,
        footer_key=settings.footer_key,
        settings=settings,
        page_number=page_number,
        theme=theme,
    )