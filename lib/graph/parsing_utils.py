# -*- coding: utf-8 -*-
"""
parsing_utils.py
----------------
貼り付けテキスト（Excel/CSV/表形式）を堅牢にDataFrame化するユーティリティ。

・改行コード・BOM除去などのテキスト正規化
・区切り文字の自動推定（タブ, カンマ, セミコロン, パイプ, 連続スペース）
・1行目をタイトル、2行目以降を表データとして分離
・各列のトリム・数値変換
・診断情報（diag）を返してパース結果を可視化可能
"""

from __future__ import annotations
import io
import numpy as np
import pandas as pd


# =========================
# ユーティリティ（前処理）
# =========================
def _normalize_text(t: str) -> str:
    """
    改行コードやBOMなどを正規化し、不要な空行を除去して返す。
    """
    t = t.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    lines = [ln.rstrip() for ln in t.split("\n")]

    # 先頭の空行を除去
    while lines and (lines[0].strip() == ""):
        lines.pop(0)

    # 末尾の空行が2行以上続く場合は削除
    while len(lines) >= 2 and lines[-1].strip() == "" and lines[-2].strip() == "":
        lines.pop()

    return "\n".join(lines)


# =========================
# メイン処理（堅牢パーサ）
# =========================
def parse_pasted_robust(raw: str) -> tuple[str, pd.DataFrame, dict]:
    """
    ExcelやCSV貼り付けテキストを堅牢にDataFrame化する。

    Returns
    -------
    title : str
        最初の1行（タイトル行）
    df : pd.DataFrame
        パースされた表データ
    diag : dict
        診断情報（lines, delimiter, attempts, reason等）
    """
    diag = {"lines": 0, "delimiter": None, "attempts": []}

    # --- 1) テキスト正規化 ---
    t = _normalize_text(raw)
    if not t.strip():
        return "", pd.DataFrame(), {**diag, "reason": "empty_text"}

    lines = t.split("\n")
    diag["lines"] = len(lines)
    if len(lines) < 2:
        return "", pd.DataFrame(), {**diag, "reason": "need_at_least_2_lines"}

    # --- 2) タイトルと本文分離 ---
    title = lines[0].strip()
    body = "\n".join(lines[1:]).strip()

    # --- 3) 区切り文字候補抽出 ---
    sniff_chunk = "\n".join(lines[1:min(len(lines), 6)])
    counts = {
        "\t": sniff_chunk.count("\t"),
        ",": sniff_chunk.count(","),
        ";": sniff_chunk.count(";"),
        "|": sniff_chunk.count("|"),
    }
    candidates = [k for k, _ in sorted(counts.items(), key=lambda x: -x[1]) if counts[k] > 0]
    for d in ["\t", ",", ";", "|"]:
        if d not in candidates:
            candidates.append(d)
    regex_spaces = r"\s{2,}"

    # --- 4) 各候補でトライ ---
    for delim in candidates:
        try:
            df = pd.read_csv(io.StringIO(body), sep=delim, engine="python")
            diag["attempts"].append({"sep": repr(delim), "ok": True, "shape": df.shape})
            if df.shape[0] >= 1 and df.shape[1] >= 1:
                diag["delimiter"] = delim
                df.columns = [str(c).strip() for c in df.columns]
                for c in df.columns:
                    if df[c].dtype == object:
                        df[c] = df[c].astype(str).str.strip().replace({"": np.nan})
                        df[c] = pd.to_numeric(df[c].replace({",": ""}, regex=True), errors="ignore")
                return title, df, diag
        except Exception as e:
            diag["attempts"].append({"sep": repr(delim), "ok": False, "err": str(e)})

    # --- 5) 連続スペース区切り（最終手段） ---
    try:
        df = pd.read_csv(io.StringIO(body), sep=regex_spaces, engine="python", regex=True)
        diag["attempts"].append({"sep": regex_spaces, "ok": True, "shape": df.shape})
        if df.shape[0] >= 1 and df.shape[1] >= 1:
            diag["delimiter"] = regex_spaces
            df.columns = [str(c).strip() for c in df.columns]
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].astype(str).str.strip().replace({"": np.nan})
                    df[c] = pd.to_numeric(df[c].replace({",": ""}, regex=True), errors="ignore")
            return title, df, diag
    except Exception as e:
        diag["attempts"].append({"sep": regex_spaces, "ok": False, "err": str(e)})

    # --- 6) 全滅時 ---
    return title, pd.DataFrame(), {**diag, "reason": "parse_failed"}
