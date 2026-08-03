# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_layouts/forest_illustration.py
# ============================================================
# forest_illustration テーマ専用レイアウト
#
# 機能：
# - タイトルページの文字配置を行う
# - 見出しページの章番号と文字配置を行う
# - 小見出しページの文字配置を行う
#
# 方針：
# - 背景画像の配置はtheme_image_renderer.pyへ任せる
# - このファイルでは文字と章番号だけを配置する
# - 背景画像内の図形と重ならない位置へ配置する
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
    key="forest_illustration",
    label="フォレスト・イラスト",
    description=(
        "森林をモチーフとした"
        "幾何学イラストデザインです．"
    ),
    font_name="游ゴシック",
    primary_color=RGBColor(53, 105, 67),
    accent_color=RGBColor(146, 186, 96),
    background_color=RGBColor(250, 249, 242),
    panel_color=RGBColor(255, 255, 255),
    panel_line_color=RGBColor(197, 214, 185),
    title_text_color=RGBColor(255, 255, 255),
    body_text_color=RGBColor(54, 79, 57),
    sub_text_color=RGBColor(108, 132, 104),
    layout_key="forest_illustration",
    title_font_size=30,
    body_font_size=21,
    footer_font_size=9,
    theme_asset_key="forest_illustration",
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
    forest_illustrationのタイトルページを描画する．
    """

    style_key = slide_def.style_key

    # ========================================================
    # 下部情報を縦に配置
    # ========================================================
    if style_key == "vertical_info":
        add_textbox(
            slide,
            left=1.65,
            top=1.75,
            width=10.00,
            height=1.30,
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
            left=2.00,
            top=3.10,
            width=9.30,
            height=0.70,
            text=slide_def.subtitle,
            theme=theme,
            font_size=19,
            color=theme.sub_text_color,
            alignment=PP_ALIGN.CENTER,
            vertical_anchor=MSO_ANCHOR.MIDDLE,
        )

        presenter_name = (
            slide_def.presenter_name
            or settings.presenter_name
        )

        if settings.company_name:
            add_textbox(
                slide,
                left=2.00,
                top=5.10,
                width=9.30,
                height=0.35,
                text=settings.company_name,
                theme=theme,
                font_size=11,
                color=theme.sub_text_color,
                alignment=PP_ALIGN.CENTER,
                vertical_anchor=MSO_ANCHOR.MIDDLE,
            )

        if presenter_name:
            add_textbox(
                slide,
                left=2.00,
                top=5.52,
                width=9.30,
                height=0.40,
                text=presenter_name,
                theme=theme,
                font_size=14,
                color=theme.body_text_color,
                bold=True,
                alignment=PP_ALIGN.CENTER,
                vertical_anchor=MSO_ANCHOR.MIDDLE,
            )

        if settings.presentation_date:
            add_textbox(
                slide,
                left=2.00,
                top=6.00,
                width=9.30,
                height=0.35,
                text=settings.presentation_date,
                theme=theme,
                font_size=11,
                color=theme.sub_text_color,
                alignment=PP_ALIGN.CENTER,
                vertical_anchor=MSO_ANCHOR.MIDDLE,
            )

        return

    # ========================================================
    # 標準タイトル
    # ========================================================
    add_textbox(
        slide,
        left=1.65,
        top=2.00,
        width=10.00,
        height=1.30,
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
        left=2.00,
        top=3.35,
        width=9.30,
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
        left=2.00,
        top=5.85,
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
    """
    forest_illustrationの見出しページを描画する．

    章番号は背景画像左側の幾何学図形内へ配置し，
    見出し文字は中央から右側へ配置する．
    """

    add_textbox(
        slide,
        left=1.15,
        top=3.00,
        width=1.45,
        height=1.35,
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
        left=3.00,
        top=2.15,
        width=8.50,
        height=1.30,
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
        left=3.30,
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
    """
    forest_illustrationの小見出しページを描画する．

    背景画像内の中央枠を利用し，
    追加の帯やパネルは配置しない．
    """

    add_textbox(
        slide,
        left=1.75,
        top=2.35,
        width=9.80,
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
        left=2.15,
        top=3.55,
        width=9.00,
        height=0.75,
        text=slide_def.subtitle,
        theme=theme,
        font_size=17,
        color=theme.sub_text_color,
        alignment=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )