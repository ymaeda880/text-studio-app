# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/table/styles.py
# ============================================================
# SlideTex 表スタイル
#
# 機能：
# - 表スタイルごとの見た目を定義する
# - ヘッダー・通常セル・罫線の設定を保持する
# - SlideThemeの色を使用して実際の描画設定を生成する
#
# 方針：
# - PowerPointの表生成そのものはrenderer.pyへ任せる
# - 固定色を持たず，SlideThemeの色を利用する
# - スタイル追加はTABLE_STYLE_KEYSへの追加で対応する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from dataclasses import dataclass
from typing import Any

from lib.slide_creation.models import (
    SlideTheme,
)


# ============================================================
# 公開定数
# ============================================================
DEFAULT_TABLE_STYLE_KEY = "simple"

TABLE_STYLE_KEYS = {
    "simple",
    "grid",
    "banded",
    "accent",
    "minimal",
}


# ============================================================
# 表スタイル設定
# ============================================================
@dataclass(frozen=True)
class TableStyleDefinition:
    # --------------------------------------------------------
    # 基本設定
    # --------------------------------------------------------
    key: str

    # --------------------------------------------------------
    # 罫線
    # --------------------------------------------------------
    show_outer_border: bool = True
    show_inner_horizontal_border: bool = True
    show_inner_vertical_border: bool = True

    border_width_pt: float = 0.8

    # --------------------------------------------------------
    # ヘッダー
    # --------------------------------------------------------
    header_bold: bool = True
    header_fill_color: Any | None = None
    header_text_color: Any | None = None

    # --------------------------------------------------------
    # 通常セル
    # --------------------------------------------------------
    body_fill_color: Any | None = None
    body_text_color: Any | None = None

    # --------------------------------------------------------
    # 左端ヘッダー列
    # --------------------------------------------------------
    row_header_fill_color: Any | None = None
    row_header_text_color: Any | None = None

    # --------------------------------------------------------
    # 交互行
    # --------------------------------------------------------
    use_banded_rows: bool = False
    banded_fill_color: Any | None = None

    # --------------------------------------------------------
    # 文字設定
    # --------------------------------------------------------
    font_size: int = 15
    header_font_size: int = 15

    # --------------------------------------------------------
    # セル余白
    # --------------------------------------------------------
    margin_left_inch: float = 0.08
    margin_right_inch: float = 0.08
    margin_top_inch: float = 0.04
    margin_bottom_inch: float = 0.04


# ============================================================
# スタイル確認
# ============================================================
def is_supported_table_style(
    style_key: str,
) -> bool:
    normalized = str(
        style_key or ""
    ).strip().lower()

    return normalized in TABLE_STYLE_KEYS


# ============================================================
# simple
# ============================================================
def _build_simple_style(
    theme: SlideTheme,
) -> TableStyleDefinition:
    return TableStyleDefinition(
        key="simple",

        # ----------------------------------------------------
        # 罫線
        # - simpleでは罫線を表示しない
        # ----------------------------------------------------
        show_outer_border=False,
        show_inner_horizontal_border=False,
        show_inner_vertical_border=False,
        border_width_pt=0.7,

        # ----------------------------------------------------
        # 上部ヘッダー
        # ----------------------------------------------------
        header_bold=True,
        header_fill_color=theme.panel_color,
        header_text_color=theme.body_text_color,

        # ----------------------------------------------------
        # 本文セル
        # ----------------------------------------------------
        body_fill_color=theme.background_color,
        body_text_color=theme.body_text_color,

        # ----------------------------------------------------
        # 左端ヘッダー列
        # ----------------------------------------------------
        row_header_fill_color=theme.panel_color,
        row_header_text_color=theme.body_text_color,

        # ----------------------------------------------------
        # 交互行
        # ----------------------------------------------------
        use_banded_rows=False,

        # ----------------------------------------------------
        # 文字
        # ----------------------------------------------------
        font_size=15,
        header_font_size=15,
    )

