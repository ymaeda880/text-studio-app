# -*- coding: utf-8 -*-
# text_studio_app/pages/44_頁テキスト抽出.py
# 目的：
#   単独行の頁ラベル抽出 → 連番チェック(valid=True) のページ本文をTXTに結合。
#   ★ 追加要件：page_label が無いページも必ず出力（headerは page_label=None）。
#
#   14_図表チェック.py と同じロジックに統一するため，
#   頁ラベル関連の処理は lib/toc_check/toc_segments の関数を利用する。

from __future__ import annotations
import io
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import streamlit as st
import pandas as pd

# ==== 共通ライブラリからインポート ====
from lib.toc_check.toc_segments import (
    pdf_to_text_per_page,
    extract_single_page_label,
    valid_and_reason_auto,
)
from lib.text_normalizer import normalize_strict

# （任意）PyMuPDF / pdfplumber の存在チェックだけここでもしておく
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
st.set_page_config(
    page_title="📄 頁テキスト抽出（valid＋ラベル無しも出力）",
    page_icon="📄",
    layout="wide",
)
st.title("📄 頁テキスト抽出（valid=True＋label無しページもTXTへ）")
st.caption(
    "OCRは行いません。PDFのテキスト層から抽出し、"
    "単独行ラベル→連番チェックで valid=True のページに加え、"
    "ラベル無しページもTXTに出力します。"
)
with st.expander("📘 PDF抽出テキストへの加工処理（内部仕様のまとめ）", expanded=False):
    st.markdown(
        r"""
以下は，PDF から抽出したテキスト（`pages_text`）に対して，本アプリが行っている加工処理の詳細です．  
校正処理や図表チェックと同じロジックに統一してあり，このページでも同じルールで整形されています．

---

### 🔧 1. PDF→テキスト抽出後に行われる前処理

PDF 抽出後の `pages_text[i]` は以下の標準化を受けます．

1. 改行コードの正規化  
   - `\r\n` → `\n`  
   - `\r` → `\n`  

2. `normalize_strict` による正規化  
   - 全角英数字 → 半角  
   - 全角ハイフン類 → 半角 `-`  
   - Unicode 正規化（NFKC 系）  
   - 不可視文字の除去  
   - 全角スペース → 半角  

---

### 🔎 2. ページラベル抽出（`extract_single_page_label`）

各ページの先頭 **1〜3 行** を対象に次の優先順位でラベル判定を行います．

1. 単独数字（例：`3`, `15`）  
2. 括弧付き数字（例：`(3)`, `（10）`）  
3. 数字範囲（例：`3-4`, `３－４`）  
4. フォールバック（`page 3`, `p.5` など）

見つからない場合は `page_label = None` とします．

---

### 🔁 3. `valid_and_reason_auto` による連番チェック

抽出されたラベルが自然な連番になっているかを検査します．  
問題なければ `valid=True`，番号飛び・形式不一致があると `valid=False` になります．

---

### 📄 4. TXT に出力されるページ

- `page_label is None` → **必ず出力**  
- `page_label` があり `valid=True` → **出力**  
- `page_label` があり `valid=False` → **出力しない**

---

### 📝 5. TXT 生成時の加工内容

- `normalize_strict` 済みテキストをそのまま利用  
- ページ先頭にヘッダーを付与  
- 本文の末尾の改行を調整して 1 行に統一  

例：

\`\`\`
==== pdf頁（pdf_page）=8 pdf頁ラベル（page_label）=5 (chars=1320) ====
\`\`\`

---

### 🚫 6. 加工されない項目（保持されるもの）

- OCR（画像のみの PDF はそのまま空）  
- レイアウト（段組みなど）  
- 行順  
- 単語間スペース  

        """
    )


uploaded = st.file_uploader("PDF をアップロード", type=["pdf"])
run = st.button("▶ 抽出してTXTを作成", type="primary", use_container_width=True)

with st.sidebar:
    st.markdown("### オプション")
    show_debug = st.checkbox("内部情報（デバッグ）を表示", value=False)

