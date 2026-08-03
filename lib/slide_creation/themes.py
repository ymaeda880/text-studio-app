# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/themes.py
# ============================================================
# PowerPointスライド作成 テーマ・選択肢定義
#
# 機能：
# - 共通テーマを管理する
# - ヘッダー・フッターを管理する
# - ページ種別ごとのスタイルを管理する
#
# 方針：
# - 新しいスタイルは辞書への追加で対応する
# - Streamlitには依存しない
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pptx.dml.color import RGBColor

from lib.slide_creation.models import SelectionOption, SlideTheme

from lib.slide_creation.theme_layouts.discovery import (
    discover_special_themes,
)

# ============================================================
# デフォルト
# ============================================================
DEFAULT_THEME_KEY = "business_blue"
DEFAULT_HEADER_KEY = "title_band"
DEFAULT_FOOTER_KEY = "standard"

DEFAULT_SLIDE_TYPES = [
    "title",
    "section",
    "content",
    "subsection",
    "ending",
]


# ============================================================
# ページ種別
# ============================================================
SLIDE_TYPES: dict[str, SelectionOption] = {
    "title": SelectionOption(
        key="title",
        label="タイトルページ",
        description="資料全体のタイトル，サブタイトル，発表者などを表示します．",
    ),
    "section": SelectionOption(
        key="section",
        label="見出しページ",
        description="章や大きなテーマの開始位置に使用します．",
    ),
    "subsection": SelectionOption(
        key="subsection",
        label="小見出しページ",
        description="資料の途中で話題を切り替える際に使用します．",
    ),
    "content": SelectionOption(
        key="content",
        label="本文ページ",
        description="箇条書き，2カラム，比較などの本文を表示します．",
    ),
    "ending": SelectionOption(
        key="ending",
        label="最終ページ",
        description="終了メッセージ，問い合わせ先，まとめなどを表示します．",
    ),
}


# ============================================================
# 共通テーマ
# ============================================================
STANDARD_SLIDE_THEMES: dict[str, SlideTheme] = {
    "business_blue": SlideTheme(
        key="business_blue",
        label="ビジネス・ブルー",
        description="青を基調とした標準的な業務資料向けデザインです．",
        font_name="游ゴシック",
        primary_color=RGBColor(31, 78, 121),
        accent_color=RGBColor(91, 155, 213),
        background_color=RGBColor(245, 247, 250),
        panel_color=RGBColor(255, 255, 255),
        panel_line_color=RGBColor(210, 218, 228),
        title_text_color=RGBColor(255, 255, 255),
        body_text_color=RGBColor(45, 55, 65),
        sub_text_color=RGBColor(110, 120, 130),
        layout_key="basic",
    ),
    "simple_light": SlideTheme(
        key="simple_light",
        label="シンプル・ライト",
        description="白を基調とした明るく簡潔なデザインです．",
        font_name="游ゴシック",
        primary_color=RGBColor(55, 55, 55),
        accent_color=RGBColor(92, 145, 175),
        background_color=RGBColor(255, 255, 255),
        panel_color=RGBColor(248, 249, 250),
        panel_line_color=RGBColor(225, 225, 225),
        title_text_color=RGBColor(255, 255, 255),
        body_text_color=RGBColor(55, 55, 55),
        sub_text_color=RGBColor(125, 125, 125),
        layout_key="basic",
    ),
    "modern_dark": SlideTheme(
        key="modern_dark",
        label="モダン・ダーク",
        description="暗い背景と明るい文字を使用したデザインです．",
        font_name="游ゴシック",
        primary_color=RGBColor(27, 31, 39),
        accent_color=RGBColor(62, 169, 245),
        background_color=RGBColor(20, 23, 29),
        panel_color=RGBColor(35, 40, 49),
        panel_line_color=RGBColor(67, 74, 87),
        title_text_color=RGBColor(255, 255, 255),
        body_text_color=RGBColor(235, 238, 242),
        sub_text_color=RGBColor(165, 172, 185),
        layout_key="basic",
    ),
    "academic_green": SlideTheme(
        key="academic_green",
        label="アカデミック・グリーン",
        description="講義や研究発表向けの落ち着いたデザインです．",
        font_name="游ゴシック",
        primary_color=RGBColor(39, 91, 75),
        accent_color=RGBColor(89, 156, 128),
        background_color=RGBColor(247, 250, 248),
        panel_color=RGBColor(255, 255, 255),
        panel_line_color=RGBColor(205, 221, 214),
        title_text_color=RGBColor(255, 255, 255),
        body_text_color=RGBColor(45, 65, 58),
        sub_text_color=RGBColor(105, 125, 118),
        layout_key="basic",
    ),
}

