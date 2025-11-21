# -*- coding: utf-8 -*-
# lib/graph/bar/jsonc_presets.py
#
# 棒グラフページ用の JSONC プリセット入出力ユーティリティ
# - 現在の設定を JSONC（コメント付き JSON）としてダウンロード
# - JSONC ファイルを読み込んでセッションに適用

from __future__ import annotations

from typing import Any, Dict, List
import json
import re


# ------------------------------
# どのキーをどのカテゴリとして出すかの定義
# ------------------------------
TITLE_KEYS = [
    "m_k_chart_title",
    "m_k_title_bold",
    "m_k_title_size",
    "m_k_title_align",
]

ORIENTATION_KEYS = [
    "m_k_orientation",
    "k_bar_mode",
    "m_manual_bar_width",
    "m_k_bar_label_mode",
    "m_k_enable_highlight",
    "m_k_highlight_top_k",
]

SIZE_KEYS = [
    "m_k_preview_width",
    "m_k_preview_height",
]

MARGIN_KEYS = [
    "m_k_margin_l",
    "m_k_margin_r",
    "m_k_margin_t",
    "m_k_margin_b",
]

FONT_KEYS = [
    "m_k_font_family",
    "m_k_axis_title_family",
    "m_k_tick_font_family",
    "m_k_legend_font_size",
]

AXIS_KEYS = [
    "m_k_x_title",
    "m_k_y_title",
    "m_k_use_headers_as_axis_title",
    "m_k_x_title_standoff",
    "m_k_y_title_standoff",
]

TICKS_KEYS = [
    "m_k_ticks_x",
    "m_k_ticklen_x",
    "m_k_ticklabelpos_x",
    "m_k_tickangle_x",
    "m_k_ticks_y",
    "m_k_ticklen_y",
    "m_k_ticklabelpos_y",
    "m_k_tickangle_y",
    "m_k_show_grid",
]

LEGEND_KEYS = [
    "m_k_show_legend",
    "m_k_legend_location",
    "m_k_legend_orientation",
    "m_k_legend_bg",
    "m_k_legend_bordercolor",
    "m_k_legend_borderwidth",
]

COLOR_KEYS = [
    "m_k_palette_name",
    "m_k_color_alpha",
    "m_k_plot_bgcolor",
    "m_k_paper_bgcolor",
    "m_k_highlight_color",
    "m_k_nonhighlight_color",
]

FRAME_KEYS = [
    "m_k_frame_style",
    "m_k_frame_dash",
    "m_k_frame_ref_domain",
]


PARAM_GROUPS: List[Dict[str, Any]] = [
    {
        "heading": "タイトル関連",
        "keys": TITLE_KEYS,
    },
    {
        "heading": "棒の向き・バー表示・ハイライト",
        "keys": ORIENTATION_KEYS,
    },
    {
        "heading": "プレビューサイズ",
        "keys": SIZE_KEYS,
    },
    {
        "heading": "マージン（余白）",
        "keys": MARGIN_KEYS,
    },
    {
        "heading": "フォント関連",
        "keys": FONT_KEYS,
    },
    {
        "heading": "軸タイトル関連",
        "keys": AXIS_KEYS,
    },
    {
        "heading": "目盛・グリッド線",
        "keys": TICKS_KEYS,
    },
    {
        "heading": "凡例関連",
        "keys": LEGEND_KEYS,
    },
    {
        "heading": "色・背景・ハイライト色",
        "keys": COLOR_KEYS,
    },
    {
        "heading": "内側枠（プロット領域の枠線）",
        "keys": FRAME_KEYS,
    },
]


def _build_flat_preset(session_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    session_state からプリセット対象となるキー（m_k_*, k_bar_mode）だけ抜き出してフラットな dict にする。
    """
    return {
        k: v
        for k, v in session_state.items()
        if isinstance(k, str) and k.startswith(("m_k_", "k_bar_mode"))
    }


def _json_value(v: Any) -> str:
    """
    値を JSON 表現の文字列に変換する（ensure_ascii=False で日本語保持）。
    """
    return json.dumps(v, ensure_ascii=False)


def export_jsonc_from_session(session_state: Dict[str, Any]) -> str:
    """
    現在の session_state から JSONC 文字列を生成する。
    コメント行（// ...）でカテゴリごとに見出しを付ける。
    """
    flat = _build_flat_preset(session_state)

    # 「どのキーをどの順番で出すか」を並べた props リストを作る
    props: List[Dict[str, Any]] = []

    used_keys: set[str] = set()
    for grp in PARAM_GROUPS:
        heading: str = grp["heading"]
        keys: List[str] = grp["keys"]
        present_keys = [k for k in keys if k in flat]
        if not present_keys:
            continue

        props.append({"type": "comment", "text": f"=== {heading} ==="})
        for k in present_keys:
            props.append({"type": "prop", "key": k, "value": flat[k]})
            used_keys.add(k)

    # 上記いずれにも属さないキーは "その他" としてまとめる
    other_keys = [k for k in flat.keys() if k not in used_keys]
    if other_keys:
        props.append({"type": "comment", "text": "=== その他の設定 ==="})
        for k in other_keys:
            props.append({"type": "prop", "key": k, "value": flat[k]})

    lines: List[str] = []
    lines.append("{")

    # 最後の prop の位置を把握して、そこだけカンマを付けない
    prop_indices = [i for i, p in enumerate(props) if p["type"] == "prop"]
    last_prop_index = prop_indices[-1] if prop_indices else -1

    for idx, p in enumerate(props):
        if p["type"] == "comment":
            lines.append(f'  // {p["text"]}')
        else:
            key = p["key"]
            v_str = _json_value(p["value"])
            comma = "," if idx != last_prop_index else ""
            lines.append(f'  "{key}": {v_str}{comma}')

    lines.append("}")
    return "\n".join(lines)


# ------------------------------
# JSONC 読み込み・適用
# ------------------------------

_COMMENT_LINE_RE = re.compile(r"(^|\s)//.*$")


def strip_jsonc_comments(text: str) -> str:
    """
    JSONC テキストから // と /* */ のコメントを取り除いて純粋な JSON にする。
    ※簡易実装なので、文字列中の // などは使わない前提。
    """
    # /* ... */ コメントを削除（複数行対応）
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    # 行末の // コメントを削除
    lines = []
    for line in text.splitlines():
        # // から右側を落とす
        line = _COMMENT_LINE_RE.sub(r"\1", line)
        lines.append(line)
    return "\n".join(lines)


def load_preset_from_jsonc(text: str) -> Dict[str, Any]:
    """
    JSONC テキストを dict にして返す。
    """
    cleaned = strip_jsonc_comments(text)
    obj = json.loads(cleaned)
    if not isinstance(obj, dict):
        raise ValueError("プリセット JSONC はオブジェクト（{ ... }）である必要があります。")
    # キーは str のみ対象にする
    return {str(k): v for k, v in obj.items()}


def apply_preset_to_session(preset: Dict[str, Any], session_state: Dict[str, Any]) -> None:
    """
    読み込んだプリセット dict を session_state に適用する。
    - m_k_* / k_bar_mode など、既存のパラメータだけを対象にする。
    """
    for k, v in preset.items():
        if not isinstance(k, str):
            continue
        # 今回は m_k_, k_bar_mode のみ対象（必要ならここに条件を足す）
        if k.startswith(("m_k_", "k_bar_mode")):
            session_state[k] = v
