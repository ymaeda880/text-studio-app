# -*- coding: utf-8 -*-
# pages/26_目次チェック.py — GPT API 不使用版：本文の各行で目次タイトルを照合
from __future__ import annotations
import io, re, tempfile
from pathlib import Path
from typing import List, Tuple

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
st.set_page_config(page_title="📄 目次チェック（ローカル照合・行単位）", page_icon="📄", layout="wide")
st.title("📄 目次チェック（ローカル照合・行単位）")
st.caption("目次候補のタイトルが、本文の **各行** に現れるかを直接チェックします。")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])

c1, c2 = st.columns([1.3, 1])
with c1:
    scheme = st.radio("ページ方式", ["(1) 1,2,3,4, …", "(2) 1-1,1-2,2-1,2-2, …"], index=1, horizontal=True)
with c2:
    join_pages = st.checkbox("全ページ連結で抽出（TOC抽出用に先頭数ページを使用）", value=True, help="TOC候補の抽出は先頭数ページから行います。")

# サイドバー：本文の上限文字数（0で全文）
with st.sidebar:
    excerpt_chars = st.number_input(
        "ページ本文の上限文字数（0で全文）",
        min_value=0, max_value=200000, value=0, step=500,
        help="各ページの先頭から照合対象にする最大文字数。0 は全文。"
    )
    max_toc = st.number_input("TOC候補の最大件数", min_value=10, max_value=500, value=300, step=10)
    max_toc_show = st.number_input("画面に表示するTOC件数", min_value=10, max_value=200, value=60, step=10)

run = st.button("▶ 目次チェック開始", type="primary", use_container_width=True)

if not uploaded or not run:
    st.stop()
if fitz is None and pdfplumber is None:
    st.error("PyMuPDF か pdfplumber のどちらかをインストールしてください。`pip install pymupdf pdfplumber`")
    st.stop()

# =========================
# PDF→ページ別テキスト抽出
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
    pages_text = pdf_to_text_per_page(pdf_path)

st.success(f"テキスト抽出完了（ページ数: {len(pages_text)}）")

# =========================
# 目次候補の抽出（先頭数ページから）
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D]"
LEADERS = r"[\.．・…]+"

def z2h_numhy(s: str) -> str:
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return re.sub(HY, "-", s)

def build_label_tail_regex(scheme: str) -> re.Pattern:
    if scheme.startswith("(1)"):
        tail = r"(?P<label>[0-9０-９]{1,6})"
    else:
        tail = rf"(?P<label>[0-9０-９]+(?:{HY}[0-9０-９]+)+)"
    pat = rf"""
        ^(?P<head>.*?)                               # 左側本文
        (?:\s*{LEADERS}\s*|\s{{2,}})?                # ドットリーダー or 空白
        {tail}\s*$                                   # 行末にページラベル
    """
    return re.compile(pat, re.X)

LABEL_TAIL_RE = build_label_tail_regex(scheme)

def extract_toc_lines_from_text(fulltext: str, limit: int) -> List[str]:
    """
    目次候補行を抽出（行頭が「第」or 数字で始まり、行末にページラベル）。
    返り値: "タイトル ::: ページラベル" の配列
    """
    lines = [l.rstrip() for l in fulltext.replace("\r\n","\n").replace("\r","\n").split("\n")]
    head_ok = re.compile(r"^(第|[0-9０-９])")
    text_char = re.compile(r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]")
    out: List[str] = []

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if not head_ok.match(s):
            continue
        if not text_char.search(s):
            continue
        m = LABEL_TAIL_RE.match(s)
        if not m:
            continue
        head = re.sub(rf"\s*{LEADERS}\s*$", "", m.group("head")).strip()
        label = z2h_numhy(m.group("label"))
        if len(head) <= 1:
            continue
        out.append(f"{head} ::: {label}")
        if len(out) >= limit:
            break
    return out

# TOCは先頭 ~10 ページを対象に抽出（結構多い資料でも十分）
head_pages = min(10, len(pages_text))
sample_text = "\n".join(pages_text[:head_pages])
toc_lines = extract_toc_lines_from_text(sample_text, limit=int(max_toc))

st.subheader("抽出された目次候補（上位）")
if len(toc_lines) == 0:
    st.warning("目次候補が見つかりませんでした。")
    st.stop()
st.code("\n".join(toc_lines[: int(max_toc_show) ]))

# =========================
# 本文を「行ごと」に照合（厳密：行内検索）
# =========================
def normalize_for_match(s: str) -> str:
    """マッチの頑健化（全角→半角数字, 各種ハイフン統一, 連続空白の1化, 前後空白削除）"""
    s = z2h_numhy(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def find_in_page_lines(title: str, body: str) -> Tuple[str, int, str]:
    """
    ページ本文（body）を行分割し、各行と照合。
    - 完全一致：行文字列に title を含む
    - 部分一致：title 先頭 5 or 4 文字が行に含まれる
    戻り値: (判定, 行番号(1始), 一致した行全文) / 未検出なら ("未検出", -1, "")
    """
    # 本文の対象長さを絞る
    if excerpt_chars and excerpt_chars > 0:
        body = body[:excerpt_chars]

    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    n_title = normalize_for_match(title)

    # ---- 完全一致（行内にタイトル全文が出現）
    for idx, raw in enumerate(lines, start=1):
        n_line = normalize_for_match(raw)
        if not n_line:
            continue
        if n_title and n_title in n_line:
            return ("一致", idx, raw)  # 元の行を返す

    # ---- 部分一致（先頭 5 → 4 文字）
    if len(n_title) >= 4:
        for k in [n_title[:5], n_title[:4]]:
            for idx, raw in enumerate(lines, start=1):
                n_line = normalize_for_match(raw)
                if k and k in n_line:
                    return ("部分一致", idx, raw)

    return ("未検出", -1, "")

def check_toc_in_pages_linewise(toc_lines: List[str], pages_text: List[str]) -> pd.DataFrame:
    results = []
    for toc in toc_lines:
        if " ::: " not in toc:
            continue
        title, label = toc.split(" ::: ", 1)
        title = title.strip()

        found = False
        hit_page, hit_line_no, hit_line_text, status = None, None, "", "未検出"

        for i, text in enumerate(pages_text):
            judge, line_no, line_text = find_in_page_lines(title, text)
            if judge != "未検出":
                found = True
                hit_page = i + 1
                hit_line_no = line_no
                hit_line_text = line_text.replace("\t", " ")
                status = judge
                break

        results.append({
            "タイトル": title,
            "目次ラベル": label,
            "本文内ページ": hit_page if found else "-",
            "本文内行番号": hit_line_no if found else "-",
            "判定": status,
            "一致テキスト行": hit_line_text if hit_line_text else "-"
        })

    return pd.DataFrame(results)

df_result = check_toc_in_pages_linewise(toc_lines, pages_text)

st.subheader("🔍 照合結果（行ベース）")
st.dataframe(df_result, use_container_width=True)
st.caption("※『一致』は行内にタイトル全文が出現。『部分一致』はタイトルの先頭 4〜5 文字が行内に出現。該当行全文を表示します。")

# 統計
summary = df_result["判定"].value_counts().to_dict()
st.markdown(f"**結果概要**: {summary}")

# ダウンロード
buf = io.StringIO()
df_result.to_csv(buf, index=False)
st.download_button(
    "📥 照合結果をCSVで保存",
    data=buf.getvalue().encode("utf-8-sig"),
    file_name="toc_check_local_linewise_result.csv",
    mime="text/csv",
)
