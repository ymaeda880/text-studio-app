# -*- coding: utf-8 -*-
# pages/24_図表チェック.py — GPT不使用：図表見出し ↔ 本文参照の照合（全件文脈つき）
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
st.set_page_config(page_title="🧾 図表チェック（ローカル照合）", page_icon="🧾", layout="wide")
st.title("🧾 図表チェック（見出し ↔ 参照 の照合）")
st.caption("見出しは行頭の「図/表/図表 + 番号 + タイトル（1行）」、参照は本文行中の「図/表/図表 + 番号」。見出し行は参照から除外。参照文脈は全件を page_label＋行番号つきで収集。")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 解析・照合を実行", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    context_radius = st.number_input("参照前後の行数（文脈）", min_value=0, max_value=10, value=2, step=1)
    show_debug = st.checkbox("内部情報（抽出中間）を表示", value=False)

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
# 正規化・ページラベル抽出（目次チェック準拠）
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D]"   # 各種ハイフン
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"
LEADERS_SPACED = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"  # 英/かな/漢

def z2h_numhy(s: str) -> str:
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝", "0123456789()[]{}"))
    return re.sub(HY, "-", s)

def normalize_strict(s: str) -> str:
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

# 「行単独のページラベル」検出（連番 / 章-ページ / シリーズ-番号）
def build_label_line_regex_mixed() -> re.Pattern:
    core_seq    = r"[0-9０-９]{1,6}"
    core_chap   = rf"[0-9０-９]+(?:{HY}[0-9０-９]+)+"
    core_series = rf"{ALPHAJP}{HY}[0-9０-９]+"
    core = rf"(?:{core_seq}|{core_chap}|{core_series})"
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_LINE_RE = build_label_line_regex_mixed()

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
    st.warning("単独行のページラベルが見つからず、抽出ページが作成できませんでした（PDF版面により行単独とならない場合があります）。")
else:
    df_segments_overview = pd.DataFrame([{
        "page_label": s["page_label"],
        "char_count": len(s["body"]),
        "preview": s["body"][:120].replace("\n"," ") + ("…" if len(s["body"])>120 else "")
    } for s in segments])
    st.dataframe(df_segments_overview, use_container_width=True)

# ラベルの連番妥当性（簡易）
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
        "valid": ok,
        "reason": "" if ok else reason,
        "char_count": len(s["body"]),
        "preview": s["body"][:100].replace("\n"," ") + ("…" if len(s["body"])>100 else "")
    })
df_check = pd.DataFrame(rows_check)
st.dataframe(df_check, use_container_width=True)

valid_segments = [s for s in segments if any((r["page_label"]==s["page_label"] and r["valid"]) for r in rows_check)]

# --- ここは rows_check/df_check の後、valid_segments を作った直後に追加 ---
# valid ラベル集合
valid_label_set = {s["page_label"] for s in segments
                   if any((r["page_label"] == s["page_label"] and r["valid"]) for r in rows_check)}

# ==== PDFページ → validな page_label を引ける辞書を用意 ====
# 各ページ本文内を個別に走査して「行単独のページラベル(LABEL_LINE_RE)」を拾い、
# 連番検証(valid_and_reason_auto)に通ったものだけを page_to_valid_label[pidx] に登録
page_to_valid_label: Dict[int, str] = {}
_prev_ok: Optional[str] = None
for pidx, ptxt in enumerate(pages_text, start=1):
    txt = normalize_strict(ptxt.replace("\r\n","\n").replace("\r","\n"))
    m = LABEL_LINE_RE.search(txt)
    if not m:
        continue
    cand = z2h_numhy(m.group("label"))
    ok, _ = valid_and_reason_auto(cand, _prev_ok)
    if ok:
        _prev_ok = cand
        page_to_valid_label[pidx] = cand



# PDFページ順 → page_label の対応（緩い対応：segments順を流用、足りなければ連番）
page_labels = [s["page_label"] for s in segments] if segments else [str(i+1) for i in range(len(pages_text))]
if len(page_labels) < len(pages_text):
    # 足りない分は末尾に連番を補完
    page_labels = page_labels + [str(i+1) for i in range(len(page_labels), len(pages_text))]


# =========================
# 図表 見出し抽出 ＆ 参照抽出（見出し行は参照から除外）
# =========================
# ドット類・数値トークン（2. 2-1 / ２．１－１ / （１） を許容）
DOT = r"[\.．・･]"
NUM = r"[0-9０-９]+"
NUM_TOKEN = rf"""
(?:                                     # ① ドット区切り + ハイフン区切り
    {NUM}
    (?:\s*{DOT}\s*{NUM})*               # 2.2 や 2． 2 など
    (?:\s*-\s*{NUM})*                   # -1 や -１
  |
    [（(]\s*{NUM}\s*[）)]               # ② （１）/ (12)
)
"""
NUM_TOKEN_RE = re.compile(NUM_TOKEN, re.X)

