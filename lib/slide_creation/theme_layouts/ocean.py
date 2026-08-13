# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_layouts/ocean.py
from __future__ import annotations
from typing import Any
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from lib.slide_creation.components import add_textbox
from lib.slide_creation.font_settings import resolve_font_name, resolve_font_size
from lib.slide_creation.models import PresentationSettings, SlideDefinition, SlideTheme

FONT_DEFAULTS = {'font_name': '游ゴシック', 'title_page_title': 38, 'title_page_subtitle': 19, 'title_page_detail': 11, 'title_page_presenter': 14, 'section_number': 46, 'section_title': 39, 'section_subtitle': 17, 'subsection_title': 35, 'subsection_subtitle': 17}

THEME = SlideTheme(
    key='ocean', label='オーシャン', description='海と波をモチーフにした，爽やかで開放感のあるデザインです．', font_name="游ゴシック",
    primary_color=RGBColor(0, 101, 160), accent_color=RGBColor(52, 173, 210), background_color=RGBColor(244, 252, 255),
    panel_color=RGBColor(255, 255, 255), panel_line_color=RGBColor(173, 226, 241), title_text_color=RGBColor(255, 255, 255),
    body_text_color=RGBColor(18, 74, 112), sub_text_color=RGBColor(72, 122, 148), layout_key='ocean',
    title_font_size=30, body_font_size=21, footer_font_size=9, theme_asset_key='ocean',
)

def _size(role:str,theme:SlideTheme,slide_def:SlideDefinition)->int:
    return resolve_font_size(role=role,theme=theme,slide_def=slide_def,layout_defaults=FONT_DEFAULTS,style_key=slide_def.style_key)

def _name(theme:SlideTheme,slide_def:SlideDefinition)->str:
    return resolve_font_name(theme=theme,slide_def=slide_def,layout_defaults=FONT_DEFAULTS)


def render_title(slide:Any,*,slide_def:SlideDefinition,settings:PresentationSettings,theme:SlideTheme)->None:
    fn=_name(theme,slide_def)
    add_textbox(slide,left=1.45,top=1.85,width=10.45,height=1.35,text=slide_def.title,theme=theme,font_size=_size("title_page_title",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=1.85,top=3.2,width=9.65,height=0.75,text=slide_def.subtitle,theme=theme,font_size=_size("title_page_subtitle",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    values=[v for v in (settings.company_name,slide_def.presenter_name or settings.presenter_name,settings.presentation_date) if v]
    add_textbox(slide,left=2.0,top=5.75,width=9.3,height=.45,text="　｜　".join(values),theme=theme,font_size=_size("title_page_detail",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)

def render_section(slide:Any,*,slide_def:SlideDefinition,theme:SlideTheme)->None:
    fn=_name(theme,slide_def)
    add_textbox(slide,left=0.55,top=2.25,width=2.45,height=1.55,text=slide_def.section_number,theme=theme,font_size=_size("section_number",theme,slide_def),font_name=fn,color=theme.title_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=3.2,top=2.2,width=8.4,height=1.2,text=slide_def.title,theme=theme,font_size=_size("section_title",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=3.45,top=3.55,width=7.9,height=0.75,text=slide_def.subtitle,theme=theme,font_size=_size("section_subtitle",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)

def render_subsection(slide:Any,*,slide_def:SlideDefinition,theme:SlideTheme)->None:
    fn=_name(theme,slide_def)
    add_textbox(slide,left=1.7,top=2.35,width=9.95,height=1.05,text=slide_def.title,theme=theme,font_size=_size("subsection_title",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=2.1,top=3.55,width=9.15,height=0.75,text=slide_def.subtitle,theme=theme,font_size=_size("subsection_subtitle",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
