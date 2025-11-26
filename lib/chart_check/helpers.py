# -*- coding: utf-8 -*-
# lib/chart_check/helpers.py
#
# 図表チェック共通の helper 関数群

from __future__ import annotations
from typing import Dict, Any, Tuple, Iterable, Mapping, List
import re

import pandas as pd


# =========================
# 図表キー関連
# =========================
def base_key(k: object) -> str:
    """
    図表キーから末尾の (1/3), （1／3） などの「分割番号部分」を削ったベースキーを返す。
    例：'表3.1.5-1(1/3)' → '表3.1.5-1'
    """
    if k is None:
        return ""
    s = str(k)
    s = re.sub(
        r"[\(（][^()（）]*?\d+\s*[\/／]\s*\d+\s*[\)）]\s*$",
        "",
        s,
    )
    return s.strip()


def index_pages_by_key(df: pd.DataFrame, key_col: str = "図表キー") -> Dict[str, List[int]]:
    """
    DataFrame から key_col ごとに pdf_page の一覧を集約して返す。
    """
    from collections import defaultdict

    idx = defaultdict(set)
    if df is None or df.empty or key_col not in df.columns:
        return {}

    for _, row in df.iterrows():
        k = row.get(key_col)
        p = row.get("pdf_page")
        if pd.notna(k) and pd.notna(p):
            try:
                idx[str(k)].add(int(p))
            except Exception:
                pass

    return {k: sorted(v) for k, v in idx.items()}


# =========================
# 画面表示用：参照集約
# =========================
def ref_aggregate_for_view(
    df_refs: pd.DataFrame,
    *,
    base_key_func=base_key,
):
    """
    本文中の参照を「ベースキー」で集約して返す。
    例）表3.1.5-5, 表3.1.5-5(1/3) → base は '表3.1.5-5'
    戻り値:
      ref_lbls, ref_pdfs, ref_texts, ref_hi の 4 辞書
    """
    if df_refs is None or df_refs.empty:
        return {}, {}, {}, {}

    df = df_refs.copy()
    df["_base"] = df["図表キー"].map(base_key_func)

    ref_lbls, ref_pdfs, ref_texts, ref_hi = {}, {}, {}, {}
    for base, grp in df.groupby("_base"):
        grp2 = grp.sort_values(["pdf_page", "行番号"], kind="mergesort")
        lbls  = grp2["page_label"].dropna().astype(str).unique().tolist()
        pnums = grp2["pdf_page"].dropna().astype(int).unique().tolist()
        texts = grp2["行テキスト"].dropna().astype(str).unique().tolist()
        his   = grp2["行テキスト(強調)"].dropna().astype(str).unique().tolist()

        ref_lbls[base]  = ",".join(lbls)
        ref_pdfs[base]  = ",".join(str(x) for x in pnums)
        ref_texts[base] = " | ".join(texts)
        ref_hi[base]    = " | ".join(his)

    return ref_lbls, ref_pdfs, ref_texts, ref_hi


# =========================
# キャプション側情報
# =========================
def caption_info_first_by_key(
    df_cap: pd.DataFrame,
    df_pages: pd.DataFrame,
) -> Dict[str, Dict[str, Any]]:
    """
    key（図表キー）ごとに『最初のキャプション行』を取り、
    pdf_page を基に df_per_page_labels から正しい page_label を参照し直す。
    戻り値: key -> {"図表タイトル", "頁", "pdf頁"}
    """
    info: Dict[str, Dict[str, Any]] = {}
    if df_cap is None or df_cap.empty:
        return info

    # pdf_page → correct page_label の辞書を作る
    page_map: Dict[int, str] = {
        int(r["pdf_page"]): (r["page_label"] if r["page_label"] != "-" else "")
        for _, r in df_pages.iterrows()
        if pd.notna(r["pdf_page"])
    }

    for k, grp in df_cap.groupby("図表キー"):
        row = grp.sort_values("pdf_page").iloc[0]
        pdfp = row.get("pdf_page")
        corrected_label = page_map.get(int(pdfp), "") if pd.notna(pdfp) else ""
        info[str(k)] = {
            "図表タイトル": row.get("見出しタイトル", "") or "",
            "頁": corrected_label,
            "pdf頁": int(pdfp) if pd.notna(pdfp) else "",
        }

    return info


