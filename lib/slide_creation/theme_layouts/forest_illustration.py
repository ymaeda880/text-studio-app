# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_layouts/forest_illustration.py
from __future__ import annotations
from typing import Any
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from lib.slide_creation.components import add_textbox
from lib.slide_creation.font_settings import resolve_font_name, resolve_font_size
from lib.slide_creation.models import PresentationSettings, SlideDefinition, SlideTheme

FONT_DEFAULTS = {'font_name': '游ゴシック', 'title_page_title': 38, 'title_page_subtitle': 19, 'title_page_detail': 11, 'title_page_presenter': 14, 'section_number': 46, 'section_title': 39, 'section_subtitle': 17, 'subsection_title': 35, 'subsection_subtitle': 17}

THEME = SlideTheme(
    key='forest_illustration', label='フォレスト・イラスト', description='森林をモチーフとした幾何学イラストデザインです．', font_name="游ゴシック",
    primary_color=RGBColor(53, 105, 67), accent_color=RGBColor(146, 186, 96), background_color=RGBColor(250, 249, 242),
    panel_color=RGBColor(255, 255, 255), panel_line_color=RGBColor(197, 214, 185), title_text_color=RGBColor(255, 255, 255),
    body_text_color=RGBColor(54, 79, 57), sub_text_color=RGBColor(108, 132, 104), layout_key='forest_illustration',
    title_font_size=30, body_font_size=21, footer_font_size=9, theme_asset_key='forest_illustration',
)

def _size(role:str,theme:SlideTheme,slide_def:SlideDefinition)->int:
    return resolve_font_size(role=role,theme=theme,slide_def=slide_def,layout_defaults=FONT_DEFAULTS,style_key=slide_def.style_key)

def _name(theme:SlideTheme,slide_def:SlideDefinition)->str:
    return resolve_font_name(theme=theme,slide_def=slide_def,layout_defaults=FONT_DEFAULTS)


def render_title(slide:Any,*,slide_def:SlideDefinition,settings:PresentationSettings,theme:SlideTheme)->None:
    fn=_name(theme,slide_def)
    title_top=1.75 if slide_def.style_key == "vertical_info" else 2.00
    subtitle_top=3.10 if slide_def.style_key == "vertical_info" else 3.35
    add_textbox(slide,left=1.65,top=title_top,width=10,height=1.3,text=slide_def.title,theme=theme,font_size=_size("title_page_title",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=2,top=subtitle_top,width=9.3,height=0.7,text=slide_def.subtitle,theme=theme,font_size=_size("title_page_subtitle",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    presenter=slide_def.presenter_name or settings.presenter_name
    if slide_def.style_key == "vertical_info":
        if settings.company_name:
            add_textbox(slide,left=2,top=5.10,width=9.3,height=.35,text=settings.company_name,theme=theme,font_size=_size("title_page_detail",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
        if presenter:
            add_textbox(slide,left=2,top=5.52,width=9.3,height=.40,text=presenter,theme=theme,font_size=_size("title_page_presenter",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
        if settings.presentation_date:
            add_textbox(slide,left=2,top=6.00,width=9.3,height=.35,text=settings.presentation_date,theme=theme,font_size=_size("title_page_detail",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
        return
    values=[v for v in (settings.company_name,presenter,settings.presentation_date) if v]
    add_textbox(slide,left=2.0,top=5.85,width=9.3,height=.45,text="　｜　".join(values),theme=theme,font_size=_size("title_page_detail",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)

def render_section(slide:Any,*,slide_def:SlideDefinition,theme:SlideTheme)->None:
    fn=_name(theme,slide_def)
    add_textbox(slide,left=1.15,top=3,width=1.45,height=1.35,text=slide_def.section_number,theme=theme,font_size=_size("section_number",theme,slide_def),font_name=fn,color=theme.title_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=3,top=2.15,width=8.5,height=1.3,text=slide_def.title,theme=theme,font_size=_size("section_title",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=3.3,top=3.55,width=7.9,height=0.75,text=slide_def.subtitle,theme=theme,font_size=_size("section_subtitle",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)

def render_subsection(slide:Any,*,slide_def:SlideDefinition,theme:SlideTheme)->None:
    fn=_name(theme,slide_def)
    add_textbox(slide,left=1.75,top=2.35,width=9.8,height=1.05,text=slide_def.title,theme=theme,font_size=_size("subsection_title",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=2.15,top=3.55,width=9,height=0.75,text=slide_def.subtitle,theme=theme,font_size=_size("subsection_subtitle",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
