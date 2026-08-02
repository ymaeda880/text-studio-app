# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/layouts/ending_slides.py
# ============================================================
# 最終ページ描画
# ============================================================

from __future__ import annotations

from typing import Any

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from lib.slide_creation.components import (
    add_bullet_text,
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


def add_ending_slide(
    prs: Any,
    *,
    slide_def: SlideDefinition,
    settings: PresentationSettings,
    theme: SlideTheme,
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    style_key = slide_def.style_key

    if style_key == "thank_you":
        set_slide_background(slide, color=theme.primary_color)

        add_textbox(
            slide,
            left=1.0,
            top=2.15,
            width=11.3,
            height=1.4,
            text=slide_def.title or "ご清聴ありがとうございました",
            theme=theme,
            font_size=38,
            color=theme.title_text_color,
            bold=True,
            alignment=PP_ALIGN.CENTER,
            vertical_anchor=MSO_ANCHOR.MIDDLE,
        )

        add_textbox(
            slide,
            left=1.4,
            top=3.75,
            width=10.5,
            height=0.8,
            text=slide_def.subtitle,
            theme=theme,
            font_size=18,
            color=theme.title_text_color,
            alignment=PP_ALIGN.CENTER,
        )
        return

    set_slide_background(slide, color=theme.background_color)

    if style_key == "contact":
        add_textbox(
            slide,
            left=1.0,
            top=1.25,
            width=11.3,
            height=0.8,
            text=slide_def.title or "お問い合わせ",
            theme=theme,
            font_size=34,
            color=theme.body_text_color,
            bold=True,
            alignment=PP_ALIGN.CENTER,
        )

        add_panel(
            slide,
            left=1.4,
            top=2.35,
            width=10.5,
            height=3.2,
            theme=theme,
        )

        contact_values = [
            value
            for value in (
                settings.company_name,
                slide_def.presenter_name or settings.presenter_name,
                slide_def.contact_text,
            )
            if value
        ]

        add_textbox(
            slide,
            left=1.9,
            top=2.75,
            width=9.5,
            height=2.3,
            text="\n".join(contact_values),
            theme=theme,
            font_size=20,
            color=theme.body_text_color,
            alignment=PP_ALIGN.CENTER,
            vertical_anchor=MSO_ANCHOR.MIDDLE,
        )
        return

    if style_key == "summary":
        add_textbox(
            slide,
            left=0.75,
            top=0.55,
            width=11.8,
            height=0.7,
            text=slide_def.title or "まとめ",
            theme=theme,
            font_size=32,
            color=theme.body_text_color,
            bold=True,
        )

        add_panel(
            slide,
            left=0.85,
            top=1.55,
            width=11.6,
            height=4.9,
            theme=theme,
        )

        add_bullet_text(
            slide,
            lines=split_body_lines(slide_def.body),
            left=1.25,
            top=1.95,
            width=10.8,
            height=4.0,
            theme=theme,
        )
        return

    add_textbox(
        slide,
        left=1.0,
        top=2.45,
        width=11.3,
        height=1.2,
        text=slide_def.title or "以上です",
        theme=theme,
        font_size=38,
        color=theme.body_text_color,
        bold=True,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )

    add_textbox(
        slide,
        left=1.4,
        top=3.8,
        width=10.5,
        height=0.8,
        text=slide_def.subtitle,
        theme=theme,
        font_size=18,
        color=theme.sub_text_color,
        alignment=PP_ALIGN.CENTER,
    )