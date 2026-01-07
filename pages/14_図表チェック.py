# -*- coding: utf-8 -*-
# pages/14_図表チェック.py（改良版：強調表示・excerpt付き + 番号品質/突き合わせ + XLSX出力）
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
from lib.toc_check.toc_segments import (
    pdf_to_text_per_page,
    extract_single_page_label,
)
from lib.chart_check.explanation import render_numbering_logic_expander  # ★追加
from lib.chart_check.helpers import (
    base_key,
    index_pages_by_key,
    ref_aggregate_for_view,
    caption_info_first_by_key,
    aggregate_ref_info,
    make_crosscheck_rows,
    protect_for_excel_csv,
    protect_for_excel_xlsx,
)

# =========================
# ページ設定 & メインUI
# =========================
st.set_page_config(page_title="🖼️ 図表 抽出（行頭/助詞/句点ルール + 頁ラベル）", page_icon="🖼️", layout="wide")
st.title("🖼️ 図表の参照照合チェック")
st.caption(
    "図表番号と本文の参照に対して照合してチェックを行います。"
    "（１）図表があるのに本文で参照されていないもの，（２）本文で参照されているのに図表の本体がないもの,"
    "（３）図表番号が重複しているものをチェックします．"
)
st.caption("AIは使用していません．安心してpdfを丸ごとアップロードしてください．")

# 👇 利用者向けのロジック説明（折りたたみ）
render_numbering_logic_expander()

uploaded = st.file_uploader("PDF をアップロード", type=None)
run = st.button("▶ 解析を実行", type="primary", use_container_width=True)

# --- 実行ボタンが押されていなければ何もしない ---
if not run:
    st.stop()

# --- ファイル未アップロード ---
if uploaded is None:
    st.warning("PDF ファイル（.pdf）をアップロードしてください。")
    st.stop()

# --- 拡張子チェック（念のため：.pdf 以外ならエラー）---

suffix = Path(uploaded.name).suffix.lower()
if suffix != ".pdf":
    st.error("PDF 以外のファイルがアップロードされました。PDF（.pdf）をドロップしてください。")
    st.stop()

with st.sidebar:
    st.markdown("### オプション")
    ctx_chars  = st.slider("参照の前後コンテキスト文字数（excerpt 用）", 10, 300, 60, 5)
    show_debug = st.checkbox("内部情報（デバッグ）を表示", value=False)


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
# DOT = r"[\.．・･]"
# NUM_ZH = r"[0-9０-９]+"
# NUM_TOKEN = rf"""
# (
#     # 例：4.2-1(1/6), 4.2-1（1／６） など
#     {NUM_ZH}
#     (?:\s*(?:{DOT}|{HY})\s*{NUM_ZH})*
#     (?:\s*[（(]?\s*{NUM_ZH}\s*[\/／]\s*{NUM_ZH}\s*[）)])?
#     |
#     # 例：(1), （２）
#     [（(]\s*{NUM_ZH}\s*[）)]
# )
# """

DOT = r"[\.．・･]"
NUM_ZH = r"[0-9０-９]+"
NUM_TOKEN = rf"""
(
    # 例：4.2-1(1/6), 4.2-1（1／６）, 2.2.1-3(1) など
    {NUM_ZH}
    (?:\s*(?:{DOT}|{HY})\s*{NUM_ZH})*
    (?:\s*[（(]\s*
        (?:                               # 末尾括弧：続き(i/n) or サブ番号(i)
            {NUM_ZH}\s*[\/／]\s*{NUM_ZH}  # 続き：1/3
            |
            {NUM_ZH}                      # サブ番号：1
        )
    \s*[）)]\s*)?
    |
    # 例：(1), （２）
    [（(]\s*{NUM_ZH}\s*[）)]
)
"""


EXTRACT_RE = re.compile(
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})",
    re.X
)


def canon_num(num: str) -> str:
    # 全角 → 半角
    s = num.translate(str.maketrans("０１２３４５６７８９（）", "0123456789()"))

    # ドット類 → "."
    s = re.sub(DOT, ".", s)

    # ハイフン類 → "-"
    s = re.sub(HY, "-", s)

    # "." と "-" の前後スペース削除
    s = re.sub(r"\s*\.\s*", ".", s)
    s = re.sub(r"\s*-\s*", "-", s)

    # 複数スペース → 1 個
    s = re.sub(r"[ \u3000]+", " ", s)

    # 括弧内スペース削除
    s = re.sub(r"\(\s*", "(", s)
    s = re.sub(r"\s*\)", ")", s)

    return s.strip()


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
        # ★ base_key を通してから、「図表/図/表」プレフィックスを削る
        s = base_key(key)
        return re.sub(r"^(図表|図|表)", "", s)

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
cap_idx = index_pages_by_key(df_captions)  # 図表キー → pdf_page 一覧
ref_idx = index_pages_by_key(df_refs)

