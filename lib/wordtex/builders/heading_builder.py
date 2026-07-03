# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/builders/heading_builder.py
# ============================================================
# wordTex 見出し builder
#
# - HeadingBlock を Word の見出しへ出力する
# - section番号もここで付与する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from docx.document import Document as DocumentObject
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn

from lib.wordtex.font.presets import get_font_preset
from lib.wordtex.blocks import HeadingBlock
from lib.wordtex.settings import WordTexSettings


# ============================================================
# 見出し出力
# ============================================================
def add_heading_block(
    *,
    doc: DocumentObject,
    settings: WordTexSettings,
    block: HeadingBlock,
) -> None:
    r"""
    HeadingBlock を Word 見出しとして出力する。

    例:
        \section{はじめに,label="sec:intro"}
            → 1 はじめに

        \subsection{背景,label="sec:background"}
            → 1.1 背景
    """

    # ------------------------------------------------------------
    # section番号を1つ進める
    # ------------------------------------------------------------
    number_text = settings.next_section_number(
        level=int(block.level),
    )

    title = str(block.title or "").strip()

    # ------------------------------------------------------------
    # 見出し表示形式
    # ------------------------------------------------------------
    if block.level == 1:
        fmt = settings.section_title_format

    elif block.level == 2:
        fmt = settings.subsection_title_format

    else:
        fmt = settings.subsubsection_title_format

    heading_text = (
        fmt.replace("{num}", number_text)
           .replace("{title}", title)
    )
    
    # ------------------------------------------------------------
    # Word見出し出力
    # ------------------------------------------------------------
    p = doc.add_heading(
        heading_text,
        level=int(block.level),
    )

    # ------------------------------------------------------------
    # 見出し文字色
    # - Word標準では Heading スタイルが青色になるため，
    #   wordTexでは黒へ統一する。
    # ------------------------------------------------------------
    for run in p.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)

        preset = get_font_preset(settings.font)
        heading_font = preset.heading

        run.font.name = heading_font
        run._element.rPr.rFonts.set(qn("w:eastAsia"), heading_font)

    # ------------------------------------------------------------
    # 見出しの段落間隔
    #
    # Word標準の Heading スタイルに任せると，
    # 見出し下の余白が環境やスタイルにより変わる。
    # そのため wordTex 側で明示的に固定する。
    # ------------------------------------------------------------
    if block.level == 1:
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)

    elif block.level == 2:
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(4)

    else:
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)

    # ------------------------------------------------------------
    # label登録
    #
    # \section{...,label="sec:intro"}
    #        ↓
    # sec:intro → "1"
    #
    # \subsection{...,label="sec:background"}
    #        ↓
    # sec:background → "1.1"
    # ------------------------------------------------------------
    label = str(block.label or "").strip()

    if label:
        settings.register_label(
            label=label,
            value=number_text,
        )