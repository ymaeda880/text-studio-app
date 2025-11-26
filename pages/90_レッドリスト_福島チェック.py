# -*- coding: utf-8 -*-
# pages/90_レッドリスト_福島チェック.py
# _app/redlist/{fukushima, MOE, prec, chiba} にある CSV / Excel をスキャンして先頭N行を表示
# さらに prec ×（環境省 和名／福島県 和名）で照合し、元ファイル名・シート名・行番号も併記

from __future__ import annotations
import io
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import streamlit as st
import pandas as pd
import re  # ← 追加


# ─────────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="📚 レッドリスト（CSV/Excel）プレビュー", page_icon="📚", layout="wide")
st.title("📚 レッドリスト（CSV / Excel）プレビュー")
st.caption("_app/redlist 以下のフォルダをスキャンし、各ファイルの先頭行をプレビューします。")

# ─────────────────────────────────────────────
# 設定（サイドバー）
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### オプション")
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

CSV_EXTS  = {".csv"}
XLSX_EXTS = {".xlsx", ".xls"}

# ─────────────────────────────────────────────
# CSV / Excel 読み込みユーティリティ
# ─────────────────────────────────────────────
def _read_csv_head(path: Path, n: int) -> Optional[pd.DataFrame]:
    """CSVを先頭n行だけ読み込む（エンコーディング自動フォールバック）"""
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return pd.read_csv(path, nrows=n, encoding=enc)
        except Exception:
            continue
    try:
        return pd.read_csv(path, nrows=n, encoding="utf-8", errors="ignore")
    except Exception as e:
        st.warning(f"CSV読み込み失敗: {path.name} ({e})")
        return None


def _read_excel_heads(path: Path, n: int, all_sheets: bool) -> List[Tuple[str, pd.DataFrame]]:
    """Excelを先頭n行読み込む（一般用）"""
    out: List[Tuple[str, pd.DataFrame]] = []
    try:
        xls = pd.ExcelFile(path)
        targets = xls.sheet_names if all_sheets else xls.sheet_names[:1]
        for s in targets:
            try:
                df = pd.read_excel(path, sheet_name=s, nrows=n)
                out.append((s, df))
            except Exception as e:
                st.warning(f"Excelシート読み込み失敗: {path.name} [{s}] ({e})")
    except Exception as e:
        st.warning(f"Excel読み込み失敗: {path.name} ({e})")
    return out


def _read_excel_heads_fukushima(path: Path, n: int, all_sheets: bool) -> List[Tuple[str, pd.DataFrame]]:
    """福島専用：最初の3行をスキップして読む"""
    out: List[Tuple[str, pd.DataFrame]] = []
    try:
        xls = pd.ExcelFile(path)
        targets = xls.sheet_names if all_sheets else xls.sheet_names[:1]
        for s in targets:
            try:
                df = pd.read_excel(path, sheet_name=s, skiprows=3, dtype=str)
                out.append((s, df.head(n)))
            except Exception as e:
                st.warning(f"Excelシート読み込み失敗: {path.name} [{s}] ({e})")
    except Exception as e:
        st.warning(f"Excel読み込み失敗: {path.name} ({e})")
    return out


def _read_excel_all_fukushima(path: Path) -> List[Tuple[str, pd.DataFrame]]:
    """福島専用：skiprows=3 ですべてのシートを読む"""
    out: List[Tuple[str, pd.DataFrame]] = []
    try:
        xls = pd.ExcelFile(path)
        for s in xls.sheet_names:
            try:
                df = pd.read_excel(path, sheet_name=s, skiprows=3, dtype=str)
                out.append((s, df))
            except Exception as e:
                st.warning(f"Excelシート読み込み失敗: {path.name} [{s}] ({e})")
    except Exception as e:
        st.warning(f"Excel読み込み失敗: {path.name} ({e})")
    return out

