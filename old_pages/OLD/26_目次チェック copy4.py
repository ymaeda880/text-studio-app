# -*- coding: utf-8 -*-
# pages/26_目次チェック.py — GPT API 不使用版：目次候補 ↔ 本文（行スキャン）照合
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
st.set_page_config(page_title="📄 目次チェック（ローカル照合）", page_icon="📄", layout="wide")
st.title("📄 目次チェック（ローカル照合 / 行スキャン）")
st.caption("GPT を使わず、目次候補（タイトル）を本文に対して **行ごとに順番に** 照合します。")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])

c1, c2, c3 = st.columns([1.3, 1.1, 1.2])
with c1:
    scheme = st.radio("ページ方式", ["(1) 1,2,3,4, …", "(2) 1-1,1-2,2-1,2-2, …"], index=1, horizontal=True)
with c2:
    toc_join_front = st.checkbox("目次抽出は冒頭10pを連結", value=True)
with c3:
    run = st.button("▶ 解析・照合を実行", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### 出力オプション")
    max_toc_lines = st.number_input("目次候補の上限行数", min_value=10, max_value=500, value=120, step=10)
    show_debug = st.checkbox("内部情報を表示（デバッグ）", value=False)

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
LEADERS = r"[\.．・…]+"                                     # ドットリーダー群

def z2h_numhy(s: str) -> str:
    """全角数字→半角、ハイフン類を '-' に正規化、全角空白→半角空白"""
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return re.sub(HY, "-", s)

def normalize_strict(s: str) -> str:
    """軽い正規化：z2h + 連続空白を単一空白 + 末尾のドットリーダー除去"""
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS}\s*$", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def normalize_loose(s: str) -> str:
    """強めの正規化：空白全除去（行末リーダーも除去）"""
    s = z2h_numhy(s)
    s = re.sub(rf"{LEADERS}$", "", s)
    return re.sub(r"\s+", "", s)


# =========================
# 目次候補の抽出（行末にページラベルがある行）
# =========================
def build_label_tail_regex(scheme: str) -> re.Pattern:
    if scheme.startswith("(1)"):
        tail = r"(?P<label>[0-9０-９]{1,6})"          # 連番
    else:
        tail = rf"(?P<label>[0-9０-９]+(?:{HY}[0-9０-９]+)+)"  # 章-ページ
    pat = rf"""
        ^(?P<head>.*?)                               # 左側本文
        (?:\s*{LEADERS}\s*|\s{{2,}})?                # ドットリーダー or 連続空白
        {tail}\s*$                                   # 行末ラベル
    """
    return re.compile(pat, re.X)

LABEL_TAIL_RE = build_label_tail_regex(scheme)

def extract_toc_lines(fulltext: str, limit: int) -> List[str]:
    """
    目次候補を抽出：行頭が『第』or 数字で始まり、文字（和/英）を含む行のみ。
    出力形式： 'タイトル ::: ラベル'
    """
    lines = [l.rstrip() for l in fulltext.replace("\r\n","\n").replace("\r","\n").split("\n")]
    head_ok   = re.compile(r"^(第|[0-9０-９])")
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

        head  = re.sub(rf"\s*{LEADERS}\s*$", "", m.group("head")).strip()
        label = z2h_numhy(m.group("label"))

        if len(head) <= 1:
            continue

        out.append(f"{head} ::: {label}")
        if len(out) >= limit:
            break
    return out


# 目次候補抽出（前半ページから）
front_n = min(10, len(pages_text))
sample_text = "\n".join(pages_text[:front_n]) if toc_join_front else pages_text[0]
toc_lines = extract_toc_lines(sample_text, limit=max_toc_lines)

st.subheader("抽出された目次候補（上位）")
if not toc_lines:
    st.warning("目次候補が見つかりませんでした。")
    st.stop()
st.code("\n".join(toc_lines[:80]))


# =========================
# 単独行ラベルで本文を分割（抽出ページを作る）
# =========================
def build_label_line_regex(scheme: str) -> re.Pattern:
    if scheme.startswith("(1)"):
        core = r"[0-9０-９]{1,6}"                 # 連番
    else:
        core = rf"[0-9０-９]+(?:{HY}[0-9０-９]+)+"  # 章-ページ
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_LINE_RE = build_label_line_regex(scheme)

def split_segments_by_label(all_text: str) -> List[Dict[str, Any]]:
    """
    全文（連結）を、単独行のページラベルで分割し、[{'page_label','body'}] を返す。
    """
    txt = normalize_strict(all_text.replace("\r\n","\n").replace("\r","\n"))
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
        body  = txt[start:end].lstrip("\n ")
        segs.append({"page_label": label, "body": body})
    return segs


all_text_joined = "\n".join(pages_text)
segments = split_segments_by_label(all_text_joined)

st.subheader("抽出ページ（単独行ラベルで区切り）— 概観")
if not segments:
    st.warning("単独行のページラベルが見つからず、抽出ページが作成できませんでした。")
else:
    df_segments_overview = pd.DataFrame([{
        "page_label": s["page_label"],
        "char_count": len(s["body"]),
        "preview": s["body"][:120].replace("\n"," ") + ("…" if len(s["body"])>120 else "")
    } for s in segments])
    st.dataframe(df_segments_overview, use_container_width=True)


