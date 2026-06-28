# -*- coding: utf-8 -*-
# lib/image_embed/image_utils.py
# ============================================================
# Word画像埋込 画像ユーティリティ
# ============================================================
from __future__ import annotations

from pathlib import Path

from PIL import Image


def get_image_size_px(
    *,
    image_path: Path,
) -> tuple[int, int]:
    """
    画像のpxサイズを取得する。
    """
    with Image.open(image_path) as img:
        return img.size


def calc_docx_image_width_inches(
    *,
    mode: str,
    manual_width_cm: float,
    columns: int,
) -> float:
    """
    Word貼り付け用の画像幅を inch で返す。

    自動の場合は，列数に応じて概算幅を決める。
    """
    if mode == "手動指定":
        width_cm = float(manual_width_cm)
    else:
        if columns <= 1:
            width_cm = 14.0
        elif columns == 2:
            width_cm = 7.0
        elif columns == 3:
            width_cm = 4.7
        else:
            width_cm = 3.5

    return width_cm / 2.54


def normalize_hex_color(value: str) -> str:
    """
    Word背景色用に #RRGGBB または RRGGBB を RRGGBB へ正規化する。
    """
    text = str(value or "").strip()

    if text.startswith("#"):
        text = text[1:]

    if len(text) != 6:
        return "F2F2F2"

    return text.upper()