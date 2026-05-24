# -*- coding: utf-8 -*-
# text_studio_app/lib/word_analysis/intermediate_text.py
# ============================================================
# Word intermediate text builder（正本）
#
# 役割:
# - Word(.docx) の Document を受け取り、AI入力用の中間テキストへ変換する
# - 見出し / 本文 / 図 / 表 / 目次候補 / 表キャプションを分類する
# - 04_word解析.py と 12_一括word校正.py の共通ロジックとして使う
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
import json
from typing import List, Tuple, Dict

# ============================================================
# imports（3rd party）
# ============================================================
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table

# ============================================================
# imports（app lib）
# ============================================================
from lib.word_analysis.blocks import (
    Block,
    iter_block_items,
    classify_paragraph,
    classify_block,
)
from lib.word_analysis.headings import (
    is_heading_paragraph,
    detect_heading_level,
    format_heading_id,
)
from lib.word_analysis.tables import table_to_json
from lib.word_analysis.images import get_image_filenames_from_paragraph


# ============================================================
# helper：見出しらしい1行かどうか
# ============================================================
def _looks_like_heading_line(s: str) -> bool:
    # ------------------------------------------------------------
    # 空文字チェック
    # ------------------------------------------------------------
    if not s:
        return False

    t = s.strip()
    if not t:
        return False

    # ------------------------------------------------------------
    # 1行のみを対象にする
    # ------------------------------------------------------------
    if "\n" in t or "\r" in t:
        return False

    # ------------------------------------------------------------
    # 句読点・記号がある場合は本文寄りとみなす
    # ------------------------------------------------------------
    for ch in ["。", "、", "，", "．", ".", ",", "!", "?", "！", "？", ":", "：", ";", "；"]:
        if ch in t:
            return False

    # ------------------------------------------------------------
    # 長さガード
    # ------------------------------------------------------------
    if len(t) < 2:
        return False
    if len(t) > 80:
        return False

    return True