# =========================
# ラベル妥当性（連番チェックのみ）→ valid=True のみを採用
# =========================
st.subheader("📑 ページラベル検証（連番チェック）")
def valid_and_reason(label: str, scheme: str, prev_ok: Optional[str]) -> Tuple[bool, str]:
    """
    方式(1)：n == prev+1 で OK
    方式(2)：(c,p) → (c,p+1) or (c+1,1) で OK
    """
    if scheme.startswith("(1)"):
        try:
            n = int(label)
        except Exception:
            return False, "連番で数値化できない"
        if prev_ok is None:
            return True, ""
        try:
            prev = int(prev_ok)
        except Exception:
            return True, ""
        return (True, "") if n == prev + 1 else (False, "非連番")

    # 章-ページ
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


rows_check: List[Dict[str, Any]] = []
prev_ok: Optional[str] = None
for s in segments:
    ok, reason = valid_and_reason(s["page_label"], scheme, prev_ok)
    if ok:
        prev_ok = s["page_label"]
    rows_check.append({
        "page_label": s["page_label"],
        "valid": ok,
        "reason": "" if ok else reason,
        "char_count": len(s["body"]),
        "preview": s["body"][:100].replace("\n"," ") + ("…" if len(s["body"])>100 else "")
    })
df_check = pd.DataFrame(rows_check)
st.dataframe(df_check, use_container_width=True)

# valid=True の抽出ページのみ採用
valid_segments = [s for s in segments if any((r["page_label"]==s["page_label"] and r["valid"]) for r in rows_check)]
seg_index: Dict[str, str] = {s["page_label"]: s["body"] for s in valid_segments}

# 抽出ページ（validのみ）TXTダウンロード
if valid_segments:
    txt_buf = io.StringIO()
    for s in valid_segments:
        header = f"==== page_label={s['page_label']} (chars={len(s['body'])}) ====\n"
        txt_buf.write(header)
        txt_buf.write(s["body"].rstrip("\n") + "\n\n")
    st.download_button(
        "📥 抽出ページTXTをダウンロード（valid=True のみ）",
        data=txt_buf.getvalue().encode("utf-8"),
        file_name="extracted_pages_valid.txt",
        mime="text/plain"
    )


# =========================
# 目次タイトル ↔ 本文（行スキャン）照合
# =========================
def scan_lines_for_match(title_raw: str, body: str) -> Tuple[str, str]:
    """
    本文 body を改行で分割して上から順にチェック。
    戻り値: (判定, 一致テキスト行)
      - "一致"                    : 厳しめの完全一致（strict）
      - "一致（空白差吸収）"      : 空白全除去一致（loose）
      - "一致（行内部分一致）"    : 行にタイトル文字列が含まれる
      - "部分一致（N文字）"        : タイトル先頭 N=5/4/3 の部分一致
      - "未検出"
    """
    title_strict = normalize_strict(title_raw)
    title_loose  = normalize_loose(title_raw)

    lines = [ln for ln in body.split("\n")]  # 改行は保持したまま比較用に別で正規化
    for ln in lines:
        if not ln.strip():
            continue
        ln_strict = normalize_strict(ln)
        if ln_strict == title_strict:
            return "一致", ln.rstrip("\n")
        ln_loose = normalize_loose(ln)
        if ln_loose == title_loose:
            return "一致（空白差吸収）", ln.rstrip("\n")
        if title_raw in ln:
            return "一致（行内部分一致）", ln.rstrip("\n")

        for klen in (5, 4, 3):
            if len(title_raw) >= klen and title_raw[:klen] in ln:
                return f"部分一致（{klen}文字）", ln.rstrip("\n")

    return "未検出", "-"


def check_toc_by_order(toc_lines: List[str],
                       seg_index: Dict[str, str],
                       pages_text: List[str]) -> pd.DataFrame:
    """
    1) 目次ラベルと一致する抽出ページ（valid=True）内の行を上から順にスキャン
    2) 見つからなければ全ページ本文を順に行スキャン
    """
    out_rows: List[Dict[str, Any]] = []

    for toc in toc_lines:
        if " ::: " not in toc:
            continue
        title_raw, label = toc.split(" ::: ", 1)
        title_raw = title_raw.strip()
        label     = label.strip()

        # 1) ラベル一致ページで探索
        body = seg_index.get(label, "")
        status = "未検出"
        matched = "-"
        found_page_num: Optional[int] = None

        if body:
            status, matched = scan_lines_for_match(title_raw, body)

        # 2) まだ未検出なら全ページを順に探索
        if status == "未検出":
            for i, ptxt in enumerate(pages_text):
                stt, m = scan_lines_for_match(title_raw, ptxt)
                if stt != "未検出":
                    status, matched = stt, m
                    found_page_num = i + 1
                    break

        out_rows.append({
            "タイトル": title_raw,
            "目次ラベル": label,
            "本文内ラベル": label if body else "-",
            "本文内ページ": found_page_num if found_page_num is not None else "-",
            "判定": status,
            "一致テキスト行": matched,
        })

    return pd.DataFrame(out_rows)


df_result = check_toc_by_order(toc_lines, seg_index, pages_text)

st.subheader("🔍 照合結果（行ベース）")
st.dataframe(df_result, use_container_width=True)
st.caption("※ 目次の各行を順に辿り、まず同ラベルの抽出ページ（valid=True）で行スキャン、見つからなければ全ページを行スキャンします。")

# 集計
summary = df_result["判定"].value_counts().to_dict()
st.markdown(f"**結果概要**: {summary}")

# ダウンロード（CSV）
buf = io.StringIO()
df_result.to_csv(buf, index=False)
st.download_button(
    "📥 照合結果CSVを保存",
    data=buf.getvalue().encode("utf-8-sig"),
    file_name="toc_check_local_result.csv",
    mime="text/csv"
)

# デバッグ表示
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.write({"valid_segments": len(valid_segments), "segments_all": len(segments)})
