# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/layouts/section_slides.py
# ============================================================
# 見出しページ生成
#
# 機能：
# - 空白スライドを追加する
# - テーマ背景画像を配置する
# - 登録された見出しレイアウトを呼び出す
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from typing import Any

from lib.slide_creation.models import (
    SlideDefinition,
    SlideTheme,
)
from lib.slide_creation.theme_image_renderer import (
    add_theme_background_image,
)
from lib.slide_creation.theme_layouts.registry import (
    render_registered_section,
)


# ============================================================
# 見出しページ生成
# ============================================================
def add_section_slide(
    prs: Any,
    *,
    slide_def: SlideDefinition,
    theme: SlideTheme,
) -> None:
    slide = prs.slides.add_slide(
        prs.slide_layouts[6],
    )

    add_theme_background_image(
        slide=slide,
        prs=prs,
        theme=theme,
        slide_type="section",
    )

    rendered = render_registered_section(
        slide,
        slide_def=slide_def,
        theme=theme,
    )

    if not rendered:
        raise RuntimeError(
            "見出しページのレイアウトを"
            "取得できませんでした："
            f"theme={theme.key}，"
            f"layout={theme.layout_key or theme.key}"
        )