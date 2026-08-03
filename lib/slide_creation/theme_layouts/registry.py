# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_layouts/registry.py
# ============================================================
# テーマレイアウト 動的読込・振り分け
#
# 機能：
# - テーマが指定するレイアウトモジュールを動的に読み込む
# - ページ種別ごとの描画関数を呼び出す
# - 専用描画がない場合はbasicレイアウトを使用する
#
# 方針：
# - 色テーマとページレイアウトを分離する
# - layout_keyとPythonファイル名を一致させる
# - テーマ追加時に登録辞書を編集しない
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import importlib
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from lib.slide_creation.models import (
    PresentationSettings,
    SlideDefinition,
    SlideTheme,
)


# ============================================================
# 共通レイアウト
# ============================================================
_BASIC_LAYOUT_KEY = "basic"


# ============================================================
# レイアウトキー取得
# ============================================================
def _resolve_layout_key(
    theme: SlideTheme,
) -> str:
    """
    テーマが使用するレイアウトキーを返す．

    layout_keyが空の場合は，テーマキーを使用する．
    """

    layout_key = str(theme.layout_key or "").strip()

    if layout_key:
        return layout_key

    return str(theme.key or "").strip()


# ============================================================
# レイアウトモジュール読込
# ============================================================
@lru_cache(maxsize=None)
def _load_layout_module(
    layout_key: str,
) -> ModuleType | None:
    """
    レイアウトキーに対応するモジュールを読み込む．

    例：
        basic
        ↓
        lib.slide_creation.theme_layouts.basic
    """

    cleaned_key = str(layout_key or "").strip()

    if not cleaned_key:
        return None

    module_name = (
        "lib.slide_creation.theme_layouts."
        f"{cleaned_key}"
    )

    try:
        return importlib.import_module(module_name)

    except ModuleNotFoundError as exc:
        # 指定したモジュール自体がない場合だけ，
        # レイアウトなしとして扱う．
        if exc.name == module_name:
            return None

        # モジュール内部の別importが失敗した場合は，
        # 原因を隠さない．
        raise


# ============================================================
# 描画関数取得
# ============================================================
def _get_renderer(
    *,
    theme: SlideTheme,
    renderer_name: str,
) -> Any | None:
    """
    テーマが指定するレイアウトから描画関数を取得する．

    指定レイアウトに関数がない場合は，
    basicレイアウトから取得する．
    """

    layout_key = _resolve_layout_key(theme)

    module = _load_layout_module(layout_key)

    if module is not None:
        renderer = getattr(
            module,
            renderer_name,
            None,
        )

        if callable(renderer):
            return renderer

    # --------------------------------------------------------
    # basicへのフォールバック
    # --------------------------------------------------------
    if layout_key != _BASIC_LAYOUT_KEY:
        basic_module = _load_layout_module(
            _BASIC_LAYOUT_KEY,
        )

        if basic_module is not None:
            renderer = getattr(
                basic_module,
                renderer_name,
                None,
            )

            if callable(renderer):
                return renderer

    return None


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
    renderer = _get_renderer(
        theme=theme,
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
    renderer = _get_renderer(
        theme=theme,
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
    renderer = _get_renderer(
        theme=theme,
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


# ============================================================
# 本文ページ描画
# ============================================================
# ============================================================
# 本文ページ描画
# ============================================================
def render_registered_content(
    slide: Any,
    *,
    slide_def: SlideDefinition,
    settings: PresentationSettings,
    page_number: int,
    theme: SlideTheme,
    inbox_root: Path,
    sub: str,
) -> bool:
    """
    テーマレイアウトの本文ページを描画する．

    描画関数がない場合はFalseを返す．
    """

    renderer = _get_renderer(
        theme=theme,
        renderer_name="render_content",
    )

    if renderer is None:
        return False

    renderer(
        slide,
        slide_def=slide_def,
        settings=settings,
        page_number=page_number,
        theme=theme,
        inbox_root=inbox_root,
        sub=sub,
    )

    return True

# ============================================================
# 最終ページ描画
# ============================================================
def render_registered_ending(
    slide: Any,
    *,
    slide_def: SlideDefinition,
    settings: PresentationSettings,
    theme: SlideTheme,
) -> bool:
    renderer = _get_renderer(
        theme=theme,
        renderer_name="render_ending",
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