# -*- coding: utf-8 -*-
# pages/26_目次チェック.py — GPT API 不使用版：本文照合で目次チェック（ラベル連番検証つき・有効ページのみTXT出力）
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
st.set_page_config(page_title="📄 目次チェック（ローカル照合＋連番検証）", page_icon="📄", layout="wide")
st.title("📄 目次チェック（ローカル照合）")
st.caption("GPT を使わず、目次候補のタイトルが本文に出現するかを直接照合します。ページラベルは連番のみ検証（“年っぽい除外”は行いません）。")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])

c1, c2 = st.columns([1.3, 1])
with c1:
    scheme = st.radio("ページ方式", ["(1) 1,2,3,4, …", "(2) 1-1,1-2,2-1,2-2, …"], index=1, horizontal=True)
with c2:
    join_pages = st.checkbox("目次抽出用に冒頭数ページを連結（推奨）", value=True)

# サイドバー：本文の上限文字数（0で全文）
with st.sidebar:
    excerpt_chars = st.number_input(
        "照合対象の本文上限文字数（0で全文）",
        min_value=0, max_value=50000, value=800, step=100,
        help="各ページ本文の先頭から何文字までを照合対象にするか。0 なら全文。"
    )
    show_debug = st.checkbox("デバッグ情報を表示", value=False)

run = st.button("▶ 目次チェック開始", type="primary", use_container_width=True)

if not uploaded or not run:
    st.stop()
if fitz is None and pdfplumber is None:
    st.error("PyMuPDF か pdfplumber のどちらかをインストールしてください。`pip install pymupdf pdfplumber`")
    st.stop()

# =========================
# PDF→テキスト抽出（ページ単位）
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
# 目次候補の抽出（行末ページラベルのある行）
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D]"  # 各種ハイフン
LEADERS = r"[\.．・…]+"                                   # ドットリーダー群

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
        (?:\s*{LEADERS}\s*|\s{{2,}})?                # ドットリーダー or 複数空白
        {tail}\s*$                                   # 行末にページラベル
    """
    return re.compile(pat, re.X)

LABEL_TAIL_RE = build_label_tail_regex(scheme)

def extract_toc_lines(fulltext: str, limit: int = 300) -> List[str]:
    """
    目次候補行を抽出。
    行頭が「第」または数字で始まり、文字（日本語/英字）を含む行のみ採用。
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

