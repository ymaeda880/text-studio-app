# -*- coding: utf-8 -*-
# pages/45_レッドリスト_プレビュー.py
# _app/redlist/{fukusiima, MOE, prec, chiba} にある CSV / Excel をスキャンして先頭N行を表示

from __future__ import annotations
import io
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import streamlit as st
import pandas as pd

st.set_page_config(page_title="📚 レッドリスト（CSV/Excel）プレビュー", page_icon="📚", layout="wide")
st.title("📚 レッドリスト（CSV / Excel）プレビュー")
st.caption("_app/redlist 以下のフォルダをスキャンし、各ファイルの先頭行をプレビューします。")

# ─────────────────────────────────────────────
# 設定（サイドバー）
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### オプション")
    # pages/ ディレクトリ直下にアプリがある前提：pages/ の1つ上がアプリルート
    app_root_default = Path(__file__).resolve().parents[1]
    base_dir_str = st.text_input("ベースディレクトリ", value=str(app_root_default / "data" / "redlist"))
    n_rows = st.number_input("表示行数（先頭）", min_value=5, max_value=100, value=10, step=5)
    show_sheet_all = st.checkbox("Excelは全シートを表示（既定は先頭シートのみ）", value=False)
    st.markdown("---")
    st.caption("フォルダ名 → 表示名の対応")
    st.write({
        "fukushima": "福島県",
        "MOE": "環境省",
        "prec": "プレック",
        "chiba": "千葉県",
    })

# ─────────────────────────────────────────────
# 対象フォルダ
# ─────────────────────────────────────────────
FOLDERS = [
    ("fukushima", "福島県"),
    ("MOE",       "環境省"),
    ("prec",      "プレック"),
    ("chiba",     "千葉県"),
]

# ─────────────────────────────────────────────
# 読み込みユーティリティ
# ─────────────────────────────────────────────
CSV_EXTS  = {".csv"}
XLSX_EXTS = {".xlsx", ".xls"}

def _read_csv_head(path: Path, n: int) -> Optional[pd.DataFrame]:
    """CSVを先頭n行だけ読み込む（エンコーディング自動フォールバック）。"""
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return pd.read_csv(path, nrows=n, encoding=enc)
        except Exception:
            continue
    try:
        # 最後の手段：errors='ignore'
        return pd.read_csv(path, nrows=n, encoding="utf-8", errors="ignore")
    except Exception as e:
        st.warning(f"CSV読み込み失敗: {path.name} ({e})")
        return None

def _read_excel_heads(path: Path, n: int, all_sheets: bool) -> List[Tuple[str, pd.DataFrame]]:
    """
    Excelを先頭n行読み込む。
    戻り値: [(sheet_name, df_head), ...]
    """
    out: List[Tuple[str, pd.DataFrame]] = []
    try:
        xls = pd.ExcelFile(path)
        sheets = xls.sheet_names
        targets = sheets if all_sheets else sheets[:1]
        for s in targets:
            try:
                df = pd.read_excel(path, sheet_name=s, nrows=n)
                out.append((s, df))
            except Exception as e:
                st.warning(f"Excelシート読み込み失敗: {path.name} [{s}] ({e})")
    except Exception as e:
        st.warning(f"Excel読み込み失敗: {path.name} ({e})")
    return out

# ─────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────
base_dir = Path(base_dir_str).expanduser().resolve()
if not base_dir.exists():
    st.error(f"ベースディレクトリが見つかりません: {base_dir}")
    st.stop()

