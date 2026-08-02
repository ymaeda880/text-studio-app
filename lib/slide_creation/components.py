# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/components.py
# ============================================================
# PowerPointスライド 共通描画部品
#
# 機能：
# - 背景を設定する
# - テキストボックスを追加する
# - パネル，ヘッダー，フッターを追加する
# - 箇条書きテキストを追加する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from typing import Any

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from lib.slide_creation.models import PresentationSettings, SlideTheme


# ============================================================
# 背景
# ============================================================
def set_slide_background(
    slide: Any,
    *,
    color: Any,
) -> None:
    background = slide.background
    background.fill.solid()
    background.fill.fore_color.rgb = color


# ============================================================
# テキストボックス
# ============================================================
def add_textbox(
    slide: Any,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    text: str,
    theme: SlideTheme,
    font_size: int,
    color: Any,
    bold: bool = False,
    alignment: PP_ALIGN = PP_ALIGN.LEFT,
    vertical_anchor: MSO_ANCHOR = MSO_ANCHOR.TOP,
) -> Any:
    box = slide.shapes.add_textbox(
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )

    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = vertical_anchor

    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.alignment = alignment

    for run in paragraph.runs:
        run.font.name = theme.font_name
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = color

    return box


# ============================================================
# パネル
# ============================================================
def add_panel(
    slide: Any,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    theme: SlideTheme,
    rounded: bool = True,
    fill_color: Any | None = None,
) -> Any:
    shape_type = (
        MSO_SHAPE.ROUNDED_RECTANGLE
        if rounded
        else MSO_SHAPE.RECTANGLE
    )

    panel = slide.shapes.add_shape(
        shape_type,
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )

    panel.fill.solid()
    panel.fill.fore_color.rgb = fill_color or theme.panel_color
    panel.line.color.rgb = theme.panel_line_color
    panel.line.width = Pt(1.2)

    return panel


# ============================================================
# 箇条書き
# ============================================================
def add_bullet_text(
    slide: Any,
    *,
    lines: list[str],
    left: float,
    top: float,
    width: float,
    height: float,
    theme: SlideTheme,
    font_size: int | None = None,
) -> None:
    box = slide.shapes.add_textbox(
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )

    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.TOP

    display_lines = lines or ["本文が入力されていません．"]

    for index, line in enumerate(display_lines):
        paragraph = (
            frame.paragraphs[0]
            if index == 0
            else frame.add_paragraph()
        )

        paragraph.text = f"●  {line}"
        paragraph.space_after = Pt(12)

        for run in paragraph.runs:
            run.font.name = theme.font_name
            run.font.size = Pt(font_size or theme.body_font_size)
            run.font.color.rgb = theme.body_text_color


# ============================================================
# 本文ページ用ヘッダー
# ============================================================
def add_header(
    slide: Any,
    *,
    slide_width: Any,
    slide_title: str,
    header_key: str,
    theme: SlideTheme,
) -> None:
    if header_key == "title_band":
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0,
            0,
            slide_width,
            Inches(1.05),
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = theme.primary_color
        bar.line.fill.background()

        add_textbox(
            slide,
            left=0.65,
            top=0.17,
            width=11.8,
            height=0.7,
            text=slide_title,
            theme=theme,
            font_size=theme.title_font_size,
            color=theme.title_text_color,
            bold=True,
            vertical_anchor=MSO_ANCHOR.MIDDLE,
        )
        return

    add_textbox(
        slide,
        left=0.65,
        top=0.28,
        width=11.8,
        height=0.7,
        text=slide_title,
        theme=theme,
        font_size=theme.title_font_size,
        color=theme.body_text_color,
        bold=True,
    )

    if header_key == "simple_line":
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0.65),
            Inches(1.02),
            Inches(2.1),
            Inches(0.07),
        )
        line.fill.solid()
        line.fill.fore_color.rgb = theme.accent_color
        line.line.fill.background()


# ============================================================
# 本文ページ用フッター
# ============================================================
def add_footer(
    slide: Any,
    *,
    footer_key: str,
    settings: PresentationSettings,
    page_number: int,
    theme: SlideTheme,
) -> None:
    if footer_key == "none":
        return

    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.65),
        Inches(6.62),
        Inches(12.0),
        Inches(0.015),
    )
    line.fill.solid()
    line.fill.fore_color.rgb = theme.panel_line_color
    line.line.fill.background()

    if footer_key == "detailed":
        values = [
            value
            for value in (
                settings.company_name,
                settings.presentation_title,
                settings.presentation_date,
            )
            if value
        ]
        left_text = "　｜　".join(values)

    elif footer_key == "confidential":
        left_text = (
            f"{settings.presentation_title}　｜　社外秘"
        )

    else:
        left_text = settings.presentation_title

    add_textbox(
        slide,
        left=0.7,
        top=6.68,
        width=10.7,
        height=0.3,
        text=left_text,
        theme=theme,
        font_size=theme.footer_font_size,
        color=theme.sub_text_color,
    )

    add_textbox(
        slide,
        left=11.7,
        top=6.68,
        width=0.6,
        height=0.3,
        text=str(page_number),
        theme=theme,
        font_size=theme.footer_font_size,
        color=theme.sub_text_color,
        alignment=PP_ALIGN.RIGHT,
    )


# ============================================================
# 文字列分割
# ============================================================
def split_body_lines(body: str) -> list[str]:
    return [
        line.strip()
        for line in body.splitlines()
        if line.strip()
    ]