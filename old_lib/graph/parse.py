# -*- coding: utf-8 -*-
from __future__ import annotations
import io, csv
from typing import Tuple, Dict
import pandas as pd
import numpy as np

def _normalize_text(t: str) -> str:
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.lstrip("\ufeff")
    lines = [ln.rstrip() for ln in t.split("\n")]
    while lines and (lines[0].strip() == ""):
        lines.pop(0)
    while len(lines) >= 2 and lines[-1].strip() == "" and lines[-2].strip() == "":
        lines.pop()
    return "\n".join(lines)

def _detect_delimiter_chunk(chunk: str) -> list[str]:
    counts = { "\t": chunk.count("\t"), ",": chunk.count(","), ";": chunk.count(";"), "|": chunk.count("|") }
    ordered = [k for k,_ in sorted(counts.items(), key=lambda x: -x[1]) if counts[k] > 0]
    for d in ["\t", ",", ";", "|"]:
        if d not in ordered:
            ordered.append(d)
    return ordered

def parse_pasted_robust(raw: str) -> Tuple[str, pd.DataFrame, Dict]:
    """
    1行目=タイトル、2行目=ヘッダー、3行目以降=データ。
    区切り：\t, ',', ';', '|', (2つ以上の空白) を順に試す。
    戻り: (title, df, diagnostics)
    """
    diag = {"lines": 0, "delimiter": None, "attempts": []}
    t = _normalize_text(raw)
    if not t.strip():
        diag["reason"] = "empty_text"
        return "", pd.DataFrame(), diag

    lines = t.split("\n")
    diag["lines"] = len(lines)
    if len(lines) < 2:
        diag["reason"] = "need_at_least_2_lines"
        return "", pd.DataFrame(), diag

    title = lines[0].strip()
    body  = "\n".join(lines[1:]).strip()

    sniff_chunk = "\n".join(lines[1: min(len(lines), 6)])
    candidates = _detect_delimiter_chunk(sniff_chunk)

    for delim in candidates:
        try:
            df = pd.read_csv(io.StringIO(body), sep=delim, engine="python")
            diag["attempts"].append({"sep": repr(delim), "ok": True, "shape": df.shape})
            if df.shape[0] >= 1 and df.shape[1] >= 1:
                diag["delimiter"] = delim
                df.columns = [str(c).strip() for c in df.columns]
                for c in df.columns:
                    if df[c].dtype == object:
                        df[c] = df[c].astype(str).str.strip()
                        df[c] = df[c].replace({"": np.nan})
                        df[c] = pd.to_numeric(df[c].replace({",": ""}, regex=True), errors="ignore")
                return title, df, diag
        except Exception as e:
            diag["attempts"].append({"sep": repr(delim), "ok": False, "err": str(e)})

    # regex: 2+ spaces
    use_regex = r"\s{2,}"
    try:
        df = pd.read_csv(io.StringIO(body), sep=use_regex, engine="python", regex=True)
        diag["attempts"].append({"sep": use_regex, "ok": True, "shape": df.shape})
        if df.shape[0] >= 1 and df.shape[1] >= 1:
            diag["delimiter"] = use_regex
            df.columns = [str(c).strip() for c in df.columns]
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].astype(str).str.strip()
                    df[c] = df[c].replace({"": np.nan})
                    df[c] = pd.to_numeric(df[c].replace({",": ""}, regex=True), errors="ignore")
            return title, df, diag
    except Exception as e:
        diag["attempts"].append({"sep": use_regex, "ok": False, "err": str(e)})

    diag["reason"] = "parse_failed"
    return title, pd.DataFrame(), diag