# 見出し（行頭）: 図/表/図表 + 番号 + タイトル（1行）
HEADING_RE = re.compile(
    rf"^\s*(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})\s*[:：.\-．、]?\s*(?P<title>.+?)\s*$",
    re.X
)

# 本文参照（行中）: 図/表/図表 + 番号
REF_RE = re.compile(
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})(?![0-9])",
    re.X
)

def canon_num(num: str) -> str:
    """番号をキー用に正規化：全角→半角、（1）→1、ドット類→'.'、ハイフン類→'-'、空白除去。"""
    s = z2h_numhy(num)
    s = re.sub(r"[()（）]", "", s)     # （1）→1
    s = re.sub(DOT, ".", s)           # ．・ → .
    s = re.sub(r"\s*\.\s*", ".", s)   # '2 . 2' → '2.2'
    s = re.sub(r"\s*-\s*", "-", s)    # '2 - 1' → '2-1'
    s = re.sub(r"\s+", "", s)         # 残りの空白除去
    return s

def canon_label(kind: str, num: str) -> str:
    return f"{kind}{canon_num(num)}"

# ---- 見出し抽出（行番号保持・page_label付与）
heading_rows: List[Dict[str, Any]] = []
heading_line_index: set[Tuple[int,int]] = set()  # {(pidx, line_no)} 見出し行の座標（参照除外に使う）

for pidx, page_text in enumerate(pages_text, start=1):
    #page_label = page_labels[pidx-1] if pidx-1 < len(page_labels) else str(pidx)
    page_label = page_to_valid_label.get(pidx, "-")
    lines = page_text.replace("\r\n","\n").replace("\r","\n").split("\n")
    for ln_no, raw_line in enumerate(lines, start=1):
        line = normalize_strict(raw_line)
        if not line:
            continue
        m = HEADING_RE.match(line)
        if not m:
            continue
        kind = m.group("kind")
        num  = m.group("num")
        title= m.group("title").strip()
        heading_rows.append({
            "図表種類": kind,
            "図表番号": f"{kind}{z2h_numhy(num)}",
            "図表キー": canon_label(kind, num),
            "見出しタイトル": title,
            "見出しページ(連番)": pidx,
            "見出しpage_label": page_label,
            "見出し行番号": ln_no,
        })
        heading_line_index.add((pidx, ln_no))

df_heads = pd.DataFrame(heading_rows) if heading_rows else pd.DataFrame(columns=[
    "図表種類","図表番号","図表キー","見出しタイトル","見出しページ(連番)","見出しpage_label","見出し行番号"
])

# ---- 本文参照抽出（見出し行を除外）＋ 文脈（±N行）
ref_rows: List[Dict[str, Any]] = []
for pidx, page_text in enumerate(pages_text, start=1):
    # page_label = page_labels[pidx-1] if pidx-1 < len(page_labels) else str(pidx)
    page_label = page_to_valid_label.get(pidx, "-")
    lines = page_text.replace("\r\n","\n").replace("\r","\n").split("\n")

    for ln_no, raw_line in enumerate(lines, start=1):
        # 見出し行は本文参照から除外
        if (pidx, ln_no) in heading_line_index:
            continue

        line = raw_line  # 文脈は元の改行・空白感を保持したいので normalize しない
        for m in REF_RE.finditer(line):
            kind = m.group("kind")
            num  = m.group("num")
            # 文脈抽出（±context_radius 行）
            i0 = max(1, ln_no - context_radius)
            i1 = min(len(lines), ln_no + context_radius)
            ctx = "\n".join(lines[i0-1:i1])

            ref_rows.append({
                "参照テキスト": m.group(0),
                "図表キー": canon_label(kind, num),
                "参照ページ(連番)": pidx,
                "参照page_label": page_label,   # ← valid 由来の page_label
                "参照行番号": ln_no,
                "参照前後（行）": ctx,
            })

df_refs = pd.DataFrame(ref_rows) if ref_rows else pd.DataFrame(columns=[
    "参照テキスト","図表キー","参照ページ(連番)","参照page_label","参照行番号","参照前後（行）"
])

col1, col2 = st.columns(2)
with col1:
    st.subheader("抽出された図表見出し")
    st.dataframe(df_heads, use_container_width=True)
with col2:
    st.subheader("抽出された本文内参照（見出し行は除外済み）")
    st.dataframe(df_refs, use_container_width=True)

if show_debug:
    st.caption("正規表現")
    st.code(f"HEADING_RE = {HEADING_RE.pattern}\nREF_RE = {REF_RE.pattern}")


