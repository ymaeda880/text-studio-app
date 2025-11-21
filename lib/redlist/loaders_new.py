# -*- coding: utf-8 -*-
# lib/redlist/loaders_new.py
#
# loaders.py を整理した代替版
#

from __future__ import annotations

import re
import unicodedata
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

def _add_line_numbers(df: pd.DataFrame, header_offset: int = 1) -> pd.DataFrame:
    """
    元ファイル内の行番号を付加する。
    header_offset: 見出し行の分だけオフセットする（通常は1で「2行目」から開始）
    """
    df = df.copy()
    df["行番号"] = (df.index + 1 + header_offset).astype(int)
    return df

# =========================================================
# 環境省 (MOE)
# =========================================================
from __future__ import annotations
from pathlib import Path
from typing import List
import re
import pandas as pd

def load_moe(path: Path) -> List[pd.DataFrame]:
    dfs: List[pd.DataFrame] = []

    def moe_symbol(x: str) -> str:
        # 環境省カテゴリー列から ( ) 内の記号を抽出。CR+EN なども対応。
        if pd.isna(x) or str(x).strip() == "":
            return "未分類"
        s = str(x).strip()
        m = re.search(r"（([A-Z\+\-]{1,10})）", s)
        return m.group(1) if m else "未分類"

    if path.suffix.lower() == ".csv":
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
        out = _add_line_numbers(out, header_offset=1)
        dfs.append(_add_meta_cols(out, path.name, ""))

    return dfs

# =========================================================
# 福島県 (fukushima)
# =========================================================
FUKUSHIMA_MAP: Dict[str, str] = {
    "絶滅": "EX", "野生絶滅": "EW", "絶滅危惧ⅠＡ類": "CR",
    "準絶滅危惧": "NT", "絶滅危惧Ⅱ類": "VU", "情報不足": "DD",
    "絶滅危惧ⅠＢ類": "EN", "絶滅危惧Ⅰ類": "CR+EN",
    "希少": "D", "未評価": "NE", "注意": "N",
    "絶滅のおそれのある地域個体群": "LP",
}

