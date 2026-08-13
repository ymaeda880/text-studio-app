# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/font_settings.py
# ============================================================
# SlideTex フォント設定解決
# ============================================================
from __future__ import annotations
import importlib
from functools import lru_cache
from typing import Any, Mapping
from lib.slide_creation.models import RegionDefinition, SlideDefinition, SlideTheme

GLOBAL_FONT_DEFAULTS: dict[str, Any] = {
    "font_name": "游ゴシック",
    "title_page_title": 38,
    "title_page_subtitle": 19,
    "title_page_detail": 11,
    "title_page_presenter": 14,
    "section_number": 26,
    "section_title": 40,
    "section_subtitle": 17,
    "subsection_title": 35,
    "subsection_subtitle": 17,
    "content_title": 30,
    "content_body": 21,
    "content_narrow_body": 17,
    "content_heading": 16,
    "message": 30,
    "image_caption": 11,
    "table_caption": 12,
    "table_description": 11,
    "table_note": 10,
    "table_body": 12,
    "table_header": 12,
    "footer": 9,
    "ending_title": 38,
    "ending_subtitle": 18,
    "ending_contact": 20,
}

_ROLE_TO_THEME_ATTRIBUTE = {
    "title_page_title": "title_page_title_font_size",
    "title_page_subtitle": "title_page_subtitle_font_size",
    "title_page_detail": "title_page_detail_font_size",
    "title_page_presenter": "title_page_presenter_font_size",
    "section_number": "section_number_font_size",
    "section_title": "section_title_font_size",
    "section_subtitle": "section_subtitle_font_size",
    "subsection_title": "subsection_title_font_size",
    "subsection_subtitle": "subsection_subtitle_font_size",
    "content_title": "content_title_font_size",
    "content_body": "content_body_font_size",
    "content_narrow_body": "content_narrow_body_font_size",
    "content_heading": "content_heading_font_size",
    "message": "message_font_size",
    "image_caption": "image_caption_font_size",
    "table_caption": "table_caption_font_size",
    "table_description": "table_description_font_size",
    "table_note": "table_note_font_size",
    "table_body": "table_body_font_size",
    "table_header": "table_header_font_size",
    "footer": "footer_font_size",
    "ending_title": "ending_title_font_size",
    "ending_subtitle": "ending_subtitle_font_size",
    "ending_contact": "ending_contact_font_size",
}

@lru_cache(maxsize=None)
def get_layout_font_defaults(layout_key: str) -> dict[str, Any]:
    key=str(layout_key or "").strip()
    if not key:
        return {}
    module_name=f"lib.slide_creation.theme_layouts.{key}"
    try:
        module=importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return {}
        raise
    values=getattr(module,"FONT_DEFAULTS",{})
    return dict(values) if isinstance(values, Mapping) else {}

def _layout_key(theme: SlideTheme) -> str:
    return str(theme.layout_key or theme.key or "").strip()

def _layout_value(defaults: Mapping[str, Any], role: str, style_key: str) -> Any:
    if style_key:
        styled=defaults.get(f"{role}.{style_key}")
        if styled not in (None, ""):
            return styled
    return defaults.get(role)

def resolve_font_name(*, theme: SlideTheme, slide_def: SlideDefinition | None = None,
                      region: RegionDefinition | None = None,
                      layout_defaults: Mapping[str, Any] | None = None) -> str:
    defaults=dict(layout_defaults or get_layout_font_defaults(_layout_key(theme)))
    return str(
        (region.font_name if region else "")
        or (slide_def.font_name if slide_def else "")
        or defaults.get("font_name")
        or theme.font_name
        or GLOBAL_FONT_DEFAULTS["font_name"]
    ).strip()

def resolve_font_size(*, role: str, theme: SlideTheme,
                      slide_def: SlideDefinition | None = None,
                      region: RegionDefinition | None = None,
                      layout_defaults: Mapping[str, Any] | None = None,
                      style_key: str = "") -> int:
    defaults=dict(layout_defaults or get_layout_font_defaults(_layout_key(theme)))
    # SlideTex個別指定
    # --------------------------------------------------------
    # Region・Frameの本文系フォントサイズ
    #
    # Regionのfont_sizeを最優先し，
    # 指定がない場合はFrameのbody_font_sizeを使用する．
    # --------------------------------------------------------
    if role in {
        "content_body",
        "content_narrow_body",
        "content_heading",
        "image_caption",
        "table_caption",
        "table_description",
        "table_note",
        "table_body",
        "table_header",
    }:
        if (
            region is not None
            and region.font_size is not None
        ):
            return int(
                region.font_size
            )

        if (
            slide_def is not None
            and slide_def.body_font_size is not None
        ):
            return int(
                slide_def.body_font_size
            )
        
    elif role in {"content_title", "title_page_title", "section_title", "subsection_title", "ending_title"}:
        if slide_def is not None and slide_def.title_font_size is not None:
            return int(slide_def.title_font_size)
    elif role in {"title_page_subtitle", "section_subtitle", "subsection_subtitle", "ending_subtitle"}:
        if slide_def is not None and slide_def.body_font_size is not None:
            return int(slide_def.body_font_size)
    layout_value=_layout_value(defaults,role,style_key)
    if layout_value not in (None, ""):
        return int(layout_value)
    attr=_ROLE_TO_THEME_ATTRIBUTE.get(role)
    if attr:
        value=getattr(theme,attr,None)
        if value is not None:
            return int(value)
    return int(GLOBAL_FONT_DEFAULTS[role])