# =========================
# 照合（見出し ↔ 参照） — 重複定義・全件文脈つき
# =========================
# 見出しの重複定義チェック（0件でも列を持たせる）
# ---- 見出しの重複定義（page_labelも集約）----
if df_heads.empty:
    dup_heads = pd.DataFrame(columns=["図表キー","見出しページ(連番)","見出しpage_label","定義件数"])
else:
    dup_heads = (
        df_heads.groupby("図表キー", as_index=False)
        .agg(**{
            "見出しページ(連番)": ("見出しページ(連番)", list),
            "見出しpage_label": ("見出しpage_label", lambda s: sorted({x for x in s if x and x != "-"}))
        })
    )
    dup_heads["定義件数"] = dup_heads["見出しページ(連番)"].str.len()

# ---- 参照の集約（page_labelも集約）----
if df_refs.empty:
    refs_grouped = pd.DataFrame(columns=["図表キー","参照ページ(連番)","参照page_label"])
else:
    refs_grouped = (
        df_refs.groupby("図表キー", as_index=False)
        .agg(**{
            "参照ページ(連番)": ("参照ページ(連番)", lambda x: sorted(set(x))),
            "参照page_label": ("参照page_label", lambda s: sorted({x for x in s if x and x != "-"})),
        })
    )

# ---- 結合（メタ付与）----
meta = df_heads.drop_duplicates(subset=["図表キー"])[
    ["図表キー","図表種類","図表番号","見出しタイトル"]
]
df_merge = pd.merge(dup_heads, refs_grouped, on="図表キー", how="outer")
df_merge = pd.merge(meta, df_merge, on="図表キー", how="right")

# ---- 欠損をリスト化（安全化）----
for col in ["見出しページ(連番)","見出しpage_label","参照ページ(連番)","参照page_label"]:
    if col not in df_merge.columns:
        df_merge[col] = [[]] * len(df_merge)
    else:
        df_merge[col] = df_merge[col].apply(lambda v: v if isinstance(v, list) else ([] if pd.isna(v) else [v]))

# ---- 表示用の文字列化（page_labelを優先的に出す）----
def list_to_str(v): 
    return ",".join(str(x) for x in v) if isinstance(v, list) and len(v)>0 else "-"

df_merge["定義page_label"] = df_merge["見出しpage_label"].apply(list_to_str)
df_merge["参照page_label"] = df_merge["参照page_label"].apply(list_to_str)

# 状態
def judge(row) -> str:
    defs = row.get("定義件数", 0) or 0
    has_def = defs > 0
    has_ref = isinstance(row.get("参照ページ(連番)"), list) and len(row["参照ページ(連番)"])>0
    if has_def and has_ref:
        return "一致（参照あり）" if defs == 1 else "一致（重複定義+参照あり）"
    if has_def and not has_ref:
        return "未参照（見出しのみ）" if defs == 1 else "重複定義（参照なし）"
    if (not has_def) and has_ref:
        return "未定義参照（見出しなし）"
    return "不明"

df_merge["状態"] = df_merge.apply(judge, axis=1)

# ---- 最終出力（Excel でも page_label 列を使う）----
df_result = df_merge[[
    "図表種類","図表番号","見出しタイトル","図表キー",
    "定義page_label","参照page_label","状態"
]].sort_values(["図表種類","図表キー"], ignore_index=True)

st.subheader("🔍 照合結果（page_label表示）")
st.dataframe(df_result, use_container_width=True)

# === Excel ===
xlsx_buf = io.BytesIO()
with pd.ExcelWriter(xlsx_buf, engine="xlsxwriter") as writer:
    sheet_name = "fig_table_check"
    df_result.to_excel(writer, index=False, sheet_name=sheet_name)
    wb = writer.book
    ws = writer.sheets[sheet_name]
    text_fmt   = wb.add_format({"num_format": "@"})
    header_fmt = wb.add_format({"bold": True})
    wrap_fmt   = wb.add_format({"text_wrap": True})

    cols = list(df_result.columns)
    col_idx = {name: i for i, name in enumerate(cols)}

    # 文字列固定（誤日付化対策）
    for name in ["図表キー","図表番号","見出しタイトル","状態","定義page_label","参照page_label"]:
        if name in col_idx:
            ws.set_column(col_idx[name], col_idx[name], 26, text_fmt if name!="見出しタイトル" else wrap_fmt)

    # ヘッダ/フィルタ/固定
    for j, name in enumerate(cols): ws.write(0, j, name, header_fmt)
    ws.autofilter(0, 0, len(df_result), len(cols)-1)
    ws.freeze_panes(1, 0)

st.download_button(
    "📥 照合結果をExcelで保存 (.xlsx)",
    data=xlsx_buf.getvalue(),
    file_name="fig_table_check.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
