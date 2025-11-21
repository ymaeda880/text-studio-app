# -*- coding: utf-8 -*-
# lib/table/presets.py
#
# 33_表作成(new) 用のプリセット定義とサンプルテキスト

from __future__ import annotations

# ① サンプル表（「サンプルデータを入れる」用）
EXAMPLE_TEXT: str = (
    "品目\t分類\t数量\t単価(円)\t金額(円)\n"
    "りんご\t青果\t12\t120\t1440\n"
    "<同上＞\t<同上＞\t8\t120\t960\n"
    "みかん\t青果\t8\t80\t640\n"
    "ぶどう\t青果\t2\t450\t900\n"
    "<同上＞\t<同上＞\t2\t450\t900"
)

# ② スタイルプリセット
PRESETS: dict[str, dict] = {
    "シンプル（罫線あり・見出し白）": dict(
        header_bg="#FFFFFF",
        header_fg="#000000",
        header_bold=True,
        body_bg=None,
        body_fg="#000000",
        font_name="Meiryo",
        inner_h=True,
        inner_v=True,
        outer=True,
        zebra=False,
    ),
    "ゼブラ（横＋縦罫・見出し濃色）": dict(
        header_bg="#2F5597",
        header_fg="#FFFFFF",
        header_bold=True,
        body_bg=None,
        body_fg="#222222",
        font_name="Meiryo",
        inner_h=True,
        inner_v=True,
        outer=True,
        zebra=True,
    ),
    "横罫のみ（モノトーン）": dict(
        header_bg=None,
        header_fg="#000000",
        header_bold=True,
        body_bg=None,
        body_fg="#000000",
        font_name="Meiryo",
        inner_h=True,
        inner_v=False,
        outer=True,            # 外枠ロジックを有効化
        outer_mode="top_bottom",  # ★ helpers の outer_mode に渡す用
        zebra=False,
    ),
    "ボックス＋見出し色": dict(
        header_bg="#DDEBF7",
        header_fg="#000000",
        header_bold=True,
        body_bg="#FFFFFF",
        body_fg="#000000",
        font_name="Meiryo",
        inner_h=True,
        inner_v=True,
        outer=True,
        zebra=False,
    ),
    "濃色ヘッダー": dict(
        header_bg="#1F4E79",
        header_fg="#FFFFFF",
        header_bold=True,
        body_bg="#FFFFFF",
        body_fg="#222222",
        font_name="Meiryo",
        inner_h=True,
        inner_v=True,
        outer=True,
        zebra=False,
    ),
}
