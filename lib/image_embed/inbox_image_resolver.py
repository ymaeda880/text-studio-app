# -*- coding: utf-8 -*-
# text_studio_app/lib/image_embed/inbox_image_resolver.py
# ============================================================
# InBox画像ファイル解決
#
# - wordTexなどから file="xxx.png" で指定された画像を
#   InBoxのitems.db経由で探す
# - rglobではなく，既存のInBox検索系を使う
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pathlib import Path

import pandas as pd

from common_lib.inbox.inbox_common.paths import (
    items_db_path,
    last_viewed_db_path,
)
from common_lib.inbox.inbox_db.items_db import ensure_items_db
from common_lib.inbox.inbox_db.last_viewed_db import ensure_last_viewed_db
from common_lib.inbox.inbox_query.query_builder import (
    split_terms_and,
    build_where_and_params,
)
from common_lib.inbox.inbox_query.query_exec import query_items_page

from lib.image_embed.inbox_images import load_inbox_image_items


# ============================================================
# DB内pathを実ファイルPathへ変換
# ============================================================
def resolve_inbox_path_value(
    *,
    inbox_root: Path,
    sub: str,
    path_value: object,
) -> Path | None:
    """
    items.db の path 値を実ファイルPathへ変換する。

    path が絶対パスならそのまま使う。
    相対パスなら候補を順に確認する。
    """
    text = str(path_value or "").strip()

    if not text:
        return None

    p = Path(text)

    if p.is_absolute() and p.exists():
        return p

    candidates = [
        Path(inbox_root) / str(sub) / text,
        Path(inbox_root) / text,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


# ============================================================
# filename一致でInBox画像を探す
# ============================================================
def resolve_inbox_image_path_by_filename(
    *,
    inbox_root: Path,
    sub: str,
    file_name: str,
    limit: int = 500,
) -> Path | None:
    """
    InBox内の画像をファイル名で探し，実ファイルPathを返す。

    110_word画像埋込.py と同じく，
    load_inbox_image_items() を経由して画像一覧を取得する。
    """
    target_name = str(file_name or "").strip()

    if not target_name:
        return None

    inbox_root = Path(inbox_root)

    items_db = items_db_path(inbox_root, sub)
    lv_db = last_viewed_db_path(inbox_root, sub)

    ensure_items_db(items_db)
    ensure_last_viewed_db(lv_db)

    image_items_df = load_inbox_image_items(
        inbox_root=inbox_root,
        sub=sub,
        items_db=items_db,
        lv_db=lv_db,
        query_items_page=query_items_page,
        build_where_and_params=build_where_and_params,
        split_terms_and=split_terms_and,
        tag_q="",
        name_q=target_name,
        limit=int(limit),
    )

    if not isinstance(image_items_df, pd.DataFrame):
        return None

    if image_items_df.empty:
        return None

    # ------------------------------------------------------------
    # まずファイル名の完全一致を優先する
    # ------------------------------------------------------------
    file_col_candidates = [
        "ファイル名",
        "filename",
        "name",
    ]

    path_col_candidates = [
        "path",
        "ファイルパス",
        "保存パス",
    ]

    file_col = next(
        (c for c in file_col_candidates if c in image_items_df.columns),
        None,
    )

    path_col = next(
        (c for c in path_col_candidates if c in image_items_df.columns),
        None,
    )

    if path_col is None:
        return None

    df = image_items_df.copy()

    if file_col is not None:
        matched_df = df[
            df[file_col].astype(str).str.strip() == target_name
        ]

        if not matched_df.empty:
            df = matched_df

    # ------------------------------------------------------------
    # pathから実ファイルを解決する
    # ------------------------------------------------------------
    for _, row in df.iterrows():
        resolved = resolve_inbox_path_value(
            inbox_root=inbox_root,
            sub=sub,
            path_value=row.get(path_col),
        )

        if resolved is not None and resolved.exists():
            return resolved

    return None