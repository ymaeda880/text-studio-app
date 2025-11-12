# -*- coding: utf-8 -*-
# pages/24_図表チェック.py — GPT不使用：図表見出し ↔ 本文参照の照合（DLはサイドバー集約 & セッション保存）

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
st.caption("目次チェックと同一のページ抽出ロジック（連番/章-ページ/シリーズ-番号の混在対応）。ダウンロードはサイドバーに集約。")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])

with st.sidebar:
    st.markdown("### ⚙️ オプション")
    show_debug = st.checkbox("内部情報（抽出中間）を表示", value=False)
run = st.button("▶ 解析・照合を実行", type="primary", use_container_width=True)


# =========================
# ユーティリティ（正規化・抽出共通）
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D]"   # 各種ハイフン
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"
LEADERS_SPACED = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"
ALPHAJP = r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+"  # 英/かな/漢
DOT = r"[\.．・･]"
NUM = r"[0-9０-９]+"

def z2h_numhy(s: str) -> str:
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝", "0123456789()[]{}"))
    return re.sub(HY, "-", s)

def normalize_strict(s: str) -> str:
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def normalize_loose(s: str) -> str:
    s = z2h_numhy(s)
    s = re.sub(rf"{LEADERS_SPACED}$", "", s)
    return re.sub(r"\s+", "", s)


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


# =========================
# ページ区切り（行単独ラベル）
# =========================
def build_label_line_regex_mixed() -> re.Pattern:
    core_seq    = r"[0-9０-９]{1,6}"                 # 12
    core_chap   = rf"[0-9０-９]+(?:{HY}[0-9０-９]+)+" # 1-2 / 2-10-3
    core_series = rf"{ALPHAJP}{HY}[0-9０-９]+"       # 序-1 / 資-2 など
    core = rf"(?:{core_seq}|{core_chap}|{core_series})"
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_LINE_RE = build_label_line_regex_mixed()

def split_segments_by_label(all_text: str) -> List[Dict[str, Any]]:
    """
    全文（連結）を、単独行のページラベルで分割し、[{'page_label','body'}] を返す。
    """
    txt = normalize_strict(all_text.replace("\r\n", "\n").replace("\r", "\n"))
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
# 図表 見出し / 参照 抽出
# =========================
# 例: 2.2-1 / 2. 2-1 / ２．１－１ / （１）
NUM_TOKEN = rf"""
(?:                                     # ① ドット区切り + ハイフン区切り
    {NUM}
    (?:\s*{DOT}\s*{NUM})*               # 2.2 や 2． 2
    (?:\s*-\s*{NUM})*                   # -1 や -１
  |
    [（(]\s*{NUM}\s*[）)]               # ② （１）/ (12)
)
"""
NUM_TOKEN_RE = re.compile(NUM_TOKEN, re.X)

HEADING_RE = re.compile(  # 行頭の見出し1行
    rf"^\s*(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})\s*[:：.\-．、]?\s*(?P<title>.+?)\s*$",
    re.X
)
REF_RE = re.compile(      # 本文参照（行中）
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})(?![0-9])",
    re.X
)

def canon_num(num: str) -> str:
    s = z2h_numhy(num)                  # 全角→半角、ハイフン→'-'
    s = re.sub(r"[()（）]", "", s)        # （1）→1
    s = re.sub(DOT, ".", s)             # ．・ → .
    s = re.sub(r"\s*\.\s*", ".", s)     # '2 . 2' → '2.2'
    s = re.sub(r"\s*-\s*", "-", s)      # '2 - 1' → '2-1'
    s = re.sub(r"\s+", "", s)           # 残りの空白除去
    return s

def canon_label(kind: str, num: str) -> str:
    return f"{kind}{canon_num(num)}"


