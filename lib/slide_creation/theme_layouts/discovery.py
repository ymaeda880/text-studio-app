# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/theme_layouts/discovery.py
# ============================================================
# 特別テーマ 自動検出
#
# 機能：
# - theme_layouts配下のPythonファイルを検索する
# - 各モジュールのTHEMEを読み込む
# - SlideThemeの辞書として返す
#
# 方針：
# - registry.pyやthemes.pyへテーマ名を列挙しない
# - registry，discovery，__init__は検索対象外とする
# - 不正なテーマ定義は明確な例外として扱う
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import importlib
from pathlib import Path

from lib.slide_creation.models import SlideTheme


# ============================================================
# 除外モジュール
# ============================================================
_EXCLUDED_MODULE_NAMES = {
    "__init__",
    "discovery",
    "registry",
}


# ============================================================
# 特別テーマ検出
# ============================================================
def discover_special_themes() -> dict[str, SlideTheme]:
    """
    theme_layouts配下にある特別テーマを自動検出する．

    各テーマファイルには，次が必要：
        THEME = SlideTheme(...)
    """

    theme_dir = Path(__file__).resolve().parent
    discovered: dict[str, SlideTheme] = {}

    for file_path in sorted(theme_dir.glob("*.py")):
        module_stem = file_path.stem

        if module_stem in _EXCLUDED_MODULE_NAMES:
            continue

        module_name = (
            "lib.slide_creation.theme_layouts."
            f"{module_stem}"
        )

        module = importlib.import_module(module_name)

        theme = getattr(
            module,
            "THEME",
            None,
        )

        if theme is None:
            # THEMEを持たない補助モジュールは登録しない．
            continue

        if not isinstance(theme, SlideTheme):
            raise TypeError(
                "特別テーマのTHEMEは"
                "SlideThemeで定義してください："
                f"{module_name}"
            )

        if theme.key != module_stem:
            raise ValueError(
                "テーマキーとファイル名が一致していません："
                f"file={module_stem}.py，"
                f"theme.key={theme.key}"
            )

        if theme.key in discovered:
            raise ValueError(
                "テーマキーが重複しています："
                f"{theme.key}"
            )

        discovered[theme.key] = theme

    return discovered