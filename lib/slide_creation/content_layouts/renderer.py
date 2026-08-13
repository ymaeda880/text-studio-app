# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Any
from lib.slide_creation.components import add_panel
from lib.slide_creation.content_layouts.registry import get_region_bounds
from lib.slide_creation.content_renderers.registry import render_region_contents
from lib.slide_creation.font_settings import get_layout_font_defaults
from lib.slide_creation.models import PresentationSettings, SlideDefinition, SlideTheme

def render_content_regions(slide:Any,*,slide_def:SlideDefinition,settings:PresentationSettings,theme:SlideTheme,inbox_root:Path,sub:str)->None:
    bounds_by_name=get_region_bounds(slide_def.layout_key,ratio=slide_def.layout_ratio)
    regions_by_name={region.name:region for region in slide_def.regions}
    layout_defaults=get_layout_font_defaults(theme.layout_key or theme.key)
    for region_name,bounds in bounds_by_name.items():
        add_panel(slide,left=bounds.left,top=bounds.top,width=bounds.width,height=bounds.height,theme=theme)
        region=regions_by_name.get(region_name)
        if region is None: continue
        render_region_contents(slide,contents=region.contents,bounds=bounds,settings=settings,inbox_root=inbox_root,sub=sub,
            theme=theme,slide_def=slide_def,region=region,layout_defaults=layout_defaults)
