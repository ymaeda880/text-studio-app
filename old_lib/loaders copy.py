# -*- coding: utf-8 -*-
# lib/redlist/loaders.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

# =========================================================
# 共通ユーティリティ
# =========================================================
def _read_csv_any(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path)

def _add_meta_cols(df: pd.DataFrame, file_label: str, sheet_label: Optional[str]) -> pd.DataFrame:
    df = df.copy()
    df["ファイル名"] = file_label
    df["シート名"] = sheet_label if sheet_label is not None else ""
    return df

# =========================================================
# 環境省 (MOE)
# =========================================================
def load_moe(path: Path) -> List[pd.DataFrame]:
    dfs: List[pd.DataFrame] = []

    def moe_symbol(x: str) -> str:
    # 環境省カテゴリー列から ( ) 内の記号を抽出。CR+EN なども対応。
        if pd.isna(x) or str(x).strip() == "":
            return "未分類"
        s = str(x).strip()
        # （CR+EN）や（CR）などをすべてキャプチャ
        m = re.search(r"（([A-Z\+\-]{1,10})）", s)
        return m.group(1) if m else "未分類"


    if path.suffix.lower() in [".xlsx", ".xls"]:
        xls = pd.read_excel(path, sheet_name=None, header=0)
        for sheet, df in xls.items():
            if df is None or df.empty:
                continue
            df = df.iloc[1:].reset_index(drop=True)
            cols = list(df.columns)
            out = pd.DataFrame()
            out["カテゴリー"] = df[cols[0]] if len(cols) > 0 else ""
            out["分類群"] = df[cols[1]] if len(cols) > 1 else ""
            out["和名"] = df[cols[2]] if len(cols) > 2 else ""
            out["学名"] = df[cols[3]] if len(cols) > 3 else ""
            out["環境省カテゴリー記号"] = out["カテゴリー"].map(moe_symbol)
            dfs.append(_add_meta_cols(out, path.name, sheet))
    elif path.suffix.lower() == ".csv":
        df = _read_csv_any(path)
        if len(df) > 0:
            df = df.iloc[1:].reset_index(drop=True)
        cols = list(df.columns)
        out = pd.DataFrame()
        out["カテゴリー"] = df[cols[0]] if len(cols) > 0 else ""
        out["分類群"] = df[cols[1]] if len(cols) > 1 else ""
        out["和名"] = df[cols[2]] if len(cols) > 2 else ""
        out["学名"] = df[cols[3]] if len(cols) > 3 else ""
        out["環境省カテゴリー記号"] = out["カテゴリー"].map(moe_symbol)
        dfs.append(_add_meta_cols(out, path.name, ""))
    return dfs

# =========================================================
# 福島県 (fukushima)
#   参照ラベル: (A, 番号), (B, 生物群), (C, 分類), (D, 科名),
#               (E, 和名), (F, 学名),
#               (H, ふくしまRL2022カテゴリー), (I, 福島カテゴリー)
#   データ開始は5行目（skiprows=4）
# =========================================================
FUKUSHIMA_MAP: Dict[str, str] = {
    "絶滅": "EX",
    "野生絶滅": "EW",
    "絶滅危惧ⅠＡ類": "CR",
    "準絶滅危惧": "NT",
    "絶滅危惧Ⅱ類": "VU",
    "情報不足": "DD",
    "絶滅危惧ⅠＢ類": "EN",
    "絶滅危惧Ⅰ類": "CR+EN",
    "希少": "D",
    "未評価": "NE",
    "注意": "N",
}

