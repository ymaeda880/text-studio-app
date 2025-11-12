# -*- coding: utf-8 -*-
# pages/24_図表クロスチェック.py
# 図/表/図表の見出し ↔ 本文参照を、PDF内の「ページラベル」（1-2, 3-10, 序-1, 資-2 等）単位でクロスチェック
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
st.set_page_config(page_title="🖼️ 図表クロスチェック（ページラベル対応）", page_icon="🖼️", layout="wide")
st.title("🖼️ 図表クロスチェック（見出し ↔ 本文参照／ページラベル対応）")
st.caption("PDFから『ページラベル』（1-2 / 序-1 等）を抽出して本文を分割し、図表見出しと参照の突合を行います。")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])

c1, c2, c3 = st.columns([1.2, 1.1, 1.2])
with c1:
    join_front = st.checkbox("先頭10ページを結合してヘッダ例を表示", value=True)
with c2:
    min_caption = st.number_input("見出しの最短文字数（見出し抽出の下限）", 0, 200, 4, 1)
with c3:
    run = st.button("▶ 解析を実行", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    strict_kind_match = st.checkbox(
        "『図表n』見出しは図/表参照と別扱い（厳格）",
        value=True,
        help="OFFにすると『図表1』見出しに対して『図1』『表1』参照も一致扱い（寛容）。"
    )
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
# 正規化ユーティリティ（目次チェック準拠）
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0Dー–—−]"  # ハイフン類
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"                               # リーダ候補
LEADERS_SPACED = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"          # 空白を挟むリーダー列
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"                   # 英字/かな/漢字

def z2h_numhy(s: str) -> str:
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝", "0123456789()[]{}"))
    return re.sub(HY, "-", s)

def normalize_strict(s: str) -> str:
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)   # 行末リーダー列除去
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def norm_label_core(s: str) -> str:
    """(1)/(１２)等→数字、全角→半角、ハイフン統一"""
    s = z2h_numhy(s)
    s = re.sub(r"^[\(\[]\s*([0-9]+)\s*[\)\]]$", r"\1", s)  # (1)/[1] → 1
    return s.strip().strip("．.：:、，")


# =========================
# ページラベル（行単独）を検出して本文を分割
#   許容ラベル:
#     1) 連番           12
#     2) 章-ページ      3-2, 10-4-2
#     3) シリーズ-数字  序-1, 資-2, 付-3, A-10 など（先頭に和文/英字の単語）
# =========================
def build_label_line_regex_mixed() -> re.Pattern:
    core_seq    = r"[0-9０-９]{1,6}"
    core_chap   = rf"[0-9０-９]+(?:{HY}[0-9０-９]+)+"
    core_series = rf"{ALPHAJP}{HY}[0-9０-９]+"
    core = rf"(?:{core_seq}|{core_chap}|{core_series})"
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_LINE_RE = build_label_line_regex_mixed()

def split_segments_by_label(all_text: str) -> List[Dict[str, Any]]:
    """
    全文を単独行のページラベルで分割し、[{'page_label','body'}] を返す。
    見つからない場合は空配列（→後段で数値ページにフォールバック）。
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
        label = norm_label_core(m.group("label"))
        start = next_nonempty_pos(m.end())
        end   = matches[i+1].start() if i+1 < len(matches) else len(txt)
        body  = txt[start:end].lstrip("\n ")
        segs.append({"page_label": label, "body": body})
    return segs


# === セグメント化（ページラベル単位） ===
all_text_joined = "\n".join(pages_text)
segments = split_segments_by_label(all_text_joined)

if not segments:
    st.warning("単独行の『ページラベル』が見つかりませんでした。数値ページでフォールバックします。")
    # フォールバック：数値ページごとに擬似セグメント
    segments = [{"page_label": str(i+1), "body": normalize_strict(p)} for i, p in enumerate(pages_text)]

st.subheader("抽出ページ（ページラベルで区切り）— 概観")
df_segments_overview = pd.DataFrame([{
    "ページラベル": s["page_label"],
    "char_count": len(s["body"]),
    "preview": s["body"][:120].replace("\n"," ") + ("…" if len(s["body"])>120 else "")
} for s in segments])
st.dataframe(df_segments_overview, use_container_width=True)


# =========================
# 図表見出し／本文参照のパターン
# =========================
# 見出し：行全体が「(図|表|図表|Fig|Table) + 番号 + タイトル」で構成
RE_HEAD_LINE = re.compile(
    rf"""(?ix) ^
    \s*
    (?P<kind>図表|図|表|Fig(?:\.|ure)?|Tab(?:\.|le)?)
    \s*[:：．.]?\s*
    (?P<label>
        [0-9]+(?:-{1}[0-9]+)* |      # 12 / 1-2 / 2-10-3
        \([0-9]+\) | \[[0-9]+\]      # (1) / [1]
    )
    (?P<after>
        (?:\s*(?:{LEADER_CHARS_CLASS}|\:|：))*    # 記号
        .*                                        # タイトル
    )? $