# 先頭に追加：prec用の2段ヘッダーフラット化
def _flatten_prec_columns(mi) -> list[str]:
    """
    MultiIndex columns (通常2段) を単層化。
    ・'Unnamed: ...' や nan/空は無視
    ・残った要素を半角スペースで結合（例：'選定基準 環境省レッド'）
    ・両方空なら 'col{i}'
    """
    out = []
    for i, col in enumerate(mi.to_list()):
        parts = []
        for c in (col if isinstance(col, (list, tuple)) else [col]):
            s = "" if c is None else str(c).strip()
            if not s or s.lower() == "nan" or s.startswith("Unnamed"):
                continue
            parts.append(s)
        name = " ".join(parts).strip()
        if not name:
            name = f"col{i}"
        out.append(name)
    return out

def _read_excel_heads_prec(path: Path, n: int, all_sheets: bool):
    out = []
    try:
        xls = pd.ExcelFile(path)
        targets = xls.sheet_names if all_sheets else xls.sheet_names[:1]
        for s in targets:
            try:
                df = pd.read_excel(path, sheet_name=s, header=[0, 1], dtype=str)
                df.columns = _flatten_prec_columns(df.columns)   # ★ここだけ差し替え
                base = [c for c in ["分類群","目名","科名","種名","学名","和名"] if c in df.columns]
                if base:
                    df = df[~df[base].isna().all(axis=1)]
                out.append((s, df.head(n)))
            except Exception as e:
                st.warning(f"Excelシート読み込み失敗: {path.name} [{s}] ({e})")
    except Exception as e:
        st.warning(f"Excel読み込み失敗: {path.name} ({e})")
    return out

def _read_excel_all_prec(path: Path):
    out = []
    try:
        xls = pd.ExcelFile(path)
        for s in xls.sheet_names:
            try:
                df = pd.read_excel(path, sheet_name=s, header=[0, 1], dtype=str)
                df.columns = _flatten_prec_columns(df.columns)   # ★ここだけ差し替え
                base = [c for c in ["分類群","目名","科名","種名","学名","和名"] if c in df.columns]
                if base:
                    df = df[~df[base].isna().all(axis=1)]
                out.append((s, df))
            except Exception as e:
                st.warning(f"Excelシート読み込み失敗: {path.name} [{s}] ({e})")
    except Exception as e:
        st.warning(f"Excel読み込み失敗: {path.name} ({e})")
    return out


# ─────────────────────────────────────────────
# メイン（プレビュー表示）
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
            if folder == "fukushima":
                heads = _read_excel_heads_fukushima(f, n_rows, show_sheet_all)
            elif folder == "prec":
                heads = _read_excel_heads_prec(f, n_rows, show_sheet_all)
            else:
                heads = _read_excel_heads(f, n_rows, show_sheet_all)

            if not heads:
                st.error("読み込みに失敗しました。")
            else:
                for sheet_name, df in heads:
                    st.markdown(f"- **Sheet:** `{sheet_name}`")
                    st.dataframe(df, use_container_width=True)

        else:
            st.error("未対応の拡張子です。")

        st.divider()


# ─────────────────────────────────────────────
# 照合処理（prec × MOE × 福島）
# ─────────────────────────────────────────────
st.header("🔎 照合（prec×環境省×福島県）")

def pick_cols(df: pd.DataFrame, wanted: Dict[str, List[str]],
              passthrough_cols: List[str] = ["_src_file", "_src_sheet", "_src_row"]) -> pd.DataFrame:
    def _norm(s: str) -> str:
        return _norm_text(s)   # ← ここだけ差し替え

    cols = {}
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
            st.info(f"列が見つかりませんでした: '{cands[0]}'")
    for c in passthrough_cols:
        if c in df.columns:
            cols[c] = df[c]
    return pd.DataFrame(cols)


def _read_csv_any(path: Path) -> Optional[pd.DataFrame]:
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return None


