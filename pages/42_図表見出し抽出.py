# -*- coding: utf-8 -*-
# pages/42_図表見出し抽出.py
#
# PDF から「図/表/図表」の見出し行だけを抽出して一覧表示し，
# Excel (xlsx) でダウンロードできるページ。

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Tuple
import io
import re
import tempfile

import streamlit as st
import pandas as pd

# === 共通ライブラリ（lib/）からインポート ===
from lib.text_normalizer import (
    z2h_numhy,
    HY,
)
from lib.toc_check.toc_segments import (
    pdf_to_text_per_page,
    extract_single_page_label,
)
from lib.chart_check.helpers import (
    protect_for_excel_csv,
    protect_for_excel_xlsx,
)

# =========================
# ページ設定 & メインUI
# =========================
st.set_page_config(
    page_title="🖼️ 図表見出し抽出（頁ラベル付き）",
    page_icon="🖼️",
    layout="wide",
)
st.title("🖼️ 図表見出し抽出（図/表/図表）")
st.caption(
    "PDFから「図」「表」「図表」の見出し行を自動抽出して一覧表示します．"
    "抽出した結果は Excel（xlsx）としてダウンロードできます．"
)
st.caption("AIは使用していません．安心してpdfを丸ごとアップロードしてください．")

uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 抽出を実行", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    ctx_chars  = st.slider("番号前後のコンテキスト文字数（excerpt 用）", 10, 300, 60, 5)
    show_debug = st.checkbox("内部情報（デバッグ）を表示", value=False)

if not uploaded or not run:
    st.stop()

# =========================
# PDF → ページ別テキスト
# =========================
with tempfile.TemporaryDirectory() as td:
    pdf_path = Path(td) / "input.pdf"
    pdf_path.write_bytes(uploaded.getvalue())
    pages_text: List[str] = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")

# =========================
# 図表抽出用の正規表現など（14_図表チェック.py と同じロジック）
# =========================
DOT = r"[\.．・･]"
NUM_ZH = r"[0-9０-９]+"
NUM_TOKEN = rf"""
(
    # 例：4.2-1(1/6), 4.2-1（1／６） など
    {NUM_ZH}
    (?:\s*(?:{DOT}|{HY})\s*{NUM_ZH})*
    (?:\s*[（(]?\s*{NUM_ZH}\s*[\/／]\s*{NUM_ZH}\s*[）)])?
    |
    # 例：(1), （２）
    [（(]\s*{NUM_ZH}\s*[）)]
)
"""

EXTRACT_RE = re.compile(
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})",
    re.X
)


def canon_num(num: str) -> str:
    """
    図表番号の正規化：
    - 全角→半角
    - ドット類を "."
    - ハイフン類を "-"
    - 括弧内の余計な空白削除
    """
    # 全角 → 半角
    s = num.translate(str.maketrans("０１２３４５６７８９（）", "0123456789()"))

    # ドット類 → "."
    s = re.sub(DOT, ".", s)

    # ハイフン類 → "-"
    s = re.sub(HY, "-", s)

    # "." と "-" の前後スペース削除
    s = re.sub(r"\s*\.\s*", ".", s)
    s = re.sub(r"\s*-\s*", "-", s)

    # 複数スペース → 1 個
    s = re.sub(r"[ \u3000]+", " ", s)

    # 括弧内スペース削除
    s = re.sub(r"\(\s*", "(", s)
    s = re.sub(r"\s*\)", ")", s)

    return s.strip()


def canon_label(kind: str, num: str) -> str:
    """
    図表キー（例：'表3.1.5-1(1/3)'）を生成。
    """
    return f"{kind}{canon_num(num)}"


# regex があればそれを優先
try:
    import regex as re2
except Exception:
    re2 = re

PARTICLES_RE = re2.compile(r"(?:に|を|は|へ|で|と|の|など|等|または|又は|および|及び|かつ)")


