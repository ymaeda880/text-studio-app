# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_image_renderer.py
# ============================================================
# スライドテーマ背景画像 描画
#
# 機能：
# - テーマ画像をスライド全面へ配置する
# - 画像の縦横比を維持する
# - スライド比率に合わせて中央トリミングする
#
# 方針：
# - Streamlitには依存しない
# - テーマ画像がない場合は何もせずFalseを返す
# - 画像は他の図形より先に追加し，最背面として扱う
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from typing import Any

from PIL import Image

from lib.slide_creation.models import SlideTheme
from lib.slide_creation.theme_assets import (
    get_theme_image_path,
)


# ============================================================
# クロップ率
# ============================================================
def _calculate_center_crop(
    *,
    image_width: int,
    image_height: int,
    slide_width: int,
    slide_height: int,
) -> tuple[float, float, float, float]:
    """
    スライド全面へ画像を配置するための中央クロップ率を返す．

    戻り値：
        crop_left
        crop_top
        crop_right
        crop_bottom
    """

    if (
        image_width <= 0
        or image_height <= 0
        or slide_width <= 0
        or slide_height <= 0
    ):
        return 0.0, 0.0, 0.0, 0.0

    image_ratio = image_width / image_height
    slide_ratio = slide_width / slide_height

    crop_left = 0.0
    crop_top = 0.0
    crop_right = 0.0
    crop_bottom = 0.0

    if image_ratio > slide_ratio:
        # 画像の方が横長の場合，左右を切り取る．
        visible_ratio = slide_ratio / image_ratio
        horizontal_crop = (
            1.0 - visible_ratio
        ) / 2.0

        crop_left = horizontal_crop
        crop_right = horizontal_crop

    elif image_ratio < slide_ratio:
        # 画像の方が縦長の場合，上下を切り取る．
        visible_ratio = image_ratio / slide_ratio
        vertical_crop = (
            1.0 - visible_ratio
        ) / 2.0

        crop_top = vertical_crop
        crop_bottom = vertical_crop

    return (
        crop_left,
        crop_top,
        crop_right,
        crop_bottom,
    )


# ============================================================
# テーマ背景画像
# ============================================================
def add_theme_background_image(
    *,
    slide: Any,
    prs: Any,
    theme: SlideTheme,
    slide_type: str,
) -> bool:
    """
    スライド種別に対応するテーマ背景画像を追加する．

    画像を追加した場合はTrue，
    画像を使用しなかった場合はFalseを返す．
    """

    if not theme.theme_asset_key:
        return False

    image_path = get_theme_image_path(
        theme_asset_key=theme.theme_asset_key,
        slide_type=slide_type,
    )

    if image_path is None:
        raise FileNotFoundError(
            "テーマ背景画像が見つかりません："
            f"theme={theme.key}，"
            f"theme_asset_key={theme.theme_asset_key}，"
            f"slide_type={slide_type}"
        )

    try:
        with Image.open(image_path) as image:
            image_width, image_height = image.size

        picture = slide.shapes.add_picture(
            str(image_path),
            0,
            0,
            width=prs.slide_width,
            height=prs.slide_height,
        )

        (
            crop_left,
            crop_top,
            crop_right,
            crop_bottom,
        ) = _calculate_center_crop(
            image_width=image_width,
            image_height=image_height,
            slide_width=int(prs.slide_width),
            slide_height=int(prs.slide_height),
        )

        picture.crop_left = crop_left
        picture.crop_top = crop_top
        picture.crop_right = crop_right
        picture.crop_bottom = crop_bottom

        return True

    except Exception as exc:
        raise RuntimeError(
            "テーマ背景画像の追加に失敗しました："
            f"theme={theme.key}，"
            f"theme_asset_key={theme.theme_asset_key}，"
            f"slide_type={slide_type}，"
            f"image_path={image_path}，"
            f"error={exc}"
        ) from exc