def _read_excel_all(path: Path) -> List[Tuple[str, pd.DataFrame]]:
    out: List[Tuple[str, pd.DataFrame]] = []
    try:
        xls = pd.ExcelFile(path)
        for s in xls.sheet_names:
            try:
                df = pd.read_excel(path, sheet_name=s)
                out.append((s, df))
            except Exception as e:
                st.warning(f"Excelシート読み込み失敗: {path.name} [{s}] ({e})")
    except Exception as e:
        st.warning(f"Excel読み込み失敗: {path.name} ({e})")
    return out


def _add_src_info(df: pd.DataFrame, *, file: Path, sheet: Optional[str] = None, row_offset: int = 0) -> pd.DataFrame:
    g = df.copy()
    g["_src_file"] = file.name
    if sheet is not None:
        g["_src_sheet"] = sheet
    g["_src_row"] = g.index + 2 + row_offset
    return g


# ---- 正規化（最小限：空白除去/全角→半角/ローマ数字→英字/IとA混在補正/小文字化）----
def _norm_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    t = str(s)

    # 空白類を削除
    for ch in ("\u3000", "\u00A0", "\u200B", "\uFEFF", "\n", "\t"):
        t = t.replace(ch, " ")
    t = t.strip().replace(" ", "")

    # 全角英数 → 半角
    z = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９"
    h = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    t = t.translate(str.maketrans(z, h))

    # ローマ数字 → ラテン（Ⅰ/Ⅱ/Ⅲ…）
    roman_map = {
        "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V",
        "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX", "Ⅹ": "X",
        "Ⅺ": "XI", "Ⅻ": "XII",
    }
    for k, v in roman_map.items():
        t = t.replace(k, v)

    # I と A の全角/半角混在補正（例：ⅠＡ → IA, IＡ → IA, ⅠA → IA）
    t = re.sub(r"([IVX]+)[ＡA]", lambda m: m.group(1) + "A", t, flags=re.IGNORECASE)

    return t.lower()


# ───────────────────────────
# ① prec
# ───────────────────────────
# ① prec（Excel）→ 「種名」「環境省レッド」「県レッド」
prec_dir = base_dir / "prec"
prec_frames = []
if prec_dir.exists():
    for p in sorted(prec_dir.iterdir()):
        if p.suffix.lower() in {".xlsx", ".xls"}:
            # ❌ 旧: for sheet_name, df in _read_excel_all(p):
            for sheet_name, df in _read_excel_all_prec(p):  # ✅ 専用関数に
                df = _add_src_info(df, file=p, sheet=sheet_name)
                sub = pick_cols(df, {
                    "prec種名": ["種名", "和名"],  # ← 種名 or 和名 どちらでも拾えるように
                    "prec環境省レッド": ["環境省レッド", "選定基準 環境省レッド"],
                    "prec県レッド":   ["県レッド",   "選定基準 県レッド"],
                })
                prec_frames.append(sub)

else:
    st.warning(f"prec フォルダが見つかりません: {prec_dir}")

              

prec_df = pd.concat(prec_frames, ignore_index=True) if prec_frames else pd.DataFrame(columns=["prec種名","prec環境省レッド","prec県レッド"])
prec_df["_ord"] = range(len(prec_df))

# ───────────────────────────
# ② MOE（環境省）
# ───────────────────────────
moe_dir = base_dir / "MOE"
moe_frames = []
if moe_dir.exists():
    for p in sorted(moe_dir.iterdir()):
        if p.suffix.lower() == ".csv":
            df = _read_csv_any(p)
            if df is not None:
                df = _add_src_info(df, file=p)
                sub = pick_cols(df, {"環境省カテゴリー": ["カテゴリー"], "環境省和名": ["和名"]})
                moe_frames.append(sub)
moe_df = pd.concat(moe_frames, ignore_index=True) if moe_frames else pd.DataFrame(columns=["環境省カテゴリー","環境省和名"])

