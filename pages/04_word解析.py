# -*- coding: utf-8 -*-
# text_studio_app/pages/04_word解析.py
#
# Word(.docx) をアップロードして内部構造をざっくり解析し、
# - 本文 / 図 / 表 / 目次候補 / 見出し を分類
# - 「生成AIへの入力用」の中間テキストを 1 つ生成してダウンロード
# - 画像ファイルを ZIP で一括ダウンロード
#
# ※ Word解析ロジックの正本:
#   text_studio_app/lib/word_analysis/intermediate_text.py

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
from pathlib import Path
import sys
from typing import List
from io import BytesIO

# ============================================================
# path
# ============================================================
_THIS = Path(__file__).resolve()
PROJECTS_ROOT = _THIS.parents[3]

APP_DIR = _THIS.parents[1]
APP_NAME = APP_DIR.name
PAGE_NAME = _THIS.stem

if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))

# ============================================================
# imports（3rd party）
# ============================================================
import streamlit as st

try:
    from docx import Document
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False

# ============================================================
# imports（app lib：Word解析）
# ============================================================
from lib.word_analysis.intermediate_text import build_intermediate_text
from lib.word_analysis.images import collect_images_as_zip
from lib.word_analysis.chunking import (
    chunk_text_by_markers,
    make_planned_filenames,
)
from lib.word_analysis.explanation import (
    render_word_analysis_page_intro,
    render_word_analysis_help_expander,
)

# ============================================================
# imports（common_lib：Inbox）
# ============================================================
from common_lib.inbox.inbox_ops.ingest import ingest_to_inbox
from common_lib.inbox.inbox_common.types import (
    IngestRequest,
    InboxNotAvailable,
    QuotaExceeded,
    IngestFailed,
)

# ============================================================
# imports（common_lib：UI）
# ============================================================
from common_lib.ui.page_header import render_standard_page_header
from common_lib.ui.input_source import render_input_source

# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　ヘッダー　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪

# ============================================================
# Streamlit UI
# ============================================================
st.set_page_config(
    page_title="Text Studio",
    page_icon="📄",
    layout="wide",
)

# ============================================================
# 共通ヘッダー
# ============================================================
sub, theme, BANNER_KEY, settings = render_standard_page_header(
    st_module=st,
    projects_root=PROJECTS_ROOT,
    app_dir=APP_DIR,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
    title="📄 Word解析",
    subtitle_text="生成AI入力用テキスト生成",
    default_banner_key="purple_light",
)

# ============================================================
# ページ説明
# ============================================================
render_word_analysis_page_intro()

# ============================================================
# ヘルプ
# ============================================================
render_word_analysis_help_expander(
    theme=theme,
)

# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　前処理　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪


# ============================================================
# session_state keys
# ============================================================
SS_TEXT = "word16_intermediate_text"
SS_STATS = "word16_stats"
SS_TXT_NAME = "word16_txt_name"
SS_SOURCE = "word16_source_filename"

# ============================================================
# python-docx check
# ============================================================
if not HAS_DOCX:
    st.error("python-docx がインポートできませんでした。`python-docx` をインストールしてください。")
    st.stop()


# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# サイドバー
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩

# ============================================================
# sidebar options
# ============================================================
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

    use_same_left_placeholder = merge_label == "横結合セルを <同左> にする"

    st.caption("「Inboxへ送る時の分割上限」は，続けて「文章校正」を行う時は30,000で使用してくだい．")

    chunk_char_limit = st.slider(
        "📏 Inbox送信用 分割上限（文字数）",
        min_value=10000,
        max_value=50000,
        value=30000,
        step=5000,
        help="「<ここから見出し> / <ここから表>」の直前を優先して切って、1ファイルがこの文字数を超えないように分割します。",
    )

# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　メイン処理　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# 入力ソース選択（upload / inbox）
# ============================================================

st.divider()
st.subheader("① Wordファイルの設定")


input_result = render_input_source(
    projects_root=PROJECTS_ROOT,
    user_sub=sub,
    page_name=PAGE_NAME,
    key_prefix=f"{PAGE_NAME}__word_input",
    allowed_sources=["upload", "inbox"],
    upload_types=["docx"],
    inbox_kinds=None,
    inbox_extensions=["docx"],
    input_label="入力方法",
    upload_label="Word ファイル（.docx）を選択してください",
    inbox_page_size=8,
)

if not input_result.confirmed:
    st.info("まず解析ファイルを設定してください。")
    st.stop()


# ============================================================
# 解析処理
# ============================================================
st.divider()
st.subheader("② Word解析")
run = st.button(
    "解析して中間テキストを生成",
    type="primary",
    key=f"{PAGE_NAME}__run_word_analysis",
)

# ============================================================
# cached result check
# ============================================================
has_cached = (
    bool(st.session_state.get(SS_TEXT))
    and st.session_state.get(SS_SOURCE) == input_result.file_name
)

if (not run) and (not has_cached):
    st.stop()

# ============================================================
# Word load
# ============================================================
try:
    src_doc = Document(
        BytesIO(input_result.data_bytes)
    )
except Exception as e:
    st.error(f"Word ファイルの読み込みに失敗しました: {e}")
    st.stop()

# ============================================================
# analyze
# ============================================================
has_cached = (
    bool(st.session_state.get(SS_TEXT))
    and st.session_state.get(SS_SOURCE) == input_result.file_name
)

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
    st.session_state[SS_SOURCE] = input_result.file_name

    base_name = input_result.file_name.rsplit(".", 1)[0]

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

# ============================================================
# result metrics
# ============================================================
st.subheader("📊 分類結果（ブロック数）")

c1, c2, c3, c4 = st.columns(4)

c1.metric("見出し数", stats.get("heading", 0))
c2.metric("本文段落数", stats.get("paragraph", 0))
c3.metric("表ブロック数", stats.get("table", 0))
c4.metric("図ブロック数", stats.get("figure", 0))

st.markdown("---")

# ============================================================
# preview
# ============================================================
st.markdown("#### 生成された中間テキスト（先頭部分プレビュー）")


txt_name = st.session_state.get(SS_TXT_NAME) or "intermediate.txt"

st.code(intermediate_text[:3000], language="text")

st.markdown("---")

# ============================================================
# split preview
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

st.markdown("#### 生成された中間テキスト（分割後ファイル一覧）")

if planned_names:
    st.caption("※ 文字数上限と <ここから見出し> / <ここから表> の直前を基準に分割した場合の、保存・運用上のファイル名一覧です。")
    st.code("\n".join(planned_names), language="text")
else:
    st.caption("※ テキストが空のため、分割ファイルは生成されません。")

#st.markdown("---")

# ============================================================
# downloads
# ============================================================
st.divider()
st.subheader("③ ダウンロード")

# ============================================================
# mode label
# ============================================================
if output_mode == "simple":
    mode_jp = "簡素"
elif output_mode == "standard":
    mode_jp = "標準"
else:
    mode_jp = "詳細"

# ============================================================
# Inbox metadata
# ============================================================
tags_json = '["word_analysis/intermediate"]'

origin = {
    "app": "text_studio_app",
    "page": "04_word解析",
    "action": "word_intermediate_text",
    "source_filename": input_result.file_name,
    "mode": mode_jp,
    "base_chapter": int(base_chapter),
    "chunk_char_limit": int(chunk_char_limit),
    "chunk_markers": markers,
}

# ============================================================
# 1) Inbox save
# ============================================================
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

# ============================================================
# 2) text download
# ============================================================
buf_txt = intermediate_text.encode("utf-8")

st.download_button(
    label="⬇️ 中間テキスト（.txt）をダウンロード",
    data=buf_txt,
    file_name=txt_name,
    mime="text/plain; charset=utf-8",
)

# ============================================================
# 3) image zip download
# ============================================================
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
# ============================================================
# footer
# ============================================================
st.caption(
    "この中間テキストをInboxへ保存し，Inboxからそのまま AI に投げることで、"
    "見出し構造・表（JSON）・図情報を含んだ形で文章の校正が行えます。"
)