# =========================
# 参照コンテキスト抽出
# =========================
def get_context_windows(text: str, match_span: Tuple[int, int], win: int = 60) -> Dict[str, str]:
    s, e = match_span
    left  = max(0, s - win)
    right = min(len(text), e + win)
    around = text[left:right].replace("\n", " ")
    # 1文抽出（簡易）：行を句点/ピリオド/改行でスプリットし、該当スパンが入る文を返す
    lines = re.split(r"(?<=[。．\.！？!?])\s+|\n", text)
    acc = 0
    hit_sent = ""
    for ln in lines:
        if acc <= s < acc + len(ln) + 1:  # +1 for delimiter char consumed
            hit_sent = ln.strip()
            break
        acc += len(ln) + 1
    return {
        "参照_前後±60": around,
        "参照_1文": hit_sent if hit_sent else around
    }


# =========================
# メイン処理（結果を全部作ってセッションに保存）
# =========================
def compute_results(pdf_bytes: bytes, show_debug: bool = False) -> Dict[str, Any]:
    # 1) PDF読み → ページテキスト
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        pdf_path = td / "input.pdf"
        pdf_path.write_bytes(pdf_bytes)
        pages_text: List[str] = pdf_to_text_per_page(pdf_path)

    # 2) ページ区切り（segments）と page_label 生成（valid も別途計算）
    all_text_joined = "\n".join(pages_text)
    segments = split_segments_by_label(all_text_joined)

    # 2-1) 連番チェック（prev_ok は OK のときだけ更新）
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
            "preview": s["body"][:120].replace("\n", " ") + ("…" if len(s["body"]) > 120 else "")
        })
    df_check = pd.DataFrame(rows_check)
    df_segments_overview = pd.DataFrame([{
        "page_label": s["page_label"],
        "char_count": len(s["body"]),
        "preview": s["body"][:120].replace("\n", " ") + ("…" if len(s["body"]) > 120 else "")
    } for s in segments]) if segments else pd.DataFrame(columns=["page_label","char_count","preview"])

    # valid_segments は参考用（DLにも使う）
    valid_segments = [s for s in segments if any((r["page_label"] == s["page_label"] and r["valid"]) for r in rows_check)]

    # 3) page_label の配列（抽出順で対応）
    page_labels = [s["page_label"] for s in segments] if segments else [str(i+1) for i in range(len(pages_text))]

    # 4) 見出し抽出
    heading_rows: List[Dict[str, Any]] = []
    for pidx, page_text in enumerate(pages_text, start=1):
        page_label = page_labels[pidx-1] if pidx-1 < len(page_labels) else str(pidx)
        for raw_line in page_text.replace("\r\n","\n").replace("\r","\n").split("\n"):
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
                "図表番号": f"{kind}{z2h_numhy(num)}",  # 表示用（全角→半角）
                "図表キー": canon_label(kind, num),     # 照合キー
                "見出しタイトル": title,
                "見出しページ(連番)": pidx,
                "見出しpage_label": page_label,        # ← こちらに page_label
            })
    df_heads = pd.DataFrame(heading_rows) if heading_rows else pd.DataFrame(
        columns=["図表種類","図表番号","図表キー","見出しタイトル","見出しページ(連番)","見出しpage_label"]
    )

    # 5) 本文参照抽出（見出し行は本文扱いしない：見出しに一致した行はスキップ）
    ref_rows: List[Dict[str, Any]] = []
    for pidx, page_text in enumerate(pages_text, start=1):
        # 見出し行を除いた本文テキストを構築（１行ずつ見て heading にマッチなら参照探索はスキップ）
        lines = page_text.replace("\r\n","\n").replace("\r","\n").split("\n")
        acc = 0
        for ln in lines:
            raw_ln = ln
            line = normalize_strict(raw_ln)
            span_base = (acc, acc + len(raw_ln))
            acc += len(raw_ln) + 1  # 改行分 +1

            if not line:
                continue
            if HEADING_RE.match(line):
                # これは見出し行なので参照探索しない
                continue
            # 参照抽出（行テキスト基準）
            for m in REF_RE.finditer(raw_ln):
                kind = m.group("kind"); num = m.group("num")
                # 原文全体でのスパン（ざっくり行頭からの相対→ページ内全体文字列が無いので±60は行テキストで）
                ctx = get_context_windows(raw_ln, m.span(), win=60)
                ref_rows.append({
                    "参照テキスト": m.group(0),
                    "図表キー": canon_label(kind, num),
                    "参照ページ(連番)": pidx,
                    "参照_1文": ctx["参照_1文"],
                    "参照_前後±60": ctx["参照_前後±60"],
                    # page_label は pages_text ベースに全体対応（segments数とズレる場合はフォールバック）
                    "参照page_label": page_labels[pidx-1] if pidx-1 < len(page_labels) else str(pidx),
                })

    df_refs = pd.DataFrame(ref_rows) if ref_rows else pd.DataFrame(
        columns=["参照テキスト","図表キー","参照ページ(連番)","参照_1文","参照_前後±60","参照page_label"]
    )

    # 6) 照合（見出し ↔ 参照）
    # 見出し重複定義チェック
    if df_heads.empty:
        dup_heads = pd.DataFrame(columns=["図表キー", "見出しページ(連番)", "定義件数"])
    else:
        dup_heads = (
            df_heads.groupby("図表キー", as_index=False)
            .agg(**{"見出しページ(連番)": ("見出しページ(連番)", list)})
        )
        dup_heads["定義件数"] = dup_heads["見出しページ(連番)"].str.len()

    # 参照集約
    if df_refs.empty:
        refs_grouped = pd.DataFrame(columns=["図表キー", "参照ページ(連番)", "参照page_label"])
    else:
        # 参照ページ(連番) は重複排除＆昇順
        g = df_refs.groupby("図表キー", as_index=False)
        refs_grouped = g.agg({
            "参照ページ(連番)": lambda x: sorted(set(x)),
            "参照page_label":  lambda x: ",".join(sorted(set(map(str, x)))),
        })

    # 結合
    df_merge = pd.merge(dup_heads, refs_grouped, on="図表キー", how="outer")

    # 見出しメタ付与（page_labelは最初の見出しのラベルを代表に）
    meta = (df_heads.sort_values("見出しページ(連番)")
            .drop_duplicates(subset=["図表キー"], keep="first"))[
        ["図表キー","図表種類","図表番号","見出しタイトル","見出しpage_label"]
    ]
    df_merge = pd.merge(meta, df_merge, on="図表キー", how="right")

    # list 正規化（欠損→[]）
    df_merge["見出しページ(連番)"] = df_merge.get("見出しページ(連番)", pd.Series([], dtype=object)).apply(
        lambda v: v if isinstance(v, list) else ([] if pd.isna(v) else [v])
    )
    df_merge["参照ページ(連番)"] = df_merge.get("参照ページ(連番)", pd.Series([], dtype=object)).apply(
        lambda v: v if isinstance(v, list) else ([] if pd.isna(v) else [v])
    )

    # 状態判定
    def judge(row) -> str:
        defs = row.get("定義件数", 0) or 0
        has_def = defs > 0
        has_ref = isinstance(row.get("参照ページ(連番)"), list) and len(row["参照ページ(連番)"]) > 0
        if has_def and has_ref:
            return "一致（参照あり）" if defs == 1 else "一致（重複定義+参照あり）"
        if has_def and not has_ref:
            return "未参照（見出しのみ）" if defs == 1 else "重複定義（参照なし）"
        if (not has_def) and has_ref:
            return "未定義参照（見出しなし）"
        return "不明"

    df_merge["状態"] = df_merge.apply(judge, axis=1)

    def fmt_pages(x):
        if isinstance(x, list):
            return ",".join(str(i) for i in x)
        return x

    df_merge["定義ページ(連番)"] = df_merge["見出しページ(連番)"].apply(lambda v: fmt_pages(v) if isinstance(v, list) else v)

    df_summary = df_merge[[
        "図表種類","図表番号","見出しタイトル","図表キー",
        "見出しpage_label","定義ページ(連番)","参照page_label","参照ページ(連番)","状態"
    ]].sort_values(["図表種類","図表キー"], ignore_index=True)

    # 7) 参照詳細（文脈）そのまま
    df_ref_details = df_refs[[
        "図表キー","参照page_label","参照ページ(連番)","参照テキスト","参照_1文","参照_前後±60"
    ]].sort_values(["図表キー","参照ページ(連番)"], ignore_index=True)

    return {
        "pages_text": pages_text,
        "segments": segments,
        "df_segments_overview": df_segments_overview,
        "df_check": df_check,
        "df_heads": df_heads,
        "df_refs": df_refs,
        "df_summary": df_summary,
        "df_ref_details": df_ref_details,
        "valid_segments": valid_segments,
    }


