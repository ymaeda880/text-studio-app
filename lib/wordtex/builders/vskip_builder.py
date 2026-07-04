# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/builders/vskip_builder.py
# ============================================================
# wordTex vskip builder
#
# - \vskip{...} を Word の縦方向スペースとして出力する
# - line / pt / mm / cm / in に対応する
# ============================================================

from __future__ import annotations

import re

from docx.document import Document as DocumentObject
from docx.shared import Pt

from lib.wordtex.blocks import VSkipBlock
from lib.wordtex.settings import WordTexSettings


_VSKIP_AMOUNT_RE = re.compile(
    r"^\s*(?P<value>[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>line|pt|mm|cm|in)\s*$",
    re.IGNORECASE,
)


def _vskip_amount_to_pt(
    *,
    amount: str,
    settings: WordTexSettings,
) -> float | None:
    """
    \vskip の指定値を pt に変換する。

    対応:
        1line
        0.5line
        2line
        12pt
        5mm
        1cm
        0.3in

    line は本文サイズを基準にする。
    現時点では 1line = settings.size * 1.2 とする。
    """
    text = str(amount or "").strip()

    m = _VSKIP_AMOUNT_RE.match(text)
    if not m:
        return None

    value = float(m.group("value"))
    unit = str(m.group("unit") or "").lower()

    if unit == "line":
        return float(settings.size) * 1.2 * value

    if unit == "pt":
        return value

    if unit == "mm":
        return value * 72.0 / 25.4

    if unit == "cm":
        return value * 72.0 / 2.54

    if unit == "in":
        return value * 72.0

    return None


def add_vskip_block(
    *,
    doc: DocumentObject,
    settings: WordTexSettings,
    block: VSkipBlock,
) -> None:
    """
    VSkipBlock を Word の空段落として出力する。

    空き量は space_after に入れる。
    段落自体の文字は入れない。
    """
    amount = str(block.amount or "").strip()

    pt_value = _vskip_amount_to_pt(
        amount=amount,
        settings=settings,
    )

    if pt_value is None:
        settings.add_warning(
            f"vskip の指定が不正です: {amount}"
        )
        return

    if pt_value < 0:
        settings.add_warning(
            f"vskip に負の値は指定できません: {amount}"
        )
        return

    # ------------------------------------------------------------
    # 縦方向スペース
    #
    # space_after に入れると，
    #   空段落そのものの高さ + space_after
    # になり，指定より広くなる。
    #
    # そのため，空段落の行高を exact 指定して，
    # その段落1個ぶんを vskip の高さとして使う。
    # ------------------------------------------------------------
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = Pt(pt_value)