# -*- coding: utf-8 -*-
# text_studio_app/lib/chart_check/extractors.py
# ============================================================
# 図表チェック：抽出ロジック
#
# - 図・表・図表番号の抽出
# - タイトル / 本文参照の判定
# - 全角・半角・ハイフン揺れの正規化
# - excerpt / 強調行の作成
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import re
from typing import Any, Dict, List, Tuple

from lib.text_normalizer import (
    z2h_numhy,
    HY,
)

# ============================================================
# 正規表現定義
# ============================================================
DOT = r"[\.．・･]"
NUM_ZH = r"[0-9０-９]+"

NUM_TOKEN = rf"""
(
    {NUM_ZH}
    (?:\s*(?:{DOT}|{HY})\s*{NUM_ZH})*
    (?:\s*[（(]\s*
        (?:
            {NUM_ZH}\s*[\/／]\s*{NUM_ZH}
            |
            {NUM_ZH}
        )
    \s*[）)]\s*)?
    |
    [（(]\s*{NUM_ZH}\s*[）)]
)
"""

EXTRACT_RE = re.compile(
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})",
    re.X,
)

# ============================================================
# regex fallback
# ============================================================
try:
    import regex as re2
except Exception:
    re2 = re

PARTICLES_RE = re2.compile(r"(?:に|を|は|へ|で|と|の|など|等|または|又は|および|及び|かつ)")


# ============================================================
# 番号正規化
# ============================================================
def canon_num(num: str) -> str:
    # ------------------------------------------------------------
    # 全角数字・全角括弧 → 半角
    # ------------------------------------------------------------
    s = num.translate(str.maketrans("０１２３４５６７８９（）", "0123456789()"))

    # ------------------------------------------------------------
    # ドット類 → "."
    # ------------------------------------------------------------
    s = re.sub(DOT, ".", s)

    # ------------------------------------------------------------
    # ハイフン類 → "-"
    # ------------------------------------------------------------
    s = re.sub(HY, "-", s)

    # ------------------------------------------------------------
    # "." と "-" の前後スペース削除
    # ------------------------------------------------------------
    s = re.sub(r"\s*\.\s*", ".", s)
    s = re.sub(r"\s*-\s*", "-", s)

    # ------------------------------------------------------------
    # 複数スペース → 1個
    # ------------------------------------------------------------
    s = re.sub(r"[ \u3000]+", " ", s)

    # ------------------------------------------------------------
    # 括弧内スペース削除
    # ------------------------------------------------------------
    s = re.sub(r"\(\s*", "(", s)
    s = re.sub(r"\s*\)", ")", s)

    return s.strip()


# ============================================================
# ラベル正規化
# ============================================================
def canon_label(kind: str, num: str) -> str:
    return f"{kind}{canon_num(num)}"


# ============================================================
# マッチを含む行を抽出
# ============================================================
def extract_line_covering_match(full: str, start: int, end: int) -> Tuple[int, str, int, int]:
    """
    マッチを必ず含む行を返す。
    改行またぎ対策として、match start/end から行範囲を復元する。
    """
    line_start = full.rfind("\n", 0, start)
    line_start = 0 if line_start == -1 else line_start + 1

    line_end = full.find("\n", end)
    if line_end == -1:
        line_end = len(full)

    line_txt = full[line_start:line_end].rstrip("\r\n")
    approx_lineno = full.count("\n", 0, line_start) + 1

    return approx_lineno, line_txt, line_start, line_end


# ============================================================
# 1ページ内の図表タイトル / 本文参照を抽出
# ============================================================
def judge_hits_in_page(page_text: str, ctx: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    1ページ分のテキストから、図表タイトルと本文参照を抽出する。

    判定方針：
    - 行頭でない → 参照
    - 行頭でも直後が助詞・接続語 → 参照
    - 行に句点がある → 参照
    - それ以外 → タイトル
    """
    captions: List[Dict[str, Any]] = []
    refs: List[Dict[str, Any]] = []

    full = page_text.replace("\r\n", "\n").replace("\r", "\n")

    for m in EXTRACT_RE.finditer(full):
        kind = m.group("kind")
        num = m.group("num")
        raw = m.group(0)

        lineno, line_txt, line_start, line_end = extract_line_covering_match(
            full,
            m.start(),
            m.end(),
        )

        # ------------------------------------------------------------
        # タイトル / 参照 判定
        # ------------------------------------------------------------
        is_line_head = full[line_start:m.start()].strip() == ""
        rel_end = (m.start() - line_start) + len(raw)
        after_on_line = line_txt[rel_end:] if rel_end <= len(line_txt) else ""

        particle_follow = bool(re2.match(rf"\s*{PARTICLES_RE.pattern}", after_on_line))
        # has_period = "。" in line_txt
        has_period = ("。" in line_txt) or ("．" in line_txt)

        is_reference = (not is_line_head) or particle_follow or has_period

        # ------------------------------------------------------------
        # 表示用：強調行 / excerpt
        # ------------------------------------------------------------
        highlighted = line_txt.replace(raw, f"⟪{raw}⟫", 1)

        left = max(0, m.start() - ctx)
        right = min(len(full), m.end() + ctx)
        excerpt = full[left:m.start()] + f"⟪{raw}⟫" + full[m.end():right]

        # ------------------------------------------------------------
        # 本文参照
        # ------------------------------------------------------------
        if is_reference:
            refs.append(
                {
                    "行番号": lineno,
                    "参照テキスト": raw.strip(),
                    "図表種類": kind,
                    "図表番号": f"{kind}{z2h_numhy(num)}",
                    "図表キー": canon_label(kind, num),
                    "match_start": int(m.start()),
                    "match_end": int(m.end()),
                    "line_start": int(line_start),
                    "line_end": int(line_end),
                    "excerpt": excerpt,
                    "行テキスト": line_txt,
                    "行テキスト(強調)": highlighted,
                    "判定": "参照",
                    "rule(理由)": (
                        "行頭でない→参照"
                        if not is_line_head
                        else ("直後が助詞/接続語→参照" if particle_follow else "行に句点あり→参照")
                    ),
                }
            )

        # ------------------------------------------------------------
        # 図表タイトル
        # ------------------------------------------------------------
        else:
            title = re.sub(r"^[\s:：.\-．、・]+", "", after_on_line).strip()

            captions.append(
                {
                    "行番号": lineno,
                    "図表種類": kind,
                    "図表番号": f"{kind}{z2h_numhy(num)}",
                    "図表キー": canon_label(kind, num),
                    "見出しタイトル": title,
                    "matched_line": line_txt,
                    "matched_line(強調)": highlighted,
                    "excerpt": excerpt,
                    "判定": "タイトル",
                    "rule(理由)": "その他→タイトル",
                }
            )

    return captions, refs