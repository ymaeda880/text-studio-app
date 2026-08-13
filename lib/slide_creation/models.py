# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/models.py
# ============================================================
# PowerPointスライド作成 データモデル
# ============================================================
from __future__ import annotations
from dataclasses import dataclass, field
from pptx.dml.color import RGBColor
from lib.slide_creation.table.models import TableDefinition

@dataclass
class ContentDefinition:
    content_type: str
    text: str = ""
    font_name: str = ""
    font_size: int | None = None
    image_file: str = ""
    table: TableDefinition | None = None

@dataclass
class RegionDefinition:
    name: str
    font_name: str = ""
    font_size: int | None = None
    contents: list[ContentDefinition] = field(default_factory=list)

@dataclass
class SlideDefinition:
    slide_type: str
    style_key: str
    title: str = ""
    subtitle: str = ""
    body: str = ""
    section_number: str = ""
    left_heading: str = ""
    right_heading: str = ""
    presenter_name: str = ""
    contact_text: str = ""
    layout_key: str = ""
    layout_ratio: tuple[float, ...] = field(default_factory=tuple)
    font_name: str = ""
    title_font_size: int | None = None
    body_font_size: int | None = None
    regions: list[RegionDefinition] = field(default_factory=list)
    description: str = ""
    note: str = ""
    image_file: str = ""
    image_caption: str = ""
    table: TableDefinition | None = None

@dataclass(frozen=True)
class PresentationSettings:
    presentation_title: str
    company_name: str = ""
    presenter_name: str = ""
    presentation_date: str = ""
    theme_key: str = "business_blue"
    header_key: str = "title_band"
    footer_key: str = "standard"
    image_path: str = "inbox"

@dataclass(frozen=True)
class SlideTheme:
    key: str
    label: str
    description: str
    font_name: str
    primary_color: RGBColor
    accent_color: RGBColor
    background_color: RGBColor
    panel_color: RGBColor
    panel_line_color: RGBColor
    title_text_color: RGBColor
    body_text_color: RGBColor
    sub_text_color: RGBColor
    layout_key: str = ""
    title_font_size: int = 30
    body_font_size: int = 21
    footer_font_size: int = 9
    title_page_title_font_size: int = 38
    title_page_subtitle_font_size: int = 19
    title_page_detail_font_size: int = 11
    title_page_presenter_font_size: int = 14
    section_number_font_size: int = 26
    section_title_font_size: int = 40
    section_subtitle_font_size: int = 17
    subsection_title_font_size: int = 35
    subsection_subtitle_font_size: int = 17
    content_title_font_size: int = 30
    content_body_font_size: int = 21
    content_narrow_body_font_size: int = 17
    content_heading_font_size: int = 16
    message_font_size: int = 30
    image_caption_font_size: int = 11
    table_caption_font_size: int = 12
    table_description_font_size: int = 11
    table_note_font_size: int = 10
    table_body_font_size: int = 12
    table_header_font_size: int = 12
    ending_title_font_size: int = 38
    ending_subtitle_font_size: int = 18
    ending_contact_font_size: int = 20
    theme_asset_key: str = ""

@dataclass(frozen=True)
class SelectionOption:
    key: str
    label: str
    description: str
