# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanation.py
# ============================================================
# wordTexページ 説明UI
#
# - ページ上部説明UI
# - 詳細説明 expander の入口
# - 詳細本文は lib/wordtex/explanations/ 以下へ分割
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from typing import Any

import streamlit as st

from common_lib.ui.help_expander import render_themed_help_expander
from common_lib.ui.intro_panel import (
    render_info_card_compact,
    render_info_card_bullets_compact_custom,
)

from lib.wordtex.explanations.overview import OVERVIEW_TEXT
from lib.wordtex.explanations.input_source import INPUT_LOGIC_TEXT
from lib.wordtex.explanations.set_settings import SET_LOGIC_TEXT
from lib.wordtex.explanations.section_number import SECTION_NUMBER_TEXT
from lib.wordtex.explanations.figure_number import FIGURE_NUMBER_TEXT
from lib.wordtex.explanations.figuretable import FIGURE_TABLE_TEXT
from lib.wordtex.explanations.reference import REFERENCE_TEXT
from lib.wordtex.explanations.word_preview import WORD_PREVIEW_TEXT
from lib.wordtex.explanations.word_build import WORD_BUILD_LOGIC_TEXT
from lib.wordtex.explanations.library_structure import LIBRARY_STRUCTURE_TEXT
from lib.wordtex.explanations.future import FUTURE_TEXT


# ============================================================
# ページ上部説明UI
# ============================================================
def render_wordtex_page_intro() -> None:

    # ------------------------------------------------------------
    # ページ概要
    # ------------------------------------------------------------
    render_info_card_compact(
        body_html="""
このページでは，wordTex形式（.wtex）のソーステキストを読み込み，
プログラムで解析して，Word報告書を作成します．
""",
    )

    # ------------------------------------------------------------
    # 使い方
    # ------------------------------------------------------------
    render_info_card_bullets_compact_custom(
        title="使い方",
        items=[
            ("①", "<b>wordTexソースを設定します．</b>"),
            (
                "",
                "貼り付け，.wtexファイルのアップロード，InBoxからの選択に対応します．",
            ),
            ("②", "<b>wordTexソースを確認します．</b>"),
            (
                "",
                "読み込んだソーステキストを画面上で確認します．",
            ),
            ("③", "<b>wordTexを解析します．</b>"),
            (
                "",
                "通常段落，section，set設定，figureTableなどのブロックに分解します．",
            ),
            ("④", "<b>Word文書を作成します．</b>"),
            (
                "",
                "解析結果をもとに，見出し番号，図番号，参照を反映したWord文書を作成します．",
            ),
            ("⑤", "<b>Wordプレビューを確認します．</b>"),
            (
                "",
                "作成したWordをPDF化し，保存前に画面上で確認します．",
            ),
            ("⑥", "<b>Word文書を保存します．</b>"),
            (
                "",
                "作成したWord文書をダウンロードできます．",
            ),
        ],
    )

    st.markdown(
        "<div style='height:16px'></div>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------
    # 注意
    # ------------------------------------------------------------
    render_info_card_compact(
        title="注意",
        body_html="""
wordTexは，ソーステキストを正本としてWord文書を再生成する仕組みです．
初版では，通常段落，section番号，figureTable，図番号，参照，Wordプレビューを中心に扱います．
""",
    )

    st.markdown(
        "<div style='height:16px'></div>",
        unsafe_allow_html=True,
    )


# ============================================================
# public API：詳細説明 expander
# ============================================================
def render_wordtex_help_expander(
    *,
    theme: dict[str, Any] | None = None,
    banner_key: str = "navy_dark",
) -> None:
    render_themed_help_expander(
        expander_key=HELP_EXPANDER_KEY,
        expander_title=HELP_EXPANDER_TITLE,
        tabs=HELP_TABS,
        theme=theme,
        banner_key=banner_key,
        expanded=False,
    )


# ============================================================
# expander 設定
# ============================================================
HELP_EXPANDER_KEY = "wordtex_help_expander"
HELP_EXPANDER_TITLE = "📌 詳細説明（クリックで展開）"


# ============================================================
# 詳細説明タブ
# ============================================================
HELP_TABS = [
    ("概要", OVERVIEW_TEXT),
    ("入力方法", INPUT_LOGIC_TEXT),
    ("set設定", SET_LOGIC_TEXT),
    ("section番号", SECTION_NUMBER_TEXT),
    ("図番号", FIGURE_NUMBER_TEXT),
    ("figureTable", FIGURE_TABLE_TEXT),
    ("参照", REFERENCE_TEXT),
    ("Wordプレビュー", WORD_PREVIEW_TEXT),
    ("Word生成ロジック", WORD_BUILD_LOGIC_TEXT),
    ("ライブラリー構成", LIBRARY_STRUCTURE_TEXT),
    ("今後の拡張", FUTURE_TEXT),
]