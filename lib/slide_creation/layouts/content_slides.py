# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/layouts/content_slides.py
# ============================================================
# 本文ページ生成
#
# 機能：
# - 空白スライドを追加する
# - 登録された本文レイアウトを呼び出す
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pathlib import Path
from typing import Any

from lib.slide_creation.models import (
    PresentationSettings,
    SlideDefinition,
    SlideTheme,
)
from lib.slide_creation.theme_layouts.registry import (
    render_registered_content,
)


# ============================================================
# 本文ページ生成
# ============================================================
def add_content_slide(
    prs: Any,
    *,
    slide_def: SlideDefinition,
    settings: PresentationSettings,
    page_number: int,
    theme: SlideTheme,
    inbox_root: Path,
    sub: str,
) -> None:
    slide = prs.slides.add_slide(
        prs.slide_layouts[6],
    )

    rendered = render_registered_content(
        slide,
        slide_def=slide_def,
        settings=settings,
        page_number=page_number,
        theme=theme,
        inbox_root=inbox_root,
        sub=sub,
    )

    if not rendered:
        raise RuntimeError(
            "本文ページのレイアウトを"
            "取得できませんでした："
            f"theme={theme.key}，"
            f"layout={theme.layout_key or theme.key}"
        )