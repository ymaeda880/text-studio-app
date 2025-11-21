# -*- coding: utf-8 -*-
# pages/35_レッドリスト検索.py
from __future__ import annotations

import io, re
from pathlib import Path
from typing import List, Iterable
import pandas as pd
import streamlit as st

# =========================================================
# ページ設定
# =========================================================
st.set_page_config(page_title="🔎 レッドリスト検索（複数語対応）", page_icon="🔎", layout="wide")
st.title("🔎 72_レッドリスト検索")
st.caption("フォルダ: data/redlist/{fukushima, MOE, chiba} を読み込み、和名/種名を複数語まとめて横断検索します。")

# =========================================================
# データ読み込み
# =========================================================
from lib.redlist.loaders import load_all
DATA_ROOT = Path("data/redlist").resolve()
moe_df, fuku_df, chiba_df = load_all(DATA_ROOT)

# =========================================================
# ソース選択（サイドバー）
# =========================================================
with st.sidebar:
    st.subheader("📁 データソース選択")
    use_moe = st.checkbox("環境省", value=True)
    use_fuku = st.checkbox("福島県", value=False)
    use_chiba = st.checkbox("千葉県", value=False)

    st.markdown("---")
    st.subheader("📊 読み込み件数（参考）")
    st.code(str(DATA_ROOT))
    st.write({
        "環境省": 0 if moe_df.empty else int(moe_df.shape[0]),
        "福島県": 0 if fuku_df.empty else int(fuku_df.shape[0]),
        "千葉県": 0 if chiba_df.empty else int(chiba_df.shape[0]),
    })

# =========================================================
# ヘルパー
# =========================================================
def normalize_name(s: str) -> str:
    return "" if pd.isna(s) else str(s).replace("\u3000", " ").strip()

def parse_queries(raw: str) -> List[str]:
    """改行・カンマ・スペースなどで区切ってユニーク化（順序保持）"""
    if not raw:
        return []
    raw = raw.replace("\u3000", " ")
    parts = re.split(r"[,\s]+", raw)
    seen, uniq = set(), []
    for p in parts:
        p = normalize_name(p)
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq

def mask_for_queries(series: pd.Series, qs: Iterable[str], exact: bool) -> pd.Series:
    s_norm = series.fillna("").map(normalize_name)
    if exact:
        return s_norm.isin(list(qs))
    mask = pd.Series(False, index=series.index)
    s_low = s_norm.str.lower()
    for q in qs:
        ql = q.lower()
        mask = mask | s_low.str.contains(re.escape(ql), na=False)
    return mask

def ensure_line_numbers(hit: pd.DataFrame) -> pd.Series:
    """ローダーで行番号があれば使用。無ければcumcountで補完 (+2: 見出し1行想定)"""
    if "行番号" in hit.columns:
        try:
            return pd.to_numeric(hit["行番号"], errors="coerce").fillna("").astype("Int64")
        except Exception:
            pass
    if "ファイル名" in hit.columns and "シート名" in hit.columns:
        seq = hit.groupby(["ファイル名", "シート名"], sort=False).cumcount()
    elif "ファイル名" in hit.columns:
        seq = hit.groupby(["ファイル名"], sort=False).cumcount()
    else:
        seq = pd.Series(range(len(hit)), index=hit.index)
    return (seq + 2).astype(int)

def build_output(hit: pd.DataFrame, source: str, name_col: str) -> pd.DataFrame:
    """出力列の構築"""
    hit = hit.copy()
    out = pd.DataFrame(index=hit.index)
    out["和名"] = hit[name_col].astype(str).map(normalize_name)
    out["ソース"] = source

    if "ファイル名" in hit.columns:
        out["ファイル名"] = hit["ファイル名"].astype(str).map(normalize_name)
    if "シート名" in hit.columns:
        out["シート名"] = hit["シート名"].astype(str).map(normalize_name)
    out["行番号"] = ensure_line_numbers(hit)
    if "学名" in hit.columns:
        out["学名"] = hit["学名"].astype(str).map(normalize_name)

    if source == "環境省":
        out["カテゴリー記号"] = hit.get("環境省カテゴリー記号", "")
        out["元カテゴリ"] = hit.get("カテゴリー", "")
    elif source == "福島県":
        out["カテゴリー記号"] = hit.get("福島県カテゴリー記号", "")
        out["元カテゴリ"] = hit.get("福島カテゴリー", "")
    elif source == "千葉県":
        out["カテゴリー記号"] = hit.get("千葉県カテゴリー記号", "")
        out["元カテゴリ"] = hit.get("カテゴリー", "")
    else:
        out["カテゴリー記号"] = ""
        out["元カテゴリ"] = ""

    first = ["和名", "ソース", "カテゴリー記号", "元カテゴリ", "ファイル名", "行番号", "シート名", "学名"]
    rest = [c for c in out.columns if c not in first]
    out = out[first + rest]
    return out.reset_index(drop=True)

