# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_assets.py
# ============================================================
# スライドテーマ画像 パス管理
#
# 機能：
# - テーマ画像の保存先を管理する
# - スライド種別に対応する画像ファイルを取得する
# - 画像が存在しない場合はNoneを返す
#
# 方針：
# - Streamlitには依存しない
# - assets配下の構成をこのファイルで一元管理する
# - 画像がなくてもPowerPoint生成全体は停止させない
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pathlib import Path


# ============================================================
# パス
# ============================================================
_THIS = Path(__file__).resolve()
APP_DIR = _THIS.parents[2]

SLIDE_THEME_ASSETS_DIR = (
    APP_DIR
    / "assets"
    / "slide"
    / "themes"
)


# ============================================================
# スライド種別別画像名
# ============================================================
_THEME_IMAGE_NAMES: dict[str, str] = {
    "title": "title.png",
    "section": "section.png",
    "subsection": "subsection.png",
}


# ============================================================
# テーマ画像フォルダー
# ============================================================
def get_theme_asset_dir(
    *,
    theme_asset_key: str,
) -> Path | None:
    """
    テーマ画像フォルダーを取得する．

    theme_asset_keyが空の場合，またはフォルダーが存在しない場合は
    Noneを返す．
    """

    cleaned_key = theme_asset_key.strip()

    if not cleaned_key:
        return None

    asset_dir = (
        SLIDE_THEME_ASSETS_DIR
        / cleaned_key
    )

    if not asset_dir.is_dir():
        return None

    return asset_dir


# ============================================================
# テーマ画像
# ============================================================
def get_theme_image_path(
    *,
    theme_asset_key: str,
    slide_type: str,
) -> Path | None:
    """
    スライド種別に対応するテーマ画像のパスを取得する．

    対応する画像名がない場合，画像ファイルが存在しない場合は
    Noneを返す．
    """

    image_name = _THEME_IMAGE_NAMES.get(
        slide_type.strip()
    )

    if not image_name:
        return None

    asset_dir = get_theme_asset_dir(
        theme_asset_key=theme_asset_key,
    )

    if asset_dir is None:
        return None

    image_path = asset_dir / image_name

    if not image_path.is_file():
        raise FileNotFoundError(
            f"画像がありません：{image_path}"
        )

    return image_path