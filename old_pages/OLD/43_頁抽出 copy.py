# -*- coding: utf-8 -*-
# pages/43_頁抽出.py — 単独行の版面ラベルで抽出頁を作成し、連番検証＋元PDFページも表示
from __future__ import annotations
import re, io, tempfile
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
st.set_page_config(page_title="📃 頁抽出＋連番検証（PDFページ付き）", page_icon="📃", layout="wide")
st.title("📃 頁抽出（単独行ラベルで区切り）＋ 連番検証 ＋ 元PDFページ表示")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 抽出・検証を実行", type="primary", use_container_width=True)

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
# 正規化ユーティリティ
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D]"   # 各種ハイフン
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"               # 英字/かな/漢字

# リーダー系（……や・やドットの連なり）
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"
LEADERS_SPACED = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"

def z2h_numhy(s: str) -> str:
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝", "0123456789()[]{}"))
    return re.sub(HY, "-", s)

def normalize_strict(s: str) -> str:
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)  # 行末のリーダー列除去
    s = re.sub(r"[ \t]+", " ", s)                   # 連続空白を1つへ
    return s.strip()

# =========================
# 単独行ラベルで本文を分割（抽出ページを作る）
#  + 元PDFページ番号の推定
# =========================
# ポイント：「行頭～行末がラベルだけ」に限定しているため、本文の途中に出てくる “○-○” などが誤検出されない
def build_label_line_regex_mixed() -> re.Pattern:
    # 許容する行単独ラベル：
    #  (1) 連番: 12
    #  (2) 章-ページ: 1-2, 3-10-2
    #  (3) シリーズ-数字: 序-1, 資-2, 付-3, A-10 等
    core_seq    = r"[0-9０-９]{1,6}"
    core_chap   = rf"[0-9０-９]+(?:{HY}[0-9０-９]+)+"
    core_series = rf"{ALPHAJP}{HY}[0-9０-９]+"
    core = rf"(?:{core_seq}|{core_chap}|{core_series})"
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_LINE_RE = build_label_line_regex_mixed()

# ページ境界マーカー（元PDFページ n）
PAGE_MARK_FMT = "\n<<<PAGE:{n}>>>\n"
PAGE_MARK_RE  = re.compile(r"\n<<<PAGE:(\d+)>>>\n")

def join_with_page_marks(pages: List[str]) -> str:
    buf = []
    for i, t in enumerate(pages, start=1):
        buf.append(PAGE_MARK_FMT.format(n=i))
        buf.append(t if t else "")
    return "".join(buf)

def pages_in_slice(txt: str, start: int, end: int) -> List[int]:
    """txt[start:end] に含まれる PAGE_MARK のページ番号を抽出"""
    sub = txt[start:end]
    return [int(m.group(1)) for m in PAGE_MARK_RE.finditer(sub)]

def split_segments_by_label_with_pdfpages(pages_text: List[str]) -> List[Dict[str, Any]]:
    """
    ページ境界マーカー付きで結合 → 行単独ラベルで区切り。
    各セグメントに:
      - page_label（版面ラベル）
      - body（本文。マーカー除去後）
      - pdf_pages（元PDFのページ範囲： [start, ..., end]）
      - pdf_page_start / pdf_page_end
    を付与。
    """
    all_text_marked = join_with_page_marks(pages_text)
    txt = normalize_strict(all_text_marked.replace("\r\n", "\n").replace("\r", "\n"))

    matches = list(LABEL_LINE_RE.finditer(txt))
    if not matches:
        return []

    def next_nonempty_pos(pos: int) -> int:
        n = pos
        while n < len(txt) and txt[n] == "\n":
            n += 1
        return n

    segs: List[Dict[str, Any]] = []
    for i, m in enumerate(matches):
        label = z2h_numhy(m.group("label"))
        start = next_nonempty_pos(m.end())
        end   = matches[i+1].start() if i+1 < len(matches) else len(txt)
        raw   = txt[start:end].lstrip("\n ")
        # このセグメントに含まれる元PDFページを取得
        pdfs  = pages_in_slice(txt, start, end)
        pdfs  = sorted(set(pdfs))
        # プレビュー用にマーカーを除去
        body  = PAGE_MARK_RE.sub("", raw)
        segs.append({
            "page_label": label,
            "body": body,
            "pdf_pages": pdfs,
            "pdf_page_start": (min(pdfs) if pdfs else None),
            "pdf_page_end":   (max(pdfs) if pdfs else None),
        })
    return segs

segments = split_segments_by_label_with_pdfpages(pages_text)



# ==== PDF読み込みが終わった直後に追加 ====
# st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")

# === 結合後テキストを作成してセッションに保持 ===
if "joined_text" not in st.session_state:
    st.session_state.joined_text = join_with_page_marks(pages_text)

# === expanderで確認とDL ===
with st.expander("📄 結合後テキスト（確認・ダウンロード）", expanded=False):
    st.text_area(
        "結合済みテキスト（先頭部分プレビュー）",
        st.session_state.joined_text[:3000],
        height=250
    )
    st.download_button(
        "📥 結合テキストをダウンロード",
        data=st.session_state.joined_text.encode("utf-8"),
        file_name="joined_pages_with_marks.txt",
        mime="text/plain",
        use_container_width=True,
    )


# =========================
# 表示（概観テーブル）
# =========================
st.subheader("抽出ページ（単独行ラベルで区切り）— 概観")
if not segments:
    st.warning("単独行のページラベルが見つからず、抽出ページが作成できませんでした。")
else:
    def fmt_pdf_range(s, e):
        if s is None:
            return "-"
        return str(s) if s == e else f"{s}–{e}"
    df_segments_overview = pd.DataFrame([{
        "page_label": s["page_label"],
        "pdf_pages": ",".join(map(str, s["pdf_pages"])) if s["pdf_pages"] else "-",
        "pdf_page_range": fmt_pdf_range(s["pdf_page_start"], s["pdf_page_end"]),
        "char_count": len(s["body"]),
        "preview": s["body"][:120].replace("\n"," ") + ("…" if len(s["body"])>120 else "")
    } for s in segments])
    st.dataframe(df_segments_overview, use_container_width=True)

# =========================
# ラベル妥当性（連番チェック）
# =========================
st.subheader("📑 ページラベル検証（連番チェック）")

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

rows_check: List[Dict[str, Any]] = []
prev_ok: Optional[str] = None
for s in segments:
    ok, reason = valid_and_reason_auto(s["page_label"], prev_ok)
    if ok:
        prev_ok = s["page_label"]
    rows_check.append({
        "page_label": s["page_label"],
        "pdf_page_range": (f"{s['pdf_page_start']}–{s['pdf_page_end']}" 
                           if s["pdf_page_start"] is not None else "-"),
        "valid": ok,
        "reason": "" if ok else reason,
        "char_count": len(s["body"]),
        "preview": s["body"][:100].replace("\n"," ") + ("…" if len(s["body"])>100 else "")
    })

df_check = pd.DataFrame(rows_check)
st.dataframe(df_check, use_container_width=True)

# デバッグ表示（任意）
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.write({
        "segments_all": len(segments),
        "first_page_label": segments[0]["page_label"] if segments else None,
        "last_page_label": segments[-1]["page_label"] if segments else None,
        "first_pdf_range": (segments[0]["pdf_page_start"], segments[0]["pdf_page_end"]) if segments else None,
        "last_pdf_range":  (segments[-1]["pdf_page_start"], segments[-1]["pdf_page_end"]) if segments else None,
    })
