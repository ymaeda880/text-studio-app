# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/chunking.py
# ============================================================
# AI参照チェック：チャンク分割
#
# 機能：
# - AI送信用recordsを件数ベースで分割する
# - 将来的に文字数ベース分割へ拡張しやすくする
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from typing import Any, Dict, List


# ============================================================
# 件数ベースchunk分割
# ============================================================
def split_records_by_count(
    *,
    records: List[Dict[str, Any]],
    chunk_size: int,
) -> List[List[Dict[str, Any]]]:
    size = int(chunk_size)

    if size <= 0:
        size = 20

    return [
        records[i : i + size]
        for i in range(0, len(records), size)
    ]