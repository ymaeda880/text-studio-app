# -*- coding: utf-8 -*-
# lib/image_embed/tag_metadata.py
# ============================================================
# Word画像埋込 タグ内メタ情報処理
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import re


# ============================================================
# constants
# ============================================================
META_BLOCK_RE = re.compile(r"\{[^{}]*\}")
TITLE_RE = re.compile(r"title\s*:\s*([^,{}]+)")
EXP_RE = re.compile(r"exp\s*:\s*([^,{}]+)")


# ============================================================
# tag metadata parse
# ============================================================
def parse_title_exp_from_tag(
    tag: str,
) -> tuple[str, str]:
    """
    タグ文字列から {title:...} / {exp:...} を取得する。

    例:
    プロジェクト/2025-100,{title:入口, exp:着工前}
    """
    text = str(tag or "").strip()

    title = ""
    exp = ""

    m_title = TITLE_RE.search(text)
    if m_title:
        title = m_title.group(1).strip()

    m_exp = EXP_RE.search(text)
    if m_exp:
        exp = m_exp.group(1).strip()

    return title, exp


# ============================================================
# remove metadata
# ============================================================
def remove_title_exp_metadata(
    tag: str,
) -> str:
    """
    タグ文字列から {title:...} / {exp:...} を含むメタ情報ブロックを削除する。
    """
    text = str(tag or "").strip()

    blocks = META_BLOCK_RE.findall(text)

    for block in blocks:
        if "title" in block or "exp" in block:
            text = text.replace(block, "")

    text = text.replace(",,", ",")
    text = text.strip(" ,")

    return text


# ============================================================
# build tag
# ============================================================
def build_tag_with_title_exp(
    *,
    base_tag: str,
    title: str,
    exp: str,
) -> str:
    """
    既存タグに {title:... , exp:...} を付け直す。

    title / exp が両方空なら，メタ情報なしのタグだけを返す。
    """
    base = remove_title_exp_metadata(base_tag)

    title_text = str(title or "").strip()
    exp_text = str(exp or "").strip()

    parts: list[str] = []

    if title_text:
        parts.append(f"title:{title_text}")

    if exp_text:
        parts.append(f"exp:{exp_text}")

    if not parts:
        return base

    meta = "{" + ", ".join(parts) + "}"

    if base:
        return f"{base},{meta}"

    return meta