# ① フルの図表キー集合（DataFrame からダイレクトに取得）
cap_keys_full: set[str] = set()
ref_keys_full: set[str] = set()
if not df_captions.empty and "図表キー" in df_captions.columns:
    cap_keys_full = set(df_captions["図表キー"].dropna().astype(str))
if not df_refs.empty and "図表キー" in df_refs.columns:
    ref_keys_full = set(df_refs["図表キー"].dropna().astype(str))

# ② ベースキー集合（(1/3) だけ落としたもの）
cap_base_keys = {base_key(k) for k in cap_keys_full}
ref_base_keys = {base_key(k) for k in ref_keys_full}

#############################################
# --- 未引用チェック（見出し側） ---
#   ・見出しのフルキー k が本文で一度も出てこない
#   ・またはベースキーでもマッチしない
#############################################
missing_in_refs = sorted(
    k for k in cap_keys_full
    if not (
        (k in ref_keys_full)              # 完全一致引用あり
        or (base_key(k) in ref_base_keys) # ベースキー一致で引用あり（表3.1.5-1(1/3) vs 表3.1.5-1）
    )
)

#############################################
# --- 見出しなし参照（本文側） ---
#   ・本文のフルキー k に対応する見出しがない
#   ・ただしベースキー一致で見出しがあれば OK
#############################################
missing_in_captions = sorted(
    k for k in ref_keys_full
    if not (
        (k in cap_keys_full)              # 完全一致で見出しあり
        or (base_key(k) in cap_base_keys) # ベースキー一致で見出しあり
    )
)

all_captions_referenced  = (len(missing_in_refs) == 0)
has_refs_without_caption = (len(missing_in_captions) > 0)




st.subheader("🔎 突き合わせ結果（見出し ↔ 参照）")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**① 全ての図表見出しが本文で引用されているか？**")
    st.write("→ **{}**".format("はい（全て引用あり）✅" if all_captions_referenced else "いいえ（未引用あり）⚠️"))
with c2:
    st.markdown("**② 本文に参照があるが見出しが無いものはないか？**")
    st.write("→ **{}**".format(
        "はい（全て見出しあり）✅" if not has_refs_without_caption else "いいえ（見出しなしの参照あり）⚠️"
    ))


# 画面表示用：参照情報をベースキーで集約
ref_lbls, ref_pdfs, ref_texts, ref_hi = ref_aggregate_for_view(df_refs, base_key_func=base_key)


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


# ベースキーが参照側に存在する図表キーを「引用されている見出し」とみなす
ref_base_keys_view = set(ref_lbls.keys())
referenced_keys = sorted(
    k for k in cap_idx.keys()
    if base_key(k) in ref_base_keys_view
)

rows = []
for k in referenced_keys:
    ci = _first_caption_row(df_captions, k)
    bk = base_key(k)
    rows.append({
        "図表キー": k,
        "図表タイトル": ci["図表タイトル"],
        "頁": ci["頁"],
        "pdf頁": ci["pdf頁"],
        "参照頁ラベル": ref_lbls.get(bk, ""),
        "参照pdf頁": ref_pdfs.get(bk, ""),
        "参照テキスト": ref_texts.get(bk, ""),
        "参照テキスト(強調)": ref_hi.get(bk, ""),
        "_sort": ci["pdf頁"],
    })

