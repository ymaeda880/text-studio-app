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
from lib.redlist.loaders import load_all, get_column_templates

DATA_ROOT = Path("data/redlist").resolve()
moe_df, fuku_df, chiba_df = load_all(DATA_ROOT)

# --- 各ソースのカラムテンプレートを取得
COL_TEMPLATES = get_column_templates()

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
# ヘルパー
# =========================================================
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
    raw = raw.replace("\u3000", " ")
    parts = re.split(r"[,\s]+", raw)
    parts = [normalize_name(p) for p in parts if p and normalize_name(p)]
    seen = set()
    uniq: List[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq

def mask_for_queries(series: pd.Series, qs: Iterable[str], exact: bool) -> pd.Series:
    """
    series を正規化した上で、複数クエリの OR マッチを返す。
    exact=True: 完全一致（== の OR）、False: 部分一致（contains の OR、大小無視）
    """
    s_norm = series.fillna("").map(normalize_name)
    if exact:
        return s_norm.isin(list(qs))
    s_low = s_norm.str.lower()
    mask = pd.Series(False, index=series.index)
    for q in qs:
        if not q:
            continue
        ql = q.lower()
        mask = mask | s_low.str.contains(re.escape(ql), na=False)
    return mask

# =========================================================
# 入力（フォーム：検索ボタンで実行）
# =========================================================
st.subheader("🧭 和名/種名 検索（複数語対応）")

with st.form("search_form"):
    col_q1, col_q2 = st.columns([3, 1])
    with col_q1:
        multi_query_raw = st.text_area(
            "和名（環境省/福島）・種名（千葉）を改行/カンマ/スペース/タブで複数入力できます",
            value="",
            height=120,
            placeholder="例）\nニホンザル\nヤマネ, トキ\n  ヤンバルクイナ"
        )
    with col_q2:
        mode_exact = st.toggle("完全一致", value=True, help="OFFにすると部分一致（包含）で検索します。", key="mode_exact")
    do_search = st.form_submit_button("🔎 検索を実行")

# ボタンが押された時だけクエリを確定
queries = parse_queries(multi_query_raw) if do_search else []
if do_search and queries:
    st.caption(f"🔎 検索語：{', '.join(queries)}（{len(queries)} 語）")

# =========================================================
# 各ソースのヒット収集
# =========================================================
results: List[pd.DataFrame] = []
if do_search and queries:
    with st.spinner("🔍 検索中です…"):
        # 環境省：和名
        if moe_df is not None and not moe_df.empty and "和名" in moe_df.columns:
            mask = mask_for_queries(moe_df["和名"], queries, mode_exact)
            hit = moe_df.loc[mask].copy()
            if not hit.empty:
                hit.insert(0, "ソース", "環境省")
                cols = COL_TEMPLATES["moe"]
                for c in cols:
                    if c not in hit.columns: hit[c] = ""
                results.append(hit[cols])

        # 福島県：和名
        if fuku_df is not None and not fuku_df.empty and "和名" in fuku_df.columns:
            mask = mask_for_queries(fuku_df["和名"], queries, mode_exact)
            hit = fuku_df.loc[mask].copy()
            if not hit.empty:
                hit.insert(0, "ソース", "福島県")
                cols = COL_TEMPLATES["fukushima"]
                for c in cols:
                    if c not in hit.columns: hit[c] = ""
                results.append(hit[cols])

        # 千葉県：種名
        if chiba_df is not None and not chiba_df.empty and "種名" in chiba_df.columns:
            mask = mask_for_queries(chiba_df["種名"], queries, mode_exact)
            hit = chiba_df.loc[mask].copy()
            if not hit.empty:
                hit.insert(0, "ソース", "千葉県")
                cols = COL_TEMPLATES["chiba"]
                for c in cols:
                    if c not in hit.columns: hit[c] = ""
                results.append(hit[cols])
# =========================================================
# 結果表示 & ダウンロード（内部保存＋検索語の入力順で整列）
#   ※ 検索語列は使用せず、「和名/種名」を統一した“和名”を先頭に表示
# =========================================================
if do_search and queries:
    def _norm(s: pd.Series) -> pd.Series:
        return s.fillna("").astype(str).str.replace("\u3000", " ").str.strip()

    # 入力順の維持（重複は最初のみ採用）
    queries_ordered: list[str] = []
    seen = set()
    for q in queries:
        qn = q.replace("\u3000", " ").strip()
        if qn and qn not in seen:
            queries_ordered.append(qn); seen.add(qn)

    # ---- ユーティリティ（列ゆれ・テンプレ補完） ----
    def first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    def ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        h = df.copy()
        for c in cols:
            if c not in h.columns:
                h[c] = ""
        return h[cols]

    # ---- 共通処理：ソースごとのヒット抽出（検索語列は作らない） ----
    def _hits_for_source(df: pd.DataFrame | None,
                         source_label: str,
                         name_candidates: list[str],
                         cols_template_key: str,
                         q: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        name_col = first_existing_col(df, name_candidates)
        if name_col is None:
            return pd.DataFrame()

        m = _norm(df[name_col]) == q
        h = df.loc[m].copy()
        if h.empty:
            return pd.DataFrame()

        # ソース列を追加（先頭側に付ける）
        h.insert(0, "ソース", source_label)

        # テンプレ列を満たして並べ替え（テンプレ外の列はこの時点で落ちる）
        cols = COL_TEMPLATES[cols_template_key]
        h = ensure_cols(h, cols)
        return h

    def _hits_for_query(q: str) -> pd.DataFrame:
        parts = []
        # 環境省：和名優先（将来のゆれ対応で候補に“種名”も入れる）
        parts.append(_hits_for_source(
            moe_df, "環境省", ["和名", "種名"], "moe", q
        ))
        # 福島県：和名優先
        parts.append(_hits_for_source(
            fuku_df, "福島県", ["和名", "種名"], "fukushima", q
        ))
        # 千葉県：種名優先（元データが種名中心）
        parts.append(_hits_for_source(
            chiba_df, "千葉県", ["種名", "和名"], "chiba", q
        ))
        parts = [p for p in parts if p is not None and not p.empty]
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    with st.spinner("📚 検索結果を整形中…"):
        blocks = [_hits_for_query(q) for q in queries_ordered]
        results_df = pd.concat([b for b in blocks if not b.empty], ignore_index=True) \
                      if any(not b.empty for b in blocks) else pd.DataFrame()

        # 保存（内部）
        st.session_state["redlist_last_queries"] = queries_ordered
        st.session_state["redlist_last_results"] = results_df

    if results_df.empty:
        st.warning("一致するデータが見つかりませんでした。")
    else:
        st.success(f"検索ヒット件数: {len(results_df):,} 件（{len(queries_ordered)}語）")

        # ========= 列の統一と並べ替え =========
        # 1) 「和名/種名」を“和名”に統一
        name_candidates = ["和名", "種名"]
        exist_names = [c for c in name_candidates if c in results_df.columns]
        if exist_names:
            results_df["和名"] = results_df[exist_names].bfill(axis=1).iloc[:, 0]
        else:
            results_df["和名"] = ""

        # 2) カテゴリー記号を統合（環境省/福島/千葉/記号のどれか）
        symbol_candidates = ["環境省カテゴリー記号", "福島県カテゴリー記号", "千葉県カテゴリー記号", "記号"]
        exist_symbols = [c for c in symbol_candidates if c in results_df.columns]
        if exist_symbols:
            results_df["カテゴリー記号"] = results_df[exist_symbols].bfill(axis=1).iloc[:, 0]
        else:
            results_df["カテゴリー記号"] = ""

        # 3) 入力語の順（queries_ordered）で整列
        #    和名を正規化して order_map によるキーで並べ、安定ソート
        order_map = {q: i for i, q in enumerate(queries_ordered)}
        results_df["__name_norm"] = _norm(results_df["和名"])
        results_df["__ord"] = results_df["__name_norm"].map(order_map)
        # "__ord" が NaN（＝入力していない和名）の行がもしあれば後ろへ
        # ※ ヒットはすべて一致検索なので通常は NaN は出ませんが安全策
        results_df["__ord"] = results_df["__ord"].fillna(len(queries_ordered) + 1)
        results_df = results_df.sort_values(["__ord"], kind="stable").drop(columns=["__ord", "__name_norm"])

        # 4) 同じ“和名”の2行目以降を空白化（視認性向上）
        dup_mask = results_df["和名"].duplicated(keep="first")
        results_df.loc[dup_mask, "和名"] = ""

        # 5) 列順を再構成：和名 → ソース → カテゴリー記号 → その他
        first_cols = [c for c in ["和名", "ソース", "カテゴリー記号"] if c in results_df.columns]
        other_cols = [c for c in results_df.columns if c not in first_cols]
        results_df = results_df[first_cols + other_cols]

        # ========= 表示 =========
        st.dataframe(results_df, use_container_width=True)

        # ========= Excel（1シート＋Countsシート） =========
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            # メインシート（現在の列順のまま）
            results_df.to_excel(writer, sheet_name="Search_Results", index=False)

            # 集計シート（和名 × ソース）
            if not results_df.empty and {"ソース","和名"}.issubset(results_df.columns):
                cnt = results_df.copy()
                # 空白化された和名は前の値で埋めてから集計
                cnt["和名"] = cnt["和名"].replace("", pd.NA).fillna(method="ffill")
                cnt = cnt.groupby(["和名","ソース"]).size().reset_index(name="件数")

                # queries_ordered の順に並べ替え（和名を正規化して order_map）
                cnt["__name_norm"] = cnt["和名"].astype(str).str.replace("\u3000", " ").str.strip()
                cnt["__ord"] = cnt["__name_norm"].map(order_map).fillna(len(queries_ordered) + 1)
                cnt = cnt.sort_values(["__ord","ソース"]).drop(columns=["__ord","__name_norm"])

                cnt.to_excel(writer, sheet_name="Counts", index=False)

        st.download_button(
            "📥 検索結果をExcelで保存",
            data=buf.getvalue(),
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
- **複数語入力**：カンマ・スペース（半/全）・タブ・改行・空白行で区切れます。  
- **完全一致**（既定）/ **部分一致** をトグルで切替できます。  
- 環境省・福島は **「和名」**、千葉は **「種名」** を検索対象にしています。  
- 表示・保存の列名は **参照ラベル** で統一しています。  
- 取り込み・正規化ロジックは `lib/redlist/loaders.py` に依存します。  
    """)
