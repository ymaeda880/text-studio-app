# -*- coding: utf-8 -*-
# text_studio_app/pages/200_wordtex.py
# ============================================================
# 📄 wordTex
#
# .wtex ソースを読み込み，
# wordTex parser / builder で Word 報告書を作成する。
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
from pathlib import Path
import sys
import traceback
import hashlib

# ============================================================
# imports（3rd party）
# ============================================================
import streamlit as st

# ============================================================
# ページ設定
# - st.set_page_config は最初に1回だけ実行する
# ============================================================
st.set_page_config(
    page_title="Text Studio / wordTex",
    page_icon="📄",
    layout="wide",
)

# ============================================================
# パス設定
# - common_lib / app lib を import できるようにする
# - 03_文章校正.py / 110_word画像埋込.py の構成に合わせる
# ============================================================
_THIS = Path(__file__).resolve()
APP_DIR = _THIS.parents[1]
PROJ_DIR = _THIS.parents[2]
MONO_ROOT = _THIS.parents[3]

for p in (MONO_ROOT, PROJ_DIR, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PROJECTS_ROOT = MONO_ROOT
APP_NAME = APP_DIR.name
PAGE_NAME = _THIS.stem

# ============================================================
# common_lib
# ============================================================
from common_lib.ui.page_header import render_standard_page_header
from common_lib.ui.input_source import render_input_source

# ============================================================
# lib：wordTex
# ============================================================
from lib.wordtex.explanation import (
    render_wordtex_page_intro,
    render_wordtex_help_expander,
)
from lib.wordtex.parser import parse_wordtex_source
from lib.wordtex.builder import build_wordtex_docx_bytes
from lib.wordtex.preview.preview import (
    render_wordtex_preview,
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
    title="📄 wordTex",
    subtitle_text=".wtexソースからWord報告書を作成",
    default_banner_key="navy_dark",
)

# ============================================================
# ページ説明
# ============================================================
render_wordtex_page_intro()
render_wordtex_help_expander(
    theme=theme,
    banner_key=BANNER_KEY,
)

# ============================================================
# session_state
# ============================================================
K_SRC_TEXT = f"{PAGE_NAME}__src_text"
K_SRC_NAME = f"{PAGE_NAME}__src_name"
K_SRC_EDITOR = f"{PAGE_NAME}__src_editor"
K_LAST_INPUT_SIG = f"{PAGE_NAME}__last_input_sig"
K_PARSED = f"{PAGE_NAME}__parsed"
K_DOCX_BYTES = f"{PAGE_NAME}__docx_bytes"
K_DOCX_NAME = f"{PAGE_NAME}__docx_name"
K_DOCX_PATH = f"{PAGE_NAME}__docx_path"
K_DOCX_PREVIEW_ID = f"{PAGE_NAME}__docx_preview_id"

st.session_state.setdefault(K_SRC_TEXT, "")
st.session_state.setdefault(K_SRC_NAME, "")
st.session_state.setdefault(K_SRC_EDITOR, "")
st.session_state.setdefault(K_LAST_INPUT_SIG, "")
st.session_state.setdefault(K_PARSED, None)
st.session_state.setdefault(K_DOCX_BYTES, None)
st.session_state.setdefault(K_DOCX_NAME, "")
st.session_state.setdefault(K_DOCX_PATH, "")
st.session_state.setdefault(K_DOCX_PREVIEW_ID, "")

# ============================================================
# ① wordTexソースの設定
# ============================================================
st.divider()
st.subheader("① wordTexソースの設定")

input_result = render_input_source(
    projects_root=PROJECTS_ROOT,
    user_sub=sub,
    page_name=PAGE_NAME,
    key_prefix=f"{PAGE_NAME}__wordtex_input",
    allowed_sources=["upload","paste", "inbox"],
    upload_types=["wtex"],
    inbox_kinds=None,
    inbox_extensions=["wtex"],
    input_label="入力方法（.wtexソースを指定してください）",
    paste_label="ここにwordTexソースを貼り付け",
    upload_label=".wtex ファイルをアップロード",
    inbox_page_size=8,
)

if not input_result.confirmed:
    st.info("まず wordTex ソースを設定してください。")
    st.stop()

# ============================================================
# 入力確定
# ============================================================
# ------------------------------------------------------------
# 入力変更判定
# - 同じファイル名・同じサイズでも中身が変わる場合があるため，
#   内容ハッシュで判定する
# ------------------------------------------------------------
if input_result.data_bytes:
    input_hash_src = input_result.data_bytes
else:
    input_hash_src = str(input_result.text or "").encode(
        "utf-8",
        errors="replace",
    )

input_hash = hashlib.sha256(input_hash_src).hexdigest()

input_sig = (
    f"{input_result.source_type}|"
    f"{input_result.file_name}|"
    f"{input_hash}"
)

if st.session_state[K_LAST_INPUT_SIG] != input_sig:

    src_text = ""
    src_name = input_result.file_name or "input.wtex"

    # ------------------------------------------------------------
    # paste
    # ------------------------------------------------------------
    if input_result.source_type == "paste":
        src_text = str(input_result.text or "").strip()
        src_name = "pasted_text.wtex"

    # ------------------------------------------------------------
    # upload / inbox
    # ------------------------------------------------------------
    else:
        data_bytes = input_result.data_bytes or b""

        if not data_bytes:
            st.warning("ファイルの読み込みに失敗しました（0バイト）。")
            st.stop()

        try:
            src_text = data_bytes.decode("utf-8")
        except UnicodeDecodeError:
            src_text = data_bytes.decode("utf-8", errors="replace")

        src_text = str(src_text or "").strip()

    if not src_text:
        st.warning("wordTexソースを取得できませんでした。")
        st.stop()

    # ------------------------------------------------------------
    # 入力変更時は前回生成物を破棄
    # ------------------------------------------------------------
    st.session_state[K_SRC_TEXT] = src_text
    st.session_state[K_SRC_EDITOR] = src_text
    st.session_state[K_SRC_NAME] = src_name
    st.session_state[K_LAST_INPUT_SIG] = input_sig
    st.session_state[K_PARSED] = None
    st.session_state[K_DOCX_BYTES] = None
    st.session_state[K_DOCX_NAME] = ""
    st.session_state[K_DOCX_PATH] = ""
    st.session_state[K_DOCX_PREVIEW_ID] = ""

# ============================================================
# ② wordTexソース表示
# ============================================================
st.divider()
st.subheader("② wordTexソース表示")

src_text = str(st.session_state.get(K_SRC_TEXT) or "")
src_name = str(st.session_state.get(K_SRC_NAME) or "input.wtex")

st.caption(f"入力ファイル: {src_name}")

src_text = st.text_area(
    "wordTexソース",
    height=360,
    key=K_SRC_EDITOR,
)

st.session_state[K_SRC_TEXT] = src_text

# ============================================================
# ③ wordTex解析
# ============================================================
st.divider()
st.subheader("③ wordTex解析")

parse_clicked = st.button(
    "wordTexを解析",
    type="secondary",
    key=f"{PAGE_NAME}__parse_wordtex",
)

if parse_clicked:
    try:
        parsed = parse_wordtex_source(src_text)
        st.session_state[K_PARSED] = parsed
        st.session_state[K_DOCX_BYTES] = None
        st.session_state[K_DOCX_NAME] = ""

        st.success(f"解析しました: {len(parsed.blocks)} ブロック")

    except Exception as e:
        st.exception(e)
        st.code(traceback.format_exc())
        st.stop()

parsed = st.session_state.get(K_PARSED)

if parsed is not None:
    st.caption(f"解析済みブロック数: {len(parsed.blocks)}")

    if parsed.warnings:
        with st.expander("解析警告", expanded=False):
            for warning in parsed.warnings:
                st.warning(str(warning))

    with st.expander("解析結果（ブロック一覧）", expanded=False):
        for i, block in enumerate(parsed.blocks, start=1):
            st.markdown(f"**{i}. {type(block).__name__}**")
            st.write(block)

else:
    st.info("Word作成前に「wordTexを解析」を押してください。")

# ============================================================
# ④ Word作成
# ============================================================
st.divider()
st.subheader("④ Word作成")

create_clicked = st.button(
    "Wordを作成",
    type="primary",
    key=f"{PAGE_NAME}__create_word",
)

if create_clicked:
    try:
        if parsed is None:
            parsed = parse_wordtex_source(src_text)
            st.session_state[K_PARSED] = parsed

        docx_bytes = build_wordtex_docx_bytes(
            parsed=parsed,
            inbox_root=PROJECTS_ROOT / "InBoxStorages",
            sub=str(sub),
        )

        file_base = src_name.rsplit(".", 1)[0] if src_name else "wordtex"
        docx_name = f"{file_base}.docx"

        preview_root = (
            APP_DIR
            / "data"
            / "wordtex_preview"
            / str(sub)
        )

        preview_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        docx_path = preview_root / docx_name
        docx_path.write_bytes(docx_bytes)

        # ------------------------------------------------------------
        # プレビューID
        # - 同じファイル名でも内容が変わればキャッシュを作り直す
        # ------------------------------------------------------------
        preview_hash = hashlib.sha256(docx_bytes).hexdigest()[:12]

        preview_id = (
            f"{PAGE_NAME}_"
            f"{file_base}_"
            f"{preview_hash}"
        )

        st.session_state[K_DOCX_BYTES] = docx_bytes
        st.session_state[K_DOCX_NAME] = docx_name
        st.session_state[K_DOCX_PATH] = str(docx_path)
        st.session_state[K_DOCX_PREVIEW_ID] = preview_id

        st.success("Word文書を作成しました。")

    except Exception as e:
        st.exception(e)
        st.code(traceback.format_exc())
        st.stop()

# ============================================================
# ⑤ Wordプレビュー
# ============================================================
st.divider()
st.subheader("⑤ Wordプレビュー")

docx_path_text = str(
    st.session_state.get(K_DOCX_PATH) or ""
).strip()

if docx_path_text:

    docx_path = Path(docx_path_text)

    if docx_path.exists():

        render_wordtex_preview(
            docx_path=docx_path,
            preview_root=(
                APP_DIR
                / "data"
                / "wordtex_preview"
                / str(sub)
                / "_preview"
            ),
            key_prefix=PAGE_NAME,
        )

    else:
        st.warning("プレビュー用Wordファイルが見つかりません。")

else:
    st.info("Word作成後にプレビューできます。")


# ============================================================
# ⑥ Word保存
# ============================================================
st.divider()
st.subheader("⑥ Word保存")

if st.session_state.get(K_DOCX_BYTES):
    st.download_button(
        "Wordとして保存",
        data=st.session_state[K_DOCX_BYTES],
        file_name=st.session_state[K_DOCX_NAME] or "wordtex.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key=f"{PAGE_NAME}__download_word",
        on_click="ignore",
    )
else:
    st.info("Word作成後に保存できます。")