# ============================================================
# grid
# ============================================================
def _build_grid_style(
    theme: SlideTheme,
) -> TableStyleDefinition:
    return TableStyleDefinition(
        key="grid",

        # ----------------------------------------------------
        # 罫線
        # ----------------------------------------------------
        show_outer_border=True,
        show_inner_horizontal_border=True,
        show_inner_vertical_border=True,
        border_width_pt=0.75,

        # ----------------------------------------------------
        # 上部ヘッダー
        # - テーマの主色を使用する
        # - 白文字で明確に区別する
        # ----------------------------------------------------
        header_bold=True,
        header_fill_color=theme.primary_color,
        header_text_color=theme.title_text_color,

        # ----------------------------------------------------
        # 本文セル
        # ----------------------------------------------------
        body_fill_color=theme.background_color,
        body_text_color=theme.body_text_color,

        # ----------------------------------------------------
        # 左端ヘッダー列
        # ----------------------------------------------------
        row_header_fill_color=theme.panel_color,
        row_header_text_color=theme.body_text_color,

        # ----------------------------------------------------
        # 交互行
        # ----------------------------------------------------
        use_banded_rows=True,
        banded_fill_color=theme.panel_color,

        # ----------------------------------------------------
        # 文字
        # ----------------------------------------------------
        font_size=13,
        header_font_size=14,

        # ----------------------------------------------------
        # セル余白
        # ----------------------------------------------------
        margin_left_inch=0.10,
        margin_right_inch=0.10,
        margin_top_inch=0.06,
        margin_bottom_inch=0.06,
    )

# ============================================================
# banded
# ============================================================
def _build_banded_style(
    theme: SlideTheme,
) -> TableStyleDefinition:
    return TableStyleDefinition(
        key="banded",
        show_outer_border=True,
        show_inner_horizontal_border=True,
        show_inner_vertical_border=False,
        border_width_pt=0.7,
        header_bold=True,
        header_fill_color=theme.primary_color,
        header_text_color=theme.title_text_color,
        body_fill_color=theme.background_color,
        body_text_color=theme.body_text_color,
        row_header_fill_color=theme.panel_color,
        row_header_text_color=theme.body_text_color,
        use_banded_rows=True,
        banded_fill_color=theme.panel_color,
        font_size=15,
        header_font_size=15,
    )


# ============================================================
# accent
# ============================================================
def _build_accent_style(
    theme: SlideTheme,
) -> TableStyleDefinition:
    return TableStyleDefinition(
        key="accent",
        show_outer_border=True,
        show_inner_horizontal_border=True,
        show_inner_vertical_border=True,
        border_width_pt=0.9,
        header_bold=True,
        header_fill_color=theme.primary_color,
        header_text_color=theme.title_text_color,
        body_fill_color=theme.background_color,
        body_text_color=theme.body_text_color,
        row_header_fill_color=theme.accent_color,
        row_header_text_color=theme.title_text_color,
        use_banded_rows=False,
        font_size=15,
        header_font_size=15,
    )


# ============================================================
# minimal
# ============================================================
def _build_minimal_style(
    theme: SlideTheme,
) -> TableStyleDefinition:
    return TableStyleDefinition(
        key="minimal",
        show_outer_border=False,
        show_inner_horizontal_border=True,
        show_inner_vertical_border=False,
        border_width_pt=0.7,
        header_bold=True,
        header_fill_color=theme.background_color,
        header_text_color=theme.body_text_color,
        body_fill_color=theme.background_color,
        body_text_color=theme.body_text_color,
        row_header_fill_color=theme.background_color,
        row_header_text_color=theme.body_text_color,
        use_banded_rows=False,
        font_size=15,
        header_font_size=15,
    )


# ============================================================
# 公開関数
# ============================================================
def get_table_style(
    style_key: str,
    *,
    theme: SlideTheme,
) -> TableStyleDefinition:
    normalized = str(
        style_key or DEFAULT_TABLE_STYLE_KEY
    ).strip().lower()

    if normalized == "grid":
        return _build_grid_style(
            theme,
        )

    if normalized == "banded":
        return _build_banded_style(
            theme,
        )

    if normalized == "accent":
        return _build_accent_style(
            theme,
        )

    if normalized == "minimal":
        return _build_minimal_style(
            theme,
        )

    return _build_simple_style(
        theme,
    )