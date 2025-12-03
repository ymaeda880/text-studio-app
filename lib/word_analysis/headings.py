# -*- coding: utf-8 -*-
# lib/word_analysis/headings.py
#
# 見出し検出・見出しID生成まわり

from __future__ import annotations

from typing import List
import re

from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn


def detect_heading_level(p: Paragraph) -> int:
    """
    見出しレベルを 1〜4 くらいで推定する。

    優先順位:
    1) スタイル名 'Heading 1', '見出し 1' など
    2) outlineLvl (w:outlineLvl)
    3) テキスト内容からの簡易推定（「第○章」「第○節」「第○項」）
    4) デフォルト 2
    """
    text = (p.text or "").strip()
    style_name = (p.style.name if p.style is not None else "") or ""

    # 1) スタイル名
    m = re.search(r"(Heading|見出し)\s*([1-4])", style_name)
    if m:
        try:
            return int(m.group(2))
        except Exception:
            pass

    # 2) outlineLvl
    try:
        elems = p._element.xpath("./w:pPr/w:outlineLvl")
        if elems:
            val = elems[0].get(qn("w:val"))
            if val is not None:
                # outlineLvl=0 → Heading1 相当
                lvl = int(val)
                return min(max(lvl + 1, 1), 4)
    except Exception:
        pass

    # 3) テキスト内容から
    if "章" in text:
        return 1
    if "節" in text:
        return 2
    if "項" in text:
        return 3

    # 4) デフォルト
    return 2


def is_heading_paragraph(p: Paragraph) -> bool:
    """
    この段落を「見出し」とみなすかどうかを判定。

    - スタイル名に 'Heading' / '見出し' を含む
    - あるいは「本文」というよりは短いラベルぽい行（句点がなくて40字以下）
    """
    text = (p.text or "").strip()
    if not text:
        return False

    style_name = (p.style.name if p.style is not None else "") or ""
    if "Heading" in style_name or "見出し" in style_name:
        return True

    # 「岩手県は〜。」のような文章は本文扱いにしたいので、
    # 句点「。」を含む場合は原則として見出し扱いしない。
    if "。" not in text and len(text) <= 40:
        return True

    return False


def format_heading_id(base_chapter: int, counters: List[int], level: int) -> str:
    """
    base_chapter + 見出しカウンタから、"3-1-2" のような ID を生成する。

    level に応じてカウンタを進める:
    - level=1: 章内の「大見出し」 → counters[0] を+1、以下リセット
    - level=2: 小見出し → counters[1] を+1、以下リセット
    - level=3,4: さらに細かい見出し

    戻り値: "3-1" / "3-1-2" / "3-1-2-1" など
    """
    # インデックスは 0〜3 を使う想定
    idx = max(1, min(level, 4)) - 1  # 0〜3 にクリップ

    # 対象レベルのカウンタを+1、より下位はリセット
    for i in range(len(counters)):
        if i < idx:
            continue
        elif i == idx:
            counters[i] += 1
        else:
            counters[i] = 0

    # 実際に 0 でないところまでを ID として採用
    parts = [str(base_chapter)]
    for c in counters:
        if c > 0:
            parts.append(str(c))
        else:
            break

    return "-".join(parts)
