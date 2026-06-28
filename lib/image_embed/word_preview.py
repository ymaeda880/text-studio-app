# -*- coding: utf-8 -*-
# lib/image_embed/word_preview.py
# ============================================================
# Word画像埋込 Word写真一覧表プレビュー
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pathlib import Path
from typing import Any
import base64
import html

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from common_lib.inbox.inbox_common.paths import thumb_path_for_item


# ============================================================
# image helper
# ============================================================
def _image_src_from_path(path: Path) -> str:
    suffix = path.suffix.lower()

    mime = "image/png"
    if suffix in [".jpg", ".jpeg"]:
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"

    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


# ============================================================
# Word写真一覧表プレビュー
# ============================================================
def render_photo_table_preview(
    *,
    inbox_root: Path,
    sub: str,
    selected_df: pd.DataFrame,
    document_title: str,
    columns: int,
    cell_background_color: str = "#F2F2F2",
    max_items: int = 50,
) -> None:
    """
    Word出力前に，画面上で写真一覧表の表形式プレビューを表示する。

    Streamlit標準の container では背景色を付けられないため，
    components.html で表・罫線・背景色・画像をまとめて描画する。
    """
    if selected_df is None or selected_df.empty:
        st.info("プレビュー対象がありません。")
        return

    title_text = html.escape(str(document_title or "").strip())
    columns = max(1, int(columns))
    rows: list[dict[str, Any]] = selected_df.head(max_items).to_dict("records")

    parts: list[str] = []

    parts.append(
        f"""
<style>
.photo-preview-title {{
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0 0 16px 0;
}}
.photo-preview-table {{
    border-collapse: collapse;
    width: 100%;
    table-layout: fixed;
}}
.photo-preview-table td {{
    border: 1px solid #999;
    background: {cell_background_color};
    text-align: center;
    vertical-align: middle;
}}
.photo-title-cell {{
    padding: 10px;
    font-weight: 700;
}}
.photo-image-cell {{
    padding: 12px;
    background: {cell_background_color};
}}
.photo-image-cell img {{
    width: 100%;
    height: auto;
    display: block;
    margin: 0 auto;
}}
.photo-file-name {{
    font-size: 0.8rem;
    color: #777;
    margin-top: 6px;
}}
</style>
"""
    )

    if title_text:
        parts.append(f"<div class='photo-preview-title'>{title_text}</div>")

    parts.append("<table class='photo-preview-table'>")

    for start in range(0, len(rows), columns):
        chunk = rows[start : start + columns]

        # ------------------------------------------------------------
        # タイトル行
        # ------------------------------------------------------------
        parts.append("<tr>")
        for i in range(columns):
            if i < len(chunk):
                row = chunk[i]
                title = html.escape(str(row.get("タイトル") or "").strip())
                desc = html.escape(str(row.get("説明") or "").strip())

                text = f"<div>{title}</div>"
                if desc:
                    text += f"<div style='font-size:0.85rem;color:#666;'>{desc}</div>"
            else:
                text = ""

            parts.append(f"<td class='photo-title-cell'>{text}</td>")
        parts.append("</tr>")

        # ------------------------------------------------------------
        # 画像行
        # ------------------------------------------------------------
        parts.append("<tr>")
        for i in range(columns):
            if i < len(chunk):
                row = chunk[i]
                item_id = str(row.get("item_id") or "").strip()
                filename = html.escape(str(row.get("ファイル名") or "").strip())

                image_html = "サムネ未生成"

                if item_id:
                    image_path = Path(str(row.get("path") or "").strip())

                    if image_path.exists():
                        src = _image_src_from_path(image_path)
                        image_html = f"<img src='{src}'>"

                if filename:
                    image_html += f"<div class='photo-file-name'>{filename}</div>"
            else:
                image_html = ""

            parts.append(f"<td class='photo-image-cell'>{image_html}</td>")
        parts.append("</tr>")

    parts.append("</table>")

    components.html(
        "\n".join(parts),
        height=900,
        scrolling=True,
    )