# =========================================================
# 入力フォーム
# =========================================================
st.subheader("🧭 和名/種名 検索（複数語対応）")
with st.form("search_form"):
    col_q1, col_q2 = st.columns([3, 1])
    with col_q1:
        multi_query_raw = st.text_area(
            "和名（環境省/福島）・種名（千葉）を複数入力可能",
            height=120,
            placeholder="例）\nニホンザル\nヤマネ, トキ\nヤンバルクイナ",
        )
    with col_q2:
        mode_exact = st.toggle("完全一致", True, help="OFFで部分一致")
    do_search = st.form_submit_button("🔎 検索を実行")

queries = parse_queries(multi_query_raw) if do_search else []
if do_search and queries:
    st.caption(f"🔎 検索語：{', '.join(queries)}（{len(queries)}語）")

# =========================================================
# 検索処理
# =========================================================
if do_search and queries:
    parts: List[pd.DataFrame] = []
    with st.spinner("検索中…"):

        # 環境省（和名）
        if use_moe and not moe_df.empty and "和名" in moe_df.columns:
            m = mask_for_queries(moe_df["和名"], queries, mode_exact)
            hit = moe_df.loc[m]
            if not hit.empty:
                parts.append(build_output(hit, "環境省", "和名"))

        # 福島県（和名）
        if use_fuku and not fuku_df.empty and "和名" in fuku_df.columns:
            m = mask_for_queries(fuku_df["和名"], queries, mode_exact)
            hit = fuku_df.loc[m]
            if not hit.empty:
                parts.append(build_output(hit, "福島県", "和名"))

        # 千葉県（種名）
        if use_chiba and not chiba_df.empty and "種名" in chiba_df.columns:
            m = mask_for_queries(chiba_df["種名"], queries, mode_exact)
            hit = chiba_df.loc[m]
            if not hit.empty:
                parts.append(build_output(hit, "千葉県", "種名"))

    matched_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    # --- 未ヒット語 ---
    missing_df = pd.DataFrame()
    if mode_exact:
        present_names = set(matched_df["和名"].astype(str).map(normalize_name)) if not matched_df.empty else set()
        missing = [q for q in queries if normalize_name(q) not in present_names]
        if missing:
            missing_df = pd.DataFrame({
                "和名": [q for q in missing],
                "ソース": ["—"] * len(missing),
                "カテゴリー記号": ["該当なし"] * len(missing),
                "元カテゴリ": [""] * len(missing),
                "ファイル名": [""] * len(missing),
                "行番号": [pd.NA] * len(missing),
                "シート名": [""] * len(missing),
                "学名": [""] * len(missing),
            })

    if matched_df.empty and missing_df.empty:
        st.warning("一致するデータが見つかりませんでした。")
    else:
        results_df = pd.concat([matched_df, missing_df], ignore_index=True, sort=False)

        order_map = {q: i for i, q in enumerate(queries)}
        results_df["__name_norm"] = results_df["和名"].astype(str).map(normalize_name)
        results_df["__ord"] = results_df["__name_norm"].map(order_map).fillna(len(queries) + 1)

        if "カテゴリー記号" in results_df.columns:
            is_missing_row = results_df["カテゴリー記号"].astype(str).eq("該当なし")
            results_df.loc[is_missing_row, "__ord"] = (
                len(queries) + results_df.index.to_series()[is_missing_row].rank(method="first").astype(int)
            )

        results_df = results_df.sort_values(["__ord"], kind="stable").drop(columns=["__ord", "__name_norm"])

        if "和名" in results_df.columns:
            dup_mask = results_df["和名"].eq(results_df["和名"].shift())
            results_df.loc[dup_mask, "和名"] = ""

        base = ["和名", "ソース", "カテゴリー記号", "元カテゴリ", "ファイル名", "行番号", "シート名", "学名"]
        results_df = results_df[[c for c in base if c in results_df.columns]]
        st.dataframe(results_df, use_container_width=True)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
            results_df.to_excel(w, index=False, sheet_name="Search_Results")

        st.download_button(
            "📥 検索結果をExcelで保存",
            buf.getvalue(),
            file_name="redlist_search_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
else:
    st.info("検索語を入力して『🔎 検索を実行』を押してください。")

# =========================================================
# 備考
# =========================================================
with st.expander("ℹ️ 備考", expanded=False):
    st.markdown("""
- **データソース選択**：サイドバーのチェックボックスで対象グループを選択します。初期値は「環境省」のみ。
- **並べ替え**：入力した検索語の順番に結果を並べています。
- **連続重複の空白化**：同じ“和名”が連続する場合、2行目以降の“和名”は空白表示します（Excelにも反映）。
- **該当なし**は完全一致モード時のみ判定します。
    """)