# ============================================================
# public api：Word Document から中間テキストを構築
# ============================================================
def build_intermediate_text(
    doc: Document,
    base_chapter: int,
    mode: str = "detailed",
    *,
    use_same_left_placeholder: bool,
) -> Tuple[str, Dict[str, int]]:
    # ------------------------------------------------------------
    # 初期化
    # ------------------------------------------------------------
    simple_mode = mode == "simple"

    lines: List[str] = []
    stats: Dict[str, int] = {
        "heading": 0,
        "paragraph": 0,
        "table": 0,
        "figure": 0,
    }

    heading_counters = [0, 0, 0, 0]
    prev_block: Block | None = None
    pending_table_caption: Paragraph | None = None

    # ------------------------------------------------------------
    # helper：簡素モード用の空行追加
    # ------------------------------------------------------------
    def append_blank() -> None:
        if simple_mode:
            lines.append("")

    # ------------------------------------------------------------
    # Word 内の block を順番に走査
    # ------------------------------------------------------------
    for block in iter_block_items(doc):

        # ========================================================
        # Paragraph
        # ========================================================
        if isinstance(block, Paragraph):

            # ----------------------------------------------------
            # 見出し
            # ----------------------------------------------------
            if is_heading_paragraph(block):
                level = detect_heading_level(block)
                heading_id = format_heading_id(base_chapter, heading_counters, level)
                text = (block.text or "").strip()

                if text:
                    if mode == "simple":
                        append_blank()
                        lines.append(text)

                    elif mode == "standard":
                        if _looks_like_heading_line(text):
                            lines.append("<ここから見出し>")
                            lines.append(text)
                            lines.append("<ここまで見出し>")
                            lines.append("")
                            stats["heading"] += 1
                        else:
                            lines.append(text)
                            stats["paragraph"] += 1

                    else:
                        lines.append(f"=== HEADING[{heading_id}] {text} ===")
                        stats["heading"] += 1

                prev_block = block
                pending_table_caption = None
                continue

            # ----------------------------------------------------
            # 見出し以外の段落分類
            # ----------------------------------------------------
            cat = classify_paragraph(block)

            # ----------------------------------------------------
            # 目次候補は中間テキストに入れない
            # ----------------------------------------------------
            if cat == "toc":
                prev_block = block
                pending_table_caption = None
                continue

            # ----------------------------------------------------
            # 表キャプションは次の表に渡す
            # ----------------------------------------------------
            if cat == "table_caption":
                pending_table_caption = block
                prev_block = block
                continue

            # ----------------------------------------------------
            # 図キャプション
            # ----------------------------------------------------
            if cat == "figure":
                caption = (block.text or "").strip()
                img_files = get_image_filenames_from_paragraph(block)

                stats["figure"] += 1
                fig_id = stats["figure"]

                if mode == "simple":
                    append_blank()
                    if caption:
                        lines.append(caption)

                elif mode == "standard":
                    lines.append("<ここから図>")
                    if caption:
                        lines.append(caption)
                    lines.append("<ここまで図>")

                    if img_files:
                        lines.append(f"image_files: {', '.join(img_files)}")
                    else:
                        lines.append("image_files: (none)")

                else:
                    lines.append(f"=== FIGURE[{fig_id}] {caption} ===")
                    if img_files:
                        lines.append(f"image_files: {', '.join(img_files)}")
                    else:
                        lines.append("image_files: (none)")

                lines.append("")
                prev_block = block
                pending_table_caption = None
                continue

            # ----------------------------------------------------
            # 本文
            # ----------------------------------------------------
            text = (block.text or "").strip()
            if text:
                lines.append(text)
                stats["paragraph"] += 1

            prev_block = block
            pending_table_caption = None
            continue

        # ========================================================
        # Table
        # ========================================================
        if isinstance(block, Table):
            cat = classify_block(block, prev_block)

            if cat == "table":
                stats["table"] += 1

                tbl_json = table_to_json(
                    block,
                    pending_table_caption,
                    use_same_left_placeholder=use_same_left_placeholder,
                )

                # ------------------------------------------------
                # 表：簡素 / 標準モード
                # ------------------------------------------------
                if mode in ("simple", "standard"):
                    append_blank()

                    cells = tbl_json.get("cells", [])

                    lines.append("<ここから表>")

                    raw_num = (tbl_json.get("table_number") or "").strip()
                    raw_title = (tbl_json.get("title") or "").strip()

                    tbl_num = "" if raw_num.lower() == "unknown" else raw_num

                    label = raw_title

                    if not label and tbl_num:
                        label = f"表 {tbl_num}".strip()

                    if label and (not label.lstrip().startswith("表")) and tbl_num:
                        label = f"表 {tbl_num} {label}".strip()

                    if label:
                        lines.append(label)

                    for row in cells:
                        processed: List[str] = []

                        for x in row:
                            s = str(x).replace("\n", " ").replace("\r", " ")
                            s = " ".join(s.split())
                            processed.append(s)

                        row_text = ", ".join(processed)
                        lines.append(f"[{row_text}]")

                    lines.append("<ここまで表>")
                    lines.append("")

                # ------------------------------------------------
                # 表：詳細モード
                # ------------------------------------------------
                else:
                    lines.append("")

                    tbl_num = tbl_json.get("table_number", "unknown")
                    tbl_title = tbl_json.get("title", "")

                    lines.append(f"=== TABLE {tbl_num} {tbl_title} ===")
                    lines.append("```json")
                    lines.append(json.dumps(tbl_json, ensure_ascii=False, indent=2))
                    lines.append("```")
                    lines.append("=== END_TABLE ===")
                    lines.append("")

                pending_table_caption = None
                prev_block = block
                continue

            prev_block = block
            pending_table_caption = None
            continue

        # ========================================================
        # その他
        # ========================================================
        prev_block = block
        pending_table_caption = None

    # ------------------------------------------------------------
    # 中間テキストを返す
    # ------------------------------------------------------------
    intermediate_text = "\n".join(lines).strip() + "\n"
    return intermediate_text, stats