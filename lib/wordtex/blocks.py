# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/blocks.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


BlockKind = Literal[
    "paragraph",
    "heading",
    "paragraph_heading",
    "set",
    "figure_table",
    "figure",
    "newpage",
    "vskip",
    "title",
    "author",
    "date",
    "table_of_contents",
    "itemize",
    "table",
]

@dataclass
class TitleBlock:
    text: str
    raw: str = ""
    kind: BlockKind = "title"


@dataclass
class AuthorBlock:
    text: str
    raw: str = ""
    kind: BlockKind = "author"


@dataclass
class DateBlock:
    text: str
    raw: str = ""
    kind: BlockKind = "date"


@dataclass
class TableOfContentsBlock:
    raw: str = "\\tableofcontents"
    kind: BlockKind = "table_of_contents"

@dataclass
class ParagraphBlock:
    text: str
    noindent: bool = False
    kind: BlockKind = "paragraph"

@dataclass
class HeadingBlock:
    """
    \\section{タイトル,label="sec:x"} 形式の見出し。
    """

    level: int
    title: str
    label: str = ""
    raw: str = ""
    kind: BlockKind = "heading"


@dataclass
class ParagraphHeadingBlock:
    title: str
    label: str = ""
    raw: str = ""

@dataclass
class SetBlock:
    values: dict[str, str] = field(default_factory=dict)
    raw: str = ""
    kind: BlockKind = "set"

@dataclass
class FigureTableItem:
    file: str
    title: str = ""
    desp: str = ""
    raw: str = ""


@dataclass
class FigureTableBlock:
    """
    figureTable ブロック

    width:
        表全体の幅
        例:
            "100%"
            "80%"
            "16cm"

    col_ratio:
        列幅比率
        例:
            "1,1"
            "2,1"
            "1,2,1"
    """

    title: str = ""
    caption: str = ""
    label: str = ""

    row: int = 2
    width: str = "100%"
    col_ratio: str = ""

    bc: str = "lightgray"
    numbering: bool = True

    items: list[FigureTableItem] = field(default_factory=list)

    raw: str = ""
    kind: BlockKind = "figure_table"


@dataclass
class ItemizeItem:
    text: str = ""
    label: str = ""
    children: list["ItemizeBlock"] = field(default_factory=list)
    raw: str = ""


@dataclass
class ItemizeBlock:
    style: str = ""
    items: list[ItemizeItem] = field(default_factory=list)
    raw: str = ""
    kind: BlockKind = "itemize"

@dataclass
class FigureItem:
    file: str
    title: str = ""
    desp: str = ""
    raw: str = ""


@dataclass
class FigureBlock:
    title: str
    caption: str
    label: str
    width: str
    numbering: bool
    item: FigureItem | None
    note: str
    raw: str

@dataclass
class NewPageBlock:
    raw: str = "/newpage"


@dataclass
class VSkipBlock:
    """
    縦方向の空きを入れるブロック。

    例:
        \vskip{1line}
        \vskip{0.5line}
        \vskip{2line}
        \vskip{12pt}
        \vskip{5mm}
        \vskip{1cm}
    """

    amount: str = ""
    raw: str = ""
    kind: BlockKind = "vskip"


@dataclass
class TableBlock:
    title: str = ""
    caption: str = ""
    label: str = ""
    style: str = "simple"
    header_rows: int = 1
    header_cols: int = 0

    # ------------------------------------------------------------
    # Excel読み込み指定
    #
    # 例:
    #   \begin{table,caption="全景",src=["2019003.xlsx","sheet1"]}
    # ------------------------------------------------------------
    src_file: str = ""
    src_sheet: str = ""

    # ------------------------------------------------------------
    # 表全体の幅
    # 例:
    #   width="100%"   → 通常幅
    #   width="120%"   → 通常幅の1.2倍
    #   width="18cm"   → 18cm
    # ------------------------------------------------------------
    width: str = "100%"

    # ------------------------------------------------------------
    # 列幅比率
    # 例:
    #   col_ratio=[1,2,1]
    #   col_ratio=[100,200]
    # ------------------------------------------------------------
    col_ratio: list[float] = field(default_factory=list)

    # ------------------------------------------------------------
    # 列幅cm指定
    # 例:
    #   col_widths=[4,8,4]
    # ------------------------------------------------------------
    col_widths: list[float] = field(default_factory=list)

    # ------------------------------------------------------------
    # 表のコンパクト表示
    #
    # none        : 既定
    # normal      : 少し詰める
    # tight       : かなり詰める
    # verytight   : 最大限詰める
    # ------------------------------------------------------------
    compact: str = "none"

    # ------------------------------------------------------------
    # 表内文字サイズ
    #
    # normal    : 既定
    # small     : 少し小さい
    # verysmall : さらに小さい
    # ------------------------------------------------------------
    fontsize: str = "normal"

    # ------------------------------------------------------------
    # 表罫線
    #
    # true  : 通常どおり罫線を描く
    # false : 表全体の罫線を描かない
    #         ただしセル側の <border:top=true> などは優先する
    # ------------------------------------------------------------
    border: bool = True



    rows: list[list[str]] = field(default_factory=list)
    note: str = ""
    raw: str = ""
    kind: BlockKind = "table"

@dataclass
class ParsedWordTex:
    blocks: list[
        ParagraphBlock
        | HeadingBlock
        | ParagraphHeadingBlock
        | SetBlock
        | FigureTableBlock
        | FigureBlock
        | NewPageBlock
        | VSkipBlock
        | TitleBlock
        | AuthorBlock
        | DateBlock
        | TableOfContentsBlock
        | ItemizeBlock
        | TableBlock
    ] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        message = str(message or "").strip()
        if message:
            self.warnings.append(message)