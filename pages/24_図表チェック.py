# -*- coding: utf-8 -*-
# pages/24_図表チェック.py（改良版：強調表示・excerpt付き + 番号品質/突き合わせ + XLSX出力）
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import io, re, tempfile

import streamlit as st
import pandas as pd

# === 共通ライブラリ（lib/）からインポート ===
from lib.text_normalizer import (
    z2h_numhy,
    normalize_strict,
    HY,
)
from lib.toc_segments import (
    pdf_to_text_per_page,
    extract_single_page_label,
)

# =========================
# ページ設定 & メインUI
# =========================
st.set_page_config(page_title="🖼️ 図表 抽出（行頭/助詞/句点ルール + 頁ラベル）", page_icon="🖼️", layout="wide")
st.title("🖼️ 図表 抽出 — タイトル/参照（行頭・直後助詞・句点ルール）＋ 頁ラベル併記")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 解析を実行", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    ctx_chars  = st.slider("参照の前後コンテキスト文字数（excerpt 用）", 10, 300, 60, 5)
    show_debug = st.checkbox("内部情報（デバッグ）を表示", value=False)

if not uploaded or not run:
    st.stop()

# =========================
# PDF → ページ別テキスト
# =========================
with tempfile.TemporaryDirectory() as td:
    pdf_path = Path(td) / "input.pdf"
    pdf_path.write_bytes(uploaded.getvalue())
    pages_text: List[str] = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")

# =========================
# 図表抽出（ページ固有ロジック）
# =========================
DOT = r"[\.．・･]"
NUM_ZH = r"[0-9０-９]+"
NUM_TOKEN = rf"""
(
    {NUM_ZH}
    (?:\s*(?:{DOT}|{HY})\s*{NUM_ZH})*
    |
    [（(]\s*{NUM_ZH}\s*[）)]
)
"""
EXTRACT_RE = re.compile(
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})",
    re.X
)