# ===== 行抽出補助関数 =====
def extract_line_covering_match(full: str, start: int, end: int) -> Tuple[int, str, int, int]:
    """
    マッチを必ず含む行（改行またぎ対応）を返す。
    戻り値: (行番号, 行テキスト, 行開始位置, 行終了位置)
    """
    line_start = full.rfind("\n", 0, start)
    line_start = 0 if line_start == -1 else line_start + 1
    line_end = full.find("\n", end)
    if line_end == -1:
        line_end = len(full)
    line_txt = full[line_start:line_end].rstrip("\r\n")
    approx_lineno = full.count("\n", 0, line_start) + 1
    return approx_lineno, line_txt, line_start, line_end


# ===== ページ単位の抽出 =====
def judge_hits_in_page(page_text: str, ctx: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    1ページ分のテキストから
    - captions: 見出し（タイトル行相当）
    - refs    : 本文中の参照
    を抽出して返す。

    このページ（42_）では captions だけを利用するが，
    14_図表チェック.py と同じインターフェイスを維持する。
    """
    captions: List[Dict[str, Any]] = []
    refs: List[Dict[str, Any]] = []
    full = page_text.replace("\r\n", "\n").replace("\r", "\n")

    for m in EXTRACT_RE.finditer(full):
        kind, num, raw = m.group("kind"), m.group("num"), m.group(0)
        lineno, line_txt, line_start, line_end = extract_line_covering_match(full, m.start(), m.end())

        is_line_head = (full[line_start:m.start()].strip() == "")
        rel_end = (m.start() - line_start) + len(raw)
        after_on_line = line_txt[rel_end:] if rel_end <= len(line_txt) else ""
        particle_follow = bool(re2.match(rf"\s*{PARTICLES_RE.pattern}", after_on_line))
        has_period = ("。" in line_txt)
        is_reference = (not is_line_head) or particle_follow or has_period

        # 強調と excerpt
        highlighted = line_txt.replace(raw, f"⟪{raw}⟫", 1)
        left  = max(0, m.start() - ctx)
        right = min(len(full), m.end() + ctx)
        excerpt = full[left:m.start()] + f"⟪{raw}⟫" + full[m.end():right]

        if is_reference:
            refs.append({
                "行番号": lineno,
                "参照テキスト": raw.strip(),
                "図表種類": kind,
                "図表番号": f"{kind}{z2h_numhy(num)}",
                "図表キー": canon_label(kind, num),
                "excerpt": excerpt,
                "行テキスト": line_txt,
                "行テキスト(強調)": highlighted,
                "判定": "参照",
                "rule(理由)": (
                    "行頭でない→参照" if not is_line_head else
                    ("直後が助詞/接続語→参照" if particle_follow else "行に句点あり→参照")
                ),
            })
        else:
            # 行頭に「図3.1-1 ...」などが来ている場合 → 見出しとみなす
            title = re.sub(r"^[\s:：.\-．、・]+", "", after_on_line).strip()
            captions.append({
                "行番号": lineno,
                "図表種類": kind,
                "図表番号": f"{kind}{z2h_numhy(num)}",
                "図表キー": canon_label(kind, num),
                "見出しタイトル": title,
                "matched_line": line_txt,
                "matched_line(強調)": highlighted,
                "excerpt": excerpt,
                "判定": "タイトル",
                "rule(理由)": "その他→タイトル",
            })
    return captions, refs


# =========================
# 全ページ走査（頁ラベル＋図表見出し）
# =========================
page_labels: List[str] = []
per_page_rows: List[Dict[str, Any]] = []

for i, ptxt in enumerate(pages_text, start=1):
    label, matched = extract_single_page_label(ptxt)
    page_labels.append(label)
    per_page_rows.append({
        "pdf_page": i,
        "page_label": label or "-",
        "matched_line": matched or "-",
        "has_label": label is not None,
    })

df_per_page_labels = pd.DataFrame(per_page_rows)

caption_rows: List[Dict[str, Any]] = []
for i, ptxt in enumerate(pages_text, start=1):
    page_label = page_labels[i - 1] if i - 1 < len(page_labels) and page_labels[i - 1] else "-"
    captions, _ = judge_hits_in_page(ptxt, ctx=ctx_chars)
    for h in captions:
        caption_rows.append({"pdf_page": i, "page_label": page_label, **h})

df_captions = pd.DataFrame(caption_rows)

# =========================
# 表示
# =========================
st.subheader("📑 各ページの頁ラベル（1頁=高々1）")
st.dataframe(df_per_page_labels, use_container_width=True)

st.subheader("🖼️ 図/表/図表 見出し（キャプション）一覧")
if df_captions.empty:
    st.info("図表の見出しが見つかりませんでした。抽出ルールや PDF のフォーマットをご確認ください。")
else:
    # 全件一覧
    st.dataframe(df_captions, use_container_width=True)

    # 表・図を分けた一覧を下に表示
    df_tables = df_captions[df_captions["図表種類"] == "表"].copy()
    df_figs   = df_captions[df_captions["図表種類"] != "表"].copy()  # 「図」「図表」など

    st.markdown("#### 📊 表の見出し一覧（図表種類 = 表）")
    if df_tables.empty:
        st.info("表の見出しは見つかりませんでした。")
    else:
        st.dataframe(df_tables, use_container_width=True)

    st.markdown("#### 🖼️ 図の見出し一覧（図・図表）")
    if df_figs.empty:
        st.info("図（図・図表）の見出しは見つかりませんでした。")
    else:
        st.dataframe(df_figs, use_container_width=True)

# =========================
# Excel / CSV ダウンロード
# =========================
from io import BytesIO

with st.sidebar:
    st.markdown("### 📥 ダウンロード")

    # --- CSV（おまけ） ---
    if not df_captions.empty:
        buf_csv = io.StringIO()
        df_captions.to_csv(buf_csv, index=False)
        st.download_button(
            "📄 図表見出し（CSV）をダウンロード",
            data=buf_csv.getvalue().encode("utf-8-sig"),
            file_name="figure_table_captions.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # --- Excel (xlsx) ---
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # シート1: 頁ラベル
        if not df_per_page_labels.empty:
            df_page_x = df_per_page_labels.copy()
            if "page_label" in df_page_x.columns:
                df_page_x["page_label"] = df_page_x["page_label"].map(protect_for_excel_xlsx)
            df_page_x.to_excel(writer, sheet_name="頁ラベル一覧", index=False)

        # シート2: 図表見出し（全件）
        if not df_captions.empty:
            df_cap_x = df_captions.copy()
            if "page_label" in df_cap_x.columns:
                df_cap_x["page_label"] = df_cap_x["page_label"].map(protect_for_excel_xlsx)
            df_cap_x.to_excel(writer, sheet_name="図表見出し一覧", index=False)

        # シート3: 表のみ
        if not df_captions.empty:
            df_tables_x = df_captions[df_captions["図表種類"] == "表"].copy()
            if not df_tables_x.empty:
                if "page_label" in df_tables_x.columns:
                    df_tables_x["page_label"] = df_tables_x["page_label"].map(protect_for_excel_xlsx)
                df_tables_x.to_excel(writer, sheet_name="表のみ", index=False)

        # シート4: 図・図表のみ
        if not df_captions.empty:
            df_figs_x = df_captions[df_captions["図表種類"] != "表"].copy()
            if not df_figs_x.empty:
                if "page_label" in df_figs_x.columns:
                    df_figs_x["page_label"] = df_figs_x["page_label"].map(protect_for_excel_xlsx)
                df_figs_x.to_excel(writer, sheet_name="図・図表のみ", index=False)

    base = uploaded.name.rsplit(".", 1)[0]
    xlsx_filename = f"図表見出し抽出_{base}.xlsx"

    st.download_button(
        "📘 図表見出し一覧（xlsx）をダウンロード",
        data=output.getvalue(),
        file_name=xlsx_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# =========================
# デバッグ
# =========================
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug 情報")
    st.code(f"EXTRACT_RE = {EXTRACT_RE.pattern}")
    st.caption("マッチを含む1行抽出＋⟪強調⟫＋excerpt付き。")
    st.write("df_per_page_labels.shape:", df_per_page_labels.shape)
    st.write("df_captions.shape:", df_captions.shape)