# =========================
# 参照側情報（xlsx/CSV 用）
# =========================
def aggregate_ref_info(
    df_refs: pd.DataFrame,
    *,
    base_key_func=base_key,
):
    """
    XLSX 用：参照側情報をベースキー単位で集約。
    戻り値:
      ref_page_labels, ref_pdf_pages, ref_texts, ref_highlight_texts
    """
    if df_refs is None or df_refs.empty:
        return {}, {}, {}, {}

    df = df_refs.copy()
    df["_base"] = df["図表キー"].map(base_key_func)

    ref_page_labels: Dict[str, str] = {}
    ref_pdf_pages: Dict[str, str] = {}
    ref_texts: Dict[str, str] = {}
    ref_highlight_texts: Dict[str, str] = {}

    for base, grp in df.groupby("_base"):
        grp2 = grp.sort_values(["pdf_page", "行番号"], na_position="last", kind="mergesort")
        labels = [str(x) for x in grp2["page_label"].dropna().unique().tolist()]
        pdfs   = [str(int(x)) for x in grp2["pdf_page"].dropna().unique().tolist()]

        ref_page_labels[base]     = ",".join(labels)
        ref_pdf_pages[base]       = ",".join(pdfs)
        ref_texts[base]           = " | ".join(grp2["行テキスト"].dropna().astype(str).unique().tolist())
        ref_highlight_texts[base] = " | ".join(grp2["行テキスト(強調)"].dropna().astype(str).unique().tolist())

    return ref_page_labels, ref_pdf_pages, ref_texts, ref_highlight_texts


# =========================
# Excel 用保護関数
# =========================
_HYPHEN_RANGE_RE = re.compile(r"^\s*\d{1,2}\s*[-−ー－―]\s*\d{1,2}\s*$")


def protect_for_excel_csv(x: object) -> object:
    """
    CSV 用：頁ラベル「1-2」などが日付として解釈されるのを防ぐ。
    → ="" 形式で出力。
    """
    if isinstance(x, str) and _HYPHEN_RANGE_RE.match(x.strip()):
        return f'="{x.strip()}"'
    return x


def protect_for_excel_xlsx(x: object) -> object:
    """
    XLSX 用：同様に「1-2」などを文字列として保護。
    （既存コードと同じ =\"...\" 形式を維持）
    """
    if isinstance(x, str) and _HYPHEN_RANGE_RE.match(x.strip()):
        return f'=\"{x.strip()}\"'
    return x


# =========================
# xlsx 用 cross-check 行生成
# =========================
def make_crosscheck_rows(
    keys: Iterable[str],
    *,
    caption_src: bool,
    cap_info: Mapping[str, Dict[str, Any]],
    ref_page_labels: Mapping[str, str],
    ref_pdf_pages: Mapping[str, str],
    ref_texts: Mapping[str, str],
    ref_highlight_texts: Mapping[str, str],
    base_key_func=base_key,
) -> pd.DataFrame:
    """
    突き合わせ結果（引用見出し / 未引用見出し / 見出しなし参照）用の
    DataFrame を作成する共通関数。
    """
    rows: List[Dict[str, Any]] = []

    for k in keys:
        if caption_src:
            ci = cap_info.get(k, {"図表タイトル": "", "頁": "", "pdf頁": ""})
        else:
            ci = {"図表タイトル": "", "頁": "", "pdf頁": ""}

        bk = base_key_func(k)
        pdf_page_val = ci["pdf頁"]

        if caption_src and pdf_page_val != "":
            sort_pdf = pdf_page_val
        else:
            # 参照情報側から最初の pdf_page を拾う（なければ巨大な数で後ろに飛ばす）
            nums = [int(x) for x in ref_pdf_pages.get(bk, "").split(",") if x.isdigit()]
            sort_pdf = min(nums) if nums else 10**9

        rows.append({
            "図表キー": k,
            "図表タイトル": ci["図表タイトル"],
            "頁": protect_for_excel_xlsx(ci["頁"]),
            "pdf頁": ci["pdf頁"],
            "参照頁ラベル": ref_page_labels.get(bk, ""),
            "参照pdf頁": ref_pdf_pages.get(bk, ""),
            "参照テキスト": ref_texts.get(bk, ""),
            "参照テキスト(強調)": ref_highlight_texts.get(bk, ""),
            "_sort_pdf": sort_pdf,
        })

    df = pd.DataFrame(rows, columns=[
        "図表キー", "図表タイトル", "頁", "pdf頁",
        "参照頁ラベル", "参照pdf頁",
        "参照テキスト", "参照テキスト(強調)", "_sort_pdf",
    ])
    return df.sort_values("_sort_pdf", kind="mergesort").drop(columns=["_sort_pdf"], errors="ignore")