# =========================
# 実行 & セッション保存
# =========================
if not uploaded or not run:
    st.stop()
if fitz is None and pdfplumber is None:
    st.error("PyMuPDF か pdfplumber のどちらかをインストールしてください。`pip install pymupdf pdfplumber`")
    st.stop()

st.success("PDF 読み取りを開始します…")

results = compute_results(uploaded.getvalue(), show_debug=show_debug)
st.session_state.figtbl_results = results
st.session_state.figtbl_filename_stem = Path(getattr(uploaded, "name", "result.pdf")).stem or "result"

# ===== 画面表示（概要）
st.subheader("抽出ページ（単独行ラベルで区切り）— 概観")
if not results["segments"]:
    st.warning("単独行のページラベルが見つからず、抽出ページが作成できませんでした（PDFの版面に依存します）。")
else:
    st.dataframe(results["df_segments_overview"], use_container_width=True)

st.subheader("📑 ページラベル検証（連番チェック）")
st.dataframe(results["df_check"], use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    st.subheader("抽出された図表見出し")
    st.dataframe(results["df_heads"], use_container_width=True)
with col2:
    st.subheader("抽出された本文内参照（文脈あり）")
    st.dataframe(results["df_ref_details"], use_container_width=True)

st.subheader("🔍 照合結果（Summary）")
st.dataframe(results["df_summary"], use_container_width=True)
st.caption("※ page_label は版面ラベル（例: 2-1 / 序-1 など）。参照は見出し行を本文から除外して抽出。")


# =========================
# ダウンロード用ファイルを一度だけ生成 → セッション保存
# =========================
base_stem = st.session_state.figtbl_filename_stem or "result"

# 1) summary.xlsx
xlsx_summary = io.BytesIO()
with pd.ExcelWriter(xlsx_summary, engine="xlsxwriter") as writer:
    sheet = "summary"
    results["df_summary"].to_excel(writer, index=False, sheet_name=sheet)
    wb = writer.book; ws = writer.sheets[sheet]
    text_fmt = wb.add_format({"num_format": "@"})
    header_fmt = wb.add_format({"bold": True})
    wrap_fmt = wb.add_format({"text_wrap": True})
    cols = list(results["df_summary"].columns); col_idx = {n:i for i,n in enumerate(cols)}
    for name in cols:
        width = 36 if name in ["見出しタイトル"] else 22
        fmt = wrap_fmt if name in ["見出しタイトル"] else text_fmt
        ws.set_column(col_idx[name], col_idx[name], width, fmt)
        ws.write(0, col_idx[name], name, header_fmt)
    ws.autofilter(0, 0, len(results["df_summary"]), len(cols)-1)
    ws.freeze_panes(1, 0)
st.session_state.xlsx_summary = xlsx_summary.getvalue()
st.session_state.xlsx_summary_name = f"{base_stem}_summary.xlsx"

# 2) ref_contexts.xlsx
xlsx_refs = io.BytesIO()
with pd.ExcelWriter(xlsx_refs, engine="xlsxwriter") as writer:
    sheet = "ref_contexts"
    df = results["df_ref_details"]
    if df.empty:
        df = pd.DataFrame(columns=["図表キー","参照page_label","参照ページ(連番)","参照テキスト","参照_1文","参照_前後±60"])
    df.to_excel(writer, index=False, sheet_name=sheet)
    wb2 = writer.book; ws2 = writer.sheets[sheet]
    text_fmt = wb2.add_format({"num_format": "@"})
    header_fmt = wb2.add_format({"bold": True})
    wrap_fmt = wb2.add_format({"text_wrap": True})
    for j, name in enumerate(df.columns):
        width = 40 if name in ["参照_1文","参照_前後±60"] else 24
        fmt = wrap_fmt if name in ["参照テキスト","参照_1文","参照_前後±60"] else text_fmt
        ws2.set_column(j, j, width, fmt)
        ws2.write(0, j, name, header_fmt)
    ws2.autofilter(0, 0, len(df), len(df.columns)-1)
    ws2.freeze_panes(1, 0)
st.session_state.xlsx_refs = xlsx_refs.getvalue()
st.session_state.xlsx_refs_name = f"{base_stem}_ref_contexts.xlsx"

# 3) summary.csv / ref_contexts.csv / heads.csv / refs.csv
csv_summary = results["df_summary"].to_csv(index=False).encode("utf-8-sig")
csv_refs    = results["df_ref_details"].to_csv(index=False).encode("utf-8-sig")
csv_heads   = results["df_heads"].to_csv(index=False).encode("utf-8-sig")
csv_refsraw = results["df_refs"].to_csv(index=False).encode("utf-8-sig")

st.session_state.csv_summary = csv_summary
st.session_state.csv_summary_name = f"{base_stem}_summary.csv"
st.session_state.csv_refs = csv_refs
st.session_state.csv_refs_name = f"{base_stem}_ref_contexts.csv"
st.session_state.csv_heads = csv_heads
st.session_state.csv_heads_name = f"{base_stem}_heads.csv"
st.session_state.csv_refsraw = csv_refsraw
st.session_state.csv_refsraw_name = f"{base_stem}_refs_raw.csv"

# 4) 抽出ページTXT（validのみ）
if results["valid_segments"]:
    txt_buf = io.StringIO()
    for s in results["valid_segments"]:
        header = f"==== page_label={s['page_label']} (chars={len(s['body'])}) ====\n"
        txt_buf.write(header); txt_buf.write(s["body"].rstrip("\n") + "\n\n")
    st.session_state.txt_valid = txt_buf.getvalue().encode("utf-8")
    st.session_state.txt_valid_name = f"{base_stem}_extracted_pages_valid.txt"


# =========================
# サイドバー：ダウンロード集約（セッション保存物をそのまま配布）
# =========================
with st.sidebar:
    st.markdown("### 📥 ダウンロード")
    if "xlsx_summary" in st.session_state:
        st.download_button(
            "summary をExcelで保存 (.xlsx)",
            data=st.session_state.xlsx_summary,
            file_name=st.session_state.xlsx_summary_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    if "xlsx_refs" in st.session_state:
        st.download_button(
            "参照の文脈をExcelで保存 (.xlsx)",
            data=st.session_state.xlsx_refs,
            file_name=st.session_state.xlsx_refs_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    st.download_button(
        "summary をCSVで保存",
        data=st.session_state.csv_summary,
        file_name=st.session_state.csv_summary_name,
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "参照の文脈をCSVで保存",
        data=st.session_state.csv_refs,
        file_name=st.session_state.csv_refs_name,
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "図表見出し raw をCSVで保存",
        data=st.session_state.csv_heads,
        file_name=st.session_state.csv_heads_name,
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "本文参照 raw をCSVで保存",
        data=st.session_state.csv_refsraw,
        file_name=st.session_state.csv_refsraw_name,
        mime="text/csv",
        use_container_width=True,
    )
    if "txt_valid" in st.session_state:
        st.download_button(
            "抽出ページTXT（validのみ）",
            data=st.session_state.txt_valid,
            file_name=st.session_state.txt_valid_name,
            mime="text/plain",
            use_container_width=True,
        )
