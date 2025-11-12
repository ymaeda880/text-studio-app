# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, List

PALETTES: Dict[str, List[str]] = {
    "Minimal":   ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"],
    "Corporate": ["#2E86AB", "#F6AA1C", "#A23E48", "#33658A", "#55DDE0", "#758E4F"],
    "Playful":   ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6A4C93", "#1A8FE3", "#95D02B"],
}

DEFAULT_PRESETS = {
    "Minimal": {
        "title_bold": False, "title_size": 18, "title_align": "左",
        "show_legend": True, "show_grid": True, "markers_on": True,
        "line_width": 2.4, "palette_name": "Minimal",
        "out_w": 1200, "out_h": 700, "out_dpi": 220,
        "frame_style": "なし", "corner_radius": 20,
    },
    "Corporate": {
        "title_bold": True, "title_size": 22, "title_align": "中央",
        "show_legend": True, "show_grid": True, "markers_on": False,
        "line_width": 2.4, "palette_name": "Corporate",
        "out_w": 1400, "out_h": 760, "out_dpi": 220,
        "frame_style": "四角", "corner_radius": 20,
    },
    "Playful": {
        "title_bold": True, "title_size": 22, "title_align": "中央",
        "show_legend": True, "show_grid": False, "markers_on": True,
        "line_width": 2.4, "palette_name": "Playful",
        "out_w": 1200, "out_h": 700, "out_dpi": 220,
        "frame_style": "角丸", "corner_radius": 24,
    },
}
