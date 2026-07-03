# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanation.py
# ============================================================
# wordTexページ 説明UI
# ============================================================

from __future__ import annotations

from typing import Any

import streamlit as st

from common_lib.ui.help_expander import render_themed_help_expander
from common_lib.ui.intro_panel import (
    render_info_card_compact,
    render_info_card_bullets_compact_custom,
)

from lib.wordtex.explanations.overview import OVERVIEW_TEXT
from lib.wordtex.explanations.input_source import INPUT_LOGIC_TEXT
from lib.wordtex.explanations.document_structure import DOCUMENT_STRUCTURE_TEXT
from lib.wordtex.explanations.set_settings import SET_LOGIC_TEXT
from lib.wordtex.explanations.heading import HEADING_TEXT
from lib.wordtex.explanations.itemize import ITEMIZE_TEXT
from lib.wordtex.explanations.figure import FIGURE_TEXT
from lib.wordtex.explanations.figuretable import FIGURE_TABLE_TEXT
from lib.wordtex.explanations.table import TABLE_TEXT
from lib.wordtex.explanations.reference import REFERENCE_TEXT
from lib.wordtex.explanations.colors import COLORS_TEXT
from lib.wordtex.explanations.word_preview import WORD_PREVIEW_TEXT
from lib.wordtex.explanations.word_build import WORD_BUILD_LOGIC_TEXT
from lib.wordtex.explanations.library_structure import LIBRARY_STRUCTURE_TEXT
from lib.wordtex.explanations.future import FUTURE_TEXT
from lib.wordtex.explanations.text_style import TEXT_STYLE_TEXT


def render_wordtex_page_intro() -> None:
    render_info_card_compact(
        body_html="""
        🟢 このページでは，<b>AIを使用</b>しません．
        """,
    )

    render_info_card_compact(
        body_html="""
このページでは，wordTex形式（.wtex）のソーステキストを読み込み，
プログラムで解析して，Word報告書を作成します．
""",
    )

    render_info_card_bullets_compact_custom(
        title="使い方",
        items=[
            ("①", "<b>wordTexソースを設定します．</b>"),
            ("", "貼り付け，.wtexファイルのアップロード，InBoxからの選択に対応します．"
                 "設定後に，「選択ファイルを読み込む」を押してください．"),
            ("②", "<b>wordTexソースを確認します．</b>"),
            ("", "読み込んだソーステキストを画面上で確認します．"),
            ("③", "<b>wordTexを解析します．</b>"),
            ("", "通常段落，見出し，箇条書き，図，表などのブロックに分解します．"),
            ("④", "<b>Word文書を作成します．</b>"),
            ("", "解析結果をもとに，見出し番号，図番号，参照を反映したWord文書を作成します．"),
            ("⑤", "<b>Wordプレビューを確認します．</b>"),
            ("", "作成したWordをPDF化し，保存前に画面上で確認します．"),
            ("⑥", "<b>Word文書を保存します．</b>"),
            ("", "作成したWord文書をダウンロードできます．"),
        ],
    )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)


    # ------------------------------------------------------------
    # 注意
    # ------------------------------------------------------------
#     render_info_card_compact(
#         title="注意",
#         body_html="""
# wordTexは，ソーステキストを正本としてWord文書を再生成する仕組みです．
# 初版では，通常段落，section番号，figureTable，図番号，参照，Wordプレビューを中心に扱います．
# """,
#     )

#     st.markdown(
#         "<div style='height:16px'></div>",
#         unsafe_allow_html=True,
#     )


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


HELP_EXPANDER_KEY = "wordtex_help_expander"
HELP_EXPANDER_TITLE = "📌 詳細説明（クリックで展開）"


HELP_TABS = [
    ("概要", OVERVIEW_TEXT),
    ("入力方法", INPUT_LOGIC_TEXT),
    ("文書構成", DOCUMENT_STRUCTURE_TEXT),
    ("set設定", SET_LOGIC_TEXT),
    ("見出し", HEADING_TEXT),
    ("箇条書き", ITEMIZE_TEXT),
    ("図", FIGURE_TEXT),
    ("figureTable", FIGURE_TABLE_TEXT),
    ("表", TABLE_TEXT),
    ("参照", REFERENCE_TEXT),
    ("文字書式", TEXT_STYLE_TEXT),
    ("色", COLORS_TEXT),
    ("Wordプレビュー", WORD_PREVIEW_TEXT),
    ("Word生成ロジック", WORD_BUILD_LOGIC_TEXT),
    ("ライブラリー構成", LIBRARY_STRUCTURE_TEXT),
    ("今後の拡張", FUTURE_TEXT),
]