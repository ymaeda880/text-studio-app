# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/content_layouts/models.py
# ============================================================
# 本文領域 座標モデル
# ============================================================

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionBounds:
    left: float
    top: float
    width: float
    height: float
