# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_layouts/registry.py
# ============================================================
# テーマ専用レイアウト 動的読込・振り分け
#
# 機能：
# - テーマキーに対応するテーマモジュールを動的に読み込む
# - タイトル，見出し，小見出しの専用描画を呼び出す
#
# 方針：
# - テーマ名とPythonファイル名を一致させる
# - テーマ追加時に登録辞書を編集しない
# - 専用レイアウトがない場合はFalseを返す
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import importlib
from functools import lru_cache
from types import ModuleType
from typing import Any

from lib.slide_creation.models import (
    PresentationSettings,
    SlideDefinition,
    SlideTheme,
)


# ============================================================
# テーマモジュール読込
# ============================================================
@lru_cache(maxsize=None)
def _load_theme_layout_module(
    theme_key: str,
) -> ModuleType | None:
    """
    テーマキーに対応するテーマ専用モジュールを読み込む．

    例：
        forest_green
        ↓
        lib.slide_creation.theme_layouts.forest_green

    対応するモジュールがない場合はNoneを返す．
    """

    cleaned_key = theme_key.strip()

    if not cleaned_key:
        return None

    module_name = (
        "lib.slide_creation.theme_layouts."
        f"{cleaned_key}"
    )

    try:
        return importlib.import_module(module_name)

    except ModuleNotFoundError as exc:
        # 指定したテーマモジュール自体がない場合だけ，
        # 専用レイアウトなしとして扱う．
        if exc.name == module_name:
            return None

        # テーマモジュール内の別importが失敗した場合は，
        # 原因を隠さずそのまま送出する．
        raise


# ============================================================
# 描画関数取得
# ============================================================
def _get_renderer(
    *,
    theme_key: str,
    renderer_name: str,
) -> Any | None:
    """
    テーマモジュールから指定した描画関数を取得する．
    """

    module = _load_theme_layout_module(theme_key)

    if module is None:
        return None

    renderer = getattr(
        module,
        renderer_name,
        None,
    )

    if not callable(renderer):
        return None

    return renderer


# ============================================================
# タイトルページ描画
# ============================================================
def render_registered_title(
    slide: Any,
    *,
    slide_def: SlideDefinition,
    settings: PresentationSettings,
    theme: SlideTheme,
) -> bool:
    """
    テーマ専用タイトルページを描画する．

    専用関数がない場合はFalseを返す．
    """

    renderer = _get_renderer(
        theme_key=theme.key,
        renderer_name="render_title",
    )

    if renderer is None:
        return False

    renderer(
        slide,
        slide_def=slide_def,
        settings=settings,
        theme=theme,
    )

    return True


# ============================================================
# 見出しページ描画
# ============================================================
def render_registered_section(
    slide: Any,
    *,
    slide_def: SlideDefinition,
    theme: SlideTheme,
) -> bool:
    """
    テーマ専用見出しページを描画する．

    専用関数がない場合はFalseを返す．
    """

    renderer = _get_renderer(
        theme_key=theme.key,
        renderer_name="render_section",
    )

    if renderer is None:
        return False

    renderer(
        slide,
        slide_def=slide_def,
        theme=theme,
    )

    return True


# ============================================================
# 小見出しページ描画
# ============================================================
def render_registered_subsection(
    slide: Any,
    *,
    slide_def: SlideDefinition,
    theme: SlideTheme,
) -> bool:
    """
    テーマ専用小見出しページを描画する．

    専用関数がない場合はFalseを返す．
    """

    renderer = _get_renderer(
        theme_key=theme.key,
        renderer_name="render_subsection",
    )

    if renderer is None:
        return False

    renderer(
        slide,
        slide_def=slide_def,
        theme=theme,
    )

    return True