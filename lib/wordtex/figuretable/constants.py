# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/figuretable/constants.py
# ============================================================
# figureTable 定数
# ============================================================

from __future__ import annotations


# ============================================================
# 背景色
# - 初版ではここに固定で持つ
# - 将来的には設定ファイルへ切り出す
# ============================================================
FIGURE_TABLE_BACKGROUND_COLORS: dict[str, str] = {
    "white": "FFFFFF",
    "lightgray": "F2F2F2",
    "lightgrey": "F2F2F2",
    "gray": "F2F2F2",
    "grey": "F2F2F2",
    "beige": "F7F0E6",
    "lightblue": "EAF3FF",
    "lightgreen": "EAF7EA",
    "lightyellow": "FFF8D8",
}


# ============================================================
# 既定値
# ============================================================
DEFAULT_FIGURE_TABLE_ROW = 2
DEFAULT_FIGURE_TABLE_BG_COLOR_KEY = "lightgray"
DEFAULT_FIGURE_TABLE_BG_COLOR_HEX = FIGURE_TABLE_BACKGROUND_COLORS[
    DEFAULT_FIGURE_TABLE_BG_COLOR_KEY
]


# ============================================================
# row制限
# ============================================================
MIN_FIGURE_TABLE_ROW = 1
MAX_FIGURE_TABLE_ROW = 4


# ============================================================
# 背景色取得
# ============================================================
def get_figure_table_bg_hex(
    color_key: str,
    *,
    default: str = DEFAULT_FIGURE_TABLE_BG_COLOR_HEX,
) -> str:
    key = str(color_key or "").strip().lower()

    if not key:
        return default

    return FIGURE_TABLE_BACKGROUND_COLORS.get(
        key,
        default,
    )


# ============================================================
# row正規化
# ============================================================
def normalize_figure_table_row(value: object) -> int:
    try:
        row = int(value)
    except Exception:
        return DEFAULT_FIGURE_TABLE_ROW

    if row < MIN_FIGURE_TABLE_ROW:
        return MIN_FIGURE_TABLE_ROW

    if row > MAX_FIGURE_TABLE_ROW:
        return MAX_FIGURE_TABLE_ROW

    return row