# ───────────────────────────
# ③ 福島
# ───────────────────────────
fuku_dir = base_dir / "fukushima"
fuku_frames = []
if fuku_dir.exists():
    for p in sorted(fuku_dir.iterdir()):
        if p.suffix.lower() in {".xlsx", ".xls"}:
            for sheet_name, df in _read_excel_all_fukushima(p):
                df = _add_src_info(df, file=p, sheet=sheet_name, row_offset=3)
                sub = pick_cols(df, {
                    "福島県和名": ["和名"],
                    "福島県カテゴリー": ["ふくしまRL2024カテゴリー", "福島RL2024カテゴリー", "RL2024カテゴリー"],
                })
                fuku_frames.append(sub)
fuku_df = pd.concat(fuku_frames, ignore_index=True) if fuku_frames else pd.DataFrame(columns=["福島県和名","福島県カテゴリー"])

# ───────────────────────────
# 照合処理
# ───────────────────────────
moe_map = {}
if not moe_df.empty:
    for _, r in moe_df.dropna(subset=["環境省和名"]).iterrows():
        moe_map[_norm_text(r["環境省和名"])] = {"cat": r.get("環境省カテゴリー"), "file": r.get("_src_file"), "row": r.get("_src_row")}

fuku_map = {}
if not fuku_df.empty:
    for _, r in fuku_df.dropna(subset=["福島県和名"]).iterrows():
        fuku_map[_norm_text(r["福島県和名"])] = {"cat": r.get("福島県カテゴリー"), "file": r.get("_src_file"), "sheet": r.get("_src_sheet"), "row": r.get("_src_row")}

rows = []
for _, r in prec_df.iterrows():
    name = r.get("prec種名")
    key = _norm_text(name)
    moe_hit, fuku_hit = moe_map.get(key), fuku_map.get(key)
    if moe_hit or fuku_hit:
        rows.append({
            "prec種名": name,
            "prec環境省レッド": r.get("prec環境省レッド"),
            "prec県レッド": r.get("prec県レッド"),
            "環境省カテゴリー": moe_hit.get("cat") if moe_hit else None,
            "MOE元ファイル": moe_hit.get("file") if moe_hit else None,
            "MOE行番号": moe_hit.get("row") if moe_hit else None,
            "福島県カテゴリー": fuku_hit.get("cat") if fuku_hit else None,
            "福島元ファイル": fuku_hit.get("file") if fuku_hit else None,
            "福島元シート": fuku_hit.get("sheet") if fuku_hit else None,
            "福島行番号": fuku_hit.get("row") if fuku_hit else None,
            "prec元ファイル": r.get("_src_file"),
            "prec元シート": r.get("_src_sheet"),
            "prec行番号": r.get("_src_row"),
            "_ord": r.get("_ord", 0),
        })

# 走査結果 → DataFrame
result_df = pd.DataFrame(rows)

# _ord があれば並べ替え＆削除
if "_ord" in result_df.columns:
    result_df = result_df.sort_values("_ord").drop(columns=["_ord"], errors="ignore")


# 〈追加/修正〉カテゴリー記号の生成と比較（環境省／福島県）
def _extract_moe_code(s: Optional[str]) -> Optional[str]:
    """例: '絶滅危惧IA類（CR）' → 'CR'。丸括弧/全角括弧の中の英字1-3文字を抽出。なければ None。"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    m = re.search(r"[（(]\s*([A-Za-z]{1,3})\s*[)）]", str(s))
    return m.group(1).upper() if m else None

def _to_fukushima_code(s: Optional[str]) -> Optional[str]:
    """
    福島県カテゴリーの日本語表記→記号に変換。
    完全一致で判定する。
    変換テーブル: 絶滅危惧ⅠＡ類→CR，準絶滅危惧→NT，情報不足→DD，絶滅→EX
    上記以外は '変換規則不明' を返す。
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None

    key = _norm_text(s)  # 空白除去・全角→半角・小文字化

    mapping = {
        "絶滅危惧ia類": "CR",
        "絶滅危惧ii類": "VU",
        "準絶滅危惧":   "NT",
        "情報不足":     "DD",
        "絶滅":        "EX",
        "絶滅危惧ib類": "EN",
    }

    # 完全一致で判定
    return mapping.get(key, "変換規則不明")

