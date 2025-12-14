# -*- coding: utf-8 -*-
# pages/15_word解析.py
#
# Word(.docx) をアップロードして内部構造をざっくり解析し、
# - 本文 / 図 / 表 / 目次候補 / 見出し を分類
# - 「生成AIへの入力用」の中間テキストを 1 つ生成してダウンロード
#   * 見出し     : === HEADING[3-1-2] タイトル ===  のように章番号付きで出力
#   * 本文       : プレーンテキスト
#   * 表         : 表番号＋タイトルの下に JSON を埋め込む
#   * 図         : 図のキャプション＋画像ファイル名
# - 画像ファイルを ZIP で一括ダウンロード
#
# ※ base_chapter（この章が第何章か）はサイドバーから指定

from __future__ import annotations

from io import BytesIO
from typing import List, Tuple, Dict, Any
import json

import streamlit as st

from pathlib import Path
import sys

# =========================
# プロジェクトルートを sys.path に追加
# =========================
PROJECTS_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))

# ==== python-docx 関連 ====
try:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False

# ==== 自作ライブラリ ====
from lib.word_analysis.blocks import (
    Block,
    iter_block_items,
    classify_paragraph,
    classify_block,
)
from lib.word_analysis.headings import (
    is_heading_paragraph,
    detect_heading_level,
    format_heading_id,
)
from lib.word_analysis.tables import (
    table_to_json,
)
from lib.word_analysis.images import (
    get_image_filenames_from_paragraph,
    collect_images_as_zip,
)


# =========================
# 中間テキストの構築
# =========================
def build_intermediate_text(
    doc: Document,
    base_chapter: int,
    mode: str = "standard",  # "standard" or "simple"
) -> Tuple[str, Dict[str, int]]:

    simple_mode = (mode == "simple")

    lines: List[str] = []
    stats = {"heading": 0, "paragraph": 0, "table": 0, "figure": 0}

    heading_counters = [0, 0, 0, 0]
    prev_block: Block | None = None
    pending_table_caption: Paragraph | None = None

    def append_blank():
        """簡素モードで、HEADING/FIGURE/TABLE の代わりに入れる空行"""
        if simple_mode:
            lines.append("")

    for block_idx, block in enumerate(iter_block_items(doc), start=1):

        # --------------------
        # Paragraph
        # --------------------
        if isinstance(block, Paragraph):

            # ---- 見出し ----
            if is_heading_paragraph(block):
                level = detect_heading_level(block)
                heading_id = format_heading_id(base_chapter, heading_counters, level)
                text = (block.text or "").strip()

                if text:
                    if simple_mode:
                        append_blank()
                        lines.append(text)
                    else:
                        lines.append(f"=== HEADING[{heading_id}] {text} ===")

                    stats["heading"] += 1

                prev_block = block
                pending_table_caption = None
                continue

            # ---- 見出し以外の分類 ----
            cat = classify_paragraph(block)

            if cat == "toc":
                prev_block = block
                pending_table_caption = None
                continue

            if cat == "table_caption":
                pending_table_caption = block
                prev_block = block
                continue

            # ---- 図キャプション ----
            if cat == "figure":
                caption = (block.text or "").strip()
                img_files = get_image_filenames_from_paragraph(block)
                stats["figure"] += 1
                fig_id = stats["figure"]

                if simple_mode:
                    append_blank()
                    if caption:
                        lines.append(caption)
                else:
                    lines.append(f"=== FIGURE[{fig_id}] {caption} ===")

                    # image_files 行は両モード共通
                    if img_files:
                        lines.append(f"image_files: {', '.join(img_files)}")
                    else:
                        lines.append("image_files: (none)")

                lines.append("")
                prev_block = block
                pending_table_caption = None
                continue

            # ---- 本文 ----
            text = (block.text or "").strip()
            if text:
                lines.append(text)
                stats["paragraph"] += 1

            prev_block = block
            pending_table_caption = None

        # --------------------
        # Table
        # --------------------
        elif isinstance(block, Table):
            cat = classify_block(block, prev_block)

            if cat == "table":
                stats["table"] += 1
                tbl_json = table_to_json(
                    block,
                    pending_table_caption,
                    use_same_left_placeholder=use_same_left_placeholder,
                )


                if simple_mode:
                    # 簡素モード：
                    # - 「=== TABLE ... ===」「=== END_TABLE ===」の代わりに
                    #   <ここから表> ～ <ここまで表> を出す
                    # - table_number/title/cells: の見出し行は出さない
                    # - 各行は [a, b, c, ...] の 1 行表記
                    # - セル内改行はスペースに統合
                    append_blank()

                    cells = tbl_json.get("cells", [])

                    lines.append("<ここから表>")
                    for row in cells:
                        processed = []
                        for x in row:
                            # セル内の改行をスペースに変換（標高\n(風速計高さ) → 標高 (風速計高さ)）
                            s = str(x).replace("\n", " ").replace("\r", " ")
                            # 連続スペースを 1 個に
                            s = " ".join(s.split())
                            processed.append(s)

                        row_text = ", ".join(processed)
                        lines.append(f"[{row_text}]")
                    lines.append("<ここまで表>")
                    lines.append("")

                else:
                    # 標準モード（従来仕様）
                    lines.append("")
                    tbl_num = tbl_json.get("table_number", "unknown")
                    tbl_title = tbl_json.get("title", "")
                    lines.append(f"=== TABLE {tbl_num} {tbl_title} ===")
                    lines.append("```json")
                    lines.append(json.dumps(tbl_json, ensure_ascii=False, indent=2))
                    lines.append("```")
                    lines.append("=== END_TABLE ===")
                    lines.append("")

                pending_table_caption = None
                prev_block = block
                continue

            prev_block = block
            pending_table_caption = None

        else:
            prev_block = block
            pending_table_caption = None

    intermediate_text = "\n".join(lines).strip() + "\n"
    return intermediate_text, stats