df_referenced_view = (
    pd.DataFrame(
        rows,
        columns=[
            "図表キー", "図表タイトル", "頁", "pdf頁",
            "参照頁ラベル", "参照pdf頁", "参照テキスト", "参照テキスト(強調)", "_sort"
        ]
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

    for df, name in [
        (df_per_page_labels, "per_page_labels.csv"),
        (df_captions, "figure_table_captions.csv"),
        (df_refs, "figure_table_references.csv"),
    ]:
        if not df.empty:
            df2 = df.copy()
            if "page_label" in df2.columns:
                df2["page_label"] = df2["page_label"].map(protect_for_excel_csv)
            buf = io.StringIO()
            df2.to_csv(buf, index=False)
            st.download_button(
                f"📥 {name}",
                data=buf.getvalue().encode("utf-8-sig"),
                file_name=name,
                mime="text/csv",
                use_container_width=True,
            )

# =========================
# XLSX（突き合わせ＋重複/続き）ダウンロード
# =========================
from io import BytesIO

cap_info = caption_info_first_by_key(df_captions, df_per_page_labels)
ref_page_labels, ref_pdf_pages, ref_texts, ref_highlight_texts = aggregate_ref_info(
    df_refs,
    base_key_func=base_key,
)

# XLSX 用の referenced_keys もベースキーで判定
ref_base_keys_x = set(ref_page_labels.keys())
referenced_keys_x = sorted(
    k for k in cap_idx.keys()
    if base_key(k) in ref_base_keys_x
)

df_referenced_captions_x = make_crosscheck_rows(
    referenced_keys_x,
    caption_src=True,
    cap_info=cap_info,
    ref_page_labels=ref_page_labels,
    ref_pdf_pages=ref_pdf_pages,
    ref_texts=ref_texts,
    ref_highlight_texts=ref_highlight_texts,
    base_key_func=base_key,
)
df_missing_caption_refs_x = make_crosscheck_rows(
    sorted(missing_in_refs),
    caption_src=True,
    cap_info=cap_info,
    ref_page_labels=ref_page_labels,
    ref_pdf_pages=ref_pdf_pages,
    ref_texts=ref_texts,
    ref_highlight_texts=ref_highlight_texts,
    base_key_func=base_key,
)
df_orphan_refs_x = make_crosscheck_rows(
    sorted(missing_in_captions),
    caption_src=False,
    cap_info=cap_info,
    ref_page_labels=ref_page_labels,
    ref_pdf_pages=ref_pdf_pages,
    ref_texts=ref_texts,
    ref_highlight_texts=ref_highlight_texts,
    base_key_func=base_key,
)

# 真の重複 & 続き判定のDF
dup_df = pd.DataFrame(dup_rows) if dup_rows else pd.DataFrame(
    columns=["図表キー", "見出しタイトル一覧", "pdf頁一覧", "頁ラベル一覧", "備考"]
)
cont_df = pd.DataFrame(cont_rows) if cont_rows else pd.DataFrame(
    columns=["図表キー", "図表タイトル（本体）", "pdf頁一覧", "頁ラベル一覧", "備考"]
)

with st.sidebar:
    st.markdown("### 🔗 突き合わせ結果（xlsx）")
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # サマリー
        pd.DataFrame({
            "項目": ["全て引用済みか？", "見出しなしの参照はないか？"],
            "結果": [
                "はい（全て引用あり）✅" if all_captions_referenced else "いいえ（未引用あり）⚠️",
                "はい（見出しなし参照なし）✅" if not has_refs_without_caption else "いいえ（見出しなし参照あり）⚠️",
            ]
        }).to_excel(writer, sheet_name="サマリー", index=False)

        # 突き合わせ 3 シート
        df_referenced_captions_x.to_excel(writer, sheet_name="引用見出し", index=False)
        df_missing_caption_refs_x.to_excel(writer, sheet_name="未引用見出し", index=False)
        df_orphan_refs_x.to_excel(writer, sheet_name="見出しなし参照", index=False)

        # 重複/続き 判定 2 シート
        dup_df.to_excel(writer, sheet_name="重複（疑い）", index=False)
        cont_df.to_excel(writer, sheet_name="続き判定", index=False)

        # 連番チェック
        if 'start_rows' in locals():
            (
                pd.DataFrame(start_rows)
                if start_rows else
                pd.DataFrame(columns=["種別", "系列", "開始番号", "期待", "存在番号"])
            ).to_excel(writer, sheet_name="開始番号チェック", index=False)
        if 'gap_rows' in locals():
            (
                pd.DataFrame(gap_rows)
                if gap_rows else
                pd.DataFrame(columns=["種別", "系列", "欠番", "存在番号"])
            ).to_excel(writer, sheet_name="欠番チェック", index=False)

    base = uploaded.name.rsplit(".", 1)[0]
    xlsx_filename = f"図表照合_{base}.xlsx"

    st.download_button(
        "📘 突き合わせ結果をダウンロード",
        data=output.getvalue(),
        file_name=xlsx_filename,
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