def load_fukushima(path: Path) -> List[pd.DataFrame]:
    dfs: List[pd.DataFrame] = []

    def fuku_symbol(x: str) -> str:
        if pd.isna(x):
            return "変換不能"
        s = str(x).strip()
        return FUKUSHIMA_MAP.get(s, "変換不能")

    def build_out(df: pd.DataFrame) -> pd.DataFrame:
        cols = list(df.columns)
        out = pd.DataFrame()
        out["番号"]   = df[cols[0]] if len(cols) > 0 else ""
        out["生物群"] = df[cols[1]] if len(cols) > 1 else ""
        out["分類"]   = df[cols[2]] if len(cols) > 2 else ""
        out["科名"]   = df[cols[3]] if len(cols) > 3 else ""
        out["和名"]   = df[cols[4]] if len(cols) > 4 else ""
        out["学名"]   = df[cols[5]] if len(cols) > 5 else ""
        out["ふくしまRL2022カテゴリー"] = df[cols[7]] if len(cols) > 7 else ""
        out["福島カテゴリー"]           = df[cols[8]] if len(cols) > 8 else ""
        out["福島県カテゴリー記号"]     = out["福島カテゴリー"].map(fuku_symbol)
        return out

    if path.suffix.lower() in [".xlsx", ".xls"]:
        xls = pd.read_excel(path, sheet_name=None, header=0, skiprows=4)
        for sheet, df in xls.items():
            if df is None or df.empty:
                continue
            out = build_out(df)
            dfs.append(_add_meta_cols(out, path.name, sheet))

    elif path.suffix.lower() == ".csv":
        df = _read_csv_any(path)
        if len(df) > 0:
            df = df.iloc[4:].reset_index(drop=True)  # 4行スキップ相当
        out = build_out(df)
        dfs.append(_add_meta_cols(out, path.name, ""))

    return dfs


# =========================================================
# 千葉県 (chiba)
# =========================================================
CHIBA_SHEETS = ["印刷用_レッドリスト（脊椎）", "印刷用_レッドリスト（無脊椎）"]

def _chiba_symbol(x: str) -> str:
    if pd.isna(x) or str(x).strip() == "":
        return "未分類"
    s = str(x).strip()
    if s.startswith("情報不足"):
        return "DD"
    m = re.match(r"^([A-Z])\s", s)
    return m.group(1) if m else "未分類"

def load_chiba(path: Path) -> List[pd.DataFrame]:
    dfs: List[pd.DataFrame] = []
    def build_out(df: pd.DataFrame) -> pd.DataFrame:
        cols = list(df.columns)
        out = pd.DataFrame()
        out["番号"] = df[cols[0]] if len(cols) > 0 else ""
        out["分類群"] = df[cols[1]] if len(cols) > 1 else ""
        out["カテゴリー"] = df[cols[2]] if len(cols) > 2 else ""
        out["目・科名"] = df[cols[3]] if len(cols) > 3 else ""
        out["記号"] = df[cols[4]] if len(cols) > 4 else ""
        out["種名"] = df[cols[5]] if len(cols) > 5 else ""
        out["学名"] = df[cols[6]] if len(cols) > 6 else ""
        out["千葉県カテゴリー記号"] = out["カテゴリー"].map(_chiba_symbol)
        return out

    if path.suffix.lower() in [".xlsx", ".xls"]:
        xls = pd.read_excel(path, sheet_name=None, header=0, skiprows=2)
        for sheet, df in xls.items():
            if df is None or df.empty:
                continue
            if sheet not in CHIBA_SHEETS:
                continue
            out = build_out(df)
            dfs.append(_add_meta_cols(out, path.name, sheet))
    elif path.suffix.lower() == ".csv":
        df = _read_csv_any(path)
        if len(df) > 0:
            df = df.iloc[2:].reset_index(drop=True)
        out = build_out(df)
        dfs.append(_add_meta_cols(out, path.name, ""))
    return dfs

# =========================================================
# 共通読み込み関数
# =========================================================
def scan_folder(folder: Path) -> List[Path]:
    exts = (".xlsx", ".xls", ".csv")
    return [p for p in sorted(folder.glob("*")) if p.suffix.lower() in exts and p.is_file()]

def load_all(data_root: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    moe_all: List[pd.DataFrame] = []
    fuku_all: List[pd.DataFrame] = []
    chiba_all: List[pd.DataFrame] = []

    moe_dir = data_root / "MOE"
    fuku_dir = data_root / "fukushima"
    chiba_dir = data_root / "chiba"

    if moe_dir.exists():
        for p in scan_folder(moe_dir):
            moe_all.extend(load_moe(p))
    if fuku_dir.exists():
        for p in scan_folder(fuku_dir):
            fuku_all.extend(load_fukushima(p))
    if chiba_dir.exists():
        for p in scan_folder(chiba_dir):
            chiba_all.extend(load_chiba(p))

    moe_df = pd.concat(moe_all, ignore_index=True) if moe_all else pd.DataFrame()
    fuku_df = pd.concat(fuku_all, ignore_index=True) if fuku_all else pd.DataFrame()
    chiba_df = pd.concat(chiba_all, ignore_index=True) if chiba_all else pd.DataFrame()

    return moe_df, fuku_df, chiba_df
