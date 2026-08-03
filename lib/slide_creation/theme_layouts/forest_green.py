# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_layouts/forest_green.py
# ============================================================
# forest_green テーマ定義・専用レイアウト
#
# 機能：
# - forest_greenのテーマ設定を保持する
# - タイトルページの文字配置を行う
# - 見出しページの章番号と文字配置を行う
# - 小見出しページの文字配置を行う
#
# 方針：
# - テーマ固有の色と配置をこのファイルで一括管理する
# - 背景画像の配置はtheme_image_renderer.pyへ任せる
# - 背景画像と文字のコントラストを確保する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

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
    key="forest_green",
    label="フォレスト・グリーン",
    description=(
        "木々や森林を基調とした，"
        "明るく自然なデザインです．"
    ),
    font_name="游ゴシック",
    primary_color=RGBColor(47, 92, 58),
    accent_color=RGBColor(111, 157, 92),
    background_color=RGBColor(248, 251, 246),
    panel_color=RGBColor(255, 255, 255),
    panel_line_color=RGBColor(202, 220, 194),
    title_text_color=RGBColor(255, 255, 255),
    body_text_color=RGBColor(39, 75, 49),
    sub_text_color=RGBColor(91, 116, 94),
    layout_key="forest_green",
    title_font_size=30,
    body_font_size=21,
    footer_font_size=9,
    theme_asset_key="forest_green",
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
    """
    forest_greenのタイトルページを描画する．
    """

    add_textbox(
        slide,
        left=1.25,
        top=2.00,
        width=10.83,
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
        left=1.65,
        top=3.40,
        width=10.03,
        height=0.70,
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
            (
                slide_def.presenter_name
                or settings.presenter_name
            ),
            settings.presentation_date,
        )
        if value
    ]

    add_textbox(
        slide,
        left=1.70,
        top=5.90,
        width=9.93,
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
    """
    forest_greenの見出しページを描画する．

    章番号の後ろに淡色の円形台座を置き，
    森林背景の上でも数字を読みやすくする．
    """

    # --------------------------------------------------------
    # 章番号の円形台座
    # --------------------------------------------------------
    number_circle = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(5.94),
        Inches(1.30),
        Inches(1.45),
        Inches(1.45),
    )
    number_circle.fill.solid()
    number_circle.fill.fore_color.rgb = theme.panel_color
    number_circle.line.color.rgb = theme.accent_color
    number_circle.line.width = Inches(0.02)

    # --------------------------------------------------------
    # 章番号
    # --------------------------------------------------------
    add_textbox(
        slide,
        left=5.94,
        top=1.30,
        width=1.45,
        height=1.45,
        text=slide_def.section_number,
        theme=theme,
        font_size=38,
        color=theme.primary_color,
        bold=True,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )

    # --------------------------------------------------------
    # 見出し
    # --------------------------------------------------------
    add_textbox(
        slide,
        left=1.30,
        top=2.85,
        width=10.73,
        height=1.05,
        text=slide_def.title,
        theme=theme,
        font_size=40,
        color=theme.body_text_color,
        bold=True,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )

    # --------------------------------------------------------
    # 補足説明
    # --------------------------------------------------------
    add_textbox(
        slide,
        left=1.70,
        top=4.00,
        width=9.93,
        height=0.70,
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
    """
    forest_greenの小見出しページを描画する．
    """

    add_textbox(
        slide,
        left=1.45,
        top=2.35,
        width=10.43,
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
        left=1.85,
        top=3.55,
        width=9.63,
        height=0.75,
        text=slide_def.subtitle,
        theme=theme,
        font_size=17,
        color=theme.sub_text_color,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )