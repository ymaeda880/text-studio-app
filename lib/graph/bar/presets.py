# -*- coding: utf-8 -*-
# lib/graph/bar/presets.py
#
# 棒グラフ共通のデフォルト値・プリセット・パレット・フォント候補など

from __future__ import annotations
from typing import Dict, List

# =========================
#  ページ共通 DEFAULTS
# =========================
DEFAULTS: Dict[str, object] = {
    # 表示・スタイル
    "m_k_chart_title": "",
    "m_k_title_bold": True,
    "m_k_title_size": 22,
    "m_k_title_align": "中央",
    "m_k_show_legend": True,
    "m_k_show_grid": True,
    "m_k_palette_name": "Minimal",
    "m_k_color_alpha": 0.6,
    "m_k_font_family": "(system default)",

    # 凡例（詳細）
    "m_k_legend_location": "外-上",     # 外-上/外-下/外-左/外-右/ 内-右上/内-右下/内-左上/内-左下
    "m_k_legend_orientation": "自動",    # 自動/横(h)/縦(v)
    "m_k_legend_font_size": 16,
    "m_k_legend_bg": "rgba(255,255,255,0.0)",
    "m_k_legend_bordercolor": "rgba(0,0,0,0.3)",
    "m_k_legend_borderwidth": 0,

    # 枠線（内側 / プロット領域）
    "m_k_frame_style": "四角",           # なし/四角/角丸
    "m_k_frame_dash": "実線",            # 実線/破線/点線
    #"m_k_corner_radius_frac": 0.025,
    "m_k_frame_ref_domain": True,        # True: x/y domain, False: paper

    # 枠線（外側 / 図全体）
    #"m_k_outerframe_style": "なし",
    #"m_k_outerframe_dash": "実線",
    #"m_k_outer_radius_px": 16,

    # 軸タイトル・目盛（共通）
    "m_k_x_title": "",
    "m_k_y_title": "",
    "m_k_axis_title_size": 16,
    "m_k_axis_title_family": "(グラフ全体と同じ)",
    "m_k_tick_font_size": 16,
    "m_k_tick_font_family": "(グラフ全体と同じ)",
    "m_k_use_headers_as_axis_title": True,

    # 軸の値の表示形式 & スケール
    "m_k_value_format_mode": "そのまま",  # そのまま / カンマ区切り

    # 目盛（位置/長さ/ラベル位置/角度）
    "m_k_ticks_x": "outside",           # outside / inside / (なし)
    "m_k_ticks_y": "outside",
    "m_k_ticklen_x": 3,                 # px
    "m_k_ticklen_y": 3,
    "m_k_ticklabelpos_x": "自動",       # 自動/外-下/外-上/内-下/内-上
    "m_k_ticklabelpos_y": "自動",       # 自動/外-左/外-右/内-左/内-右
    "m_k_tickangle_x": 0,               # 度
    "m_k_tickangle_y": 0,

    # 余白
    "m_k_margin_l": 60,
    "m_k_margin_r": 20,
    "m_k_margin_t": 60,
    "m_k_margin_b": 60,

    # 軸タイトル ↔ 目盛の距離
    "m_k_x_title_standoff": 12,
    "m_k_y_title_standoff": 12,

    # プレビューサイズ + アスペクト
    "m_k_preview_width": 820,
    "m_k_preview_aspect": 0.58,      # 高さ = 幅 * 0.58
    "m_k_preview_height": int(820*0.58),

    # エクスパンダ初期開閉（初期=閉）
    "exp_style_open": False,
    "exp_group_open": False,
    "exp_diag_open": False,

    # 出力サイズ（PNG/SVG）
    "m_k_out_w":820,   # 初回にプレビューから決定
    "m_k_out_h": int(820*0.58),
    "m_k_out_dpi": 220,
    "sync_export_to_preview": True,
    "lock_export_square": False,

    # 棒の太さ
    "k_bar_mode": "自動",
    "m_manual_bar_width": 1, #自動を同じ太さ
 
    # 棒グラフの向き
    "m_k_orientation": "縦",   # 縦 or 横

    # 棒ラベルの表示モード
    "m_k_bar_label_mode": "非表示",
    "m_k_label_font_size": 11,
    "m_k_label_font_family": "(グラフ全体と同じ)",
    "m_k_label_decimals": 0,   # 小数点以下の桁数


    # ハイライト関連（上位K本）
    "m_k_enable_highlight": False,
    "m_k_highlight_top_k": 3,
    "m_k_highlight_color_label": "ピンク (#f17c9b)",
    "m_k_highlight_color": "#f17c9b",

    # 非ハイライト棒の色（残りの棒を何色にするか）
    "m_k_nonhighlight_color_label": "うすグレー (#d9d9d9)",
    "m_k_nonhighlight_color": "#d9d9d9",

    # 背景色
    "m_k_plot_bgcolor": "white",    # プロット領域の背景
    "m_k_paper_bgcolor": "white",   # 全体（余白部分）の背景

    # データの変換
    "m_k_scale_exp_data": 0,   # ★ データスケーリング（10^x）のデフォルト値

    # Annotation（カテゴリラベルを annotation で描くモード）のデフォルト

    # Annotation ラベルを使うか？
    "m_k_use_annotation_labels": False,

    # Annotation テキストのフォントサイズ
    "m_k_anno_font_size": 12,

    # Annotation テキストのフォントファミリー
    # "(グラフ全体と同じ)" を使うことで統一したフォントにできる
    "m_k_anno_font_family": "(グラフ全体と同じ)",

    # Annotation 用 左側マージン幅（px）
    # 長い日本語ラベルを想定して余裕をもった値
    "m_k_anno_margin_left": 260,

    # Annotation テキストの X 位置（paper 座標系）0〜1
    # 推奨：0（グラフ左端）
    "m_k_anno_x": 0.0,

    # "ピクセル単位のずらし
    "m_k_anno_xshift": -10,

    # Annotation テキストの行揃え（left/center/right）
    "m_k_anno_align": "left",

    # Annotation テキストのアンカー
    # "left" / "center" / "right"
    # 横棒グラフの場合、右揃えのまま align=left の組み合わせが綺麗
    "m_k_anno_xanchor": "right",

    # Annotation テキストの色
    "m_k_anno_color": "#000000",

    # Annotation を表示するのは横棒のみ？
    "m_k_anno_horizontal_only": True,

    # Annotation の vertical alignment
    "m_k_anno_valign": "middle",


}

