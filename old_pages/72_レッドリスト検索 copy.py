# -*- coding: utf-8 -*-
# pages/72_レッドリスト検索.py
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
# データ読み込み（lib/redlist/loaders から）
# =========================================================
from lib.redlist.loaders import load_all

DATA_ROOT = Path("data/redlist").resolve()
moe_df, fuku_df, chiba_df = load_all(DATA_ROOT)

with st.sidebar:
    st.subheader("📁 データソース")
    st.code(str(DATA_ROOT))
    st.markdown("**読み込み件数（参考）**")
    st.write({
        "環境省": 0 if moe_df is None or moe_df.empty else int(moe_df.shape[0]),
        "福島県": 0 if fuku_df is None or fuku_df.empty else int(fuku_df.shape[0]),
        "千葉県": 0 if chiba_df is None or chiba_df.empty else int(chiba_df.shape[0]),
    })

# =========================================================
# 入力（複数語）：「和名」（千葉は「種名」）
# =========================================================
st.subheader("🧭 和名/種名 検索（複数語対応）")

def normalize_name(s: str) -> str:
    if pd.isna(s):
        return ""
    # 全角スペース→半角、前後空白除去
    return str(s).replace("\u3000", " ").strip()

def parse_queries(raw: str) -> List[str]:
    """
    カンマ・空白（半/全）・タブ・改行・空白行で分割してユニーク化（順序保持）。
    """
    if not raw:
        return []
    # 全角スペース→半角
    raw = raw.replace("\u3000", " ")
    # カンマ or 任意のホワイトスペースで分割
    parts = re.split(r"[,\s]+", raw)
    # 空要素を除去して正規化
    parts = [normalize_name(p) for p in parts if p and normalize_name(p)]
    # 重複除去（順序保持）
    seen = set()
    uniq: List[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq

col_q1, col_q2 = st.columns([3, 1])
with col_q1:
    multi_query_raw = st.text_area(
        "和名（環境省/福島）・種名（千葉）を改行/カンマ/スペース/タブで複数入力できます",
        value="",
        height=120,
        placeholder="例）\nニホンザル\nヤマネ, トキ\n  ヤンバルクイナ"
    )
with col_q2:
    mode_exact = st.toggle("完全一致", value=True, help="OFFにすると部分一致（包含）で検索します。")

queries = parse_queries(multi_query_raw)
if queries:
    st.caption(f"🔎 検索語：{', '.join(queries)}（{len(queries)} 語）")

def mask_for_queries(series: pd.Series, qs: Iterable[str], exact: bool) -> pd.Series:
    """
    series を正規化した上で、複数クエリの OR マッチを返す。
    exact=True: 完全一致（==のOR）
    exact=False: 部分一致（containsのOR）
    """
    s_norm = series.fillna("").map(normalize_name)
    if exact:
        return s_norm.isin(list(qs))
    # 部分一致（ケース無視）
    s_low = s_norm.str.lower()
    mask = pd.Series(False, index=series.index)
    for q in qs:
        if not q:
            continue
        ql = q.lower()
        mask = mask | s_low.str.contains(re.escape(ql), na=False)
    return mask

results: List[pd.DataFrame] = []

if queries:
    # 環境省：和名
    if moe_df is not None and not moe_df.empty and "和名" in moe_df.columns:
        mask = mask_for_queries(moe_df["和名"], queries, mode_exact)
        hit = moe_df.loc[mask].copy()
        if not hit.empty:
            hit.insert(0, "ソース", "環境省")
            cols = ["ソース","ファイル名","シート名","和名","学名","分類群","カテゴリー","環境省カテゴリー記号"]
            for c in cols:
                if c not in hit.columns:
                    hit[c] = ""
            results.append(hit[cols])

    # 福島県：和名
    if fuku_df is not None and not fuku_df.empty and "和名" in fuku_df.columns:
        mask = mask_for_queries(fuku_df["和名"], queries, mode_exact)
        hit = fuku_df.loc[mask].copy()
        if not hit.empty:
            hit.insert(0, "ソース", "福島県")
            cols = ["ソース","ファイル名","シート名","和名","学名","生物群","分類","科名",
                    "福島カテゴリー","ふくしまRL2022カテゴリー","福島県カテゴリー記号"]
            for c in cols:
                if c not in hit.columns:
                    hit[c] = ""
            results.append(hit[cols])

    # 千葉県：種名
    if chiba_df is not None and not chiba_df.empty and "種名" in chiba_df.columns:
        mask = mask_for_queries(chiba_df["種名"], queries, mode_exact)
        hit = chiba_df.loc[mask].copy()
        if not hit.empty:
            hit.insert(0, "ソース", "千葉県")
            cols = ["ソース","ファイル名","シート名","種名","学名","分類群","目・科名","カテゴリー","記号","千葉県カテゴリー記号"]
            for c in cols:
                if c not in hit.columns:
                    hit[c] = ""
            results.append(hit[cols])

# =========================================================
# 結果表示 & ダウンロード（内部保存＋検索語の入力順で整列）
# =========================================================
if queries:
    def _norm(s: pd.Series) -> pd.Series:
        return s.fillna("").astype(str).str.replace("\u3000", " ").str.strip()

    # 入力順を保持しつつ重複は最初だけ採用
    queries_ordered: list[str] = []
    seen = set()
    for q in queries:
        qn = q.replace("\u3000", " ").strip()
        if qn and qn not in seen:
            queries_ordered.append(qn)
            seen.add(qn)

    def _hits_for_query(q: str) -> pd.DataFrame:
        parts = []

        # --- 環境省（和名）
        if not moe_df.empty and "和名" in moe_df.columns:
            m = _norm(moe_df["和名"]) == q
            h = moe_df.loc[m].copy()
            if not h.empty:
                h.insert(0, "ソース", "環境省")
                h.insert(0, "検索語", q)
                cols = ["検索語","ソース","ファイル名","シート名","和名","学名","分類群","カテゴリー","環境省カテゴリー記号"]
                for c in cols:
                    if c not in h.columns: h[c] = ""
                parts.append(h[cols])

        # --- 福島県（和名）
        if not fuku_df.empty and "和名" in fuku_df.columns:
            m = _norm(fuku_df["和名"]) == q
            h = fuku_df.loc[m].copy()
            if not h.empty:
                h.insert(0, "ソース", "福島県")
                h.insert(0, "検索語", q)
                cols = ["検索語","ソース","ファイル名","シート名","和名","学名","生物群","分類","科名",
                        "福島カテゴリー","ふくしまRL2022カテゴリー","福島県カテゴリー記号"]
                for c in cols:
                    if c not in h.columns: h[c] = ""
                parts.append(h[cols])

        # --- 千葉県（種名）
        if not chiba_df.empty and "種名" in chiba_df.columns:
            m = _norm(chiba_df["種名"]) == q
            h = chiba_df.loc[m].copy()
            if not h.empty:
                h.insert(0, "ソース", "千葉県")
                h.insert(0, "検索語", q)
                cols = ["検索語","ソース","ファイル名","シート名","種名","学名",
                        "分類群","目・科名","カテゴリー","記号","千葉県カテゴリー記号"]
                for c in cols:
                    if c not in h.columns: h[c] = ""
                parts.append(h[cols])

        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    # 検索語の入力順でブロック連結（ここがポイント）
    blocks = [ _hits_for_query(q) for q in queries_ordered ]
    results_df = pd.concat([b for b in blocks if not b.empty], ignore_index=True) if any(not b.empty for b in blocks) else pd.DataFrame()

    # ---- 内部保存（最新の検索結果） ----
    st.session_state["redlist_last_queries"] = queries_ordered
    st.session_state["redlist_last_results"] = results_df

    if results_df.empty:
        st.warning("一致するデータが見つかりませんでした。")
    else:
        st.success(f"検索ヒット件数: {len(results_df):,} 件（{len(queries_ordered)}語）")
        # 入力順でソート（同じ検索語内は元順のまま）
        if "検索語" in results_df.columns:
            results_df["__ord"] = results_df["検索語"].map({q:i for i,q in enumerate(queries_ordered)})
            results_df = results_df.sort_values(["__ord"]).drop(columns="__ord")
        
        # ---- 同じ検索語が連続する場合、2行目以降は空白化して見やすく ----
        if not results_df.empty and "検索語" in results_df.columns:
            mask = results_df["検索語"].shift() == results_df["検索語"]
            results_df.loc[mask, "検索語"] = ""

        st.dataframe(results_df, use_container_width=True)

        # Excel（1シート、入力順のまま）
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            results_df.to_excel(writer, sheet_name="Search_Results", index=False)

            # ついでに簡単な集計（検索語×ソース件数）を2枚目に
            if not results_df.empty and "ソース" in results_df.columns and "検索語" in results_df.columns:
                cnt = results_df.groupby(["検索語","ソース"]).size().reset_index(name="件数")
                cnt["__ord"] = cnt["検索語"].map({q:i for i,q in enumerate(queries_ordered)})
                cnt = cnt.sort_values(["__ord","ソース"]).drop(columns="__ord")
                cnt.to_excel(writer, sheet_name="Counts", index=False)

        st.download_button(
            "📥 検索結果をExcelで保存",
            data=buf.getvalue(),
            file_name="redlist_search_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
else:
    st.info("検索語を1つ以上入力してください。")



# =========================================================
# 備考
# =========================================================
with st.expander("ℹ️ 備考", expanded=False):
    st.markdown("""
- **複数語入力**：カンマ・スペース（半/全）・タブ・改行・空白行で区切れます。  
- **完全一致**（既定）/ **部分一致** をトグルで切替できます。  
- 環境省・福島は **「和名」**、千葉は **「種名」** を検索対象にしています。  
- 表示・保存の列名は **参照ラベル** で統一しています。  
- 取込・正規化ロジックは `lib/redlist/loaders.py` に依存します。  
    """)
