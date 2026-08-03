# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_layouts/ocean.py
# ============================================================
# ocean テーマ定義・専用レイアウト
#
# 機能：
# - oceanのテーマ設定を保持する
# - タイトルページの文字配置を行う
# - 見出しページの章番号と文字配置を行う
# - 小見出しページの文字配置を行う
#
# 方針：
# - テーマ固有の色と配置をこのファイルで一括管理する
# - 背景画像の配置はtheme_image_renderer.pyへ任せる
# - 青い海と波の背景に合う位置へ文字を配置する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from lib.slide_creation.components import add_textbox
from lib.slide_creation.models import (
    PresentationSettings,
    SlideDefinition,
    SlideTheme,
)


# ============================================================
# テーマ定義
# ============================================================
THEME = SlideTheme(
    key="ocean",
    label="オーシャン",
    description=(
        "海と波をモチーフにした，"
        "爽やかで開放感のあるデザインです．"
    ),
    font_name="游ゴシック",
    primary_color=RGBColor(0, 101, 160),
    accent_color=RGBColor(52, 173, 210),
    background_color=RGBColor(244, 252, 255),
    panel_color=RGBColor(255, 255, 255),
    panel_line_color=RGBColor(173, 226, 241),
    title_text_color=RGBColor(255, 255, 255),
    body_text_color=RGBColor(18, 74, 112),
    sub_text_color=RGBColor(72, 122, 148),
    layout_key="ocean",
    title_font_size=30,
    body_font_size=21,
    footer_font_size=9,
    theme_asset_key="ocean",
)


# ============================================================
# タイトルページ
# ============================================================
def render_title(
    slide: Any,
    *,
    slide_def: SlideDefinition,
    settings: PresentationSettings,
    theme: SlideTheme,
) -> None:
    add_textbox(
        slide,
        left=1.45,
        top=1.85,
        width=10.45,
        height=1.35,
        text=slide_def.title,
        theme=theme,
        font_size=38,
        color=theme.body_text_color,
        bold=True,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )

    add_textbox(
        slide,
        left=1.85,
        top=3.20,
        width=9.65,
        height=0.75,
        text=slide_def.subtitle,
        theme=theme,
        font_size=19,
        color=theme.sub_text_color,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )

    detail_values = [
        value
        for value in (
            settings.company_name,
            slide_def.presenter_name or settings.presenter_name,
            settings.presentation_date,
        )
        if value
    ]

    add_textbox(
        slide,
        left=2.00,
        top=5.65,
        width=9.30,
        height=0.45,
        text="　｜　".join(detail_values),
        theme=theme,
        font_size=11,
        color=theme.sub_text_color,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )


# ============================================================
# 見出しページ
# ============================================================
def render_section(
    slide: Any,
    *,
    slide_def: SlideDefinition,
    theme: SlideTheme,
) -> None:
    add_textbox(
        slide,
        left=0.55,
        top=2.25,
        width=2.45,
        height=1.55,
        text=slide_def.section_number,
        theme=theme,
        font_size=46,
        color=theme.title_text_color,
        bold=True,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )

    add_textbox(
        slide,
        left=3.20,
        top=2.20,
        width=8.40,
        height=1.20,
        text=slide_def.title,
        theme=theme,
        font_size=39,
        color=theme.body_text_color,
        bold=True,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )

    add_textbox(
        slide,
        left=3.45,
        top=3.55,
        width=7.90,
        height=0.75,
        text=slide_def.subtitle,
        theme=theme,
        font_size=17,
        color=theme.sub_text_color,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )


# ============================================================
# 小見出しページ
# ============================================================
def render_subsection(
    slide: Any,
    *,
    slide_def: SlideDefinition,
    theme: SlideTheme,
) -> None:
    add_textbox(
        slide,
        left=1.70,
        top=2.35,
        width=9.95,
        height=1.05,
        text=slide_def.title,
        theme=theme,
        font_size=35,
        color=theme.body_text_color,
        bold=True,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )

    add_textbox(
        slide,
        left=2.10,
        top=3.55,
        width=9.15,
        height=0.75,
        text=slide_def.subtitle,
        theme=theme,
        font_size=17,
        color=theme.sub_text_color,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )
