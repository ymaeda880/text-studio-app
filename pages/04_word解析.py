# -*- coding: utf-8 -*-
# text_studio_app/pages/04_word解析.py
#
# Word(.docx) をアップロードして内部構造をざっくり解析し、
# - 本文 / 図 / 表 / 目次候補 / 見出し を分類
# - 「生成AIへの入力用」の中間テキストを 1 つ生成してダウンロード
#   * 見出し     : === HEADING[3-1-2] タイトル ===  のように章番号付きで出力
#   * 本文       : プレーンテキスト
#   * 表         : 表番号＋タイトルの下に JSON を埋め込む / または <ここから表> 形式
#   * 図         : 図のキャプション＋画像ファイル名
# - 画像ファイルを ZIP で一括ダウンロード
#
# ※ base_chapter（この章が第何章か）はサイドバーから指定

from __future__ import annotations

from pathlib import Path
import sys

_THIS = Path(__file__).resolve()
PROJECTS_ROOT = _THIS.parents[3]  # appの時は[2]
if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))

from typing import List, Tuple, Dict
import json

import streamlit as st

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

# ✅ 分割ロジック（正本）: lib/word_analysis/chunking.py（作成済み）
from lib.word_analysis.chunking import (
    chunk_text_by_markers,
    make_planned_filenames,
)

# --- Inboxへ保存（common_lib.inbox.*）---
from common_lib.auth.auth_helpers import require_login
from common_lib.inbox.inbox_ops.ingest import ingest_to_inbox
from common_lib.inbox.inbox_common.types import (
    IngestRequest,
    InboxNotAvailable,
    QuotaExceeded,
    IngestFailed,
)

from lib.word_analysis.explanation import render_word_analysis_help_expander

from common_lib.ui.ui_basics import subtitle
from common_lib.ui.banner_lines import render_banner_line_by_key


# =========================
# 中間テキストの構築
# =========================
def build_intermediate_text(
    doc: Document,
    base_chapter: int,
    mode: str = "detailed",  # "simple" | "standard" | "detailed"
    *,
    use_same_left_placeholder: bool,
) -> Tuple[str, Dict[str, int]]:
    simple_mode = (mode == "simple")

    lines: List[str] = []
    stats = {"heading": 0, "paragraph": 0, "table": 0, "figure": 0}

    heading_counters = [0, 0, 0, 0]
    prev_block: Block | None = None
    pending_table_caption: Paragraph | None = None

    def _looks_like_heading_line(s: str) -> bool:
        """
        「見出しと思われるもの」の簡易判定（標準モード用）
        条件（あなたの要件）：
          - 句読点がない（。、「」，． など）
          - 1行のみ（= 改行なし）
          - 短すぎず長すぎない（安全側のガード）
        """
        if not s:
            return False

        t = s.strip()
        if not t:
            return False

        # 1行のみ（念のため）
        if "\n" in t or "\r" in t:
            return False

        # 句読点がない（必要なら増やしてOK）
        for ch in ["。", "、", "，", "．", ".", ",", "!", "?", "！", "？", ":", "：", ";", "；"]:
            if ch in t:
                return False

        # 長さガード（お好みで調整）
        if len(t) < 2:
            return False
        if len(t) > 80:
            return False

        return True

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
                    # mode は simple / standard / detailed
                    if mode == "simple":
                        append_blank()
                        lines.append(text)

                    elif mode == "standard":
                        # ★重要：=== HEADING のスタイルでも本文を括っている場合がある
                        # → 「見出しと思われるもの」だけを見出しとして括る
                        if _looks_like_heading_line(text):
                            lines.append("<ここから見出し>")
                            lines.append(text)
                            lines.append("<ここまで見出し>")
                            lines.append("")
                            stats["heading"] += 1
                        else:
                            # 見出しっぽくなければ本文扱いとして素のテキストで出す
                            lines.append(text)
                            stats["paragraph"] += 1

                    else:  # mode == "detailed"
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

                if mode == "simple":
                    append_blank()
                    if caption:
                        lines.append(caption)

                elif mode == "standard":
                    # 標準：見出しほど厳密にしないが、分かりやすく
                    if caption:
                        lines.append("<ここから図>")
                        lines.append(caption)
                        lines.append("<ここまで図>")
                    else:
                        lines.append("<ここから図>")
                        lines.append("<ここまで図>")

                    # image_files 行は両モード共通の情報として残す（運用上便利）
                    if img_files:
                        lines.append(f"image_files: {', '.join(img_files)}")
                    else:
                        lines.append("image_files: (none)")

                else:  # detailed
                    lines.append(f"=== FIGURE[{fig_id}] {caption} ===")
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

                if mode in ("simple", "standard"):
                    # ============================================================
                    # 表（簡素/標準モード）
                    # 方針：
                    # - <ここから表> ～ <ここまで表> を出す
                    # - 表番号/表題は「<ここから表> の直下」に1行で出す（分割されても残す）
                    # - 行は TSV（タブ区切り）で出す（12,364 のような桁カンマで列が壊れない）
                    # ============================================================
                    append_blank()

                    cells = tbl_json.get("cells", [])

                    # --- 表ブロック開始 ---
                    lines.append("<ここから表>")

                    # --- 表番号/表題（Wordキャプション由来）を <ここから表> の直下に出す ---
                    raw_num = (tbl_json.get("table_number") or "").strip()
                    raw_title = (tbl_json.get("title") or "").strip()

                    # "unknown" は表示しない
                    tbl_num = "" if raw_num.lower() == "unknown" else raw_num

                    # title を優先（多くの場合「表 2.2-1 ...」を含む）
                    label = raw_title

                    # title が空なら num を使う
                    if not label and tbl_num:
                        label = f"表 {tbl_num}".strip()

                    # title が「表」で始まらないのに num がある場合だけ補う（二重表記を避ける）
                    if label and (not label.lstrip().startswith("表")) and tbl_num:
                        label = f"表 {tbl_num} {label}".strip()

                    if label:
                        lines.append(label)


                    # --- 表本体（角括弧＋カンマ区切り：旧仕様へ戻す） ---
                    for row in cells:
                        processed = []
                        for x in row:
                            s = str(x).replace("\n", " ").replace("\r", " ")
                            s = " ".join(s.split())
                            processed.append(s)

                        # 旧仕様：列はカンマ区切り、行全体は [...] で囲む
                        row_text = ", ".join(processed)
                        lines.append(f"[{row_text}]")


                    # --- 表ブロック終了 ---
                    lines.append("<ここまで表>")
                    lines.append("")



                else:  # detailed（従来仕様）
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

# ============================================================
# バナー / ログイン（テンプレ準拠）
# ============================================================
render_banner_line_by_key("purple_light")

# ============================================================
# session_state keys（解析結果を rerun でも保持する）
# ============================================================
SS_TEXT = "word16_intermediate_text"
SS_STATS = "word16_stats"
SS_TXT_NAME = "word16_txt_name"
SS_SOURCE = "word16_source_filename"

# --- Inbox保存のためログイン必須 ---
sub = require_login(st)
if not sub:
    st.stop()

left, right = st.columns([2, 1])
with left:
    st.title("📄 Word 解析")
with right:
    st.success(f"✅ ログイン中: **{sub}**")

subtitle("生成AI入力用テキスト生成")

st.caption(
    "Word書類の文章校正を行う前処理として，Word書類をAIが読めるようにした中間テキストファイルを作成します．"
    "inboxに対応していますので，作成された中間ファイルをinboxに保存して，文章校正に進むことができます．"
    "Word書類の字数が多い時は，中間ファイルは30,000字程度に区切った複数のファイルが作成されます．"
)
st.caption("オプションは原則デフォルトで問題ありません．")

render_word_analysis_help_expander()

if not HAS_DOCX:
    st.error("python-docx がインポートできませんでした。`python-docx` をインストールしてください。")
    st.stop()

# --- サイドバー設定 ---
with st.sidebar:
    st.header("🔧 オプション")
    st.caption("「出力スタイル」は，続けて「文章校正」を行う時は「標準」で使用してくだい．")

    output_mode_label = st.radio(
        "出力スタイル",
        options=["簡素", "標準", "詳細"],
        index=1,
        horizontal=True,
        help=(
            "簡素：プレーン寄り\n"
            "標準：見出し/表などを読みやすく整形（見出し候補を <ここから見出し> で括る）\n"
            "詳細：従来の === HEADING[...] === 等のマーカー付き"
        ),
    )

    if output_mode_label == "簡素":
        output_mode = "simple"
    elif output_mode_label == "標準":
        output_mode = "standard"
    else:
        output_mode = "detailed"

    st.caption("「この章の章番号」は，1のまま使用してください")
    base_chapter = st.number_input(
        "この章の章番号 (base_chapter)",
        min_value=1,
        max_value=50,
        value=1,
        step=1,
        help="見出しIDの先頭に付ける章番号です（例: 3 → HEADING[3-1-2]）。",
    )

    st.caption("「結合セルの扱い」は，続けて「文章校正」を行う時は「横結合セルを<同左>にする」で使用してくだい．")
    merge_label = st.radio(
        "結合セルの扱い",
        options=["そのまま", "横結合セルを <同左> にする"],
        index=1,
        help="横方向に結合されているセルを <同左> で埋めることができます。",
    )
    use_same_left_placeholder = (merge_label == "横結合セルを <同左> にする")

    st.caption("「Inboxへ送る時の分割上限」は，続けて「文章校正」を行う時は30,000で使用してくだい．")
    chunk_char_limit = st.slider(
        "📏 Inbox送信用 分割上限（文字数）",
        min_value=10000,
        max_value=50000,
        value=30000,
        step=5000,
        help="「<ここから見出し> / <ここから表>」の直前を優先して切って、1ファイルがこの文字数を超えないように分割します。",
    )

uploaded_file = st.file_uploader("Word ファイル（.docx）をアップロードしてください", type=["docx"])

col_btn1, _ = st.columns([1, 3])
with col_btn1:
    run = st.button("🔍 解析して中間テキストを生成", type="primary")

if uploaded_file is None:
    st.info("まず .docx ファイルをアップロードしてください。")
    st.stop()

# 解析結果が既に session_state にあれば、run=False でも表示できるようにする
has_cached = bool(st.session_state.get(SS_TEXT)) and (st.session_state.get(SS_SOURCE) == uploaded_file.name)
if (not run) and (not has_cached):
    st.stop()

# =========================
# 解析本体
# =========================
try:
    src_doc = Document(uploaded_file)
except Exception as e:
    st.error(f"Word ファイルの読み込みに失敗しました: {e}")
    st.stop()

has_cached = bool(st.session_state.get(SS_TEXT)) and (st.session_state.get(SS_SOURCE) == uploaded_file.name)

if run or (not has_cached):
    with st.status("解析中です…", expanded=False) as status:
        intermediate_text, stats = build_intermediate_text(
            src_doc,
            base_chapter=int(base_chapter),
            mode=output_mode,
            use_same_left_placeholder=bool(use_same_left_placeholder),
        )
        status.update(label="解析完了", state="complete")

    st.session_state[SS_TEXT] = intermediate_text
    st.session_state[SS_STATS] = stats
    st.session_state[SS_SOURCE] = uploaded_file.name

    base_name = uploaded_file.name.rsplit(".", 1)[0]

    if output_mode == "simple":
        mode_jp = "簡素"
    elif output_mode == "standard":
        mode_jp = "標準"
    else:
        mode_jp = "詳細"

    st.session_state[SS_TXT_NAME] = f"{base_name}_intermediate_{mode_jp}.txt"
else:
    intermediate_text = st.session_state[SS_TEXT]
    stats = st.session_state[SS_STATS]

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

# ============================================================
# 中間テキストのファイル名（以降で共通利用）
# ============================================================
txt_name = st.session_state.get(SS_TXT_NAME) or "intermediate.txt"

st.code(intermediate_text[:3000], language="text")  # 長くなりすぎないように頭だけ
st.markdown("---")

# ============================================================
# 分割（正本） & 予定ファイル名一覧
# ============================================================
markers = ["<ここから見出し>", "<ここから表>"]

chunks_preview = chunk_text_by_markers(
    intermediate_text,
    int(chunk_char_limit),
    markers=markers,
)

planned_names: List[str] = make_planned_filenames(
    txt_name,
    len(chunks_preview),
)

st.subheader("📄 生成された中間テキスト（分割後ファイル一覧）")
if planned_names:
    st.caption("※ 文字数上限と <ここから見出し> / <ここから表> の直前を基準に分割した場合の、保存・運用上のファイル名一覧です。")
    st.code("\n".join(planned_names), language="text")
else:
    st.caption("※ テキストが空のため、分割ファイルは生成されません。")

st.markdown("---")

# =========================
# ダウンロード
# =========================
st.subheader("💾 ダウンロード")

# --- 中間テキスト (.txt) ---
buf_txt = intermediate_text.encode("utf-8")

st.download_button(
    label="⬇️ 中間テキスト（.txt）をダウンロード",
    data=buf_txt,
    file_name=txt_name,
    mime="text/plain; charset=utf-8",
)

# --- 画像 ZIP ---
img_zip_buf = collect_images_as_zip(src_doc)

_src = st.session_state.get(SS_SOURCE)
if _src:
    _base = _src.rsplit(".", 1)[0]
else:
    _base = "word_images"

zip_name = f"{_base}_images.zip"

st.download_button(
    label="⬇️ 画像ファイルを ZIP でダウンロード",
    data=img_zip_buf,
    file_name=zip_name,
    mime="application/zip",
)

# ★ rerunでも必ず定義されるようにここで再計算
if output_mode == "simple":
    mode_jp = "簡素"
elif output_mode == "standard":
    mode_jp = "標準"
else:
    mode_jp = "詳細"

# tags / origin（運用で検索・追跡しやすくする）
tags_json = '["word_analysis/intermediate"]'
origin = {
    "app": "text_studio_app",   # 必要なら実際のAPP名に置換
    "page": "16_word解析",
    "action": "word_intermediate_text",
    "source_filename": (uploaded_file.name if uploaded_file is not None else ""),
    "mode": mode_jp,
    "base_chapter": int(base_chapter),
    "chunk_char_limit": int(chunk_char_limit),
    "chunk_markers": markers,
}

# =========================
# Inbox 保存
# =========================
if st.button("📥 中間テキストを Inbox に保存", type="primary"):
    try:
        chunks = chunks_preview

        if not chunks:
            st.error("❌ 保存対象テキストが空です。")
            st.stop()

        if not planned_names or len(planned_names) != len(chunks):
            st.error("❌ 分割ファイル名の生成に失敗しました（内部状態の不整合）。")
            st.stop()

        total = len(chunks)
        saved_names: List[str] = []

        for idx, chunk in enumerate(chunks, start=1):
            fn = planned_names[idx - 1]

            origin2 = dict(origin)
            origin2.update(
                {
                    "chunk_index": idx,
                    "chunk_total": total,
                }
            )

            ingest_to_inbox(
                projects_root=PROJECTS_ROOT,
                req=IngestRequest(
                    user_sub=sub,
                    filename=fn,
                    data=chunk.encode("utf-8"),
                    tags_json=tags_json,
                    origin=origin2,
                ),
            )
            saved_names.append(fn)

        if total == 1:
            st.success("Inbox に保存しました。")
        else:
            st.success(f"Inbox に保存しました（{total}分割）。")
            st.caption("保存ファイル名：")
            st.code("\n".join(saved_names), language="text")

    except InboxNotAvailable:
        st.error("❌ Inbox が存在しません。ストレージ接続を確認してください。")

    except QuotaExceeded as e:
        st.error(
            f"❌ 容量オーバーです。"
            f" 現在={e.current} / 追加={e.incoming} / 上限={e.quota}"
        )

    except IngestFailed as e:
        st.error(f"❌ Inbox への保存に失敗しました: {e}")

st.caption(
    "この中間テキストをInboxへ保存し，Inboxからそのまま AI に投げることで、"
    "見出し構造・表（JSON）・図情報を含んだ形で文章の校正が行えます。"
)