# =========================
#  サンプル貼り付け用テキスト
# =========================
sample_hint = """クラス別成績
クラス\t国語\t数学\t英語
A\t68\t72\t81
B\t75\t65\t78
C\t80\t70\t88
"""

sample_hint3 = """オンライン学習サービスの利用意向
項目\t割合
オンライン講座に興味はあるが、<br>まだ利用したことがない\t0.331
スキル向上のためにオンライン教材を<br>探してみたいと思っているが、<br>まだ実際には試していない\t0.249
定期的にオンライン講座や<br>動画教材を利用して学習している\t0.183
一度だけオンライン講座を<br>受講した経験がある\t0.122
オンライン学習には特に興味がない\t0.085
その他\t0.030
"""

sample_hint2 = """成績（サンプル）
氏名\t数学\t英語\t理科
田中 太郎\t98\t88\t74
佐藤 花子\t78\t82\t70
鈴木 一郎\t99\t83\t62
高橋 久美\t89\t97\t61
伊藤 大輔\t81\t84\t86
渡辺 綾\t62\t96\t66
中村 健\t77\t63\t84
"""

sample_hint4 = """日本のGDP
年\t名目GDP
2015\t520000000000000
2016\t535000000000000
2017\t548000000000000
2018\t556000000000000
2019\t560000000000000
2020\t540000000000000
2021\t558000000000000
2022\t575000000000000
"""


