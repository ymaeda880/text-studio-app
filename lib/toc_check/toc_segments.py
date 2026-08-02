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
# ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"

# def build_label_tail_regex_mixed() -> re.Pattern:
#     core_seq    = r"[0-9０-９]{1,6}"
#     core_chap   = rf"[0-9０-９]+(?:\s*{HY}\s*[0-9０-９]+)+"
#     core_series = rf"{ALPHAJP}\s*{HY}\s*[0-9０-９]+"
#     tail = rf"(?P<label>(?:{core_seq}|{core_chap}|{core_series}))"
#     pat = rf"""
#         ^(?P<head>.*?)                     # 左側本文
#         (?:{LEADERS_SPACED}|\s{{2,}})?     # リーダー列/2空白以上
#         {tail}\s*$                         # 末尾ラベル
#     """
#     return re.compile(pat, re.X)

# def build_label_line_regex_mixed() -> re.Pattern:
#     core_seq    = r"[0-9０-９]{1,6}"
#     core_chap   = rf"[0-9０-９]+(?:\s*{HY}\s*[0-9０-９]+)+"
#     series_word = rf"[（(［\[]?{ALPHAJP}[）)\]］]?"
#     SEP_OPT     = rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"
#     core_series = rf"{series_word}{SEP_OPT}[0-9０-９]+"
#     core = rf"(?:{core_seq}|{core_chap}|{core_series})"
#     return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

# LABEL_TAIL_RE = build_label_tail_regex_mixed()
# LABEL_LINE_RE = build_label_line_regex_mixed()

# ============================================================
# ラベル抽出用文字パターン
# ============================================================
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"

def build_label_tail_regex_mixed() -> re.Pattern:
    """
    目次行の末尾からページラベルを抽出する。

    資料1，資料2-1，図表-3，Appendix-1などの
    シリーズ番号を単独数字より先に判定する。
    """
    core_seq = r"[0-9０-９]{1,6}"
    core_chap = rf"[0-9０-９]+(?:\s*{HY}\s*[0-9０-９]+)+"

    series_word = rf"[（(［\[]?{ALPHAJP}[）)\]］]?"
    series_sep = rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"
    series_number = (
        rf"[0-9０-９]+"
        rf"(?:\s*{HY}\s*[0-9０-９]+)*"
    )
    core_series = rf"{series_word}{series_sep}{series_number}"

    # ------------------------------------------------------------
    # シリーズ番号を単独数字より先に判定する
    #
    # 例：
    # 資料1 調査票 ........ 資料1
    #
    # core_seqを先にすると，末尾の「1」だけが抽出されるため，
    # core_seriesを最優先にする。
    # ------------------------------------------------------------
    tail = (
        rf"(?P<label>"
        rf"(?:{core_series}|{core_chap}|{core_seq})"
        rf")"
    )

    pattern = rf"""
        ^(?P<head>.*?)
        (?:{LEADERS_SPACED}|\s{{2,}})?
        {tail}\s*$
    """

    return re.compile(pattern, re.X)


def build_label_line_regex_mixed() -> re.Pattern:
    """
    PDF各ページの先頭側にある単独行ページラベルを抽出する。
    """
    core_seq = r"[0-9０-９]{1,6}"
    core_chap = rf"[0-9０-９]+(?:\s*{HY}\s*[0-9０-９]+)+"

    series_word = rf"[（(［\[]?{ALPHAJP}[）)\]］]?"
    series_sep = rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"
    series_number = (
        rf"[0-9０-９]+"
        rf"(?:\s*{HY}\s*[0-9０-９]+)*"
    )
    core_series = rf"{series_word}{series_sep}{series_number}"

    core = rf"(?:{core_series}|{core_chap}|{core_seq})"

    return re.compile(
        rf"^\s*"
        rf"(?:p(?:age)?\.?\s*)?"
        rf"(?P<label>{core})"
        rf"\s*$",
        re.MULTILINE,
    )


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

    # if chap:
    #     return "未検出", "-"
    # # 平文タイトルのみ、先頭N文字救済
    # for klen in (5, 4, 3):
    #     if len(title_raw) >= klen:
    #         prefix = title_raw[:klen]
    #         for ln in lines:
    #             if prefix in ln:
    #                 return f"部分一致（{klen}文字）", ln.rstrip("\n")
    # return "未検出", "-"

    if chap:
        return "未検出", "-"

    # ------------------------------------------------------------
    # 平文タイトルのみ，先頭N文字による部分一致
    #
    # ページラベルだけの行は一致候補から除外する。
    #
    # 例：
    #   資料 1-1
    #   資料 1-1 調査票
    #
    # 上記の場合，「資料 1-1」ではなく，
    # 「資料 1-1 調査票」を一致テキスト行として返す。
    # ------------------------------------------------------------
    for klen in (5, 4, 3):
        if len(title_raw) < klen:
            continue

        prefix = title_raw[:klen]

        for ln in lines:
            line_text = ln.strip()

            if not line_text:
                continue

            # ページラベルだけの単独行は除外
            line_normalized = normalize_strict(line_text)

            if LABEL_LINE_RE.fullmatch(line_normalized):
                continue

            if prefix in ln:
                return (
                    f"部分一致（{klen}文字）",
                    ln.rstrip("\n"),
                )

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

# def _parse_label_kind(label: str) -> Tuple[str, Any]:
#     lab = z2h_numhy(label)
#     if re.fullmatch(r"[0-9]+", lab):
#         return "seq", int(lab)
#     parts = lab.split("-")
#     if len(parts) >= 2 and all(p.isdigit() for p in parts):
#         return "chap", [int(p) for p in parts]
#     m = re.fullmatch(rf"({ALPHAJP})-([0-9]+)", lab)
#     if m:
#         return "series", (m.group(1), int(m.group(2)))
#     return "unknown", None