def canon_num(num: str) -> str:
    s = num.translate(str.maketrans("０１２３４５６７８９（）", "0123456789()"))
    s = re.sub(DOT, ".", s)
    s = re.sub(HY, "-", s)
    s = re.sub(r"[()（）]", "", s)
    s = re.sub(r"\s*\.\s*", ".", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", "", s)
    return s

def canon_label(kind: str, num: str) -> str:
    return f"{kind}{canon_num(num)}"

try:
    import regex as re2
except Exception:
    re2 = re

PARTICLES_RE = re2.compile(r"(?:に|を|は|へ|で|と|の|など|等|または|又は|および|及び|かつ)")

# ===== 行抽出補助関数 =====
def extract_line_covering_match(full: str, start: int, end: int) -> Tuple[int, str, int, int]:
    """マッチを必ず含む行（改行またぎ対応）を返す"""
    line_start = full.rfind("\n", 0, start)
    line_start = 0 if line_start == -1 else line_start + 1
    line_end = full.find("\n", end)
    if line_end == -1:
        line_end = len(full)
    line_txt = full[line_start:line_end].rstrip("\r\n")
    approx_lineno = full.count("\n", 0, line_start) + 1
    return approx_lineno, line_txt, line_start, line_end

# ===== ページ単位の抽出 =====
def judge_hits_in_page(page_text: str, ctx: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    captions, refs = [], []
    full = page_text.replace("\r\n", "\n").replace("\r", "\n")

    for m in EXTRACT_RE.finditer(full):
        kind, num, raw = m.group("kind"), m.group("num"), m.group(0)
        lineno, line_txt, line_start, line_end = extract_line_covering_match(full, m.start(), m.end())

        is_line_head = (full[line_start:m.start()].strip() == "")
        rel_end = (m.start() - line_start) + len(raw)
        after_on_line = line_txt[rel_end:] if rel_end <= len(line_txt) else ""
        particle_follow = bool(re2.match(rf"\s*{PARTICLES_RE.pattern}", after_on_line))
        has_period = ("。" in line_txt)
        is_reference = (not is_line_head) or particle_follow or has_period

        # 強調とexcerpt
        highlighted = line_txt.replace(raw, f"⟪{raw}⟫", 1)
        left  = max(0, m.start() - ctx)
        right = min(len(full), m.end() + ctx)
        excerpt = full[left:m.start()] + f"⟪{raw}⟫" + full[m.end():right]

        if is_reference:
            refs.append({
                "行番号": lineno,
                "参照テキスト": raw.strip(),
                "図表種類": kind,
                "図表番号": f"{kind}{z2h_numhy(num)}",
                "図表キー": canon_label(kind, num),
                "excerpt": excerpt,
                "行テキスト": line_txt,
                "行テキスト(強調)": highlighted,
                "判定": "参照",
                "rule(理由)": (
                    "行頭でない→参照" if not is_line_head else
                    ("直後が助詞/接続語→参照" if particle_follow else "行に句点あり→参照")
                ),
            })
        else:
            title = re.sub(r"^[\s:：.\-．、・]+", "", after_on_line).strip()
            captions.append({
                "行番号": lineno,
                "図表種類": kind,
                "図表番号": f"{kind}{z2h_numhy(num)}",
                "図表キー": canon_label(kind, num),
                "見出しタイトル": title,
                "matched_line": line_txt,
                "matched_line(強調)": highlighted,
                "excerpt": excerpt,
                "判定": "タイトル",
                "rule(理由)": "その他→タイトル",
            })
    return captions, refs

# =========================
# 全ページ走査
# =========================
page_labels, per_page_rows = [], []
for i, ptxt in enumerate(pages_text, start=1):
    label, matched = extract_single_page_label(ptxt)
    page_labels.append(label)
    per_page_rows.append({
        "pdf_page": i,
        "page_label": label or "-",
        "matched_line": matched or "-",
        "has_label": label is not None,
    })
df_per_page_labels = pd.DataFrame(per_page_rows)

caption_rows, ref_rows = [], []
for i, ptxt in enumerate(pages_text, start=1):
    page_label = page_labels[i-1] if i-1 < len(page_labels) and page_labels[i-1] else "-"
    captions, refs = judge_hits_in_page(ptxt, ctx=ctx_chars)
    for h in captions:
        caption_rows.append({"pdf_page": i, "page_label": page_label, **h})
    for r in refs:
        ref_rows.append({"pdf_page": i, "page_label": page_label, **r})

df_captions = pd.DataFrame(caption_rows)
df_refs     = pd.DataFrame(ref_rows)

# =========================
# 表示
# =========================
st.subheader("📑 各ページの頁ラベル（1頁=高々1）")
st.dataframe(df_per_page_labels, use_container_width=True)

st.subheader("🖼️ 図/表/図表 見出し（キャプション）")
st.dataframe(df_captions, use_container_width=True)

# =========================
# 図表番号の品質チェック（重複・飛び・開始番号・続き判定）
# =========================
st.markdown("### ✅ 図表番号の品質チェック（重複・飛び・開始）")

if df_captions.empty or "図表番号" not in df_captions.columns:
    st.info("図表番号の検査対象がありません（df_captions が空です）。")
    cont_rows, dup_rows = [], []
else:
    
    # 末尾の（任意ラベル + i/n）や（続き）を除去してタイトル本体にする
    def _title_base(s: str) -> str:
        if s is None:
            return ""
        t = str(s)
        # 例：...(ムクドリ1/5) / ...(A 2/3) / ...(ラベル ３／５) など（全角括弧・全角スラッシュ対応）
        t = re.sub(r"[\(（][^()（）]*?(\d+)\s*[\/／]\s*(\d+)\s*[\)）]\s*$", "", t)
        # 末尾の（続き）も除去（任意）
        t = re.sub(r"[\(（]\s*続き\s*[\)）]\s*$", "", t)
        # 空白正規化
        t = re.sub(r"\s+", " ", t).strip()
        return t

    # 末尾括弧から (i/n) を抽出（括弧内に任意ラベル許容、全角スラッシュ対応）
    def _part_tuple(s: str) -> Tuple[Optional[int], Optional[int]]:
        if not s:
            return (None, None)
        m = re.search(r"[\(（][^()（）]*?(\d+)\s*[\/／]\s*(\d+)\s*[\)）]\s*$", str(s))
        if not m:
            return (None, None)
        return (int(m.group(1)), int(m.group(2)))


    def _is_continuation_group(g: pd.DataFrame) -> bool:
        """同図表キーの複数見出しが『続き』かを判定"""
        if g.shape[0] <= 1:
            return False
        g2 = g.sort_values("pdf_page")
        bases = {_title_base(x) for x in g2["見出しタイトル"].fillna("")}
        if len(bases) != 1:
            return False
        pages = g2["pdf_page"].dropna().astype(int).tolist()
        if not pages:
            return False
        diffs = [b - a for a, b in zip(pages, pages[1:])]
        if not diffs or max(diffs) != 1:   # 完全連続
            return False
        parts = [_part_tuple(t) for t in g2["見出しタイトル"].fillna("")]
        if any(p[0] is None or p[1] is None for p in parts):
            return True  # (i/n) が無くても連続なら続き扱い
        nums = [p[0] for p in parts]
        totals = {p[1] for p in parts}
        if len(totals) != 1:
            return False
        return nums == list(range(min(nums), min(nums)+len(nums)))

   
    # ---- グループ別に分類 ----
    cont_rows, dup_rows = [], []
    for k, g in df_captions.groupby("図表キー"):
        if len(g) <= 1:
            continue
        g2 = g.sort_values("pdf_page")
        # --- 続き判定 ---
        if _is_continuation_group(g2):
            cont_rows.append({
                "図表キー": k,
                # ここを修正：すべての見出しタイトルを連結して出力
                "図表タイトル": " | ".join([str(x) for x in g2["見出しタイトル"].fillna("").tolist()]),
                "pdf頁一覧": ",".join([str(int(x)) for x in g2["pdf_page"].dropna().astype(int).tolist()]),
                "頁ラベル一覧": ",".join([str(x) for x in g2["page_label"].fillna("").tolist()]),
                "備考": "（続きのページとみなす）"
            })
        # --- 真の重複 ---
        else:
            dup_rows.append({
                "図表キー": k,
                "見出しタイトル一覧": " | ".join([str(x) for x in g2["見出しタイトル"].fillna("").tolist()]),
                "pdf頁一覧": ",".join([str(int(x)) for x in g2["pdf_page"].dropna().astype(int).tolist()]),
                "頁ラベル一覧": ",".join([str(x) for x in g2["page_label"].fillna("").tolist()]),
                "備考": "（真の重複の可能性）"
            })


    # 画面表示
    if cont_rows:
        st.info("🔵 以下は **同番号の連続ページ** と判定しました（重複扱いしません）。")
        st.dataframe(pd.DataFrame(cont_rows), use_container_width=True)

    if dup_rows:
        st.warning("🟠 図表番号の**真の重複**が見つかりました。")
        st.dataframe(pd.DataFrame(dup_rows), use_container_width=True)
    elif not cont_rows:
        st.success("🟢 図表番号の重複はありません。")

    # ---- 連番チェック（欠番/開始1でない）----
    def _numeric_core_from_key(key: str) -> str:
        return re.sub(r"^(図表|図|表)", "", key)

    def _series_and_index(key: str) -> Tuple[str, Optional[int], str]:
        m = re.match(r"^(図表|図|表)", key)
        kind = m.group(1) if m else ""
        num_part = _numeric_core_from_key(key)
        if "-" in num_part:
            series, last = num_part.rsplit("-", 1)
        else:
            series, last = "", num_part
        try:
            idx = int(last)
        except Exception:
            idx = None
        return series, idx, kind

    from collections import defaultdict
    series_map = defaultdict(list)  # (kind, series) -> [(idx, key, pdf), ...]
    for _, r in df_captions.iterrows():
        key = str(r.get("図表キー"))
        pdfp = r.get("pdf_page")
        series, idx, kind = _series_and_index(key)
        if idx is None:
            continue
        series_map[(kind, series)].append((int(idx), key, int(pdfp) if pd.notna(pdfp) else 10**9))

    gap_rows, start_rows = [], []
    for (kind, series), items in series_map.items():
        items_sorted = sorted(items, key=lambda x: (x[0], x[2]))
        idxs = [i for i, _, _ in items_sorted]
        starts_at = idxs[0] if idxs else None
        if starts_at is not None and starts_at != 1:
            start_rows.append({
                "種別": kind,
                "系列": series or "(単一番号)",
                "開始番号": starts_at,
                "期待": 1,
                "存在番号": ",".join(map(str, idxs))
            })
        if len(idxs) >= 2:
            missing = []
            for a, b in zip(idxs, idxs[1:]):
                if b - a > 1:
                    missing.extend(range(a+1, b))
            if missing:
                gap_rows.append({
                    "種別": kind,
                    "系列": series or "(単一番号)",
                    "欠番": ",".join(map(str, missing)),
                    "存在番号": ",".join(map(str, idxs)),
                })

    if not gap_rows and not start_rows:
        st.success("🟢 連番の飛びは無く、各系列の開始番号も 1 になっています。")
    else:
        if start_rows:
            st.warning("🟠 系列の開始番号が 1 でないものが見つかりました。")
            st.dataframe(pd.DataFrame(start_rows), use_container_width=True)
        if gap_rows:
            st.warning("🟠 連番に欠番（飛び）が見つかりました。")
            st.dataframe(pd.DataFrame(gap_rows), use_container_width=True)

# ===== 本文参照の表示 =====
st.subheader("🔗 本文中の 図/表/図表 参照（excerpt付）")
st.dataframe(df_refs, use_container_width=True)

# =========================
# 突き合わせ：図表見出し ↔ 本文参照
# =========================
def _index_pages_by_key(df: pd.DataFrame, key_col: str = "図表キー") -> dict:
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

cap_idx = _index_pages_by_key(df_captions)
ref_idx = _index_pages_by_key(df_refs)

cap_keys = set(cap_idx.keys())
ref_keys = set(ref_idx.keys())

missing_in_refs = sorted(cap_keys - ref_keys)        # 見出しはあるが参照がない
missing_in_captions = sorted(ref_keys - cap_keys)    # 参照はあるが見出しがない

all_captions_referenced  = (len(missing_in_refs) == 0)
has_refs_without_caption = (len(missing_in_captions) > 0)

st.subheader("🔎 突き合わせ結果（見出し ↔ 参照）")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**① 全ての図表見出しが本文で引用されているか？**")
    st.write("→ **{}**".format("はい（全て引用あり）✅" if all_captions_referenced else "いいえ（未引用あり）⚠️"))
with c2:
    st.markdown("**② 本文に参照があるが見出しが無いものはあるか？**")
    st.write("→ **{}**".format("はい（見出しなしの参照あり）⚠️" if has_refs_without_caption else "いいえ（全て見出しあり）✅"))

# 画面表示用：引用されている見出し
def _ref_aggregate_for_view(df_refs: pd.DataFrame):
    if df_refs is None or df_refs.empty:
        return {}, {}, {}, {}
    ref_lbls, ref_pdfs, ref_texts, ref_hi = {}, {}, {}, {}
    for k, grp in df_refs.groupby("図表キー"):
        grp2 = grp.sort_values(["pdf_page", "行番号"], kind="mergesort")
        lbls = grp2["page_label"].dropna().astype(str).unique().tolist()
        pnums = grp2["pdf_page"].dropna().astype(int).unique().tolist()
        texts = grp2["行テキスト"].dropna().astype(str).unique().tolist()
        his   = grp2["行テキスト(強調)"].dropna().astype(str).unique().tolist()
        ref_lbls[k] = ",".join(lbls)
        ref_pdfs[k] = ",".join(str(x) for x in pnums)
        ref_texts[k] = " | ".join(texts)
        ref_hi[k]    = " | ".join(his)
    return ref_lbls, ref_pdfs, ref_texts, ref_hi

ref_lbls, ref_pdfs, ref_texts, ref_hi = _ref_aggregate_for_view(df_refs)

def _first_caption_row(df_cap: pd.DataFrame, key: str):
    grp = df_cap[df_cap["図表キー"] == key]
    if grp.empty:
        return {"図表タイトル": "", "頁": "", "pdf頁": 10**9}
    row = grp.sort_values("pdf_page").iloc[0]
    return {
        "図表タイトル": row.get("見出しタイトル", "") or "",
        "頁": row.get("page_label", "") or "",
        "pdf頁": int(row.get("pdf_page")) if pd.notna(row.get("pdf_page")) else 10**9,
    }

referenced_keys = sorted(set(cap_idx.keys()) & set(ref_idx.keys()))
rows = []
for k in referenced_keys:
    ci = _first_caption_row(df_captions, k)
    rows.append({
        "図表キー": k,
        "図表タイトル": ci["図表タイトル"],
        "頁": ci["頁"],
        "pdf頁": ci["pdf頁"],
        "参照頁ラベル": ref_lbls.get(k, ""),
        "参照pdf頁": ref_pdfs.get(k, ""),
        "参照テキスト": ref_texts.get(k, ""),
        "参照テキスト(強調)": ref_hi.get(k, ""),
        "_sort": ci["pdf頁"],
    })

df_referenced_view = (
    pd.DataFrame(
        rows,
        columns=["図表キー","図表タイトル","頁","pdf頁","参照頁ラベル","参照pdf頁","参照テキスト","参照テキスト(強調)","_sort"]
    )
    .sort_values("_sort", kind="mergesort")
    .drop(columns=["_sort"])
)

st.markdown("#### 🔵 引用されている見出し（見出しあり＋本文参照あり）")
st.dataframe(df_referenced_view, use_container_width=True)

st.markdown("#### 🟠 未引用の見出し（見出しはあるが本文参照が見つからない）")
df_missing_caption_refs = pd.DataFrame(
    [{"図表キー": k, "見出しページ": cap_idx.get(k, []), "参照ページ": ref_idx.get(k, [])}
     for k in missing_in_refs]
)
st.dataframe(df_missing_caption_refs, use_container_width=True)

st.markdown("#### 🔵 見出しなしの参照（本文に参照はあるが対応する見出しが無い）")
df_orphan_refs = pd.DataFrame(
    [{"図表キー": k, "参照ページ": ref_idx.get(k, []), "見出しページ": cap_idx.get(k, [])}
     for k in missing_in_captions]
)
st.dataframe(df_orphan_refs, use_container_width=True)

# =========================
# CSV ダウンロード
# =========================
with st.sidebar:
    st.markdown("### CSV ダウンロード")
    def _protect_for_excel_csv(x: object) -> object:
        if isinstance(x, str) and re.match(r"^\s*\d{1,2}\s*[-−ー－―]\s*\d{1,2}\s*$", x.strip()):
            return f'="{x.strip()}"'
        return x
    for df, name in [
        (df_per_page_labels, "per_page_labels.csv"),
        (df_captions, "figure_table_captions.csv"),
        (df_refs, "figure_table_references.csv"),
    ]:
        if not df.empty:
            df2 = df.copy()
            if "page_label" in df2.columns:
                df2["page_label"] = df2["page_label"].map(_protect_for_excel_csv)
            buf = io.StringIO()
            df2.to_csv(buf, index=False)
            st.download_button(f"📥 {name}",
                               data=buf.getvalue().encode("utf-8-sig"),
                               file_name=name,
                               mime="text/csv",
                               use_container_width=True)

# =========================
# XLSX（突き合わせ＋重複/続き）ダウンロード
# =========================
from io import BytesIO

def _caption_info_first_by_key(df: pd.DataFrame) -> dict:
    info = {}
    if df is None or df.empty:
        return info
    for k, grp in df.groupby("図表キー"):
        row = grp.sort_values("pdf_page").iloc[0]
        info[str(k)] = {
            "図表タイトル": row.get("見出しタイトル", "") or "",
            "頁": row.get("page_label", "") or "",
            "pdf頁": int(row.get("pdf_page")) if pd.notna(row.get("pdf_page")) else "",
        }
    return info

def _protect_for_excel(x: object) -> object:
    if isinstance(x, str) and re.match(r"^\s*\d{1,2}\s*[-−ー－―]\s*\d{1,2}\s*$", x.strip()):
        return f'=\"{x.strip()}\"'
    return x

# 参照側情報集約
def _aggregate_ref_info(df_refs: pd.DataFrame):
    if df_refs is None or df_refs.empty:
        return {}, {}, {}, {}
    ref_page_labels, ref_pdf_pages, ref_texts, ref_highlight_texts = {}, {}, {}, {}
    for k, grp in df_refs.groupby("図表キー"):
        grp2 = grp.sort_values(["pdf_page", "行番号"], na_position="last", kind="mergesort")
        labels = [str(x) for x in grp2["page_label"].dropna().unique().tolist()]
        pdfs = [str(int(x)) for x in grp2["pdf_page"].dropna().unique().tolist()]
        ref_page_labels[k] = ",".join(labels)
        ref_pdf_pages[k] = ",".join(pdfs)
        ref_texts[k] = " | ".join(grp2["行テキスト"].dropna().astype(str).unique().tolist())
        ref_highlight_texts[k] = " | ".join(grp2["行テキスト(強調)"].dropna().astype(str).unique().tolist())
    return ref_page_labels, ref_pdf_pages, ref_texts, ref_highlight_texts

cap_info = _caption_info_first_by_key(df_captions)
ref_page_labels, ref_pdf_pages, ref_texts, ref_highlight_texts = _aggregate_ref_info(df_refs)

def _make_rows(keys, caption_src=True):
    rows = []
    for k in keys:
        ci = cap_info.get(k, {"図表タイトル": "", "頁": "", "pdf頁": ""}) if caption_src else {"図表タイトル": "", "頁": "", "pdf頁": ""}
        rows.append({
            "図表キー": k,
            "図表タイトル": ci["図表タイトル"],
            "頁": _protect_for_excel(ci["頁"]),
            "pdf頁": ci["pdf頁"],
            "参照頁ラベル": ref_page_labels.get(k, ""),
            "参照pdf頁": ref_pdf_pages.get(k, ""),
            "参照テキスト": ref_texts.get(k, ""),
            "参照テキスト(強調)": ref_highlight_texts.get(k, ""),
            "_sort_pdf": ci["pdf頁"] if caption_src and ci["pdf頁"] != "" else (
                min([int(x) for x in ref_pdf_pages.get(k, "").split(",") if x.isdigit()] or [10**9])
            ),
        })
    df = pd.DataFrame(rows, columns=[
        "図表キー","図表タイトル","頁","pdf頁","参照頁ラベル","参照pdf頁","参照テキスト","参照テキスト(強調)","_sort_pdf"
    ])
    return df.sort_values("_sort_pdf", kind="mergesort").drop(columns=["_sort_pdf"], errors="ignore")

referenced_keys = sorted(set(cap_idx.keys()) & set(ref_idx.keys()))
df_referenced_captions_x = _make_rows(referenced_keys, caption_src=True)
df_missing_caption_refs_x = _make_rows(sorted(missing_in_refs), caption_src=True)
df_orphan_refs_x = _make_rows(sorted(missing_in_captions), caption_src=False)

# 真の重複 & 続き判定のDF（上の計算結果をそのまま利用）
dup_df = pd.DataFrame(dup_rows) if dup_rows else pd.DataFrame(
    columns=["図表キー","見出しタイトル一覧","pdf頁一覧","頁ラベル一覧","備考"]
)
cont_df = pd.DataFrame(cont_rows) if cont_rows else pd.DataFrame(
    columns=["図表キー","図表タイトル（本体）","pdf頁一覧","頁ラベル一覧","備考"]
)

with st.sidebar:
    st.markdown("### 🔗 突き合わせ結果（XLSX）")
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # サマリー
        pd.DataFrame({
            "項目": ["全て引用済み", "見出しなし参照あり"],
            "結果": [
                "はい（全て引用あり）✅" if all_captions_referenced else "いいえ（未引用あり）⚠️",
                "はい（見出しなし参照あり）⚠️" if has_refs_without_caption else "いいえ（全て見出しあり）✅",
            ]
        }).to_excel(writer, sheet_name="サマリー", index=False)

        # 突き合わせ 3 シート
        df_referenced_captions_x.to_excel(writer, sheet_name="引用見出し", index=False)
        df_missing_caption_refs_x.to_excel(writer, sheet_name="未引用見出し", index=False)
        df_orphan_refs_x.to_excel(writer, sheet_name="見出しなし参照", index=False)

        # 重複/続き 判定 2 シート（ご要望追加）
        dup_df.to_excel(writer, sheet_name="重複（疑い）", index=False)
        cont_df.to_excel(writer, sheet_name="続き判定", index=False)

        # 連番チェック（任意で出すなら）
        if 'start_rows' in locals():
            (pd.DataFrame(start_rows) if start_rows else pd.DataFrame(columns=["種別","系列","開始番号","期待","存在番号"])
             ).to_excel(writer, sheet_name="開始番号チェック", index=False)
        if 'gap_rows' in locals():
            (pd.DataFrame(gap_rows) if gap_rows else pd.DataFrame(columns=["種別","系列","欠番","存在番号"])
             ).to_excel(writer, sheet_name="欠番チェック", index=False)

    st.download_button(
        "📘 突き合わせ結果（引用/未引用/見出しなし参照/重複/続き/連番）.xlsx をダウンロード",
        data=output.getvalue(),
        file_name="figure_table_crosscheck.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# =========================
# デバッグ
# =========================
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.code(f"EXTRACT_RE = {EXTRACT_RE.pattern}")
    st.caption("マッチを含む1行抽出＋⟪強調⟫＋excerpt付き。")
