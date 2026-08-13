# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_layouts/forest_green.py
from __future__ import annotations
from typing import Any
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches
from lib.slide_creation.components import add_textbox
from lib.slide_creation.font_settings import resolve_font_name, resolve_font_size
from lib.slide_creation.models import PresentationSettings, SlideDefinition, SlideTheme

FONT_DEFAULTS = {'font_name': '游ゴシック', 'title_page_title': 38, 'title_page_subtitle': 19, 'title_page_detail': 11, 'section_number': 38, 'section_title': 40, 'section_subtitle': 17, 'subsection_title': 35, 'subsection_subtitle': 17}

THEME = SlideTheme(
    key='forest_green', label='フォレスト・グリーン', description='木々や森林を基調とした，明るく自然なデザインです．', font_name="游ゴシック",
    primary_color=RGBColor(47, 92, 58), accent_color=RGBColor(111, 157, 92), background_color=RGBColor(248, 251, 246),
    panel_color=RGBColor(255, 255, 255), panel_line_color=RGBColor(202, 220, 194), title_text_color=RGBColor(255, 255, 255),
    body_text_color=RGBColor(39, 75, 49), sub_text_color=RGBColor(91, 116, 94), layout_key='forest_green',
    title_font_size=30, body_font_size=21, footer_font_size=9, theme_asset_key='forest_green',
)

def _size(role:str,theme:SlideTheme,slide_def:SlideDefinition)->int:
    return resolve_font_size(role=role,theme=theme,slide_def=slide_def,layout_defaults=FONT_DEFAULTS,style_key=slide_def.style_key)

def _name(theme:SlideTheme,slide_def:SlideDefinition)->str:
    return resolve_font_name(theme=theme,slide_def=slide_def,layout_defaults=FONT_DEFAULTS)


def render_title(slide:Any,*,slide_def:SlideDefinition,settings:PresentationSettings,theme:SlideTheme)->None:
    fn=_name(theme,slide_def)
    add_textbox(slide,left=1.25,top=2.00,width=10.83,height=1.35,text=slide_def.title,theme=theme,font_size=_size("title_page_title",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=1.65,top=3.40,width=10.03,height=0.70,text=slide_def.subtitle,theme=theme,font_size=_size("title_page_subtitle",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    values=[v for v in (settings.company_name,slide_def.presenter_name or settings.presenter_name,settings.presentation_date) if v]
    add_textbox(slide,left=1.70,top=5.90,width=9.93,height=0.45,text="　｜　".join(values),theme=theme,font_size=_size("title_page_detail",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)

def render_section(slide:Any,*,slide_def:SlideDefinition,theme:SlideTheme)->None:
    circle=slide.shapes.add_shape(MSO_SHAPE.OVAL,Inches(5.94),Inches(1.30),Inches(1.45),Inches(1.45)); circle.fill.solid(); circle.fill.fore_color.rgb=theme.panel_color; circle.line.color.rgb=theme.accent_color; circle.line.width=Inches(0.02)
    fn=_name(theme,slide_def)
    add_textbox(slide,left=5.94,top=1.30,width=1.45,height=1.45,text=slide_def.section_number,theme=theme,font_size=_size("section_number",theme,slide_def),font_name=fn,color=theme.primary_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=1.30,top=2.85,width=10.73,height=1.05,text=slide_def.title,theme=theme,font_size=_size("section_title",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=1.70,top=4.00,width=9.93,height=0.70,text=slide_def.subtitle,theme=theme,font_size=_size("section_subtitle",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)

def render_subsection(slide:Any,*,slide_def:SlideDefinition,theme:SlideTheme)->None:
    fn=_name(theme,slide_def)
    add_textbox(slide,left=1.45,top=2.35,width=10.43,height=1.05,text=slide_def.title,theme=theme,font_size=_size("subsection_title",theme,slide_def),font_name=fn,color=theme.body_text_color,bold=True,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
    add_textbox(slide,left=1.85,top=3.55,width=9.63,height=0.75,text=slide_def.subtitle,theme=theme,font_size=_size("subsection_subtitle",theme,slide_def),font_name=fn,color=theme.sub_text_color,alignment=PP_ALIGN.CENTER,vertical_anchor=MSO_ANCHOR.MIDDLE)
