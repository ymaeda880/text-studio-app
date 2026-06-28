# -*- coding: utf-8 -*-
# ============================================================
# wordTex color definitions
# ============================================================

from __future__ import annotations

from docx.shared import RGBColor


COLOR_MAP: dict[str, RGBColor] = {
    "black": RGBColor(0, 0, 0),
    "gray": RGBColor(128, 128, 128),
    "grey": RGBColor(128, 128, 128),

    "red": RGBColor(255, 0, 0),
    "green": RGBColor(0, 128, 0),
    "blue": RGBColor(0, 112, 192),

    "cyan": RGBColor(0, 176, 240),
    "magenta": RGBColor(255, 0, 255),
    "yellow": RGBColor(255, 255, 0),

    "orange": RGBColor(237, 125, 49),
    "purple": RGBColor(112, 48, 160),
    "brown": RGBColor(153, 102, 51),
}