# =========================
# Streamlit UI
# =========================
st.set_page_config(
    page_title="📄 Word 解析 → 生成AI用中間テキスト",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Word 解析 → 生成AI入力用テキスト生成")

st.markdown(
    """
アップロードした Word(.docx) を解析して、**生成AIへの入力に使いやすい 1 つのテキスト**を作ります。

- 見出し: `=== HEADING[3-1-2] タイトル ===` のように章番号付きで明示  
- 本文: そのままのテキスト  
- 表: `=== TABLE 3.1.1-2 タイトル ===` の下に JSON を埋め込み  
- 図: `=== FIGURE[1] キャプション ===` と画像ファイル名の列挙  
- 画像: ZIP にまとめてダウンロード（/word/media/imageX.png 相当）

※ 表番号は、とりあえず **「3.1.1-2」形式** を復元するルールにしています。
"""
)

if not HAS_DOCX:
    st.error("python-docx がインポートできませんでした。`python-docx` をインストールしてください。")
    st.stop()

# --- サイドバー設定 ---
with st.sidebar:
    st.header("🔧 オプション")

    # 出力スタイル選択（標準 / 簡素）
    output_mode_label = st.radio(
        "出力スタイル",
        options=["簡素", "標準"],
        index=0,  # デフォルト: 簡素
        horizontal=True,
        help="「標準」は従来のマーカー付き出力、「簡素」は見出し/表マーカーを省いたプレーン寄りの出力です。",
    )
    output_mode = "simple" if output_mode_label == "簡素" else "standard"

    base_chapter = st.number_input(
        "この章の章番号 (base_chapter)",
        min_value=1,
        max_value=50,
        value=1,
        step=1,
        help="見出しIDの先頭に付ける章番号です（例: 3 → HEADING[3-1-2]）。",
    )

    st.caption(
        "※ 見出しのスタイル（Heading 1〜 / 見出し 1〜）や、"
        "『第◯章』『◯◯の状況』のような短いラベル行を見出しとして検出します。"
    )

        # --- 表の結合セル処理の選択 ---
    merge_label = st.radio(
        "結合セルの扱い",
        options=["そのまま", "横結合セルを <同左> にする"],
        index=1,
        help="横方向に結合されているセルを <同左> で埋めることができます。",
    )
    use_same_left_placeholder = (merge_label == "横結合セルを <同左> にする")


uploaded_file = st.file_uploader("Word ファイル（.docx）をアップロードしてください", type=["docx"])

col_btn1, _ = st.columns([1, 3])
with col_btn1:
    run = st.button("🔍 解析して中間テキストを生成", type="primary", use_container_width=True)

if uploaded_file is None:
    st.info("まず .docx ファイルをアップロードしてください。")
    st.stop()

if not run:
    st.stop()

# =========================
# 解析本体
# =========================
try:
    src_doc = Document(uploaded_file)
except Exception as e:
    st.error(f"Word ファイルの読み込みに失敗しました: {e}")
    st.stop()

with st.status("解析中です…", expanded=False) as status:
    intermediate_text, stats = build_intermediate_text(
        src_doc,
        base_chapter=int(base_chapter),
        mode=output_mode,  # ★ ここでモードを渡す
    )
    status.update(label="解析完了", state="complete")

# =========================
# 結果表示
# =========================
st.subheader("📊 分類結果（ブロック数）")

c1, c2, c3, c4 = st.columns(4)
c1.metric("見出し数", stats.get("heading", 0))
c2.metric("本文段落数", stats.get("paragraph", 0))
c3.metric("表ブロック数", stats.get("table", 0))
c4.metric("図ブロック数", stats.get("figure", 0))

st.markdown("---")

st.subheader("📝 生成された中間テキスト（先頭部分プレビュー）")
st.code(intermediate_text[:8000], language="text")  # 長くなりすぎないように頭だけ

st.markdown("---")

# =========================
# ダウンロード
# =========================
st.subheader("💾 ダウンロード")

base_name = uploaded_file.name.rsplit(".", 1)[0]

# --- 中間テキスト (.txt) ---
buf_txt = intermediate_text.encode("utf-8")
# ★ 日本語ファイル名モード（simple → 簡素, standard → 標準）
mode_jp = "簡素" if output_mode == "simple" else "標準"

txt_name = f"{base_name}_intermediate_{mode_jp}.txt"
# txt_name = f"{base_name}_intermediate_{output_mode}.txt"

st.download_button(
    label="⬇️ 中間テキスト（.txt）をダウンロード",
    data=buf_txt,
    file_name=txt_name,
    mime="text/plain; charset=utf-8",
    use_container_width=True,
)

# --- 画像 ZIP ---
img_zip_buf = collect_images_as_zip(src_doc)
zip_name = f"{base_name}_images.zip"

st.download_button(
    label="⬇️ 画像ファイルを ZIP でダウンロード",
    data=img_zip_buf,
    file_name=zip_name,
    mime="application/zip",
    use_container_width=True,
)

st.caption(
    "この中間テキストをそのまま GPT API に投げることで、"
    "見出し構造・表（JSON）・図情報を含んだ形で追加解析に使えます。"
)
