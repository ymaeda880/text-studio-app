# -*- coding: utf-8 -*-
from __future__ import annotations
from lib.slide_creation.content_layouts.models import RegionBounds

CONTENT_LAYOUT_REGIONS: dict[str, tuple[str, ...]] = {
    "full": ("full",),
    "two_column": ("left", "right"),
    "three_column": ("left", "center", "right"),
    "two_row": ("top", "bottom"),
    "sidebar": ("sidebar", "main"),
}
DEFAULT_LAYOUT_RATIOS = {
    "full": (1.0,), "two_column": (1.0,1.0), "three_column": (1.0,1.0,1.0),
    "two_row": (1.0,1.0), "sidebar": (3.25,8.40),
}
CONTENT_AREA_LEFT=0.75; CONTENT_AREA_TOP=1.40; CONTENT_AREA_WIDTH=11.85; CONTENT_AREA_HEIGHT=4.85
GAPS={"two_column":0.15,"three_column":0.21,"two_row":0.25,"sidebar":0.20}

def get_region_names(layout_key:str)->tuple[str,...]: return CONTENT_LAYOUT_REGIONS.get(layout_key,())

def _resolve_ratio(layout_key:str,ratio:tuple[float,...])->tuple[float,...]:
    values=tuple(float(v) for v in ratio) if ratio else DEFAULT_LAYOUT_RATIOS[layout_key]
    if len(values)!=len(CONTENT_LAYOUT_REGIONS[layout_key]) or any(v<=0 for v in values):
        raise ValueError(f"layout={layout_key}のratioが不正です．")
    return values

def _horizontal(names,ratio,gap):
    available=CONTENT_AREA_WIDTH-gap*(len(names)-1); total=sum(ratio); x=CONTENT_AREA_LEFT; out={}
    for i,name in enumerate(names):
        w=(CONTENT_AREA_LEFT+CONTENT_AREA_WIDTH-x) if i==len(names)-1 else available*ratio[i]/total
        out[name]=RegionBounds(x,CONTENT_AREA_TOP,w,CONTENT_AREA_HEIGHT); x+=w+gap
    return out

def _vertical(names,ratio,gap):
    available=CONTENT_AREA_HEIGHT-gap*(len(names)-1); total=sum(ratio); y=CONTENT_AREA_TOP; out={}
    for i,name in enumerate(names):
        h=(CONTENT_AREA_TOP+CONTENT_AREA_HEIGHT-y) if i==len(names)-1 else available*ratio[i]/total
        out[name]=RegionBounds(CONTENT_AREA_LEFT,y,CONTENT_AREA_WIDTH,h); y+=h+gap
    return out

def get_region_bounds(layout_key:str,*,ratio:tuple[float,...]=())->dict[str,RegionBounds]:
    if layout_key not in CONTENT_LAYOUT_REGIONS: raise ValueError(f"未対応の本文layoutです：{layout_key}")
    values=_resolve_ratio(layout_key,ratio)
    if layout_key=="full": return {"full":RegionBounds(CONTENT_AREA_LEFT,CONTENT_AREA_TOP,CONTENT_AREA_WIDTH,CONTENT_AREA_HEIGHT)}
    if layout_key=="two_row": return _vertical(CONTENT_LAYOUT_REGIONS[layout_key],values,GAPS[layout_key])
    return _horizontal(CONTENT_LAYOUT_REGIONS[layout_key],values,GAPS[layout_key])
