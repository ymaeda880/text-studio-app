# -*- coding: utf-8 -*-
# lib/toc_check/toc_segments.py
"""
目次チェック用のコア関数群
- PDF→ページ別テキスト化
- 目次行（末尾ラベル）抽出
- 本文ページからの単独行ラベル抽出
- ラベル妥当性検証（連番・章番号・シリーズ）
- タイトル↔本文 行スキャン照合（2行結合窓対応）
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import re

from ..text_normalizer import (
    z2h_numhy, normalize_strict, normalize_loose,
    HY, LEADERS_SPACED,
)

# ==== PDF→テキスト ====
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
try:
    import pdfplumber
except Exception:
    pdfplumber = None


def pdf_to_text_per_page(pdf_path: Path) -> List[str]:
    texts: List[str] = []
    if fitz is not None:
        doc = fitz.open(str(pdf_path))
        for p in doc:
            texts.append(p.get_text("text") or "")
    else:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for p in pdf.pages:
                texts.append(p.extract_text() or "")
    return texts


# ==== ラベル抽出（目次末尾／本文単独行） ====
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"

def build_label_tail_regex_mixed() -> re.Pattern:
    core_seq    = r"[0-9０-９]{1,6}"
    core_chap   = rf"[0-9０-９]+(?:\s*{HY}\s*[0-9０-９]+)+"
    core_series = rf"{ALPHAJP}\s*{HY}\s*[0-9０-９]+"
    tail = rf"(?P<label>(?:{core_seq}|{core_chap}|{core_series}))"
    pat = rf"""
        ^(?P<head>.*?)                     # 左側本文
        (?:{LEADERS_SPACED}|\s{{2,}})?     # リーダー列/2空白以上
        {tail}\s*$                         # 末尾ラベル
    """
    return re.compile(pat, re.X)

def build_label_line_regex_mixed() -> re.Pattern:
    core_seq    = r"[0-9０-９]{1,6}"
    core_chap   = rf"[0-9０-９]+(?:\s*{HY}\s*[0-9０-９]+)+"
    series_word = rf"[（(［\[]?{ALPHAJP}[）)\]］]?"
    SEP_OPT     = rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"
    core_series = rf"{series_word}{SEP_OPT}[0-9０-９]+"
    core = rf"(?:{core_seq}|{core_chap}|{core_series})"
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_TAIL_RE = build_label_tail_regex_mixed()
LABEL_LINE_RE = build_label_line_regex_mixed()

# ==== ページラベル専用の行判定（優先順位付きで使う） ====
NUM = r"[0-9０-９]{1,6}"

# 1) 単独数字（例：1, 12）
PAGE_SINGLE_RE = re.compile(
    rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{NUM})\s*$"
)

# 2) 括弧付き単独数字（例：(3), （10））
PAGE_PAREN_RE = re.compile(
    rf"^\s*(?:p(?:age)?\.?\s*)?[（(]\s*(?P<label>{NUM})\s*[）)]\s*$"
)

# 3) 連番区間（例：3-4, ３－４）
PAGE_RANGE_RE = re.compile(
    rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{NUM}\s*{HY}\s*{NUM})\s*$"
)

def extract_single_page_label(page_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    1ページ分のテキストから「頁ラベル」を 1 個だけ推定して返す。

    探索方針：
      - ページ先頭から順に，normalize_strict で見ても「中身が空」の行はスキップする
      - 最初に「何か文字がある行」を見つけた位置を起点として，そこから最大3行分を見る
      - その 1〜3 行の中で，
          1) 単独数字       （例：1, 12）
          2) 括弧付き単独数 （例：(3), （10））
          3) 連番区間       （例：3-4, ３－４）
        を優先的に探す
      - 見つからなければ LABEL_LINE_RE でフォールバック
      - それでも見つからなければ (None, None) を返す
    戻り値:
      (正規化したラベル, 元の行テキスト)
    """
    if not page_text:
        return None, None

    # 改行正規化
    lines_raw = page_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # normalize_strict をかけたものも併せて持っておく
    lines_norm = [normalize_strict(raw) for raw in lines_raw]

    # ─────────────────────────────
    # 先頭の「完全な空行」（スペースだけ等）をスキップ
    # ─────────────────────────────
    start = 0
    while start < len(lines_norm) and not lines_norm[start].strip():
        start += 1

    if start >= len(lines_raw):
        # ページ全体が空行だけ
        return None, None

    # ここから最大3行分だけをラベル候補として見る
    limit = min(3, len(lines_raw) - start)
    top_raw = lines_raw[start:start + limit]
    top_norm = lines_norm[start:start + limit]

    def _scan_top(pattern: re.Pattern) -> Tuple[Optional[str], Optional[str]]:
        """
        top_norm/top_raw の中から pattern にマッチする行を探す。
        見つかったら (ラベル, 元行) を返す。
        """
        for raw, s in zip(top_raw, top_norm):
            if not s:
                continue
            m = pattern.match(s)
            if not m:
                continue
            label_raw = m.group("label")
            # 数字・ハイフンを正規化（全角→半角，ハイフン統一など）
            label = z2h_numhy(label_raw).strip()
            if label:
                return label, raw
        return None, None

    # 1) 単独数字
    label, line = _scan_top(PAGE_SINGLE_RE)
    if label is not None:
        return label, line

    # 2) 括弧付き単独数字
    label, line = _scan_top(PAGE_PAREN_RE)
    if label is not None:
        return label, line

    # 3) 連番区間
    label, line = _scan_top(PAGE_RANGE_RE)
    if label is not None:
        return label, line

    # 4) フォールバック：従来の LABEL_LINE_RE ロジック
    for raw, s in zip(top_raw, top_norm):
        if not s:
            continue
        m = LABEL_LINE_RE.match(s)
        if m:
            return z2h_numhy(m.group("label")), raw

    # 見つからなければラベルなし扱い
    return None, None



