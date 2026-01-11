# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List


def parse_plan_md_tables(md: str) -> List[Dict[str, str]]:
    """
    Markdown表から行データを抽出して返す。
    期待列：頁 / 行 / 重要度 / 原文 / 修正案 / 理由（揺れは吸収）
    """
    items: List[Dict[str, str]] = []
    if not md:
        return items

    to_jp = {
        "page": "頁", "line": "行", "issue": "重要度",
        "original": "原文", "suggestion": "修正案", "reason": "理由",
        "頁": "頁", "ページ": "頁", "行": "行",
        "重要度": "重要度", "問題点": "重要度", "原文": "原文",
        "修正案": "修正案", "提案": "修正案", "理由": "理由", "根拠": "理由",
    }
    expected = ["頁", "行", "重要度", "原文", "修正案", "理由"]

    def _norm_head_cell(s: str) -> str:
        key = s.strip().lower()
        return to_jp.get(key, to_jp.get(s.strip(), s.strip()))

    def _row_to_dict(ln: str, cols_jp: List[str]) -> Dict[str, str] | None:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 3:
            return None
        row = dict(zip(cols_jp, cells[:len(cols_jp)]))
        for k in expected:
            row.setdefault(k, "")
        return row

    lines = [ln for ln in (l.strip() for l in md.splitlines()) if ln]
    header_seen = False
    cols_jp: List[str] = []

    for ln in lines:
        if not (ln.startswith("|") and "|" in ln):
            continue

        raw_cells = [c.strip() for c in ln.strip("|").split("|")]

        def _is_md_separator(cell: str) -> bool:
            s = cell.strip().replace("-", "").replace(":", "")
            return s == ""

        if all(_is_md_separator(c) for c in raw_cells):
            continue

        if not header_seen:
            norm = [_norm_head_cell(c) for c in raw_cells]
            if len(set(norm) & set(expected)) >= 3:
                cols_jp = [c if c in expected else "" for c in norm]
                if len(cols_jp) < 6:
                    cols_jp += [""] * (6 - len(cols_jp))
                cols_jp = [cols_jp[i] or expected[i] for i in range(6)]
                header_seen = True
                continue

        if header_seen and cols_jp:
            row = _row_to_dict(ln, cols_jp)
            if row:
                items.append(row)

    return items
