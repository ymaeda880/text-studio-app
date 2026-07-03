# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/table/inbox_excel_resolver.py
# ============================================================
# wordTex table Inbox Excel resolver
#
# - figure の Inbox 画像 resolver と同じ考え方で，
#   items.db から Excel ファイルをファイル名で探す
# - 画像専用の load_inbox_image_items は使わない
# ============================================================

from __future__ import annotations

from pathlib import Path
import sqlite3

from common_lib.inbox.inbox_common.paths import items_db_path
from common_lib.inbox.inbox_db.items_db import ensure_items_db

from lib.image_embed.inbox_image_resolver import resolve_inbox_path_value


def resolve_inbox_excel_path_by_filename(
    *,
    inbox_root: Path,
    sub: str,
    file_name: str,
) -> Path | None:
    """
    Inbox内のExcelファイルをファイル名で探し，実ファイルPathを返す。

    figure の画像 resolver と同じく，
    items.db の path 値を実ファイルPathに変換する。
    """
    target_name = str(file_name or "").strip()

    if not target_name:
        return None

    inbox_root = Path(inbox_root)

    db_path = items_db_path(inbox_root, sub)
    ensure_items_db(db_path)

    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))

    try:
        table_names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]

        for table_name in table_names:
            columns = [
                row[1]
                for row in conn.execute(
                    f"PRAGMA table_info({table_name})"
                ).fetchall()
            ]

            if not columns:
                continue

            rows = conn.execute(
                f"SELECT * FROM {table_name}"
            ).fetchall()

            for row in rows:
                record = dict(zip(columns, row))

                name_values = [
                    record.get("original_name"),
                    record.get("file_name"),
                    record.get("filename"),
                    record.get("name"),
                ]

                path_values = [
                    record.get("path"),
                    record.get("file_path"),
                    record.get("保存パス"),
                    record.get("ファイルパス"),
                ]

                matched = False

                for value in name_values:
                    if Path(str(value or "")).name == target_name:
                        matched = True
                        break

                for value in path_values:
                    if Path(str(value or "")).name == target_name:
                        matched = True
                        break

                if not matched:
                    continue

                for path_value in path_values:
                    resolved = resolve_inbox_path_value(
                        inbox_root=inbox_root,
                        sub=sub,
                        path_value=path_value,
                    )

                    if resolved is not None and resolved.exists():
                        return resolved

    finally:
        conn.close()

    return None