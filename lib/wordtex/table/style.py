# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/table/style.py
# ============================================================
# wordTex table style resolver
# ============================================================

from __future__ import annotations

from lib.table.presets import PRESETS


TABLE_STYLE_MAP: dict[str, str] = {
    "simple": "シンプル（罫線あり・見出し白）",
    "zebra": "ゼブラ（横＋縦罫・見出し濃色）",
    "horizontal": "横罫のみ（モノトーン）",
    "box": "ボックス＋見出し色",
    "dark": "濃色ヘッダー",
}


def resolve_table_preset(style: str) -> dict:
    """
    wordTex の style 名を 26_表作成.py 側の PRESETS 名へ変換する。
    """
    style_key = str(style or "simple").strip() or "simple"
    preset_name = TABLE_STYLE_MAP.get(style_key, style_key)

    if preset_name in PRESETS:
        return PRESETS[preset_name]

    return PRESETS[TABLE_STYLE_MAP["simple"]]