# ============================================================
# 特別テーマ
# ============================================================
SPECIAL_SLIDE_THEMES: dict[str, SlideTheme] = (
    discover_special_themes()
)

# ============================================================
# 全テーマ
# ============================================================
SLIDE_THEMES: dict[str, SlideTheme] = {
    **STANDARD_SLIDE_THEMES,
    **SPECIAL_SLIDE_THEMES,
}


# ============================================================
# ヘッダー
# ============================================================
HEADER_STYLES: dict[str, SelectionOption] = {
    "title_band": SelectionOption(
        key="title_band",
        label="タイトル帯",
        description="スライド上部に色付きのタイトル帯を表示します．",
    ),
    "simple_line": SelectionOption(
        key="simple_line",
        label="シンプルライン",
        description="タイトルの下にアクセントラインを表示します．",
    ),
    "none": SelectionOption(
        key="none",
        label="装飾なし",
        description="タイトル文字だけを表示します．",
    ),
}


# ============================================================
# フッター
# ============================================================
FOOTER_STYLES: dict[str, SelectionOption] = {
    "standard": SelectionOption(
        key="standard",
        label="標準",
        description="左に資料名，右にページ番号を表示します．",
    ),
    "detailed": SelectionOption(
        key="detailed",
        label="詳細",
        description="会社名，資料名，日付，ページ番号を表示します．",
    ),
    "confidential": SelectionOption(
        key="confidential",
        label="社外秘",
        description="資料名，社外秘，ページ番号を表示します．",
    ),
    "none": SelectionOption(
        key="none",
        label="フッターなし",
        description="フッターを表示しません．",
    ),
}


# ============================================================
# タイトルページ
# ============================================================
TITLE_STYLES: dict[str, SelectionOption] = {
    "left_accent": SelectionOption(
        key="left_accent",
        label="左アクセント",
        description="左側にアクセント帯を置き，タイトルを左寄せします．",
    ),
    "centered": SelectionOption(
        key="centered",
        label="中央配置",
        description="タイトルとサブタイトルを中央に配置します．",
    ),
    "vertical_info": SelectionOption(
        key="vertical_info",
        label="下部情報を縦に配置",
        description=(
            "タイトルとサブタイトルを中央に配置し，"
            "会社名，発表者名，日付を下部へ縦に配置します．"
        ),
    ),
    "full_color": SelectionOption(
        key="full_color",
        label="全面カラー",
        description="全面をメインカラーで塗り，白文字を使用します．",
    ),
    "minimal": SelectionOption(
        key="minimal",
        label="シンプル",
        description="装飾を抑えた簡潔なタイトルページです．",
    ),
}


# ============================================================
# 見出しページ
# ============================================================
SECTION_STYLES: dict[str, SelectionOption] = {
    "full_color": SelectionOption(
        key="full_color",
        label="全面カラー",
        description="全面カラー背景に章番号とタイトルを表示します．",
    ),
    "large_number": SelectionOption(
        key="large_number",
        label="大番号",
        description="章番号を大きく表示します．",
    ),
    "left_aligned": SelectionOption(
        key="left_aligned",
        label="左寄せ",
        description="章番号と見出しを左側へ配置します．",
    ),
    "centered": SelectionOption(
        key="centered",
        label="中央配置",
        description="見出しを中央へ大きく配置します．",
    ),
}


