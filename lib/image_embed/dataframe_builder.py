# -*- coding: utf-8 -*-
# lib/image_embed/dataframe_builder.py
# ============================================================
# Word画像埋込 編集DataFrame作成
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pathlib import Path

import pandas as pd

from lib.image_embed.tag_metadata import parse_title_exp_from_tag


# ============================================================
# text helper
# ============================================================
def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


# ============================================================
# Word出力用DataFrame作成
# ============================================================
def build_image_selection_df(
    *,
    image_items_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Inbox画像一覧から，Word出力用の編集DataFrameを作成する。

    方針:
    - 「選択」列を追加する
    - タイトル初期値は，タグがあればタグ，なければファイル名にする
    - タグ自体は今回は変更しない
    """
    columns = [
        "選択",
        "タグ",
        "タイトル",
        "説明",
        "ファイル名",
        "item_id",
        "path",
    ]

    if image_items_df.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []

    for _, row in image_items_df.iterrows():
        tag = _safe_text(row.get("tag_disp") or row.get("tags") or "")
        filename = _safe_text(row.get("original_name") or row.get("filename") or "")
        meta_title, meta_exp = parse_title_exp_from_tag(tag)

        title = meta_title if meta_title else (tag if tag else Path(filename).stem)
        desc = meta_exp if meta_exp else ""

        rows.append(
            {
                "選択": False,
                "タグ": tag,
                "タイトル": title,
                "説明": desc,
                "ファイル名": filename,
                "item_id": _safe_text(row.get("item_id")),
                "path": _safe_text(row.get("path")),
            }
        )

    return pd.DataFrame(rows, columns=columns)


# ============================================================
# 選択画像抽出
# ============================================================
def extract_selected_images(
    *,
    edited_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    st.data_editor 編集後のDataFrameから，
    「選択」が True の画像だけを抽出する。
    """
    if edited_df.empty or "選択" not in edited_df.columns:
        return pd.DataFrame()

    selected_df = edited_df[edited_df["選択"] == True].copy()  # noqa: E712

    if selected_df.empty:
        return selected_df

    for col in ["タイトル", "説明", "ファイル名", "path"]:
        if col in selected_df.columns:
            selected_df[col] = selected_df[col].fillna("").astype(str).str.strip()

    return selected_df.reset_index(drop=True)