# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/powerpoint_builder.py
# ============================================================
# PowerPointスライド生成
#
# 機能：
# - 複数枚のスライドを作成する
# - ページ種別ごとの描画関数へ振り分ける
# - テーマ，ヘッダー，フッターを適用する
#
# 方針：
# - Streamlitには依存しない
# - ページ種別ごとの描画処理はlayoutsへ分離する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from io import BytesIO
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.util import Inches

from lib.slide_creation.layouts.content_slides import (
    add_content_slide,
)
from lib.slide_creation.layouts.ending_slides import (
    add_ending_slide,
)
from lib.slide_creation.layouts.section_slides import (
    add_section_slide,
)
from lib.slide_creation.layouts.subsection_slides import (
    add_subsection_slide,
)
from lib.slide_creation.layouts.title_slides import (
    add_title_slide,
)
from lib.slide_creation.models import (
    PresentationSettings,
    SlideDefinition,
)
from lib.slide_creation.themes import get_theme


# ============================================================
# 公開定数
# ============================================================
PPTX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "presentationml.presentation"
)


# ============================================================
# 共通処理
# ============================================================
def _set_slide_size(prs: Any) -> None:
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)


# ============================================================
# PowerPoint生成
# ============================================================
def create_powerpoint(
    *,
    slides: list[SlideDefinition],
    settings: PresentationSettings,
    inbox_root: Path,
    sub: str,
) -> bytes:
    if not slides:
        raise ValueError("スライドが1枚も設定されていません．")

    theme = get_theme(settings.theme_key)

    prs = Presentation()
    _set_slide_size(prs)

    for page_number, slide_def in enumerate(slides, start=1):
        if slide_def.slide_type == "title":
            add_title_slide(
                prs,
                slide_def=slide_def,
                settings=settings,
                theme=theme,
            )

        elif slide_def.slide_type == "section":
            add_section_slide(
                prs,
                slide_def=slide_def,
                theme=theme,
            )

        elif slide_def.slide_type == "subsection":
            add_subsection_slide(
                prs,
                slide_def=slide_def,
                theme=theme,
            )

        elif slide_def.slide_type == "ending":
            add_ending_slide(
                prs,
                slide_def=slide_def,
                settings=settings,
                theme=theme,
            )

        else:
            add_content_slide(
                prs,
                slide_def=slide_def,
                settings=settings,
                page_number=page_number,
                theme=theme,
                inbox_root=inbox_root,
                sub=sub,
            )

    output = BytesIO()
    prs.save(output)

    return output.getvalue()