# ============================================================
# 小見出しページ
# ============================================================
SUBSECTION_STYLES: dict[str, SelectionOption] = {
    "accent_band": SelectionOption(
        key="accent_band",
        label="アクセント帯",
        description="中央にアクセント帯を配置します．",
    ),
    "card": SelectionOption(
        key="card",
        label="カード",
        description="見出しと説明をカード内へ配置します．",
    ),
    "minimal": SelectionOption(
        key="minimal",
        label="シンプル",
        description="見出しと短い説明だけを表示します．",
    ),
    "dark_panel": SelectionOption(
        key="dark_panel",
        label="濃色パネル",
        description="濃いパネル内に見出しを表示します．",
    ),
}


# ============================================================
# 本文ページ
# ============================================================
CONTENT_STYLES: dict[str, SelectionOption] = {
    "bullet": SelectionOption(
        key="bullet",
        label="箇条書き",
        description="本文を1つの枠に箇条書きで配置します．",
    ),
    "two_column": SelectionOption(
        key="two_column",
        label="2カラム",
        description="本文を前半と後半に分け，左右へ配置します．",
    ),
    "comparison": SelectionOption(
        key="comparison",
        label="比較",
        description="本文の奇数行と偶数行を左右へ配置します．",
    ),
    "message": SelectionOption(
        key="message",
        label="メッセージ強調",
        description="重要な短いメッセージを中央へ大きく表示します．",
    ),
    "text_image": SelectionOption(
        key="text_image",
        label="文章＋画像",
        description=(
            "左側に文章を配置し，"
            "右側に画像を配置します．"
        ),
    ),
}


# ============================================================
# 最終ページ
# ============================================================
ENDING_STYLES: dict[str, SelectionOption] = {
    "thank_you": SelectionOption(
        key="thank_you",
        label="ご清聴ありがとうございました",
        description="終了メッセージを中央へ大きく表示します．",
    ),
    "contact": SelectionOption(
        key="contact",
        label="お問い合わせ",
        description="問い合わせ先や担当者情報を表示します．",
    ),
    "summary": SelectionOption(
        key="summary",
        label="まとめ",
        description="資料のまとめを箇条書きで表示します．",
    ),
    "minimal": SelectionOption(
        key="minimal",
        label="シンプル終了",
        description="短い終了メッセージだけを表示します．",
    ),
}


# ============================================================
# ページ種別別スタイル
# ============================================================
SLIDE_STYLE_MAP = {
    "title": TITLE_STYLES,
    "section": SECTION_STYLES,
    "subsection": SUBSECTION_STYLES,
    "content": CONTENT_STYLES,
    "ending": ENDING_STYLES,
}


DEFAULT_STYLE_MAP = {
    "title": "left_accent",
    "section": "full_color",
    "subsection": "accent_band",
    "content": "bullet",
    "ending": "thank_you",
}


# ============================================================
# 取得関数
# ============================================================
def get_theme(theme_key: str) -> SlideTheme:
    return SLIDE_THEMES.get(theme_key, SLIDE_THEMES[DEFAULT_THEME_KEY])


def get_slide_type_options() -> list[str]:
    return list(SLIDE_TYPES.keys())


def get_slide_type_label(slide_type: str) -> str:
    option = SLIDE_TYPES.get(slide_type)
    return option.label if option else slide_type


def get_style_options(slide_type: str) -> list[str]:
    return list(SLIDE_STYLE_MAP.get(slide_type, {}).keys())


def get_style_label(slide_type: str, style_key: str) -> str:
    option = SLIDE_STYLE_MAP.get(slide_type, {}).get(style_key)
    return option.label if option else style_key


def get_default_style_key(slide_type: str) -> str:
    return DEFAULT_STYLE_MAP.get(slide_type, "bullet")


def get_option_label(options: dict[str, SelectionOption], key: str) -> str:
    option = options.get(key)
    return option.label if option else key