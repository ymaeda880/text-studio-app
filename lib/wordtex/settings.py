# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/settings.py
# ============================================================
# wordTex 設定状態
#
# - \set{...} の設定を保持する
# - 図番号の作成・更新を担当する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from dataclasses import dataclass, field


# ============================================================
# Preview 開発用設定
# ============================================================
DEV_FORCE_NO_MS_WORD = False
DEV_FORCE_NO_ONLYOFFICE = False
DEV_FORCE_NO_LIBREOFFICE = False

# ============================================================
# 図番号設定
# ============================================================
@dataclass
class FigureNumberSettings:
    """
    図番号の状態を保持する。

    例:
    - fig_numbers=[1], fig_format="{1}"         → 図1
    - fig_numbers=[3, 1], fig_format="{1}-{2}"  → 図3-1
    - fig_numbers=[3, 1], fig_format="{1}({2})" → 図3(1)
    - fig_numbers=[1, 1, 1], fig_format="{1}-{2}({3})" → 図1-1(1)
    """

    caption: str = "図"
    caption_sep: str = "："
    numbers: list[int] = field(default_factory=lambda: [1])
    number_format: str = "{1}"
    increment_level: int = 1
    reset_lower: bool = True
    caption_position: str = "bottom"

    def format_number_core(self) -> str:
        """
        接頭辞なしの図番号だけを返す。

        例:
        numbers=[3, 1], number_format="{1}-{2}"
        → 3-1

        \\ref{} ではこの値を使う。
        """
        number_text = self.number_format

        for i, value in enumerate(self.numbers, start=1):
            number_text = number_text.replace(
                "{" + str(i) + "}",
                str(value),
            )

        return number_text


    def format_number(self) -> str:
        """
        接頭辞つきの図番号文字列を作成する。

        例:
        caption="図", numbers=[3, 1], number_format="{1}-{2}"
        → 図3-1
        """
        return f"{self.caption}{self.format_number_core()}"
    

    def format_caption(self, caption_text: str) -> str:
        """
        図番号と図題を結合する。

        caption_text が空の場合は，図番号だけを返す。
        """
        fig_no = self.format_number()

        caption_text = str(caption_text or "").strip()
        if not caption_text:
            return fig_no

        return f"{fig_no}{self.caption_sep}{caption_text}"

    def increment(self) -> None:
        """
        図を1つ出力した後に，指定階層の番号を増やす。
        """
        level = int(self.increment_level)

        if level < 1:
            level = 1

        while len(self.numbers) < level:
            self.numbers.append(1)

        idx = level - 1
        self.numbers[idx] += 1

        if self.reset_lower:
            for j in range(idx + 1, len(self.numbers)):
                self.numbers[j] = 1

    def set_numbers(self, values: list[int]) -> None:
        """
        図番号列を直接セットする。

        例:
        [3, 1] → 次の図は 図3-1 または 図3(1)
        """
        cleaned: list[int] = []

        for v in values:
            try:
                cleaned.append(int(v))
            except Exception:
                continue

        if not cleaned:
            cleaned = [1]

        self.numbers = cleaned

    def set_increment_level(self, value: int) -> None:
        """
        図を出した後に増やす階層を指定する。
        """
        try:
            level = int(value)
        except Exception:
            level = 1

        if level < 1:
            level = 1

        self.increment_level = level

        while len(self.numbers) < level:
            self.numbers.append(1)


