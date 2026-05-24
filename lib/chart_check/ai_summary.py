# -*- coding: utf-8 -*-
# text_studio_app/lib/chart_check/ai_summary.py
# ============================================================
# 図表チェック：AI用サマリー出力
#
# 機能：
# - AI投入用サマリーを生成する
# - 通常サマリーとは異なり「1引用 = 1行」で出力する
# - 同じ図表キーに複数引用がある場合は、同じ図表キーの複数行になる
# - 前テキスト / 後テキストを追加する
# - 参照テキスト(強調)列は出力しない
# - AI用xlsx / jsonl bytesを生成する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import json
import re
from io import BytesIO
from typing import Dict, List, Tuple, Any

import pandas as pd

from lib.chart_check.helpers import base_key
from lib.chart_check.summary_export import (
    summary_kind_from_key,
    empty_summary_df,
    sort_summary_by_pdf_page,
)


# ============================================================
# constants
# ============================================================
AI_SUMMARY_COLUMNS = [
    "図表キー",
    "結果",
    "図表タイトル",
    "頁",
    "pdf頁",
    "参照頁ラベル",
    "参照pdf頁",
    "前テキスト",
    "参照テキスト",
    "後テキスト",
]


# ============================================================
# sentence split
# ============================================================
def split_japanese_sentences(text: str) -> List[str]:
    s = str(text or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n+", "\n", s).strip()

    if not s:
        return []

    #parts = re.split(r"(?<=[。！？!?])\s*", s)
    parts = re.split(r"(?<=[。．！？!?])\s*", s)
    return [p.strip() for p in parts if p.strip()]


# ============================================================
# 参照テキストの候補を整理
# ============================================================
def _first_text_piece(text: str) -> str:
    s = str(text or "").strip()

    if not s:
        return ""

    for sep in [" | ", "\n"]:
        if sep in s:
            first = s.split(sep, 1)[0].strip()
            if first:
                return first

    return s


# ============================================================
# pdf頁の候補を整理
# ============================================================
def _first_pdf_page(value: object) -> int | None:
    s = str(value or "").strip()

    if not s:
        return None

    m = re.search(r"\d+", s)
    if not m:
        return None

    try:
        return int(m.group(0))
    except Exception:
        return None


# ============================================================
# 文字数制限
# ============================================================
def _limit_prev_text(text: str, max_chars: int) -> str:
    s = str(text or "")

    if max_chars <= 0:
        return s

    return s[-max_chars:]


def _limit_next_text(text: str, max_chars: int) -> str:
    s = str(text or "")

    if max_chars <= 0:
        return s

    return s[:max_chars]


# ============================================================
# 前文・参照文・後文を抽出
# ============================================================
def extract_prev_current_next_text(
    *,
    pages_text: List[str],
    pdf_page: int | None,
    ref_text: str,
    figure_key: str,
    line_text: str = "",
    match_start: object = None,
    match_end: object = None,
) -> Tuple[str, str, str]:
    if pdf_page is None:
        return "", str(ref_text or ""), ""

    page_idx = pdf_page - 1
    if page_idx < 0 or page_idx >= len(pages_text):
        return "", str(ref_text or ""), ""

    page_text = str(pages_text[page_idx] or "")

    # ------------------------------------------------------------
    # sentence spans
    # ------------------------------------------------------------
    sent_spans = []

    start = 0

    for m in re.finditer(r"[。．！？!?]", page_text):
        end = m.end()

        sent = page_text[start:end].strip()

        if sent:
            sent_spans.append(
                {
                    "start": start,
                    "end": end,
                    "text": sent,
                }
            )

        start = end

    rest = page_text[start:].strip()

    if rest:
        sent_spans.append(
            {
                "start": start,
                "end": len(page_text),
                "text": rest,
            }
        )

    if not sent_spans:
        return "", str(ref_text or ""), ""

    hit_idx = None

    # ------------------------------------------------------------
    # match_start で直接 sentence を特定
    # ------------------------------------------------------------
    try:
        ms = int(match_start)
    except Exception:
        ms = -1

    if ms >= 0:
        for i, sp in enumerate(sent_spans):
            if sp["start"] <= ms < sp["end"]:
                hit_idx = i
                break

    # ------------------------------------------------------------
    # fallback
    # ------------------------------------------------------------
    if hit_idx is None:
        target_line = str(line_text or "").strip()

        if target_line:
            for i, sp in enumerate(sent_spans):
                sent = sp["text"]

                if target_line in sent or sent in target_line:
                    hit_idx = i
                    break

    # ------------------------------------------------------------
    # fallback2
    # ------------------------------------------------------------
    if hit_idx is None:
        ref_piece = _first_text_piece(ref_text)
        key = str(figure_key or "").strip()

        if ref_piece:
            for i, sp in enumerate(sent_spans):
                if ref_piece in sp["text"]:
                    hit_idx = i
                    break

        if hit_idx is None and key:
            key_core = base_key(key)

            for i, sp in enumerate(sent_spans):
                sent = sp["text"]

                if key in sent or key_core in sent:
                    hit_idx = i
                    break



    if hit_idx is None:
        ref_piece = _first_text_piece(ref_text)
        key = str(figure_key or "").strip()

        if ref_piece:
            for i, sent in enumerate(sentences):
                if ref_piece in sent:
                    hit_idx = i
                    break

        if hit_idx is None and key:
            key_core = base_key(key)

            for i, sent in enumerate(sentences):
                if key in sent or key_core in sent:
                    hit_idx = i
                    break

    if hit_idx is None:
        return "", str(line_text or ref_text or ""), ""

    prev_text = sent_spans[hit_idx - 1]["text"] if hit_idx - 1 >= 0 else ""
    current_text = sent_spans[hit_idx]["text"]
    next_text = sent_spans[hit_idx + 1]["text"] if hit_idx + 1 < len(sent_spans) else ""

    return prev_text, current_text, next_text


# ============================================================
# caption info
# ============================================================
def _caption_info_by_key(df_captions: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    info: Dict[str, Dict[str, Any]] = {}

    if df_captions.empty or "図表キー" not in df_captions.columns:
        return info

    for key, grp in df_captions.groupby("図表キー"):
        g = grp.sort_values("pdf_page") if "pdf_page" in grp.columns else grp
        row = g.iloc[0]

        info[str(key)] = {
            "図表キー": str(key),
            "図表タイトル": row.get("見出しタイトル", "") or "",
            "頁": row.get("page_label", "") or "",
            "pdf頁": row.get("pdf_page", ""),
        }

    return info


# ============================================================
# refs by base_key
# ============================================================
def _refs_by_base_key(df_refs: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    refs: Dict[str, List[Dict[str, Any]]] = {}

    if df_refs.empty or "図表キー" not in df_refs.columns:
        return refs

    for _, row in df_refs.iterrows():
        key = str(row.get("図表キー", "") or "")
        if not key:
            continue

        bk = base_key(key)

        refs.setdefault(bk, []).append(
            {
                "図表キー": key,
                "参照頁ラベル": row.get("page_label", "") or "",
                "参照pdf頁": row.get("pdf_page", "") or "",
                "参照テキスト": row.get("参照テキスト", "") or "",
                "行テキスト": row.get("行テキスト", "") or "",
                "match_start": row.get("match_start", None),
                "match_end": row.get("match_end", None),
            }
        )

    return refs


# ============================================================
# AI用1引用1行 rows 生成
# ============================================================
def build_ai_summary_rows(
    *,
    df_captions: pd.DataFrame,
    df_refs: pd.DataFrame,
    pages_text: List[str],
    prev_text_max_chars: int = 300,
    next_text_max_chars: int = 300,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    cap_info = _caption_info_by_key(df_captions)
    refs_map = _refs_by_base_key(df_refs)

    cap_base_keys = {base_key(k) for k in cap_info.keys()}
    ref_base_keys = set(refs_map.keys())

    # ------------------------------------------------------------
    # 見出しあり：引用あり / 未引用
    # ------------------------------------------------------------
    for cap_key, cap in cap_info.items():
        bk = base_key(cap_key)
        matched_refs = refs_map.get(bk, [])

        if matched_refs:
            for ref in matched_refs:
                ref_text = str(ref.get("参照テキスト", "") or "")
                ref_pdf_page = _first_pdf_page(ref.get("参照pdf頁", ""))

                prev_text, current_text, next_text = extract_prev_current_next_text(
                    pages_text=pages_text,
                    pdf_page=ref_pdf_page,
                    ref_text=ref_text,
                    figure_key=ref.get("図表キー", cap_key),
                    line_text=ref.get("行テキスト", ""),
                    match_start=ref.get("match_start", None),
                    match_end=ref.get("match_end", None),
                )

                rows.append(
                    {
                        "図表キー": cap_key,
                        "結果": "",
                        "図表タイトル": cap.get("図表タイトル", ""),
                        "頁": cap.get("頁", ""),
                        "pdf頁": cap.get("pdf頁", ""),
                        "参照頁ラベル": ref.get("参照頁ラベル", ""),
                        "参照pdf頁": ref.get("参照pdf頁", ""),
                        "前テキスト": _limit_prev_text(prev_text, prev_text_max_chars),
                        "参照テキスト": current_text or ref_text,
                        "後テキスト": _limit_next_text(next_text, next_text_max_chars),
                    }
                )
        else:
            rows.append(
                {
                    "図表キー": cap_key,
                    "結果": "未引用",
                    "図表タイトル": cap.get("図表タイトル", ""),
                    "頁": cap.get("頁", ""),
                    "pdf頁": cap.get("pdf頁", ""),
                    "参照頁ラベル": "",
                    "参照pdf頁": "",
                    "前テキスト": "",
                    "参照テキスト": "",
                    "後テキスト": "",
                }
            )

    # ------------------------------------------------------------
    # 見出しなし参照
    # ------------------------------------------------------------
    for ref_bk in sorted(ref_base_keys - cap_base_keys):
        for ref in refs_map.get(ref_bk, []):
            ref_key = str(ref.get("図表キー", "") or "")
            ref_text = str(ref.get("参照テキスト", "") or "")
            ref_pdf_page = _first_pdf_page(ref.get("参照pdf頁", ""))

            prev_text, current_text, next_text = extract_prev_current_next_text(
                pages_text=pages_text,
                pdf_page=ref_pdf_page,
                ref_text=ref_text,
                figure_key=ref_key,
                line_text=ref.get("行テキスト", ""),
                match_start=ref.get("match_start", None),
                match_end=ref.get("match_end", None),
            )

            rows.append(
                {
                    "図表キー": ref_key,
                    "結果": "見出しなし参照",
                    "図表タイトル": "",
                    "頁": "",
                    "pdf頁": "",
                    "参照頁ラベル": ref.get("参照頁ラベル", ""),
                    "参照pdf頁": ref.get("参照pdf頁", ""),
                    "前テキスト": _limit_prev_text(prev_text, prev_text_max_chars),
                    "参照テキスト": current_text or ref_text,
                    "後テキスト": _limit_next_text(next_text, next_text_max_chars),
                }
            )

    return rows


# ============================================================
# AI用サマリー全体df
# ============================================================
def build_ai_summary_all_df(
    *,
    df_captions: pd.DataFrame,
    df_refs: pd.DataFrame,
    pages_text: List[str],
    prev_text_max_chars: int = 300,
    next_text_max_chars: int = 300,
) -> pd.DataFrame:
    rows = build_ai_summary_rows(
        df_captions=df_captions,
        df_refs=df_refs,
        pages_text=pages_text,
        prev_text_max_chars=prev_text_max_chars,
        next_text_max_chars=next_text_max_chars,
    )

    if not rows:
        return pd.DataFrame(columns=AI_SUMMARY_COLUMNS)

    return pd.DataFrame(rows, columns=AI_SUMMARY_COLUMNS)


# ============================================================
# AI用サマリーframes生成
# ============================================================
def build_ai_summary_frames(
    *,
    df_captions: pd.DataFrame,
    df_refs: pd.DataFrame,
    pages_text: List[str],
    prev_text_max_chars: int = 300,
    next_text_max_chars: int = 300,
) -> Dict[str, pd.DataFrame]:
    df_all = build_ai_summary_all_df(
        df_captions=df_captions,
        df_refs=df_refs,
        pages_text=pages_text,
        prev_text_max_chars=prev_text_max_chars,
        next_text_max_chars=next_text_max_chars,
    )

    if df_all.empty:
        empty = pd.DataFrame(columns=AI_SUMMARY_COLUMNS)
        return {
            "図サマリー": empty.copy(),
            "表サマリー": empty.copy(),
            "図表サマリー": empty.copy(),
            "見出しなし参照": empty.copy(),
        }

    df_all["_summary_kind"] = df_all["図表キー"].map(summary_kind_from_key)

    df_fig = df_all[
        (df_all["_summary_kind"] == "図") & (df_all["結果"] != "見出しなし参照")
    ].copy()

    df_tbl = df_all[
        (df_all["_summary_kind"] == "表") & (df_all["結果"] != "見出しなし参照")
    ].copy()

    df_figtbl = df_all[
        (df_all["_summary_kind"] == "図表") & (df_all["結果"] != "見出しなし参照")
    ].copy()

    df_orphan = df_all[df_all["結果"] == "見出しなし参照"].copy()

    for df in [df_fig, df_tbl, df_figtbl, df_orphan]:
        if "_summary_kind" in df.columns:
            df.drop(columns=["_summary_kind"], inplace=True)

    return {
        "図サマリー": sort_summary_by_pdf_page(df_fig),
        "表サマリー": sort_summary_by_pdf_page(df_tbl),
        "図表サマリー": sort_summary_by_pdf_page(df_figtbl),
        "見出しなし参照": sort_summary_by_pdf_page(df_orphan),
    }


# ============================================================
# AI用xlsx bytes生成
# ============================================================
def build_ai_summary_xlsx_bytes(
    *,
    df_captions: pd.DataFrame,
    df_refs: pd.DataFrame,
    pages_text: List[str],
    prev_text_max_chars: int = 300,
    next_text_max_chars: int = 300,
) -> bytes:
    frames = build_ai_summary_frames(
        df_captions=df_captions,
        df_refs=df_refs,
        pages_text=pages_text,
        prev_text_max_chars=prev_text_max_chars,
        next_text_max_chars=next_text_max_chars,
    )

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frames["図サマリー"].to_excel(writer, sheet_name="図サマリー", index=False)
        frames["表サマリー"].to_excel(writer, sheet_name="表サマリー", index=False)
        frames["図表サマリー"].to_excel(writer, sheet_name="図表サマリー", index=False)
        frames["見出しなし参照"].to_excel(writer, sheet_name="見出しなし参照", index=False)

    return output.getvalue()


# ============================================================
# AI用jsonl bytes生成
# ============================================================
def build_ai_summary_jsonl_bytes(
    *,
    df_captions: pd.DataFrame,
    df_refs: pd.DataFrame,
    pages_text: List[str],
    prev_text_max_chars: int = 300,
    next_text_max_chars: int = 300,
) -> bytes:
    frames = build_ai_summary_frames(
        df_captions=df_captions,
        df_refs=df_refs,
        pages_text=pages_text,
        prev_text_max_chars=prev_text_max_chars,
        next_text_max_chars=next_text_max_chars,
    )

    lines = []

    for sheet_name, df in frames.items():
        if df.empty:
            continue

        for row in df.to_dict(orient="records"):
            item = {
                "sheet": sheet_name,
                **row,
            }
            lines.append(json.dumps(item, ensure_ascii=False, default=str))

    text = "\n".join(lines)
    if text:
        text += "\n"

    return text.encode("utf-8")