""")

# 本文参照：行中に出現するものを全て拾う
RE_REF_INLINE = re.compile(
    rf"""(?ix)
    (?P<kind>図表|図|表|Fig(?:\.|ure)?|Tab(?:\.|le)?)
    \s*[:：．.]?\s*
    (?P<label>
        [0-9]+(?:-{1}[0-9]+)* |
        \([0-9]+\) | \[[0-9]+\]
    )
    """
)

def norm_kind(k: str) -> str:
    k2 = k.lower()
    if k2.startswith("fig"): return "図"
    if k2.startswith("tab"): return "表"
    return "図表" if "図表" in k else ("図" if "図" in k else "表")


# =========================
# 抽出（ページラベル単位）
# =========================
def extract_headings_from_segments(segs: List[Dict[str, str]], min_caption: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for seg in segs:
        label_page = seg["page_label"]
        for raw in seg["body"].split("\n"):
            line = normalize_strict(raw)
            if not line: 
                continue
            m = RE_HEAD_LINE.match(line)
            if not m:
                continue
            kind = norm_kind(m.group("kind"))
            num  = norm_label_core(m.group("label"))
            title = (m.group("after") or "").strip()
            if len(title) < min_caption:
                title = line[m.end():].strip() or line
            title = title[:200] + ("…" if len(title) > 200 else "")
            out.append({
                "ページラベル": label_page,
                "種別": kind,
                "番号": num,
                "見出し": title,
                "行全文": line,
            })
    return out

def extract_refs_from_segments(segs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for seg in segs:
        label_page = seg["page_label"]
        for raw in seg["body"].split("\n"):
            line = normalize_strict(raw)
            if not line:
                continue
            for m in RE_REF_INLINE.finditer(line):
                kind = norm_kind(m.group("kind"))
                num  = norm_label_core(m.group("label"))
                out.append({
                    "ページラベル": label_page,
                    "種別": kind,
                    "番号": num,
                    "周辺抜粋": line[:200] + ("…" if len(line) > 200 else ""),
                })
    return out


heads = extract_headings_from_segments(segments, min_caption)
refs  = extract_refs_from_segments(segments)

df_heads = pd.DataFrame(heads)
df_refs  = pd.DataFrame(refs)

if df_heads.empty and df_refs.empty:
    st.warning("図表の見出し・参照が検出できませんでした。書式や閾値を調整してください。")
    st.stop()

st.subheader("📌 見出し（図/表/図表）検出結果")
st.dataframe(df_heads.sort_values(["ページラベル","種別","番号"]) if not df_heads.empty else pd.DataFrame(), use_container_width=True)

st.subheader("🔎 本文参照の検出結果")
st.dataframe(df_refs.sort_values(["ページラベル","種別","番号"]) if not df_refs.empty else pd.DataFrame(), use_container_width=True)


# =========================
# 照合（ページラベルを主キーに）
# =========================
def kind_keys(kind: str, strict: bool) -> List[str]:
    if strict:
        return [kind]
    if kind == "図表":
        return ["図表", "図", "表"]
    return [kind, "図表"]

def cross_check_by_label(head_df: pd.DataFrame, ref_df: pd.DataFrame, strict: bool) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # 参照を { (ページラベル, 種別, 番号) : [参照…] } に
    refs_map: Dict[Tuple[str,str,str], List[Dict[str,Any]]] = {}
    for _, r in ref_df.iterrows():
        refs_map.setdefault((r["ページラベル"], r["種別"], r["番号"]), []).append(r)

    # 見出し→参照
    rows_h2r: List[Dict[str, Any]] = []
    for _, h in head_df.iterrows():
        hits: List[Dict[str, Any]] = []
        for k in kind_keys(h["種別"], strict):
            key = (h["ページラベル"], k, h["番号"])
            if key in refs_map:
                for rr in refs_map[key]:
                    hits.append({"ページラベル": rr["ページラベル"], "抜粋": rr["周辺抜粋"]})
        rows_h2r.append({
            "ページラベル": h["ページラベル"],
            "見出し_種別": h["種別"],
            "見出し_番号": h["番号"],
            "見出し_タイトル": h.get("見出し",""),
            "参照ヒット数": len(hits),
            "参照あり": "Yes" if hits else "No",
        })
    df_h2r = pd.DataFrame(rows_h2r)

    # 参照→見出し存在
    head_keys = set((row["ページラベル"], row["種別"], row["番号"]) for _, row in head_df.iterrows())
    if not strict:
        # 寛容：図表<->図/表を相互に展開
        expanded = set()
        for pl, kind, num in head_keys:
            for kk in kind_keys(kind, strict=False):
                expanded.add((pl, kk, num))
        head_keys = expanded

    rows_r2h: List[Dict[str, Any]] = []
    for _, r in ref_df.iterrows():
        exists = (r["ページラベル"], r["種別"], r["番号"]) in head_keys
        rows_r2h.append({
            "ページラベル": r["ページラベル"],
            "参照_種別": r["種別"],
            "参照_番号": r["番号"],
            "対応見出しあり": "Yes" if exists else "No",
            "周辺抜粋": r["周辺抜粋"],
        })
    df_r2h = pd.DataFrame(rows_r2h)
    return df_h2r, df_r2h


df_h2r, df_r2h = cross_check_by_label(df_heads, df_refs, strict=strict_kind_match)

st.subheader("✅ 見出し → 参照 照合（ページラベル単位）")
st.dataframe(df_h2r.sort_values(["ページラベル","見出し_種別","見出し_番号"]), use_container_width=True)

st.subheader("✅ 参照 → 見出し 存在確認（ページラベル単位）")
st.dataframe(df_r2h.sort_values(["ページラベル","参照_種別","参照_番号"]), use_container_width=True)

summary = {
    "見出し数": int(len(df_heads)),
    "参照数": int(len(df_refs)),
    "見出しの参照なし件数": int((df_h2r["参照あり"]=="No").sum()),
    "参照の見出し欠落件数": int((df_r2h["対応見出しあり"]=="No").sum()),
}
st.markdown(f"**集計**: {summary}")


# =========================
# Excel出力（番号/ページラベルは文字列固定）
# =========================
xlsx_buf = io.BytesIO()
with pd.ExcelWriter(xlsx_buf, engine="xlsxwriter") as writer:
    if not df_heads.empty:
        df_heads.sort_values(["ページラベル","種別","番号"]).to_excel(writer, index=False, sheet_name="headings")
    if not df_refs.empty:
        df_refs.sort_values(["ページラベル","種別","番号"]).to_excel(writer, index=False, sheet_name="references")
    df_h2r.to_excel(writer, index=False, sheet_name="H_to_R")
    df_r2h.to_excel(writer, index=False, sheet_name="R_to_H")

    wb = writer.book
    text_fmt = wb.add_format({"num_format": "@"})
    wrap = wb.add_format({"text_wrap": True})
    bold = wb.add_format({"bold": True})

    def format_sheet(sheet: str, cols: List[str]):
        ws = writer.sheets[sheet]
        for j, name in enumerate(cols):
            # 文字列固定にして Excel の日付化を防止
            if name in ("番号", "ページラベル") or name.endswith("番号"):
                ws.set_column(j, j, 16, text_fmt)
            elif "見出し" in name or "抜粋" in name or "タイトル" in name:
                ws.set_column(j, j, 48, wrap)
            else:
                ws.set_column(j, j, 12)
            ws.write(0, j, name, bold)
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, 100000, len(cols)-1)

    for sheet, df_ in [
        ("headings", df_heads) if not df_heads.empty else None,
        ("references", df_refs) if not df_refs.empty else None,
        ("H_to_R", df_h2r),
        ("R_to_H", df_r2h),
    ]:
        if sheet:
            format_sheet(sheet, df_.columns.tolist())

st.download_button(
    "📥 Excelで保存（headings / references / H_to_R / R_to_H）",
    data=xlsx_buf.getvalue(),
    file_name="figure_table_crosscheck_by_page_label.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.write({
        "segments": len(segments),
        "heads_detected": 0 if df_heads is None else len(df_heads),
        "refs_detected": 0 if df_refs is None else len(df_refs),
        "strict_kind_match": strict_kind_match
    })