def _norm_code(x) -> Optional[str]:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    return str(x).strip().upper()

def _cmp_codes(left, right) -> Optional[str]:
    """
    left/right を正規化して比較。
    両方 None → None
    どちらかだけ None → '不一致'
    両方あり一致 → '一致'
    両方あり不一致 → '不一致'
    """
    lx = _norm_code(left)
    rx = _norm_code(right)
    if lx is None and rx is None:
        return None
    return "一致" if (lx is not None and rx is not None and lx == rx) else "不一致"

if not result_df.empty:
    # （１）環境省カテゴリー記号
    result_df["環境省カテゴリー記号"] = result_df["環境省カテゴリー"].apply(_extract_moe_code)

    # （２）福島県カテゴリー記号
    result_df["福島県カテゴリー記号"] = result_df["福島県カテゴリー"].apply(_to_fukushima_code)

    # （３）環境省レッド比較（prec環境省レッド vs 環境省カテゴリー記号）— None対応
    result_df["環境省レッド比較"] = [
        _cmp_codes(x, y) for x, y in zip(result_df["prec環境省レッド"], result_df["環境省カテゴリー記号"])
    ]

    # （４）福島県レッド比較（prec県レッド vs 福島県カテゴリー記号）— None対応
    result_df["福島県レッド比較"] = [
        _cmp_codes(x, y) for x, y in zip(result_df["prec県レッド"], result_df["福島県カテゴリー記号"])
    ]

    # 集計（None は NaN として入るので isna() でカウント）
    moe_counts = {
        "一致": int((result_df["環境省レッド比較"] == "一致").sum()),
        "不一致": int((result_df["環境省レッド比較"] == "不一致").sum()),
        "None": int(result_df["環境省レッド比較"].isna().sum()),
    }
    fuk_counts = {
        "一致": int((result_df["福島県レッド比較"] == "一致").sum()),
        "不一致": int((result_df["福島県レッド比較"] == "不一致").sum()),
        "None": int(result_df["福島県レッド比較"].isna().sum()),
    }
    fuk_unknown = int((result_df["福島県カテゴリー記号"] == "変換規則不明").sum())


# ── ここから結果表示（1回だけ） ─────────────────
st.subheader("✅ 照合結果（一致したもの）")
if result_df.empty:
    st.info("一致するレコードが見つかりませんでした。")
else:
    st.dataframe(result_df, use_container_width=True)

    buf = io.StringIO()
    result_df.to_csv(buf, index=False)
    st.download_button(
        "📥 照合結果をCSVで保存",
        data=buf.getvalue().encode("utf-8-sig"),
        file_name="redlist_match_result.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ← ここに集計表示を追加
st.markdown("#### 🧮 集計")
st.write({
    "環境省レッド比較": {
        "一致": int(moe_counts.get("一致", 0)),
        "不一致": int(moe_counts.get("不一致", 0)),
         "None": moe_counts["None"],
    },
    "福島県レッド比較": {
        "一致": int(fuk_counts.get("一致", 0)),
        "不一致": int(fuk_counts.get("不一致", 0)),
         "None": fuk_counts["None"],
        "変換規則不明": fuk_unknown,
    },
})

st.caption(
    f"prec入力: {len(prec_df)} 件 / 環境省: {len(moe_df)} 件 / "
    f"福島県: {len(fuku_df)} 件 / 一致: {len(result_df)} 件"
)
# ────────────────────────────────────────────