# ============================================================
# wordTex全体の設定状態
# ============================================================
@dataclass
class WordTexSettings:
    """
    wordTex全体の設定状態。

    初版では図番号とsection番号を中心に扱う。
    将来的には表番号，目次設定などを追加する。
    """

    figure: FigureNumberSettings = field(default_factory=FigureNumberSettings)

    # ------------------------------------------------------------
    # section番号
    # - section       → 1
    # - subsection    → 1.1
    # - subsubsection → 1.1.1
    # ------------------------------------------------------------
    section_numbers: list[int] = field(default_factory=lambda: [0, 0, 0])

    # ------------------------------------------------------------
    # 見出し表示形式
    # {num}   : 番号
    # {title} : タイトル
    # ------------------------------------------------------------
    section_title_format: str = "{num} {title}"
    subsection_title_format: str = "{num} {title}"
    subsubsection_title_format: str = "{num} {title}"

    labels: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


    def next_section_number(
        self,
        *,
        level: int,
    ) -> str:
        """
        section番号を進めて，表示用の番号文字列を返す。

        level=1 → 1
        level=2 → 1.1
        level=3 → 1.1.1
        """
        try:
            level_int = int(level)
        except Exception:
            level_int = 1

        if level_int < 1:
            level_int = 1

        if level_int > 3:
            level_int = 3

        while len(self.section_numbers) < 3:
            self.section_numbers.append(0)

        idx = level_int - 1

        # --------------------------------------------------------
        # 指定階層を1つ進める
        # --------------------------------------------------------
        self.section_numbers[idx] += 1

        # --------------------------------------------------------
        # 下位階層はリセットする
        # 例:
        # 1.2 の後に section が来たら 2 にする
        # --------------------------------------------------------
        for j in range(idx + 1, len(self.section_numbers)):
            self.section_numbers[j] = 0

        nums = self.section_numbers[:level_int]

        return ".".join(str(n) for n in nums)
    

    def resolve_refs(self, text: str) -> str:
        """
        本文中の \\ref{label} を登録済み番号へ置換する。

        例:
        図\\ref{fig:site}
        → 図1

        第\\ref{sec:intro}章
        → 第1章
        """
        import re

        def repl(match) -> str:
            label = str(match.group(1) or "").strip()
            if not label:
                return "??"

            return self.labels.get(
                label,
                f"??{label}??",
            )

        return re.sub(
            r"\\ref\{([^}]+)\}",
            repl,
            str(text or ""),
        )    

    def register_label(
        self,
        *,
        label: str,
        value: str,
    ) -> None:
        """
        label と図番号文字列の対応を保存する。
        """
        label = str(label or "").strip()
        value = str(value or "").strip()

        if not label:
            return

        self.labels[label] = value

    def add_warning(self, message: str) -> None:
        """
        警告を追加する。
        """
        message = str(message or "").strip()
        if message:
            self.warnings.append(message)


# ============================================================
# bool変換
# ============================================================
def parse_bool(value: object, *, default: bool = False) -> bool:
    text = str(value or "").strip().lower()

    if not text:
        return default

    if text in {"true", "1", "yes", "y", "on"}:
        return True

    if text in {"false", "0", "no", "n", "off"}:
        return False

    return default


# ============================================================
# fig_numbers 変換
# ============================================================
def parse_number_list(value: object) -> list[int]:
    """
    fig_numbers=3,1 のような値を [3, 1] に変換する。
    """
    text = str(value or "").strip()

    if not text:
        return [1]

    parts = [p.strip() for p in text.split(",")]
    numbers: list[int] = []

    for part in parts:
        if not part:
            continue

        try:
            numbers.append(int(part))
        except Exception:
            continue

    return numbers or [1]


# ============================================================
# \set{...} の適用
# ============================================================
def apply_wordtex_setting(
    *,
    settings: WordTexSettings,
    key: str,
    value: object,
) -> None:
    r"""
    \set{key=value} の設定を WordTexSettings に反映する。

    初版で扱う図番号設定:
    - fig_caption
    - fig_caption_sep
    - fig_numbers
    - fig_format
    - fig_increment_level
    - fig_reset_lower
    - fig_caption_position
    """
    key_text = str(key or "").strip()
    value_text = str(value or "").strip()

    if not key_text:
        return

    fig = settings.figure

    if key_text == "fig_caption":
        fig.caption = value_text or "図"
        return

    if key_text == "fig_caption_sep":
        fig.caption_sep = value_text
        return

    if key_text == "fig_numbers":
        fig.set_numbers(parse_number_list(value_text))
        return

    if key_text == "fig_format":
        fig.number_format = value_text or "{1}"
        return

    if key_text == "fig_increment_level":
        try:
            fig.set_increment_level(int(value_text))
        except Exception:
            settings.add_warning(
                f"fig_increment_level が不正です: {value_text}"
            )
        return

    if key_text == "fig_reset_lower":
        fig.reset_lower = parse_bool(value_text, default=True)
        return

    if key_text == "fig_caption_position":
        if value_text in {"top", "bottom"}:
            fig.caption_position = value_text
        else:
            settings.add_warning(
                f"fig_caption_position が不正です: {value_text}"
            )
        return
    
    if key_text == "section_title_format":
        settings.section_title_format = (
            value_text or "{num} {title}"
        )
        return

    if key_text == "subsection_title_format":
        settings.subsection_title_format = (
            value_text or "{num} {title}"
        )
        return

    if key_text == "subsubsection_title_format":
        settings.subsubsection_title_format = (
            value_text or "{num} {title}"
        )
        return

    settings.add_warning(
        f"未対応の set 設定です: {key_text}={value_text}"
    )