# 目次候補は冒頭～数ページから抽出（たいてい目次は前半）
sample_pages_n = min(10, len(pages_text))
sample_text = "\n".join(pages_text[:sample_pages_n]) if join_pages else "\n".join(pages_text[:max(1, sample_pages_n//2)])
toc_lines = extract_toc_lines(sample_text)

st.subheader("抽出された目次候補（上位）")
if len(toc_lines) == 0:
    st.warning("目次候補が見つかりませんでした。")
    st.stop()
st.code("\n".join(toc_lines[:80]))

# =========================
# ページラベルの単独行抽出 → 本文セグメント化
# =========================
def build_label_line_regex(scheme: str) -> re.Pattern:
    if scheme.startswith("(1)"):
        core = r"[0-9０-９]{1,6}"               # 連番
    else:
        core = rf"[0-9０-９]+(?:{HY}[0-9０-９]+)+"  # 章-ページ（複合可）
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_LINE_RE = build_label_line_regex(scheme)

def split_segments_by_label(all_text: str, scheme: str) -> List[Dict[str, Any]]:
    """
    PDF 全文（ページ連結）から、単独行のページラベルで本文を分割。
    """
    txt = z2h_numhy(all_text.replace("\r\n", "\n").replace("\r", "\n"))
    matches = list(LABEL_LINE_RE.finditer(txt))
    if not matches:
        return []

    segs: List[Dict[str, Any]] = []

    def next_nonempty_pos(pos: int) -> int:
        n = pos
        while n < len(txt) and txt[n] == "\n":
            n += 1
        return n

    for i, m in enumerate(matches):
        label = z2h_numhy(m.group("label"))
        start = next_nonempty_pos(m.end())
        end = matches[i+1].start() if i+1 < len(matches) else len(txt)
        body = txt[start:end].lstrip("\n ")
        segs.append({
            "page_label": label,
            "body": body,
        })
    return segs

# 全文を連結してセグメント化（検出しやすさ重視）
all_text_joined = "\n".join(pages_text)
segments = split_segments_by_label(all_text_joined, scheme)

st.subheader("抽出ページ（単独行ラベルで区切り）— 概観")
if len(segments) == 0:
    st.warning("単独行のページラベルが見つからず、本文セグメントを作れませんでした。")
else:
    df_segments_overview = pd.DataFrame([{
        "page_label": s["page_label"],
        "char_count": len(s["body"]),
        "preview": s["body"][:120].replace("\n"," ") + ("…" if len(s["body"])>120 else "")
    } for s in segments])
    st.dataframe(df_segments_overview, use_container_width=True)

# =========================
# ページラベル連番チェック（照合前に表示）
# =========================
st.subheader("📑 ページラベル検証（連番チェック）")

def valid_and_reason(label: str, scheme: str, prev_ok: Optional[str]) -> Tuple[bool, str]:
    """
    ラベル妥当性：
    - 方式(1)：連番チェック（n == prev+1 がOK）
    - 方式(2)：章-ページ形式の連番チェック（(c,p) → (c, p+1) or (c+1, 1) がOK）
    """
    if scheme.startswith("(1)"):
        try:
            n = int(label)
        except Exception:
            return False, "連番形式で数値化できない"
        if prev_ok is None:
            return True, ""
        try:
            prev = int(prev_ok)
        except Exception:
            return True, ""
        return (True, "") if n == prev + 1 else (False, "非連番")
    else:
        parts = label.split("-")
        if not (len(parts) >= 2 and all(p.isdigit() for p in parts)):
            return False, "章-ページ形式でない"
        chap, page_n = int(parts[0]), int(parts[1])
        if prev_ok is None:
            return True, ""
        pparts = prev_ok.split("-")
        if not (len(pparts) >= 2 and all(p.isdigit() for p in pparts)):
            return True, ""
        pchap, ppage = int(pparts[0]), int(pparts[1])
        if (chap == pchap and page_n == ppage + 1) or (chap == pchap + 1 and page_n == 1):
            return True, ""
        return False, "非連番"

rows_check = []
prev_ok = None
for s in segments:
    ok, reason = valid_and_reason(s["page_label"], scheme, prev_ok)
    if ok:
        prev_ok = s["page_label"]
    rows_check.append({
        "page_label": s["page_label"],
        "valid": ok,
        "reason": "" if ok else reason,
        "char_count": len(s["body"]),
        "preview": s["body"][:100].replace("\n", " ") + ("…" if len(s["body"]) > 100 else ""),
    })
df_check = pd.DataFrame(rows_check)
st.dataframe(df_check, use_container_width=True)
warn_df = df_check[~df_check["valid"]]
if len(warn_df):
    st.warning(f"⚠️ 非連番などの不正ラベル: {len(warn_df)} 件")

# ==== 有効（valid=True）のページだけをTXTで一括ダウンロード ====
st.subheader("📄 抽出ページ（valid=True のみ）をTXTで保存")
if len(segments):
    # valid=True の label セット
    valid_labels = {row["page_label"] for row in rows_check if row["valid"]}
    valid_segments = [s for s in segments if s["page_label"] in valid_labels]

    if valid_segments:
        sep = "＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝"
        buf_txt = io.StringIO()

        for s in valid_segments:
            page_label = str(s.get("page_label", ""))
            body = str(s.get("body", ""))
            char_count = len(body)

            buf_txt.write(f"{sep}\n")
            buf_txt.write(f"page_label: {page_label}    char_count: {char_count}\n")
            buf_txt.write(f"{sep}\n")
            buf_txt.write(body.rstrip() + "\n\n")

        st.download_button(
            "📥 抽出ページTXT（valid=True のみ）を保存",
            data=buf_txt.getvalue().encode("utf-8"),
            file_name="extracted_pages_valid_only.txt",
            mime="text/plain",
            use_container_width=True,
        )
    else:
        st.info("valid=True のページがありません。")

# =========================
# 目次タイトルと本文の照合（順送り）
# =========================
def slice_body(text: str) -> str:
    if excerpt_chars and excerpt_chars > 0:
        return text[:excerpt_chars]
    return text

# seg_index: page_label → segment body
seg_index = {s["page_label"]: s["body"] for s in segments}

def find_partial(title: str, body: str) -> Tuple[bool, str]:
    """
    部分一致：タイトルの先頭 5 / 4 / 3 文字のいずれかが本文に含まれるか。
    見つかったら抜粋を返す。
    """
    t = title.strip()
    for klen in (5, 4, 3):
        if len(t) >= klen:
            key = t[:klen]
            pos = body.find(key)
            if pos >= 0:
                snippet = body[max(0, pos-20):pos+klen+20].replace("\n", " ")
                return True, snippet
    return False, ""

def check_toc_by_order(toc_lines: List[str], seg_index: Dict[str,str], pages_text: List[str]) -> pd.DataFrame:
    """
    1) 目次ラベルに合致するセグメント本文で検索（最優先）
    2) 見つからなければ全ページを頭から検索
    """
    rows = []
    for toc in toc_lines:
        if " ::: " not in toc:
            continue
        title, label = toc.split(" ::: ", 1)
        title = title.strip()
        label = label.strip()

        found_page = "-"
        status = "未検出"
        matched_line = "-"

        # 1) ラベル一致ページの本文を優先（valid かどうかは問わず本文を参照）
        body = seg_index.get(label, "")
        if body:
            body_s = slice_body(body)
            lines = [ln.rstrip() for ln in body_s.split("\n") if ln.strip()]

            # 完全一致（行全体）
            hit = next((ln for ln in lines if ln.strip() == title), None)
            if hit:
                status = "一致"
                matched_line = hit
            else:
                # 行内にタイトルを含む
                hit = next((ln for ln in lines if title in ln), None)
                if hit:
                    status = "一致（行内部分一致）"
                    matched_line = hit
                else:
                    ok, snippet = find_partial(title, body_s)
                    if ok:
                        status = "部分一致"
                        matched_line = snippet

        # 2) まだ未検出なら、全ページを順に走査（行単位）
        if status.startswith("未検出"):
            for i, ptxt in enumerate(pages_text):
                body_s = slice_body(ptxt)
                lines = [ln.rstrip() for ln in body_s.split("\n") if ln.strip()]

                hit = next((ln for ln in lines if ln.strip() == title), None)
                if hit:
                    status = "一致"
                    matched_line = hit
                    found_page = i + 1
                    break

                hit = next((ln for ln in lines if title in ln), None)
                if hit:
                    status = "一致（行内部分一致）"
                    matched_line = hit
                    found_page = i + 1
                    break

                ok, snippet = find_partial(title, body_s)
                if ok:
                    status = "部分一致"
                    matched_line = snippet
                    found_page = i + 1
                    break

        rows.append({
            "タイトル": title,
            "目次ラベル": label,
            "本文内ページ": found_page,
            "判定": status,
            "一致テキスト行": matched_line,
        })

    return pd.DataFrame(rows)

df_result = check_toc_by_order(toc_lines, seg_index, pages_text)

st.subheader("🔍 照合結果（行ベース）")
st.dataframe(df_result, use_container_width=True)
st.caption("※ 目次の各行（タイトル）を順に見て、まず同ラベルの本文セグメントで照合し、見つからない場合は全ページを走査。完全一致／部分一致の行を抜粋表示します。")

# 統計
summary = df_result["判定"].value_counts().to_dict()
st.markdown(f"**結果概要**: {summary}")

# ダウンロード（CSV）
buf = io.StringIO()
df_result.to_csv(buf, index=False)
st.download_button(
    "📥 照合結果をCSVで保存",
    data=buf.getvalue().encode("utf-8-sig"),
    file_name="toc_check_local_result.csv",
    mime="text/csv",
    use_container_width=True,
)