# =========================
#  色パレット
# =========================
PALETTES: Dict[str, List[str]] = {
    "Minimal":   ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"],
    "Corporate": ["#2E86AB", "#F6AA1C", "#A23E48", "#33658A", "#55DDE0", "#758E4F"],
    "Playful":   ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6A4C93", "#1A8FE3", "#95D02B"],

    # ============================
    #  単色パレット  Single Colors
    # ============================

    # 🔵 青系
    "SingleBlue":           ["#6fa8dc"],   # HIGHLIGHT_COLOR_CHOICES の青
    "SingleBlueDeep":       ["#3B82F6"],   # Minimal の1色目
    "SingleNavy":           ["#1a4a89"],
    "SingleSkyBlue":        ["#87ceeb"],

    # 🟢 緑系
    "SingleGreen":          ["#93c47d"],   # HIGHLIGHT_COLOR_CHOICES の緑
    "SingleGreenDeep":      ["#10B981"],
    "SingleEmerald":        ["#2ecc71"],
    "SingleMint":           ["#a4d8c0"],

    # 🔴 赤系
    "SingleRed":            ["#e06666"],   # HIGHLIGHT_COLOR_CHOICES の赤
    "SingleRedDeep":        ["#d62828"],
    "SinglePink":           ["#f17c9b"],   # HIGHLIGHT_COLOR_CHOICES のピンク
    "SingleRose":           ["#ff4d6d"],

    # 🟠 オレンジ / 黄色系
    "SingleOrange":         ["#f6b26b"],   # HIGHLIGHT のオレンジ
    "SingleOrangeDeep":     ["#f59e0b"],
    "SingleYellow":         ["#ffd966"],   # HIGHLIGHT の黄色
    "SingleGold":           ["#daa520"],

    # 🟣 紫系
    "SinglePurple":         ["#8e7cc3"],   # HIGHLIGHT の紫
    "SinglePurpleDeep":     ["#6A4C93"],
    "SingleLavender":       ["#c8b6ff"],

    # ⚫ グレー / モノクロ系（資料でよく使う）
    "SingleGrayLight":      ["#d9d9d9"],   # NON_HIGHLIGHT のうすグレー
    "SingleGray":           ["#b7b7b7"],   # NON_HIGHLIGHT のグレー
    "SingleGrayDark":       ["#999999"],   # NON_HIGHLIGHT のこいグレー
    "SingleBlueGray":       ["#a4b7c6"],   # NON_HIGHLIGHT の青みグレー
    "SingleBeige":          ["#e6d5b8"],   # NON_HIGHLIGHT のベージュ
    "SingleBlack":          ["#000000"],   # 黒
}


# 🔹 ハイライト用色候補（ラベル → HEX）
HIGHLIGHT_COLOR_CHOICES: Dict[str, str] = {
    "ピンク (#f17c9b)": "#f17c9b",
    "赤 (#e06666)": "#e06666",
    "オレンジ (#f6b26b)": "#f6b26b",
    "黄色 (#ffd966)": "#ffd966",
    "緑 (#93c47d)": "#93c47d",
    "青 (#6fa8dc)": "#6fa8dc",
    "紫 (#8e7cc3)": "#8e7cc3",
    "グレー (#b7b7b7)": "#b7b7b7",
    "黒 (#000000)": "#000000",
}

# 🔸 非ハイライト用の色候補（ラベル → HEX）
NON_HIGHLIGHT_COLOR_CHOICES: Dict[str, str] = {
    "うすグレー (#d9d9d9)": "#d9d9d9",
    "グレー (#b7b7b7)": "#b7b7b7",
    "こいグレー (#999999)": "#999999",
    "青みグレー (#a4b7c6)": "#a4b7c6",
    "ベージュ (#e6d5b8)": "#e6d5b8",
}

# =========================
#  フォント候補
# =========================
FONT_CANDS: List[str] = [
    "IPAexGothic", "IPAGothic",
    "Noto Sans CJK JP", "Noto Sans JP",
    "Hiragino Sans", "Hiragino Kaku Gothic ProN",
    "Yu Gothic", "Yu Gothic UI",
    "Meiryo", "Meiryo UI",
    "MS Gothic", "MS PGothic",
    "(system default)",
]