# def valid_and_reason_auto(label: str, prev_ok: Optional[str]) -> Tuple[bool, str]:
#     k, cur = _parse_label_kind(label)
#     if k == "unknown":
#         return False, "不明なラベル形式"
#     if prev_ok is None:
#         return True, ""
#     pk, prev = _parse_label_kind(prev_ok)
#     if pk == "unknown":
#         return True, ""
#     if k != pk:
#         return True, "形式切替"
#     if k == "seq":
#         return (cur == prev + 1, "" if cur == prev + 1 else "非連番")
#     if k == "chap":
#         c, p = (cur + [1, 1])[:2]; pc, pp = (prev + [1, 1])[:2]
#         ok = (c == pc and p == pp + 1) or (c == pc + 1 and p == 1)
#         return (ok, "" if ok else "非連番")
#     if k == "series":
#         s, n = cur; ps, pn = prev
#         if s != ps:
#             return True, "形式切替"
#         return (n == pn + 1, "" if n == pn + 1 else "非連番")
#     return True, ""

def _parse_label_kind(label: str) -> Tuple[str, Any]:
    """
    ページラベルを判定用の種類と数値へ分解する。

    戻り値：
    - seq
        1，2，3
    - chap
        1-1，1-2，2-1
    - series
        資料1，資料2，資料2-1，図表-3，Appendix-1
    - unknown
        上記以外
    """
    lab = z2h_numhy(label).strip()

    # ------------------------------------------------------------
    # 単独数字
    # ------------------------------------------------------------
    if re.fullmatch(r"[0-9]+", lab):
        return "seq", int(lab)

    # ------------------------------------------------------------
    # ハイフン付き数字
    # ------------------------------------------------------------
    if re.fullmatch(r"[0-9]+(?:-[0-9]+)+", lab):
        parts = [int(value) for value in lab.split("-")]
        return "chap", parts

    # ------------------------------------------------------------
    # シリーズ番号
    #
    # 対応例：
    # 資料1
    # 資料 1
    # 資料-1
    # 資料．1
    # 資料・1
    # 資料2-1
    # 図表-3
    # Appendix-1
    # ------------------------------------------------------------
    series_pattern = re.compile(
        rf"^"
        rf"(?P<series>{ALPHAJP})"
        rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"
        rf"(?P<number>[0-9]+(?:\s*{HY}\s*[0-9]+)*)"
        rf"$"
    )

    match = series_pattern.fullmatch(lab)

    if match:
        series_name = match.group("series").strip()
        number_text = z2h_numhy(match.group("number"))
        number_parts = [
            int(value)
            for value in number_text.split("-")
        ]

        return "series", (series_name, number_parts)

    return "unknown", None


def _is_next_number_parts(
    current: List[int],
    previous: List[int],
) -> bool:
    """
    階層付き番号が自然に続いているかを確認する。

    正常例：
    - 1-1 → 1-2
    - 1-3 → 2-1
    - 2-2 → 3-1
    - 2 → 2-1
    - 2-1 → 2-2
    - 2-3 → 3
    """
    if not current or not previous:
        return False

    min_len = min(len(current), len(previous))

    # ------------------------------------------------------------
    # 最初に異なる階層を確認
    #
    # 例：
    # 1-3 → 2-1
    # 2-2 → 3-1
    # 1-2-4 → 1-3-1
    # ------------------------------------------------------------
    for index in range(min_len):
        if current[index] == previous[index]:
            continue

        return (
            current[:index] == previous[:index]
            and current[index] == previous[index] + 1
            and all(value == 1 for value in current[index + 1:])
        )

    # ------------------------------------------------------------
    # 既存番号の下位階層が1から始まる
    #
    # 例：
    # 2 → 2-1
    # 資料2 → 資料2-1
    # ------------------------------------------------------------
    if len(current) > len(previous):
        return (
            current[:len(previous)] == previous
            and all(value == 1 for value in current[len(previous):])
        )

    return False


def valid_and_reason_auto(
    label: str,
    prev_ok: Optional[str],
) -> Tuple[bool, str]:
    """
    現在のページラベルが，直前の正常ラベルから
    自然に続いているかを確認する。
    """
    kind, current = _parse_label_kind(label)

    if kind == "unknown":
        return False, "不明なラベル形式"

    if prev_ok is None:
        return True, ""

    prev_kind, previous = _parse_label_kind(prev_ok)

    if prev_kind == "unknown":
        return True, ""

    # ------------------------------------------------------------
    # ページラベル体系が切り替わった場合
    #
    # 例：
    # 3 → 資料1
    # 3 → Appendix-1
    # ------------------------------------------------------------
    if kind != prev_kind:
        return True, "形式切替"

    # ------------------------------------------------------------
    # 単独数字
    # ------------------------------------------------------------
    if kind == "seq":
        is_valid = current == previous + 1

        return (
            is_valid,
            "" if is_valid else "非連番",
        )

    # ------------------------------------------------------------
    # ハイフン付き番号
    # ------------------------------------------------------------
    if kind == "chap":
        is_valid = _is_next_number_parts(
            current,
            previous,
        )

        return (
            is_valid,
            "" if is_valid else "非連番",
        )

    # ------------------------------------------------------------
    # シリーズ番号
    # ------------------------------------------------------------
    if kind == "series":
        series_name, number_parts = current
        prev_series_name, prev_number_parts = previous

        if series_name != prev_series_name:
            return True, "形式切替"

        is_valid = _is_next_number_parts(
            number_parts,
            prev_number_parts,
        )

        return (
            is_valid,
            "" if is_valid else "非連番",
        )

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