for folder, label in FOLDERS:
    target_dir = base_dir / folder
    st.header(f"📁 {label} — {folder}")
    st.caption(str(target_dir))

    if not target_dir.exists():
        st.warning(f"フォルダがありません: {target_dir}")
        continue

    # ファイル列挙
    files = sorted([p for p in target_dir.iterdir() if p.is_file() and p.suffix.lower() in (CSV_EXTS | XLSX_EXTS)],
                   key=lambda p: p.name)
    if not files:
        st.info("プレビュー対象（CSV/Excel）が見つかりません。")
        continue

    for f in files:
        ext = f.suffix.lower()
        st.markdown(f"#### 📄 {f.name}")

        if ext in CSV_EXTS:
            df = _read_csv_head(f, n_rows)
            if df is not None:
                st.dataframe(df, use_container_width=True)
            else:
                st.error("読み込みに失敗しました。")
        elif ext in XLSX_EXTS:
            heads = _read_excel_heads(f, n_rows, show_sheet_all)
            if not heads:
                st.error("読み込みに失敗しました。")
            else:
                for sheet_name, df in heads:
                    st.markdown(f"- **Sheet:** `{sheet_name}`")
                    st.dataframe(df, use_container_width=True)

        st.divider()


# ─────────────────────────────────────────────
# （照合処理）prec 種名 ×（環境省 和名／福島県 和名）
#   出力列：prec種名, prec環境省レッド, prec県レッド, 環境省カテゴリー, 福島県カテゴリー
# ─────────────────────────────────────────────

st.header("🔎 照合（prec×環境省×福島県）")

# 便利：列名のゆらぎを吸収して欲しい列を取り出すヘルパ
def pick_cols(df: pd.DataFrame, wanted: Dict[str, List[str]]) -> pd.DataFrame:
    """
    wanted = {"dst_col": ["候補1", "候補2", ...], ...}
    """
    cols = {}
    # 正規化（全角空白→半角、前後空白除去）
    def _norm(s: str) -> str:
        return (str(s).replace("\u3000", " ").strip()).lower()

    norm_map = {_norm(c): c for c in df.columns}
    for dst, cands in wanted.items():
        found = None
        for c in cands:
            key = _norm(c)
            if key in norm_map:
                found = norm_map[key]
                break
        if found:
            cols[dst] = df[found]
        else:
            cols[dst] = pd.Series([None] * len(df))
            st.info(f"列が見つかりませんでした: 期待列 '{cands[0]}'（他候補: {cands[1:]}）")
    return pd.DataFrame(cols)

def _read_csv_any(path: Path) -> Optional[pd.DataFrame]:
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    try:
        return pd.read_csv(path, encoding="utf-8", errors="ignore")
    except Exception as e:
        st.warning(f"CSV読み込み失敗: {path.name} ({e})")
        return None

def _read_excel_all(path: Path) -> List[pd.DataFrame]:
    out: List[pd.DataFrame] = []
    try:
        xls = pd.ExcelFile(path)
        for s in xls.sheet_names:
            try:
                out.append(pd.read_excel(path, sheet_name=s))
            except Exception as e:
                st.warning(f"Excelシート読み込み失敗: {path.name} [{s}] ({e})")
    except Exception as e:
        st.warning(f"Excel読み込み失敗: {path.name} ({e})")
    return out

def _norm_name(s: Optional[str]) -> str:
    # 名前照合用の軽い正規化：全角空白→半角、全角英数→半角、余白削除
    if s is None:
        return ""
    t = str(s).replace("\u3000", " ").strip()
    # 一部の全角→半角（英数のみ）
    z = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９"
    h = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    t = t.translate(str.maketrans(z, h))
    return t

# ① prec（Excel）→ 「種名」「環境省レッド」「県レッド」
prec_dir = base_dir / "prec"
prec_frames: List[pd.DataFrame] = []
if prec_dir.exists():
    for p in sorted(prec_dir.iterdir()):
        if p.suffix.lower() in {".xlsx", ".xls"} and p.is_file():
            for df in _read_excel_all(p):
                sub = pick_cols(
                    df,
                    {
                        "prec種名": ["種名"],
                        "prec環境省レッド": ["環境省レッド"],
                        "prec県レッド": ["県レッド"],
                    },
                )
                prec_frames.append(sub)
else:
    st.warning(f"prec フォルダが見つかりません: {prec_dir}")