def extract_toc_lines(fulltext: str, limit: int) -> List[str]:
    lines = [l.rstrip() for l in fulltext.replace("\r\n","\n").replace("\r","\n").split("\n")]
    head_ok = re.compile(
        r"^\s*(?:"
        r"序|資料|付録|第|添付資料|⚪︎|○|"
        r"[0-9０-９]|"
        r"\[|［|"
        r"[（(][0-9０-９]{1,3}[）)]"
        r")"
    )
    text_char = re.compile(r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]")
    out: List[str] = []
    for ln in lines:
        s = ln.strip()
        if not s or not head_ok.match(s) or not text_char.search(s):
            continue
        m = LABEL_TAIL_RE.match(s)
        if not m:
            continue
        head  = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", m.group("head")).strip()
        label = z2h_numhy(m.group("label"))
        if len(head) <= 0:
            continue
        out.append(f"{head} ::: {label}")
        if len(out) >= limit:
            break
    return out


# ==== 章番号検出 & 照合 ====
CHAP_HEAD_RE = re.compile(r'^\s*[0-9０-９]+(?:\s*' + HY + r'\s*[0-9０-９]+)+')

def extract_chap_head(s: str) -> Optional[str]:
    m = CHAP_HEAD_RE.match(s or "")
    if not m:
        return None
    return z2h_numhy(m.group(0)).strip()

def scan_lines_for_match(title_raw: str, body: str) -> Tuple[str, str]:
    title_strict = normalize_strict(title_raw)
    title_loose  = normalize_loose(title_raw)
    chap = extract_chap_head(title_raw)

    lines = body.split("\n")

    # 行単位（強→弱）
    for ln in lines:
        if not ln.strip():
            continue
        ln_strict = normalize_strict(ln)
        if ln_strict == title_strict:
            return "一致", ln.rstrip("\n")
        ln_loose = normalize_loose(ln)
        if ln_loose == title_loose:
            return "一致（空白差吸収）", ln.rstrip("\n")
        if chap:
            ln_norm = z2h_numhy(ln)
            pat = re.compile(rf'(?<!\d){re.escape(chap)}(?!\s*{HY}\s*\d)')
            if pat.search(ln_norm):
                return "一致（章番号）", ln.rstrip("\n")
        if title_raw in ln:
            return "一致（行内部分一致）", ln.rstrip("\n")

    # 2行結合窓
    for i in range(len(lines) - 1):
        merged = normalize_strict(lines[i] + " " + lines[i+1])
        if title_strict in merged or title_loose in merged:
            return "一致（改行越え）", lines[i] + " / " + lines[i+1]

    if chap:
        return "未検出", "-"
    # 平文タイトルのみ、先頭N文字救済
    for klen in (5, 4, 3):
        if len(title_raw) >= klen:
            prefix = title_raw[:klen]
            for ln in lines:
                if prefix in ln:
                    return f"部分一致（{klen}文字）", ln.rstrip("\n")
    return "未検出", "-"


