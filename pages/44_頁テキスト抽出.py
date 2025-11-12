# -*- coding: utf-8 -*-
# pages/44_頁テキスト抽出.py
# 目的：
#   単独行の頁ラベル抽出 → 連番チェック(valid=True) のページ本文をTXTに結合。
#   ★ 追加要件：page_label が無いページも必ず出力（headerは page_label=None）。

from __future__ import annotations
import io, re, tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import streamlit as st
import pandas as pd

# ==== PDF→テキスト ====
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
try:
    import pdfplumber
except Exception:
    pdfplumber = None

# =========================
# ページ設定 & メインUI
# =========================
st.set_page_config(page_title="📄 頁テキスト抽出（valid＋ラベル無しも出力）", page_icon="📄", layout="wide")
st.title("📄 頁テキスト抽出（valid=True＋label無しページもTXTへ）")
st.caption("OCRは行いません。PDFのテキスト層から抽出し、単独行ラベル→連番チェックで valid=True のページに加え、ラベル無しページもTXTに出力します。")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 抽出してTXTを作成", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    show_debug = st.checkbox("内部情報（デバッグ）を表示", value=False)

if not uploaded or not run:
    st.stop()
if fitz is None and pdfplumber is None:
    st.error("PyMuPDF か pdfplumber のどちらかをインストールしてください。`pip install pymupdf pdfplumber`")
    st.stop()

# =========================
# PDF → ページ別テキスト
# =========================
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

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    pdf_path = td / "input.pdf"
    pdf_path.write_bytes(uploaded.getvalue())
    pages_text: List[str] = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")

# =========================
# 正規化・ラベル検出
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D\u30FC]"
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"
LEADERS_SPACED = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"

def z2h_numhy(s: str) -> str:
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝", "0123456789()[]{}"))
    return re.sub(HY, "-", s)

def normalize_strict(s: str) -> str:
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"

def build_label_line_regex_mixed() -> re.Pattern:
    core_seq    = r"[0-9０-９]{1,6}"
    core_chap   = rf"[0-9０-９]+(?:\s*{HY}\s*[0-9０-９]+)+"
    series_word = rf"[（(［\[]?{ALPHAJP}[）)\]］]?"
    SEP_OPT     = rf"(?:\s*(?:{HY}|[\.．・･])\s*|\s+)?"
    core_series = rf"{series_word}{SEP_OPT}[0-9０-９]+"
    core = rf"(?:{core_seq}|{core_chap}|{core_series})"
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_LINE_RE = build_label_line_regex_mixed()

def extract_single_page_label(page_text: str) -> Tuple[Optional[str], Optional[str]]:
    if not page_text:
        return None, None
    for raw in page_text.replace("\r\n","\n").replace("\r","\n").split("\n"):
        s = normalize_strict(raw)
        if not s:
            continue
        m = LABEL_LINE_RE.match(s)
        if m:
            return z2h_numhy(m.group("label")), raw
    return None, None

# =========================
# 連番チェック
# =========================
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

# =========================
# 抽出 → 出力
# =========================
# 1) ページごとの単独行ラベル抽出
segments: List[Dict[str, Any]] = []
page_labels: List[Optional[str]] = []
for i, ptxt in enumerate(pages_text, start=1):
    label, matched = extract_single_page_label(ptxt)
    page_labels.append(label)
    segments.append({
        "pdf_page": i,
        "page_label": label if label else None,   # ← Noneを保持
        "body": normalize_strict(ptxt),
        "matched_line": matched if matched else "-"
    })

# 2) 連番チェックで valid=True を判定（ラベルがあるページのみ）
prev_ok: Optional[str] = None
valid_flags: Dict[int, bool] = {}
for s in segments:
    if s["page_label"] is None:
        valid_flags[s["pdf_page"]] = False
        continue
    ok, _ = valid_and_reason_auto(s["page_label"], prev_ok)
    if ok:
        prev_ok = s["page_label"]
    valid_flags[s["pdf_page"]] = ok

# 3) TXT 結合
#    - ラベル有りかつ valid=True のページ → 出力
#    - ラベル無し（page_label is None）のページ → 出力（headerは page_label=None）
txt_buf = io.StringIO()
num_valid = 0
num_none  = 0

for s in segments:
    label = s["page_label"]
    include = False
    label_str = "None"

    if label is None:
        include = True
        num_none += 1
    else:
        if valid_flags.get(s["pdf_page"], False):
            include = True
            label_str = str(label)
            num_valid += 1
        else:
            include = False  # ラベル有りだが invalid は出さない（仕様どおり）

    if include:
        header = f"==== pdf頁（pdf_page）={s['pdf_page']} pdf頁ラベル（page_label）={label_str} (chars={len(s['body'])}) ====\n"
        txt_buf.write(header)
        txt_buf.write(s["body"].rstrip("\n") + "\n\n")

# 4) ダウンロード
if num_valid > 0 or num_none > 0:
    st.download_button(
        "📥 extracted_pages_valid_and_none.txt をダウンロード",
        data=txt_buf.getvalue().encode("utf-8"),
        file_name="extracted_pages_valid.txt",  # 既存名を維持（中身はNoneも含む）
        mime="text/plain",
        use_container_width=True,
    )
    st.success(f"出力ページ数: valid={num_valid}, label=None={num_none}")
else:
    st.warning("出力対象のページがありません（valid=True も label=None も無し）。")

# デバッグ情報
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.code(f"LABEL_LINE_RE = {build_label_line_regex_mixed().pattern}")
    st.dataframe(pd.DataFrame(segments), use_container_width=True)
