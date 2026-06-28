# -*- coding: utf-8 -*-
# lib/image_embed/inbox_images.py
# ============================================================
# Word画像埋込 InBox画像取得
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pathlib import Path
import json

import pandas as pd


# ============================================================
# tag helper
# ============================================================
def _tags_to_disp(value: object) -> str:
    text = "" if value is None else str(value).strip()

    if not text:
        return ""

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return " / ".join(str(x).strip() for x in data if str(x).strip())
    except Exception:
        pass

    return text


# ============================================================
# original image path resolver
# ============================================================
def _resolve_original_image_path(
    *,
    inbox_root: Path,
    sub: str,
    row: pd.Series,
) -> str:
    """
    InBox内の元画像ファイルの実パスを解決する。

    注意:
    - Word出力ではサムネではなく元画像を使う。
    - query_items_page の返却列は環境差があり得るため，
      絶対パス候補，relpath候補，最後に item_id / original_name 検索の順で探す。
    """
    user_root = inbox_root / sub

    # ------------------------------------------------------------
    # 1. 絶対パス候補
    # ------------------------------------------------------------
    abs_candidates = [
        "path",
        "abs_path",
        "absolute_path",
        "stored_abs_path",
        "file_path",
    ]

    for col in abs_candidates:
        if col not in row.index:
            continue

        value = str(row.get(col) or "").strip()
        if not value:
            continue

        p = Path(value)
        if p.exists() and p.is_file():
            return str(p)

    # ------------------------------------------------------------
    # 2. 相対パス候補
    # ------------------------------------------------------------
    rel_candidates = [
        "stored_relpath",
        "relpath",
        "stored_path",
        "file_relpath",
    ]

    for col in rel_candidates:
        if col not in row.index:
            continue

        value = str(row.get(col) or "").strip()
        if not value:
            continue

        p = user_root / value
        if p.exists() and p.is_file():
            return str(p)

    # ------------------------------------------------------------
    # 3. item_id / original_name から元画像を検索
    # - _meta や thumbnails 系は除外する
    # ------------------------------------------------------------
    item_id = str(row.get("item_id") or "").strip()
    original_name = str(row.get("original_name") or "").strip()

    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

    if not user_root.exists():
        return ""

    for p in user_root.rglob("*"):
        if not p.is_file():
            continue

        parts = set(p.parts)
        if "_meta" in parts:
            continue

        lower_path = str(p).lower()
        if "thumb" in lower_path or "thumbnail" in lower_path:
            continue

        if p.suffix.lower() not in image_exts:
            continue

        if item_id and item_id in p.name:
            return str(p)

        if original_name and p.name == original_name:
            return str(p)

    return ""


# ============================================================
# InBox画像一覧取得
# ============================================================
def load_inbox_image_items(
    *,
    inbox_root: Path,
    sub: str,
    items_db,
    lv_db,
    query_items_page,
    build_where_and_params,
    split_terms_and,
    tag_q: str = "",
    name_q: str = "",
    limit: int = 500,
) -> pd.DataFrame:
    """
    InBoxから画像ファイルだけを取得する。

    Word出力用に，path列にはサムネではなく元画像ファイルの実パスを入れる。
    """
    tag_terms = split_terms_and(tag_q)
    name_terms = split_terms_and(name_q)

    where_sql, params = build_where_and_params(
        kinds_checked=["image"],
        tag_terms=tag_terms,
        name_terms=name_terms,
        added_from=None,
        added_to=None,
        size_mode="指定なし",
        size_min_bytes=None,
        size_max_bytes=None,
        lv_mode="指定なし",
        lv_from=None,
        lv_to=None,
        lv_since_iso=None,
    )

    df, _total = query_items_page(
        sub=sub,
        items_db=items_db,
        lv_db=lv_db,
        where_sql=where_sql,
        params=params,
        limit=limit,
        offset=0,
        sort_key="added_at",
        sort_dir="desc",
        group_kind=False,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    if "tag_disp" not in out.columns:
        if "tags_json" in out.columns:
            out["tag_disp"] = out["tags_json"].map(_tags_to_disp)
        elif "tags" in out.columns:
            out["tag_disp"] = out["tags"].map(_tags_to_disp)
        else:
            out["tag_disp"] = ""

    # ------------------------------------------------------------
    # Word出力用の元画像パスを作る
    # ------------------------------------------------------------
    out["path"] = out.apply(
        lambda row: _resolve_original_image_path(
            inbox_root=inbox_root,
            sub=sub,
            row=row,
        ),
        axis=1,
    )

    return out