def load_fukushima(path: Path) -> List[pd.DataFrame]:
    dfs: List[pd.DataFrame] = []

    def fuku_symbol(x: str) -> str:
        if pd.isna(x) or str(x).strip() == "":
            return "未分類"
        return FUKUSHIMA_MAP.get(str(x).strip(), "変換不能")

    def build_out(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
        cols = list(df.columns)
        def col(i: int) -> pd.Series:
            return df[cols[i]] if i < len(cols) else pd.Series([""] * len(df), index=df.index)

        sname = (sheet or "").strip()
        out = pd.DataFrame()

        if sname in ("鳥類", "菌類"):
            out["番号"]   = col(0)
            out["生物群"] = col(1)
            out["分類"]   = ""
            out["科名"]   = col(2)
            out["和名"]   = col(3)
            out["学名"]   = col(4)
            out["ふくしまRL2024カテゴリー"] = col(6)
            out["福島カテゴリー"]           = col(7)
        elif sname == "海岸動物":
            out["番号"]   = col(0)
            out["生物群"] = ""
            out["分類"]   = ""
            out["目名"]   = col(1)
            out["科名"]   = col(2)
            out["和名"]   = col(3)
            out["学名"]   = col(4)
            out["ふくしまRL2024カテゴリー"] = col(6)
            out["福島カテゴリー"]           = col(7)
        else:
            out["番号"]   = col(0)
            out["生物群"] = col(1)
            out["分類"]   = col(2)
            out["科名"]   = col(3)
            out["和名"]   = col(4)
            out["学名"]   = col(5)
            out["ふくしまRL2024カテゴリー"] = col(7)
            out["福島カテゴリー"]           = col(8)

        out["福島県カテゴリー記号"] = out["福島カテゴリー"].map(fuku_symbol)
        out = _add_line_numbers(out, header_offset=4)
        return out

    if path.suffix.lower() in [".xlsx", ".xls"]:
        sheets = pd.read_excel(path, sheet_name=None, header=None)
        for sheet, df in sheets.items():
            if df is None or df.empty:
                continue
            df = df.iloc[4:].reset_index(drop=True)
            out = build_out(df, sheet)
            if "番号" in out.columns:
                out = out[pd.to_numeric(out["番号"], errors="coerce").notna()].copy()
                out["番号"] = out["番号"].astype(int)
            dfs.append(_add_meta_cols(out, file_label=path.name, sheet_label=sheet))
    elif path.suffix.lower() == ".csv":
        df = _read_csv_any(path)
        if len(df) > 0:
            df = df.iloc[4:].reset_index(drop=True)
        out = build_out(df, sheet="")
        if "番号" in out.columns:
            out = out[pd.to_numeric(out["番号"], errors="coerce").notna()].copy()
            out["番号"] = out["番号"].astype(int)
        dfs.append(_add_meta_cols(out, file_label=path.name, sheet_label=""))
    return dfs

# =========================================================
# 千葉県 (chiba)
# =========================================================
CHIBA_SHEETS = ["印刷用_レッドリスト（脊椎）", "印刷用_レッドリスト（無脊椎）"]

def load_chiba(path: Path) -> List[pd.DataFrame]:
    dfs: List[pd.DataFrame] = []

    def build_out_old(df: pd.DataFrame) -> pd.DataFrame:
        # 2019系（印刷用_…）：先頭2行が見出し
        df = df.iloc[2:].reset_index(drop=True)
        cols = list(df.columns)
        def col(i: int) -> pd.Series:
            return df[cols[i]] if i < len(cols) else pd.Series([""] * len(df), index=df.index)

        out = pd.DataFrame()
        out["番号"]   = col(0)
        out["分類群"] = col(1)
        out["カテゴリー"] = col(2)
        out["目・科名"] = col(3)
        out["記号"]   = col(4)
        out["種名"]   = col(5)
        out["学名"]   = col(6)

        # 2019は「カテゴリー」から記号抽出（互換のため維持）
        def _chiba_symbol(x: str) -> str:
            if pd.isna(x) or str(x).strip() == "":
                return "未分類"
            s = unicodedata.normalize("NFKC", str(x).strip())
            if s.startswith("情報不足"):
                return "DD"
            m = re.match(r"^([A-Z]{1,3})", s)
            return m.group(1) if m else "未分類"

        out["千葉県カテゴリー記号"] = out["カテゴリー"].map(_chiba_symbol)
        out = _add_line_numbers(out, header_offset=2)
        return out

    def build_out_2023(df: pd.DataFrame) -> pd.DataFrame:
        # 2023 植物・菌類編（Sheet1）：先頭1行が見出し
        df = df.iloc[1:].reset_index(drop=True)
        cols = list(df.columns)
        def col(i: int) -> pd.Series:
            return df[cols[i]] if i < len(cols) else pd.Series([""] * len(df), index=df.index)

        out = pd.DataFrame()
        # 位置指定：A,B,C,D,G → 0,1,2,3,6
        out["分類群"] = col(0)
        out["種名"]   = col(1)
        # 新ファイルの「科名等」は統一名「目・科名」に格納
        out["目・科名"] = col(2)
        out["学名"]   = col(3)
        # 記号は変換不要、そのまま採用
        out["千葉県カテゴリー記号"] = col(6)

        # 2019互換のため存在しない列は空で用意
        out["番号"] = ""
        out["カテゴリー"] = ""
        out["記号"] = ""

        out = _add_line_numbers(out, header_offset=1)
        return out

    if path.suffix.lower() in [".xlsx", ".xls"]:
        sheets = pd.read_excel(path, sheet_name=None, header=None)
        for sheet, df in sheets.items():
            if df is None or df.empty:
                continue
            if sheet in CHIBA_SHEETS:
                out = build_out_old(df)
            elif sheet == "Sheet1" and "千葉県RD2023植物・菌類編リスト_20230725版.xlsx" in path.name:
                out = build_out_2023(df)
            else:
                # 想定外シートはスキップ
                continue
            dfs.append(_add_meta_cols(out, path.name, sheet))

    elif path.suffix.lower() == ".csv":
        # CSVは稀だが、2019互換の位置取りで処理（必要なら分岐拡張）
        df = _read_csv_any(path)
        if len(df) > 0:
            df = df  # CSVに見出し行が含まれる前提不明のため、そのままパス
        out = build_out_old(df)
        dfs.append(_add_meta_cols(out, path.name, ""))

    return dfs


# =========================================================
# 標準列構成（ビュー側から参照される）
# =========================================================
def get_column_templates() -> dict[str, list[str]]:
    cols_moe = [
        "ソース", "和名", "環境省カテゴリー記号", "ファイル名", "シート名", "行番号",
        "学名", "分類群", "カテゴリー"
    ]
    cols_fuku = [
        "ソース", "和名", "福島県カテゴリー記号", "ファイル名", "シート名", "行番号",
        "学名", "生物群", "分類", "科名",
        "福島カテゴリー", "ふくしまRL2024カテゴリー"
    ]
    cols_chiba = [
        "ソース", "種名", "千葉県カテゴリー記号", "ファイル名", "シート名", "行番号",
        "学名", "分類群", "目・科名",
        "カテゴリー", "記号"
    ]
    return {
        "moe": cols_moe,
        "fukushima": cols_fuku,
        "chiba": cols_chiba,
    }

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
