# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/models.py
# ============================================================
# PowerPointスライド作成 データモデル
#
# 機能：
# - 資料全体の設定を保持する
# - 各スライドのページ種別と内容を保持する
# - テーマ，レイアウト，ヘッダー，フッター設定を保持する
#
# 方針：
# - UIとPowerPoint生成処理の間で共通データを使用する
# - ページ種別の追加に対応しやすい構成とする
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from dataclasses import dataclass

from pptx.dml.color import RGBColor


# ============================================================
# スライド定義
# ============================================================
@dataclass
class SlideDefinition:
    slide_type: str
    style_key: str
    title: str = ""
    subtitle: str = ""
    body: str = ""
    section_number: str = ""
    left_heading: str = ""
    right_heading: str = ""
    presenter_name: str = ""
    contact_text: str = ""


# ============================================================
# 資料全体設定
# ============================================================
@dataclass(frozen=True)
class PresentationSettings:
    presentation_title: str
    company_name: str = ""
    presenter_name: str = ""
    presentation_date: str = ""
    theme_key: str = "business_blue"
    header_key: str = "title_band"
    footer_key: str = "standard"


# ============================================================
# テーマ
# ============================================================
@dataclass(frozen=True)
class SlideTheme:
    key: str
    label: str
    description: str
    font_name: str

    primary_color: RGBColor
    accent_color: RGBColor
    background_color: RGBColor
    panel_color: RGBColor
    panel_line_color: RGBColor

    title_text_color: RGBColor
    body_text_color: RGBColor
    sub_text_color: RGBColor

    title_font_size: int = 30
    body_font_size: int = 21
    footer_font_size: int = 9

    # --------------------------------------------------------
    # テーマ共通画像
    # --------------------------------------------------------
    # 空文字の場合はテーマ共通画像を使用しない．
    # 値がある場合は，
    # assets/slide/themes/<theme_asset_key>/ を参照する．
    theme_asset_key: str = ""

# ============================================================
# 選択肢
# ============================================================
@dataclass(frozen=True)
class SelectionOption:
    key: str
    label: str
    description: str