if not uploaded or not run:
    st.stop()

if fitz is None and pdfplumber is None:
    st.error(
        "PyMuPDF か pdfplumber のどちらかをインストールしてください。"
        "`pip install pymupdf pdfplumber`"
    )
    st.stop()


# =========================
# PDF → ページ別テキスト
# =========================
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    pdf_path = td_path / "input.pdf"
    pdf_path.write_bytes(uploaded.getvalue())
    pages_text: List[str] = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")


# =========================
# ラベル検出 & segments 構築
# =========================
segments: List[Dict[str, Any]] = []
page_labels: List[Optional[str]] = []

for i, ptxt in enumerate(pages_text, start=1):
    # 14_図表チェック.py と同じ extract_single_page_label を使用
    label, matched = extract_single_page_label(ptxt)
    page_labels.append(label)

    segments.append({
        "pdf_page": i,
        "page_label": label if label else None,   # ラベル無しは None として保持
        "body": normalize_strict(ptxt),          # 本文は normalize_strict で整形
        "matched_line": matched if matched else "-",
    })


# =========================
# 連番チェック（toc_segments.valid_and_reason_auto を使用）
# =========================
prev_ok: Optional[str] = None
valid_flags: Dict[int, bool] = {}

for s in segments:
    lab = s["page_label"]
    pdf_page = s["pdf_page"]

    if lab is None:
        # ラベルが無いページは valid=False（ただし後で必ず出力対象にする）
        valid_flags[pdf_page] = False
        continue

    ok, _reason = valid_and_reason_auto(lab, prev_ok)
    if ok:
        prev_ok = lab
    valid_flags[pdf_page] = ok


# =========================
# TXT 結合ロジック
#  - ラベル有り & valid=True のページ → 出力
#  - ラベル無し（page_label is None）のページ → 出力（headerは page_label=None）
#  - ラベル有り & valid=False のページ → 出力しない
# =========================
txt_buf = io.StringIO()
num_valid = 0
num_none = 0

for s in segments:
    label = s["page_label"]
    pdf_page = s["pdf_page"]
    include = False
    label_str = "None"

    if label is None:
        # ラベル無しページは必ず出力
        include = True
        num_none += 1
    else:
        # ラベルありで valid=True のページだけ出力
        if valid_flags.get(pdf_page, False):
            include = True
            label_str = str(label)
            num_valid += 1
        else:
            include = False  # ラベルありだが invalid → 出力しない

    if include:
        header = (
            f"==== pdf頁（pdf_page）={pdf_page} "
            f"pdf頁ラベル（page_label）={label_str} "
            f"(chars={len(s['body'])}) ====\n"
        )
        txt_buf.write(header)
        txt_buf.write(s["body"].rstrip("\n") + "\n\n")


# =========================
# ダウンロードボタン
# =========================
if num_valid > 0 or num_none > 0:
    base = uploaded.name.rsplit(".", 1)[0]
    out_name = f"抽出テキスト_{base}.txt"

    st.download_button(
        "📥 抽出したテキスト（txt）をダウンロード",
        data=txt_buf.getvalue().encode("utf-8"),
        file_name=out_name,
        mime="text/plain",
        use_container_width=True,
    )
    st.success(f"出力ページ数: valid={num_valid}, label=None={num_none}")
else:
    st.warning("出力対象のページがありません（valid=True も label=None も無し）。")


# =========================
# デバッグ情報
# =========================
if show_debug:
    from lib.toc_check import toc_segments as _ts  # デバッグ用にモジュール参照

    st.divider()
    st.markdown("### 🧪 Debug")
    # 頁ラベル抽出に使っている正規表現（LABEL_LINE_RE）が見たい場合
    if hasattr(_ts, "LABEL_LINE_RE"):
        st.code(f"LABEL_LINE_RE = {_ts.LABEL_LINE_RE.pattern}")
    st.dataframe(pd.DataFrame(segments), use_container_width=True)
