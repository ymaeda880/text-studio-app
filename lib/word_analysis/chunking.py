# -*- coding: utf-8 -*-
# lib/word_analysis/chunking.py
# ============================================================
# チャンク分割ユーティリティ（正本）
#
# 目的：
# - 生成済み中間テキストを「運用しやすい単位」に分割する
# - 切れ目候補（markers）を複数指定できる
#
# 分割ルール（重要）：
# - マーカー行（例：<ここから見出し>）の直前を切れ目として扱う
#   → マーカーは次チャンクの先頭に残す
# - マーカーが1つも無い場合は固定長分割にフォールバック
# - ★見出し・表は “絶対に割らない”（limit 超過でも 1 チャンク）
#   * 標準：<ここから見出し>...<ここまで見出し> / <ここから表>...<ここまで表>
#   * 詳細：=== HEADING[...] ... === / === TABLE ... === ... === END_TABLE ===
# - 上記以外のセグメントが limit 超過の場合は、固定長で強制分割（互換）
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Iterable


# ============================================================
# types
# ============================================================
@dataclass(frozen=True)
class Chunk:
    text: str
    index: int
    total: int


# ============================================================
# filename helpers
# ============================================================
def split_filename(name: str) -> Tuple[str, str]:
    """
    "aaa.txt" -> ("aaa", ".txt")
    "aaa"     -> ("aaa", "")
    """
    if "." in name:
        base, ext = name.rsplit(".", 1)
        return base, "." + ext
    return name, ""


def make_planned_filenames(txt_name: str, num_chunks: int) -> List[str]:
    """
    1個なら txt_name のまま。
    複数なら base_part001.ext 形式（extが無ければ .txt）。
    """
    if num_chunks <= 0:
        return []

    base, ext = split_filename(txt_name)
    ext2 = ext or ".txt"

    if num_chunks == 1:
        return [txt_name]

    out: List[str] = []
    for idx in range(1, num_chunks + 1):
        out.append(f"{base}_part{idx:03d}{ext2}")
    return out


# ============================================================
# core: segmentation by markers
# ============================================================
def _iter_marker_positions(text: str, marker: str) -> Iterable[int]:
    """
    marker が現れる先頭インデックスを全てyieldする。
    """
    start = 0
    while True:
        pos = text.find(marker, start)
        if pos < 0:
            break
        yield pos
        start = pos + len(marker)


def _build_segments_keep_markers(text: str, markers: List[str]) -> List[str]:
    """
    markers の位置を全て集め、時系列順でセグメント化する。
    セグメントは「切れ目位置（markerの開始位置）」で分割し、
    marker 自体は後続セグメント側に残る（markerが次セグメント先頭に来る）。
    """
    t = text.strip()
    if not t:
        return []

    # 切れ目候補位置（開始index）を収集
    cut_positions = set()
    for m in markers:
        for pos in _iter_marker_positions(t, m):
            cut_positions.add(pos)

    if not cut_positions:
        return [t]

    # 0 は切れ目に入れない（先頭が marker のとき空セグメント化しやすいので）
    cuts = sorted(p for p in cut_positions if p > 0)
    if not cuts:
        return [t]

    # cuts で分割（marker を後ろ側に残す）
    segs: List[str] = []
    prev = 0
    for p in cuts:
        head = t[prev:p].strip()
        if head:
            segs.append(head)
        prev = p

    tail = t[prev:].strip()
    if tail:
        segs.append(tail)

    return segs


# ============================================================
# atomic blocks (do not split)
# ============================================================
def _is_heading_segment(seg: str) -> bool:
    s = seg.lstrip()

    # 標準：<ここから見出し> ... <ここまで見出し>
    if s.startswith("<ここから見出し>") and ("<ここまで見出し>" in s):
        return True

    # 詳細：=== HEADING[...] ... ===
    # 例：=== HEADING[1-2-3] タイトル ===
    if s.startswith("=== HEADING[") and s.rstrip().endswith("==="):
        return True

    return False


def _is_table_segment(seg: str) -> bool:
    s = seg.lstrip()

    # 標準：<ここから表> ... <ここまで表>
    if s.startswith("<ここから表>") and ("<ここまで表>" in s):
        return True

    # 詳細：=== TABLE ... === ... === END_TABLE ===
    if s.startswith("=== TABLE ") and ("=== END_TABLE ===" in s):
        return True

    return False


def _is_atomic_segment(seg: str) -> bool:
    # 「絶対に割らない」対象
    return _is_heading_segment(seg) or _is_table_segment(seg)


# ============================================================
# public: chunking
# ============================================================
def chunk_text_by_markers(
    text: str,
    limit: int,
    *,
    markers: List[str],
) -> List[str]:
    """
    markers を切れ目候補として、1チャンクが limit を超えないように分割する。

    重要：
    - 見出し・表（atomic）は、limit を超えても 1チャンクで保持（絶対に割らない）
    - atomic 以外は、limit 超過時に固定長で強制分割（互換）
    """
    if not text:
        return []
    t = text.strip()
    if not t:
        return []

    if limit <= 0:
        # 実運用では呼び出し側のバリデーション対象だが、念のため
        return [t + "\n"]

    # セグメント化（marker を保持して切れ目を作る）
    segments = _build_segments_keep_markers(t, markers)

    # marker が1つも無いなら固定長フォールバック（互換）
    if len(segments) == 1 and segments[0] == t and all(m not in t for m in markers):
        chunks: List[str] = []
        i = 0
        while i < len(t):
            chunks.append(t[i : i + limit].strip() + "\n")
            i += limit
        return [c for c in chunks if c.strip()]

    chunks: List[str] = []
    buf = ""

    def flush():
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip() + "\n")
        buf = ""

    for seg in segments:

        # ------------------------------------------------------------
        # seg 単体が limit 超え
        # ------------------------------------------------------------
        if len(seg) > limit:
            flush()

            # ★見出し・表は絶対に割らない（limit超えでもそのまま1チャンク）
            if _is_atomic_segment(seg):
                chunks.append(seg.strip() + "\n")
                continue

            # それ以外は固定長で強制分割（互換）
            j = 0
            while j < len(seg):
                chunks.append(seg[j : j + limit].strip() + "\n")
                j += limit
            continue

        # ------------------------------------------------------------
        # buf に足すと limit 超過 → flush
        # ------------------------------------------------------------
        if buf and (len(buf) + 1 + len(seg) > limit):
            flush()
            buf = seg
        else:
            buf = (buf + "\n" + seg) if buf else seg

    flush()
    return [c for c in chunks if c.strip()]


def chunk_text_with_meta(
    text: str,
    limit: int,
    *,
    markers: List[str],
) -> List[Chunk]:
    """
    chunk_text_by_markers の結果に index/total を付けて返す。
    Inbox保存 origin に入れる用途向け。
    """
    raw = chunk_text_by_markers(text, limit, markers=markers)
    total = len(raw)
    out: List[Chunk] = []
    for i, s in enumerate(raw, start=1):
        out.append(Chunk(text=s, index=i, total=total))
    return out
