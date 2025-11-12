# -*- coding: utf-8 -*-
# pages/26_目次チェック.py — GPT API 不使用版：本文照合で目次チェック
from __future__ import annotations
import io, os, re, tempfile
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
st.set_page_config(page_title="📄 目次チェック（ローカル照合版）", page_icon="📄", layout="wide")
st.title("📄 目次チェック（ローカル照合版）")
st.caption("GPT APIを使わずに、目次候補のタイトルが実際の本文に出現するかを直接チェックします。")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])

c1, c2 = st.columns([1.3, 1])
with c1:
    scheme = st.radio("ページ方式", ["(1) 1,2,3,4, …", "(2) 1-1,1-2,2-1,2-2, …"], index=1, horizontal=True)
with c2:
    join_pages = st.checkbox("全ページ連結で抽出（推奨）", value=True)

# サイドバー：本文の上限文字数
with st.sidebar:
    excerpt_chars = st.number_input(
        "ページ本文の上限文字数（0で全文）",
        min_value=0, max_value=20000, value=800, step=100,
        help="各ページ本文の先頭から何文字までを照合対象にするか。"
    )

run = st.button("▶ 目次チェック開始", type="primary", use_container_width=True)

if not uploaded or not run:
    st.stop()
if fitz is None and pdfplumber is None:
    st.error("PyMuPDF か pdfplumber のどちらかをインストールしてください。`pip install pymupdf pdfplumber`")
    st.stop()

# =========================
# PDF→テキスト抽出
# =========================
def pdf_to_text_per_page(pdf_path: Path) -> List[str]:
    texts = []
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
# 目次候補の抽出
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

def extract_toc_lines(fulltext: str, limit: int = 300) -> List[str]:
    """目次候補行を抽出"""
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

# 全文から目次候補を探す（最初の数ページを使用）
sample_text = "\n".join(pages_text[:min(10, len(pages_text))])
toc_lines = extract_toc_lines(sample_text)

st.subheader("抽出された目次候補（上位）")
if len(toc_lines) == 0:
    st.warning("目次候補が見つかりませんでした。")
    st.stop()
st.code("\n".join(toc_lines[:60]))

# =========================
# 目次タイトルと本文照合
# =========================
def check_toc_in_pages(toc_lines: List[str], pages_text: List[str]) -> pd.DataFrame:
    results = []
    for toc in toc_lines:
        if " ::: " not in toc:
            continue
        title, label = toc.split(" ::: ", 1)
        title = title.strip()
        found_page = None
        partial = False
        snippet = ""

        for i, text in enumerate(pages_text):
            body = text[:excerpt_chars] if excerpt_chars > 0 else text

            # 完全一致
            if title in body:
                found_page = i + 1
                status = "一致"
                pos = body.find(title)
                snippet = body[max(0, pos-20):pos+len(title)+20].replace("\n", " ")
                break

            # 部分一致（先頭4〜5文字が本文に含まれる）
            elif len(title) >= 4:
                for key in [title[:5], title[:4]]:
                    if key in body:
                        found_page = i + 1
                        partial = True
                        pos = body.find(key)
                        snippet = body[max(0, pos-20):pos+len(key)+20].replace("\n", " ")
                        break
                if partial:
                    status = "部分一致"
                    break

        if not found_page:
            status = "未検出"

        results.append({
            "タイトル": title,
            "目次ラベル": label,
            "本文内ページ": found_page if found_page else "-",
            "判定": status,
            "一致テキスト抜粋": snippet if snippet else "-"
        })

    return pd.DataFrame(results)


df_result = check_toc_in_pages(toc_lines, pages_text)
st.subheader("🔍 照合結果")
st.dataframe(df_result, use_container_width=True)
st.caption("※『一致』はタイトルがページ本文に完全一致、『部分一致』は一部語句のみ一致。")

# 統計
summary = df_result["判定"].value_counts().to_dict()
st.markdown(f"**結果概要**: {summary}")

# ダウンロード
buf = io.StringIO()
df_result.to_csv(buf, index=False)
st.download_button(
    "📥 照合結果をCSVで保存",
    data=buf.getvalue().encode("utf-8-sig"),
    file_name="toc_check_local_result.csv",
    mime="text/csv",
)
