# -*- coding: utf-8 -*-
# lib/image_embed/thumb_grid.py
# ============================================================
# Word画像埋込 サムネ一覧表示
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from common_lib.inbox.inbox_common.paths import thumb_path_for_item


# ============================================================
# サムネ一覧表示
# ============================================================
def render_image_thumb_grid(
    *,
    inbox_root: Path,
    sub: str,
    image_df: pd.DataFrame,
    max_items: int = 20,
    per_row: int = 4,
) -> None:
    """
    InBox画像のサムネ一覧を表示する。

    auth_portal_app/lib/inbox_preview/thumb_grid.py と同じ考え方で，
    元画像の path ではなく item_id からサムネパスを解決する。
    """
    if image_df is None or image_df.empty:
        st.info("サムネ表示対象がありません。")
        return

    rows: list[dict[str, Any]] = image_df.to_dict(orient="records")

    if not rows:
        st.info("サムネ表示対象がありません。")
        return

    for row_i in range(0, min(len(rows), max_items), per_row):
        row_chunk = rows[row_i : row_i + per_row]
        cols = st.columns(per_row)

        for j in range(per_row):
            col = cols[j]

            if j >= len(row_chunk):
                with col:
                    st.empty()
                continue

            r0 = row_chunk[j]

            item_id = str(r0.get("item_id") or "").strip()
            kind = str(r0.get("kind") or "image").strip().lower()
            original_name = str(
                r0.get("original_name")
                or r0.get("ファイル名")
                or ""
            ).strip()

            tag = str(
                r0.get("tag_disp")
                or r0.get("タグ")
                or ""
            ).strip()

            with col:
                if kind == "image" and item_id:
                    thumb = thumb_path_for_item(
                        inbox_root,
                        sub,
                        kind,
                        item_id,
                    )

                    if thumb.exists():
                        st.image(thumb.read_bytes())
                    else:
                        st.write("🧩 サムネ未生成")
                else:
                    st.write("🧩 サムネ未生成")

                st.caption(original_name)

                if tag:
                    st.caption(f"タグ: {tag}")