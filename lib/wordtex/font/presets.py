# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/font/presets.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FontPreset:
    body: str
    heading: str
    mono: str


FONT_PRESETS: dict[str, FontPreset] = {
    "report": FontPreset(
        body="游明朝",
        heading="游ゴシック",
        mono="Consolas",
    ),
    "biz": FontPreset(
        body="BIZ UDP明朝",
        heading="BIZ UDPゴシック",
        mono="BIZ UDゴシック",
    ),
    "gothic": FontPreset(
        body="游ゴシック",
        heading="游ゴシック",
        mono="Consolas",
    ),
    "mincho": FontPreset(
        body="游明朝",
        heading="游明朝",
        mono="Consolas",
    ),
}


def get_font_preset(name: str) -> FontPreset:
    key = str(name or "").strip()
    return FONT_PRESETS.get(key, FONT_PRESETS["report"])