# =========================
#  レイアウトプリセット
# =========================
PRESETS: Dict[str, Dict] = {
    "標準（DEFAULTS相当）": {
        # 必要なら個別の上書きを書く（今は DEFAULTS と同等）
    },
    "論文：左余白広め・外ラベル": {
        "m_k_margin_l": 90, "m_k_margin_r": 20, "m_k_margin_t": 60, "m_k_margin_b": 60,
        "m_k_ticks_y": "outside", "m_k_ticklen_y": 6, "m_k_ticklabelpos_y": "外-左",
        "m_k_ticks_x": "outside", "m_k_ticklen_x": 6, "m_k_ticklabelpos_x": "外-下",
        "m_k_x_title_standoff": 18, "m_k_y_title_standoff": 18,
        "m_k_axis_title_size": 16, "m_k_tick_font_size": 14,
        "m_k_show_grid": True,
        "m_k_frame_style": "四角", "m_k_frame_dash": "実線",
        "m_k_outerframe_style": "なし",
        "m_k_legend_location": "外-上",
        "m_k_legend_orientation": "横(h)",
        "m_k_legend_font_size": 14,
    },
    "プレゼン：文字大きめ・凡例は下外": {
        "m_k_margin_l": 60, "m_k_margin_r": 30, "m_k_margin_t": 60, "m_k_margin_b": 80,
        "m_k_tick_font_size": 16, "m_k_axis_title_size": 18,
        "m_k_x_title_standoff": 16, "m_k_y_title_standoff": 16,
        "m_k_ticks_x": "outside", "m_k_ticklabelpos_x": "外-下",
        "m_k_ticks_y": "outside", "m_k_ticklabelpos_y": "外-左",
        "m_k_show_grid": True,
        "m_k_legend_location": "外-下",
        "m_k_legend_orientation": "横(h)",
        "m_k_legend_font_size": 16,
        "m_k_title_size": 26,
        "m_k_title_align": "中央",
    },
    "記事/Web：フラット（枠なし・薄グリッド）": {
        "m_k_show_grid": False,
        "m_k_frame_style": "なし",
        "m_k_outerframe_style": "なし",
        "m_k_ticks_y": "(なし)", "m_k_ticklen_y": 0,
        "m_k_ticks_x": "outside", "m_k_ticklen_x": 4, "m_k_ticklabelpos_x": "外-下",
        "m_k_legend_location": "内-右上",
        "m_k_legend_orientation": "縦(v)",
        "m_k_legend_bg": "rgba(255,255,255,0.6)",
        "m_k_legend_borderwidth": 0,
        "m_k_palette_name": "Playful",
        "m_k_color_alpha": 0.8,
    },
    "学会投稿：細線・角丸外枠": {
        "m_k_show_grid": True,
        "m_k_frame_style": "四角",
        "m_k_frame_dash": "点線",
        "m_k_outerframe_style": "角丸",
        "m_k_outerframe_dash": "実線",
        "m_k_outer_radius_px": 16,
        "m_k_legend_location": "外-右",
        "m_k_legend_orientation": "縦(v)",
        "m_k_legend_font_size": 12,
        "m_k_axis_title_size": 14,
        "m_k_tick_font_size": 12,
        "m_k_palette_name": "Corporate",
        "m_k_color_alpha": 0.9,
        "m_k_x_title_standoff": 14,
        "m_k_y_title_standoff": 14,
    },
    "サンプル1": {
        "k_bar_mode": "手動",
        "m_manual_bar_width": 0.5,

        # == プレビューサイズ ===
        "m_k_preview_width": 700,
    },
    "サンプル2": {
        "k_bar_mode": "自動",

        #// === 色・背景・ハイライト色 ===
        "m_k_palette_name": "Corporate",

    },
    # アンケート用：横棒 + 右ラベル + 上位K本だけ色を変え、他は薄グレー
    "サンプル3": {
        "m_k_tick_font_size": 12,
        "m_k_orientation": "横",

        "m_k_bar_label_mode": "表示",
        "m_k_label_decimals": 2,   # 小数点以下の桁数

        "m_k_show_legend": False,

        "m_k_use_headers_as_axis_title": False,

        # ハイライト設定
        "m_k_enable_highlight": True,
        "m_k_highlight_top_k": 3,   # 上位3本
        "m_k_highlight_color_label": "ピンク (#f17c9b)",
        "m_k_highlight_color": "#f17c9b",

        # 非ハイライト棒の色（残りの棒を淡いグレーに）
        "m_k_nonhighlight_color_label": "うすグレー (#d9d9d9)",
        "m_k_nonhighlight_color": "#d9d9d9",

        "m_k_plot_bgcolor": "white",
        "m_k_paper_bgcolor": "white",

        "m_k_font_family":	"Meiryo",

        #// === カテゴリラベル（annotation） ===
        "m_k_use_annotation_labels": True,
        "m_k_anno_x": -0.45,
        "m_k_anno_xanchor": "left",

        # == プレビューサイズ ===
        "m_k_preview_height": 400,
    },
       "サンプル4": {
        #// === 色・背景・ハイライト色 ===
        "m_k_palette_name": "SingleEmerald",
        
        #// === 棒の向き・バー表示・ハイライト ===
        "m_k_bar_mode": "手動",
        "m_k_bar_width": 0.7,

        #// === データのスケーリング，カンマ区切り表示 ===
        "m_k_scale_exp_data": -11,
        "m_k_value_format_mode": "カンマ区切り"
       
    },
}
