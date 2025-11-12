# -*- coding: utf-8 -*-
# pages/60_レッドリスト_チェック.py
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd
import streamlit as st

# =========================================================
# ページ設定
# =========================================================
st.set_page_config(page_title="📚 レッドリスト参照（環境省/福島/千葉）", page_icon="📚", layout="wide")
st.title("📚 32_レッドリスト参照")
st.caption("フォルダ: data/redlist/{fukushima, MOE, prec, chiba} をスキャンし…")


# =========================================================
# データ読み込み（lib/redlist/loaders から）
# =========================================================
from lib.redlist.loaders import load_all

DATA_ROOT = Path("data/redlist").resolve()

moe_dir   = DATA_ROOT / "MOE"
fuku_dir  = DATA_ROOT / "fukushima"
chiba_dir = DATA_ROOT / "chiba"

moe_df, fuku_df, chiba_df = load_all(DATA_ROOT)

# =========================================================
# 簡易プレビュー用ヘルパ
# =========================================================
def _safe_head(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """空でないDataFrameの先頭n行を返す"""
    return df.head(n).copy() if not df.empty else df

# =========================================================
# 読み込み & プレビュー（先頭10行）
# =========================================================
with st.sidebar:
    st.subheader("📁 ソースフォルダ")
    st.code(str(DATA_ROOT))


st.subheader("👀 先頭プレビュー（各ファイル・シートの最初の10行）")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**環境省 (MOE)**")
    if moe_df.empty:
        st.info("環境省データが見つかりません。")
    else:
        st.dataframe(_safe_head(moe_df), use_container_width=True)

with col2:
    st.markdown("**福島県 (fukusiima)**")
    if fuku_df.empty:
        st.info("福島県データが見つかりません。")
    else:
        st.dataframe(_safe_head(fuku_df), use_container_width=True)

with col3:
    st.markdown("**千葉県 (chiba)**")
    if chiba_df.empty:
        st.info("千葉県データが見つかりません。")
    else:
        st.dataframe(_safe_head(chiba_df), use_container_width=True)


# =========================================================
# 📥 全データ一括ダウンロード（各ソースを個別のxlsxに分割）
# =========================================================
st.subheader("📥 全データを一括ダウンロード（ソース別 .xlsx）")

def _add_source(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.insert(0, "ソース", name)
    return out

moe_all   = _add_source(moe_df,  "環境省")
fuku_all  = _add_source(fuku_df, "福島県")
chiba_all = _add_source(chiba_df,"千葉県")

frames = [x for x in [moe_all, fuku_all, chiba_all] if not x.empty]
all_data = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()

if not frames:
    st.info("ダウンロード可能なデータがありません。")
else:
    import zipfile
    zbuf = io.BytesIO()

    with zipfile.ZipFile(zbuf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 環境省
        if not moe_all.empty:
            b1 = io.BytesIO()
            with pd.ExcelWriter(b1, engine="xlsxwriter") as w:
                moe_all.to_excel(w, sheet_name="MOE", index=False)
            zf.writestr("MOE.xlsx", b1.getvalue())

        # 福島県
        if not fuku_all.empty:
            b2 = io.BytesIO()
            with pd.ExcelWriter(b2, engine="xlsxwriter") as w:
                fuku_all.to_excel(w, sheet_name="Fukushima", index=False)
            zf.writestr("Fukushima.xlsx", b2.getvalue())

        # 千葉県
        if not chiba_all.empty:
            b3 = io.BytesIO()
            with pd.ExcelWriter(b3, engine="xlsxwriter") as w:
                chiba_all.to_excel(w, sheet_name="Chiba", index=False)
            zf.writestr("Chiba.xlsx", b3.getvalue())

        # 全件
        if not all_data.empty:
            b4 = io.BytesIO()
            with pd.ExcelWriter(b4, engine="xlsxwriter") as w:
                all_data.to_excel(w, sheet_name="All", index=False)
            zf.writestr("All.xlsx", b4.getvalue())

    st.download_button(
        "📥 すべてのxlsxをZIPで保存（MOE/Fukushima/Chiba/All）",
        data=zbuf.getvalue(),
        file_name="redlist_all_data_xlsx.zip",
        mime="application/zip",
        use_container_width=True,
    )



# =========================================================
# ファイル・シート集計（Excel + CSV）
# =========================================================
st.subheader("🧾 ファイル・シート集計（Excel + CSV）")

from typing import List  # 念のため

def paths_by_type(folder: Path):
    """フォルダ内の Excel/CSV を分類して返す。存在しない場合は空。"""
    if not folder or not folder.exists():
        return [], []
    files = [p for p in sorted(folder.glob("*")) if p.is_file()]
    excels = [p for p in files if p.suffix.lower() in (".xlsx", ".xls", ".xlsm")]
    csvs   = [p for p in files if p.suffix.lower() in (".csv",)]
    return excels, csvs

def file_sheet_stats(df: pd.DataFrame, source_name: str, folder: Path):
    """
    df: 参照ラベル化済み & 'ファイル名','シート名' を持つ DF（CSVはシート名が空）
    戻り値: (明細DF, サマリーDF)
    """
    excels, csvs = paths_by_type(folder)
    excel_cnt = len(excels)
    csv_cnt   = len(csvs)
    total_cnt = excel_cnt + csv_cnt

    if df.empty:
        detail = pd.DataFrame(columns=["ソース","ファイル名","シート名","データ数"])
        summary = pd.DataFrame([{
            "ソース": source_name,
            "Excelファイル数": excel_cnt,
            "CSVファイル数": csv_cnt,
            "合計ファイル数": total_cnt,
            "データ総数": 0,
        }])
        return detail, summary

    # ファイル・シートごとの行数
    detail = (
        df.groupby(["ファイル名","シート名"], dropna=False)
          .size()
          .reset_index(name="データ数")
          .sort_values(["ファイル名","シート名"])
    )
    detail.insert(0, "ソース", source_name)

    # サマリー
    summary = pd.DataFrame([{
        "ソース": source_name,
        "Excelファイル数": excel_cnt,
        "CSVファイル数": csv_cnt,
        "合計ファイル数": total_cnt,
        "データ総数": int(df.shape[0]),
    }])
    return detail, summary

# --- 明細・サマリーを作成 ---
detail_parts, summary_parts = [], []

d, s = file_sheet_stats(moe_df,  "環境省", moe_dir);   detail_parts.append(d); summary_parts.append(s)
d, s = file_sheet_stats(fuku_df, "福島県", fuku_dir);  detail_parts.append(d); summary_parts.append(s)
d, s = file_sheet_stats(chiba_df,"千葉県", chiba_dir); detail_parts.append(d); summary_parts.append(s)

detail_all = (
    pd.concat([x for x in detail_parts if not x.empty], ignore_index=True)
    if any([not x.empty for x in detail_parts])
    else pd.DataFrame(columns=["ソース","ファイル名","シート名","データ数"])
)

summary_all = (
    pd.concat([x for x in summary_parts if not x.empty], ignore_index=True)
    if any([not x.empty for x in summary_parts])
    else pd.DataFrame(columns=["ソース","Excelファイル数","CSVファイル数","合計ファイル数","データ総数"])
)

# --- 表示（上：サマリー、下：明細） ---
st.markdown("**📌 サマリー（フォルダ別）**")
if summary_all.empty:
    st.info("サマリーを表示できるデータがありません。")
else:
    st.dataframe(summary_all, use_container_width=True)

st.markdown("**📄 明細（ファイル・シート別の行数）**")
if detail_all.empty:
    st.info("明細を表示できるデータがありません。")
else:
    st.dataframe(detail_all, use_container_width=True)

# --- ダウンロード（Excel） ---
if not summary_all.empty or not detail_all.empty:
    _buf = io.BytesIO()
    with pd.ExcelWriter(_buf, engine="xlsxwriter") as writer:
        if not summary_all.empty:
            summary_all.to_excel(writer, sheet_name="summary_by_source", index=False)
        if not detail_all.empty:
            detail_all.to_excel(writer, sheet_name="detail_by_file_sheet", index=False)
    st.download_button(
        "📥 集計表をExcelで保存",
        data=_buf.getvalue(),
        file_name="redlist_file_sheet_summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# =========================================================
# 📊 カテゴリー記号の集計（単純形式＋ソース別 合計行＋空行）
# =========================================================
st.subheader("📊 カテゴリー記号の集計（単純形式）")

def _simple_counts_block(source: str, series: pd.Series) -> pd.DataFrame:
    """縦並びの集計に、合計行＋空行を付けて返す"""
    cols = ["ソース", "カテゴリー記号", "件数"]
    if series is None:
        return pd.DataFrame(columns=cols)

    # NaNはそのまま扱うと見づらいので一応「未分類」に寄せておく（loaders側で既に未分類化済でも安全）
    ser = series.fillna("未分類").astype(str)

    vc = ser.value_counts(dropna=False).sort_index()
    block = vc.reset_index()
    block.columns = ["カテゴリー記号", "件数"]
    block.insert(0, "ソース", source)

    # 合計行と空行を追加
    total_row = pd.DataFrame([{"ソース": source, "カテゴリー記号": "合計", "件数": int(block["件数"].sum())}])
    spacer    = pd.DataFrame([{"ソース": "",     "カテゴリー記号": "",     "件数": ""}])

    return pd.concat([block, total_row, spacer], ignore_index=True)[cols]

parts = []
if not moe_df.empty:
    parts.append(_simple_counts_block("環境省", moe_df["環境省カテゴリー記号"]))
if not fuku_df.empty:
    parts.append(_simple_counts_block("福島県", fuku_df["福島県カテゴリー記号"]))
if not chiba_df.empty:
    parts.append(_simple_counts_block("千葉県", chiba_df["千葉県カテゴリー記号"]))

if parts:
    summary_simple = pd.concat(parts, ignore_index=True)
    st.dataframe(summary_simple, use_container_width=True)

    # ダウンロード（Excel）
    _buf_simple = io.BytesIO()
    with pd.ExcelWriter(_buf_simple, engine="xlsxwriter") as writer:
        summary_simple.to_excel(writer, sheet_name="category_counts", index=False)
    st.download_button(
        "📥 集計（単純形式＋合計行つき）をExcelで保存",
        data=_buf_simple.getvalue(),
        file_name="redlist_category_counts_simple.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
else:
    st.info("集計対象データがありません。")



# =========================================================
# 🛠 デバッグ：カテゴリー記号＝未分類／変換不能（＋空欄）を抽出（詳細版）
# =========================================================
st.subheader("🛠 デバッグ：カテゴリー記号が『未分類』『変換不能』（＋空欄）のレコード")

DEBUG_TARGETS = {"未分類", "変換不能", ""}  # 空欄も拾う

def _mk_debug(
    df: pd.DataFrame,
    source: str,
    *,
    symbol_col: str,   # 記号列
    raw_col: str,      # 元カテゴリー文字列
    name_col: str,     # 和名 or 種名
    row_offset: int,   # 元Excelのデータ開始行（MOE=2, 福島=5, 千葉=3）
    extra_cols: list[str] = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    戻り値:
      (summary_df, detail_df)
        summary_df: ソース×記号ごとの件数
        detail_df : [ソース, ファイル名, シート名, 推定元Excel行, 和名/種名, 学名, 元カテゴリー, 記号, ...]
    """
    extra_cols = extra_cols or []
    need_cols = {"ファイル名","シート名",symbol_col,raw_col}
    if df.empty or not need_cols.issubset(df.columns):
        return pd.DataFrame(), pd.DataFrame()

    sym = df[symbol_col].fillna("").astype(str)
    hit = df.loc[sym.isin(DEBUG_TARGETS)].copy()
    if hit.empty:
        return pd.DataFrame(), pd.DataFrame()

    # ファイル×シート内での行番号→元Excel行（= データ開始行のオフセットを加算）
    hit["_row_in_df"] = hit.groupby(["ファイル名","シート名"]).cumcount()
    hit["推定元Excel行"] = (hit["_row_in_df"].astype(int) + row_offset).astype(int)
    hit.drop(columns=["_row_in_df"], inplace=True)

    # サマリー
    s = (hit[symbol_col].fillna("")
         .value_counts(dropna=False)
         .sort_index()
         .reset_index())
    s.columns = ["カテゴリー記号", "件数"]
    s.insert(0, "ソース", source)

    # 明細
    keep = ["ファイル名","シート名","推定元Excel行"]
    if name_col in hit.columns:
        keep += [name_col]
    if "学名" in hit.columns:
        keep += ["学名"]
    keep += [raw_col, symbol_col]
    keep += [c for c in extra_cols if c in hit.columns]

    detail = hit[keep].copy()
    # 列名を見やすく
    rename_map = {
        name_col: "和名/種名",
        raw_col: "元カテゴリー",
        symbol_col: "カテゴリー記号",
    }
    detail.rename(columns=rename_map, inplace=True)
    detail.insert(0, "ソース", source)

    # 行番号で並べ替え
    detail = detail.sort_values(["ファイル名","シート名","推定元Excel行"])
    return s, detail

with st.expander("デバッグ結果を表示（クリックで展開）", expanded=False):
    dbg_sum_parts, dbg_det_parts = [], []

    # 環境省（データ開始=2行目）
    s, d = _mk_debug(
        moe_df, "環境省",
        symbol_col="環境省カテゴリー記号",
        raw_col="カテゴリー",
        name_col="和名",
        row_offset=2,
        extra_cols=["分類群"]
    )
    if not s.empty: dbg_sum_parts.append(s); dbg_det_parts.append(d)

    # 福島県（データ開始=5行目）
    s, d = _mk_debug(
        fuku_df, "福島県",
        symbol_col="福島県カテゴリー記号",
        raw_col="福島カテゴリー",
        name_col="和名",
        row_offset=5,
        extra_cols=["生物群","分類","科名","ふくしまRL2022カテゴリー"]
    )
    if not s.empty: dbg_sum_parts.append(s); dbg_det_parts.append(d)

    # 千葉県（データ開始=3行目）
    s, d = _mk_debug(
        chiba_df, "千葉県",
        symbol_col="千葉県カテゴリー記号",
        raw_col="カテゴリー",
        name_col="種名",
        row_offset=3,
        extra_cols=["分類群","目・科名","記号"]
    )
    if not s.empty: dbg_sum_parts.append(s); dbg_det_parts.append(d)

    dbg_summary = (pd.concat(dbg_sum_parts, ignore_index=True)
                   if dbg_sum_parts else pd.DataFrame(columns=["ソース","カテゴリー記号","件数"]))
    dbg_detail  = (pd.concat(dbg_det_parts, ignore_index=True)
                   if dbg_det_parts else pd.DataFrame(columns=["ソース","ファイル名","シート名","推定元Excel行","和名/種名","学名","元カテゴリー","カテゴリー記号"]))

    st.markdown("**📌 サマリー（ソース×記号）**")
    if dbg_summary.empty:
        st.info("未分類・変換不能・空欄はありません。")
    else:
        st.dataframe(dbg_summary, use_container_width=True)

    st.markdown("**📄 明細（該当レコード）**")
    if dbg_detail.empty:
        st.info("該当明細はありません。")
    else:
        st.dataframe(dbg_detail, use_container_width=True)

    if not dbg_summary.empty or not dbg_detail.empty:
        _buf_dbg = io.BytesIO()
        with pd.ExcelWriter(_buf_dbg, engine="xlsxwriter") as writer:
            if not dbg_summary.empty:
                dbg_summary.to_excel(writer, sheet_name="debug_summary", index=False)
            if not dbg_detail.empty:
                dbg_detail.to_excel(writer, sheet_name="debug_detail", index=False)
        st.download_button(
            "📥 デバッグ抽出をExcelで保存",
            data=_buf_dbg.getvalue(),
            file_name="redlist_debug_unclassified_unmappable.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )



# =========================================================
# 検索：「和名」（千葉は「種名」）
# =========================================================
st.subheader("🔎 和名/種名 検索")
query = st.text_input("和名（環境省/福島）または 種名（千葉） を入力してください", value="")

def normalize_name(s: str) -> str:
    if pd.isna(s):
        return ""
    # 前後空白と全角空白を共通処理
    s = str(s).replace("\u3000", " ").strip()
    return s

if query:
    q = normalize_name(query)

    results: List[pd.DataFrame] = []

    if not moe_df.empty:
        hit = moe_df[normalize_name(moe_df["和名"]) == q].copy()
        if not hit.empty:
            hit.insert(0, "ソース", "環境省")
            # 表示列（参照ラベル順）
            cols = ["ソース","ファイル名","シート名","和名","学名","分類群","カテゴリー","環境省カテゴリー記号"]
            for c in cols:
                if c not in hit.columns:
                    hit[c] = ""
            results.append(hit[cols])

    if not fuku_df.empty:
        hit = fuku_df[normalize_name(fuku_df["和名"]) == q].copy()
        if not hit.empty:
            hit.insert(0, "ソース", "福島県")
            cols = ["ソース","ファイル名","シート名","和名","学名","生物群","分類","科名","福島カテゴリー","ふくしまRL2022カテゴリー","福島県カテゴリー記号"]
            for c in cols:
                if c not in hit.columns:
                    hit[c] = ""
            results.append(hit[cols])

    if not chiba_df.empty:
        hit = chiba_df[normalize_name(chiba_df["種名"]) == q].copy()
        if not hit.empty:
            hit.insert(0, "ソース", "千葉県")
            cols = ["ソース","ファイル名","シート名","種名","学名","分類群","目・科名","カテゴリー","記号","千葉県カテゴリー記号"]
            for c in cols:
                if c not in hit.columns:
                    hit[c] = ""
            results.append(hit[cols])

    if results:
        res_df = pd.concat(results, ignore_index=True)
        st.dataframe(res_df, use_container_width=True)

        # ダウンロード（xlsx）
        buf2 = io.BytesIO()
        with pd.ExcelWriter(buf2, engine="xlsxwriter") as writer:
            res_df.to_excel(writer, sheet_name="search_results", index=False)
        st.download_button(
            "📥 検索結果をExcelで保存",
            data=buf2.getvalue(),
            file_name=f"redlist_search_{q}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        st.warning("一致するデータが見つかりませんでした。")

# =========================================================
# 備考
# =========================================================
with st.expander("ℹ️ 備考（参照ラベルと短縮形の扱い）", expanded=False):
    st.markdown("""
- 表示・保存の列名は **参照ラベル**（例：*カテゴリー, 分類群, 和名, 学名, ファイル名, シート名*）で統一しています。  
- 指示がある場合に限り、短縮形（A, B, C, D など）を使いますが、本ページの出力は明確さのため参照ラベルを既定としています。  
- フォルダ名 **fukusiima** はご指定どおり（typo含む）で認識しています。  
- 千葉県「情報不足」は一貫性のため **DD** に正規化しています。  
- 福島県のカテゴリー変換はご指定のテーブルに厳密準拠し、該当しない値は **「変換不能」** としています。  
    """)