prec_df = pd.concat(prec_frames, ignore_index=True) if prec_frames else pd.DataFrame(columns=["prec種名","prec環境省レッド","prec県レッド"])
# 元の順序を保つための通し番号
prec_df["_ord"] = range(len(prec_df))

# ② 環境省（CSV）→ 「カテゴリー」「和名」
moe_dir = base_dir / "MOE"
moe_frames: List[pd.DataFrame] = []
if moe_dir.exists():
    for p in sorted(moe_dir.iterdir()):
        if p.suffix.lower() == ".csv" and p.is_file():
            df = _read_csv_any(p)
            if df is not None:
                sub = pick_cols(df, {"環境省カテゴリー": ["カテゴリー"], "環境省和名": ["和名"]})
                moe_frames.append(sub)
else:
    st.warning(f"MOE フォルダが見つかりません: {moe_dir}")

moe_df = pd.concat(moe_frames, ignore_index=True) if moe_frames else pd.DataFrame(columns=["環境省カテゴリー","環境省和名"])

# ③ 福島県（Excel）→ 「和名」「ふくしまRL2024カテゴリー」
fuku_dir = base_dir / "fukushima"
fuku_frames: List[pd.DataFrame] = []
if fuku_dir.exists():
    for p in sorted(fuku_dir.iterdir()):
        if p.suffix.lower() in {".xlsx", ".xls"} and p.is_file():
            for df in _read_excel_all(p):
                sub = pick_cols(
                    df,
                    {
                        "福島県和名": ["和名"],
                        "福島県カテゴリー": ["ふくしまRL2024カテゴリー", "福島RL2024カテゴリー", "RL2024カテゴリー"],
                    },
                )
                fuku_frames.append(sub)
else:
    st.warning(f"fukushima フォルダが見つかりません: {fuku_dir}")

fuku_df = pd.concat(fuku_frames, ignore_index=True) if fuku_frames else pd.DataFrame(columns=["福島県和名","福島県カテゴリー"])

# 参照用辞書（キー = 正規化した和名）
moe_map = { _norm_name(r["環境省和名"]): r["環境省カテゴリー"] for _, r in moe_df.dropna(subset=["環境省和名"]).iterrows() }
fuku_map = { _norm_name(r["福島県和名"]): r["福島県カテゴリー"] for _, r in fuku_df.dropna(subset=["福島県和名"]).iterrows() }

# 走査：prec種名 を上から順に見て、一致があれば出力
rows: List[Dict[str, Optional[str]]] = []
for _, r in prec_df.iterrows():
    name = r.get("prec種名")
    key  = _norm_name(name)
    moe_cat  = moe_map.get(key)
    fuku_cat = fuku_map.get(key)
    if (moe_cat is not None) or (fuku_cat is not None):
        rows.append(
            {
                "prec種名": name,
                "prec環境省レッド": r.get("prec環境省レッド"),
                "prec県レッド": r.get("prec県レッド"),
                "環境省カテゴリー": moe_cat,
                "福島県カテゴリー": fuku_cat,
                "_ord": r.get("_ord", 0),
            }
        )

result_df = pd.DataFrame(rows).sort_values("_ord").drop(columns=["_ord"], errors="ignore")
st.subheader("✅ 照合結果（一致したもの）")
if result_df.empty:
    st.info("一致するレコードが見つかりませんでした。列名のゆらぎや表記ゆれ（全角/半角・スペース）をご確認ください。")
else:
    st.dataframe(result_df, use_container_width=True)

    # ダウンロード
    buf = io.StringIO()
    result_df.to_csv(buf, index=False)
    st.download_button(
        "📥 照合結果をCSVで保存",
        data=buf.getvalue().encode("utf-8-sig"),
        file_name="redlist_match_result.csv",
        mime="text/csv",
        use_container_width=True,
    )

# 参考：件数サマリ
st.caption(
    f"prec入力: {len(prec_df)} 件 / 環境省: {len(moe_df)} 件 / 福島県: {len(fuku_df)} 件 / 一致: {len(result_df)} 件"
)
