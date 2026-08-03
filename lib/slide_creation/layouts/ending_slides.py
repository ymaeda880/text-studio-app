# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/layouts/ending_slides.py
# ============================================================
# 最終ページ生成
#
# 機能：
# - 空白スライドを追加する
# - 登録された最終ページレイアウトを呼び出す
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from typing import Any

from lib.slide_creation.models import (
    PresentationSettings,
    SlideDefinition,
    SlideTheme,
)
from lib.slide_creation.theme_layouts.registry import (
    render_registered_ending,
)


# ============================================================
# 最終ページ生成
# ============================================================
def add_ending_slide(
    prs: Any,
    *,
    slide_def: SlideDefinition,
    settings: PresentationSettings,
    theme: SlideTheme,
) -> None:
    slide = prs.slides.add_slide(
        prs.slide_layouts[6],
    )

    rendered = render_registered_ending(
        slide,
        slide_def=slide_def,
        settings=settings,
        theme=theme,
    )

    if not rendered:
        raise RuntimeError(
            "最終ページのレイアウトを"
            "取得できませんでした："
            f"theme={theme.key}，"
            f"layout={theme.layout_key or theme.key}"
        )