# ==== segments 構築・妥当性検証 ====
def build_segments(pages_text: List[str]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    for i, ptxt in enumerate(pages_text, start=1):
        label, matched = extract_single_page_label(ptxt)
        segments.append({
            "page_label": label if label else "-",
            "body": normalize_strict(ptxt),
            "pdf_page": i,
            "matched_line": matched if matched else "-"
        })
    return segments

def _parse_label_kind(label: str) -> Tuple[str, Any]:
    lab = z2h_numhy(label)
    if re.fullmatch(r"[0-9]+", lab):
        return "seq", int(lab)
    parts = lab.split("-")
    if len(parts) >= 2 and all(p.isdigit() for p in parts):
        return "chap", [int(p) for p in parts]
    m = re.fullmatch(rf"({ALPHAJP})-([0-9]+)", lab)
    if m:
        return "series", (m.group(1), int(m.group(2)))
    return "unknown", None

def valid_and_reason_auto(label: str, prev_ok: Optional[str]) -> Tuple[bool, str]:
    k, cur = _parse_label_kind(label)
    if k == "unknown":
        return False, "不明なラベル形式"
    if prev_ok is None:
        return True, ""
    pk, prev = _parse_label_kind(prev_ok)
    if pk == "unknown":
        return True, ""
    if k != pk:
        return True, "形式切替"
    if k == "seq":
        return (cur == prev + 1, "" if cur == prev + 1 else "非連番")
    if k == "chap":
        c, p = (cur + [1, 1])[:2]; pc, pp = (prev + [1, 1])[:2]
        ok = (c == pc and p == pp + 1) or (c == pc + 1 and p == 1)
        return (ok, "" if ok else "非連番")
    if k == "series":
        s, n = cur; ps, pn = prev
        if s != ps:
            return True, "形式切替"
        return (n == pn + 1, "" if n == pn + 1 else "非連番")
    return True, ""

def validate_segments(segments: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Tuple[str,int]]]:
    rows_check: List[Dict[str, Any]] = []
    prev_ok: Optional[str] = None

    for s in segments:
        lab = s["page_label"]
        if lab == "-":
            rows_check.append({
                "pdf_page": s["pdf_page"],
                "page_label": lab,
                "valid": False,
                "reason": "ラベルなし",
                "char_count": len(s["body"]),
                "preview": s["body"][:100].replace("\n"," ") + ("…" if len(s["body"])>100 else "")
            })
            continue
        ok, reason = valid_and_reason_auto(lab, prev_ok)
        if ok:
            prev_ok = lab
        rows_check.append({
            "pdf_page": s["pdf_page"],
            "page_label": lab,
            "valid": ok,
            "reason": "" if ok else reason,
            "char_count": len(s["body"]),
            "preview": s["body"][:100].replace("\n"," ") + ("…" if len(s["body"])>100 else "")
        })

    valid_segments = [s for s in segments if any(r["pdf_page"] == s["pdf_page"] and r["valid"] for r in rows_check)]
    seg_index: Dict[str, Tuple[str,int]] = {
        s["page_label"]: (s["body"], s["pdf_page"])
        for s in valid_segments if s["page_label"] != "-"
    }
    return rows_check, valid_segments, seg_index


# ==== 目次 ↔ 本文 照合 ====
def check_toc_by_order(
    toc_lines: List[str],
    seg_index: Dict[str, Tuple[str, int]],
    pages_text: List[str],
    search_all_pages: bool = False
) -> List[Dict[str, Any]]:
    out_rows: List[Dict[str, Any]] = []
    for toc in toc_lines:
        if " ::: " not in toc:
            continue
        title_raw, label = toc.split(" ::: ", 1)
        title_raw = title_raw.strip()
        label = label.strip()

        status = "未検出"
        matched = "-"
        found_page_num: Optional[int] = None

        # 1) ラベル一致ページを優先
        if label in seg_index:
            body_for_label, page_no = seg_index[label]
            stt, m = scan_lines_for_match(title_raw, body_for_label)
            if stt != "未検出":
                status, matched, found_page_num = stt, m, page_no

        # 2) 必要なら全ページ探索
        if status == "未検出" and search_all_pages:
            for i, ptxt in enumerate(pages_text):
                stt, m = scan_lines_for_match(title_raw, ptxt)
                if stt != "未検出":
                    status, matched, found_page_num = stt, m, i + 1
                    break

        out_rows.append({
            "タイトル": title_raw,
            "目次頁ラベル": label,
            "pdf頁ラベル": label if label in seg_index else "-",
            "pdf頁": found_page_num if found_page_num is not None else "-",
            "判定": status,
            "一致テキスト行": matched,
        })
    return out_rows
