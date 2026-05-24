# -*- coding: utf-8 -*-
# text_studio_app/pages/12_一括word校正.py
# ============================================================
# 📄 一括Word校正
# ============================================================
# 役割:
# - Word(.docx) を解析して中間テキストを生成
# - 中間テキストを Storages/<sub>/word_edit_app/<job>/ に保存
# - 保存済み中間テキストを radio で選択
# - 選択した中間テキストを AI で校正解析
# - 校正方針の表示 / PDF・Word ダウンロード
#
# 方針:
# - Word解析ロジックの正本は lib/word_analysis/intermediate_text.py
# - 一括Word校正の job 管理は lib/bulk_word_proofreading/job_store.py
# - 校正UI/AI実行部分は 03_文章校正.py を参照
# - 1回の job だけ保持し，新規保存時は word_edit_app 配下を全削除
# - radio の一覧は毎回ファイルシステムから読み直す
#
# UI方針:
# - use_container_width は使わない
# - st.form は使わない
# - st.button()/st.download_button() に width 引数は使わない
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
from functools import lru_cache
from pathlib import Path
from io import BytesIO
import sys
from typing import Any

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
# パス設定
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
# common_lib（ページ共通UI）
# ============================================================
from common_lib.ui.page_header import render_standard_page_header
from common_lib.ui.input_source import render_input_source

# ============================================================
# common_lib（AI実行管理）
# ============================================================
from common_lib.busy import busy_run
from common_lib.busy.apply_text_result import apply_text_result_to_busy
from common_lib.ui import render_run_summary_compact
from common_lib.ai.usage_extract import extract_text_in_out_tokens

# ============================================================
# common_lib（AI routing / model）
# ============================================================
from common_lib.ai.routing import call_text
from common_lib.ai.models import TEXT_MODEL_CATALOG, DEFAULT_TEXT_MODEL_KEY
from common_lib.ui.model_picker import render_text_model_picker

# ============================================================
# common_lib（費用・為替）
# ============================================================
from common_lib.ai.costs.fx import get_default_usd_jpy


# ============================================================
# lib（Word解析）
# ============================================================
from lib.word_analysis.intermediate_text import build_intermediate_text
from lib.word_analysis.chunking import (
    chunk_text_by_markers,
    make_planned_filenames,
)

# ============================================================
# lib（一括Word校正：job管理）
# ============================================================
from lib.bulk_word_proofreading.job_store import (
    get_word_edit_root,
    read_manifest,
    resolve_current_job_dir,
    list_saved_intermediate_files,
    read_saved_text,
    save_word_edit_job,
)

from lib.bulk_word_proofreading.explanation import (
    render_bulk_word_proofreading_intro,
    render_bulk_word_proofreading_help_expander,
)

# ============================================================
# lib（校正プロンプト）
# ============================================================
from lib.proofreading.prompts import (
    MODE_DEFS,
    COMMON_PROMPT,
    get_analyze_instruction,
    build_system_prompt,
)

# ============================================================
# lib（校正UI）
# ============================================================
from lib.proofreading.ui_utils import (
    to_numbered_lines,
    md_table_to_html,
    inject_proof_table_css,
)

# ============================================================
# lib（レポートビルダー）
# ============================================================
from lib.proofreading.report_builders import (
    build_policy_docx_bytes as build_policy_docx_bytes_core,
    build_policy_pdf_bytes as build_policy_pdf_bytes_core,
)


# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　ヘッダー　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="Text Studio / 一括Word校正",
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
    title="📄 一括Word校正",
    subtitle_text="Word解析 → 中間テキスト保存 → AI校正解析",
    default_banner_key="navy_dark",
)

# ============================================================
# ページ説明
# ============================================================
render_bulk_word_proofreading_intro()

# ============================================================
# ヘルプ
# ============================================================
render_bulk_word_proofreading_help_expander(
    theme=theme,
)

# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　前処理　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪


# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# 定数　／　session_state
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩

# ============================================================
# 定数（モデル / 校正モード）
# ============================================================
DEFAULT_MODEL_KEY = DEFAULT_TEXT_MODEL_KEY
WORD_EDIT_DEFAULT_MODE = "解析文書校正（通常校正）"

# ============================================================
# セッションキー（モデル / 入力 / 選択）
# ============================================================
K_MODEL_KEY = f"{PAGE_NAME}__model_key"
K_PROOF_MODE = f"{PAGE_NAME}__proof_mode"
K_SELECTED_LABEL = f"{PAGE_NAME}__selected_label"
K_SELECTED_TEXT = f"{PAGE_NAME}__selected_text"
K_SELECTED_NAME = f"{PAGE_NAME}__selected_name"
K_DO_ANALYZE = f"{PAGE_NAME}__do_analyze"

# ============================================================
# セッションキー（busy_run / usage）
# ============================================================
K_LAST_RUN_ID = f"{PAGE_NAME}__last_run_id"
K_LAST_RUN_ACTION = f"{PAGE_NAME}__last_run_action"
K_LAST_IN_TOK = f"{PAGE_NAME}__last_in_tok"
K_LAST_OUT_TOK = f"{PAGE_NAME}__last_out_tok"
K_LAST_COST_OBJ = f"{PAGE_NAME}__last_cost_obj"
K_LAST_MODEL = f"{PAGE_NAME}__last_model"
K_LAST_PROVIDER = f"{PAGE_NAME}__last_provider"
K_LAST_NOTE = f"{PAGE_NAME}__last_note"

K_RESULT_PLAN_MD = f"{PAGE_NAME}__result_plan_md"
K_RESULT_NUMBERED_PREVIEW = f"{PAGE_NAME}__result_numbered_preview"
K_RESULT_USED_FILE_NAME = f"{PAGE_NAME}__result_used_file_name"
K_RESULT_MODE = f"{PAGE_NAME}__result_mode"
K_RESULT_EXTRA_PROMPT = f"{PAGE_NAME}__result_extra_prompt"
K_RESULT_MODEL = f"{PAGE_NAME}__result_model"

# ============================================================
# session_state 初期化
# ============================================================
st.session_state.setdefault(K_MODEL_KEY, DEFAULT_MODEL_KEY)
st.session_state.setdefault(K_PROOF_MODE, WORD_EDIT_DEFAULT_MODE)
st.session_state.setdefault("extra_user_prompt", "")
st.session_state.setdefault(K_SELECTED_LABEL, "")
st.session_state.setdefault(K_SELECTED_TEXT, "")
st.session_state.setdefault(K_SELECTED_NAME, "")
st.session_state.setdefault(K_DO_ANALYZE, False)
st.session_state.setdefault(K_LAST_RUN_ID, "")
st.session_state.setdefault(K_LAST_RUN_ACTION, "")
st.session_state.setdefault(K_LAST_IN_TOK, None)
st.session_state.setdefault(K_LAST_OUT_TOK, None)
st.session_state.setdefault(K_LAST_COST_OBJ, None)
st.session_state.setdefault(K_LAST_MODEL, "")
st.session_state.setdefault(K_LAST_PROVIDER, "")
st.session_state.setdefault(K_LAST_NOTE, "")

st.session_state.setdefault(K_RESULT_PLAN_MD, "")
st.session_state.setdefault(K_RESULT_NUMBERED_PREVIEW, "")
st.session_state.setdefault(K_RESULT_USED_FILE_NAME, "")
st.session_state.setdefault(K_RESULT_MODE, "")
st.session_state.setdefault(K_RESULT_EXTRA_PROMPT, "")
st.session_state.setdefault(K_RESULT_MODEL, "")
# ============================================================
# python-docx check
# ============================================================
if not HAS_DOCX:
    st.error("python-docx がインポートできませんでした。`python-docx` をインストールしてください。")
    st.stop()


# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# helper関数
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩

# ------------------------------------------------------------
# model helper
# ------------------------------------------------------------
def _parse_model_key(model_key: str) -> tuple[str, str]:
    # ------------------------------------------------------------
    # provider:model 形式を分解する
    # ------------------------------------------------------------
    if ":" not in model_key:
        return ("openai", model_key.strip())

    p, m = model_key.split(":", 1)
    return (p.strip(), m.strip())


# ------------------------------------------------------------
# model helper：Gemini availability
# ------------------------------------------------------------
@lru_cache(maxsize=1)
def _gemini_available() -> bool:
    # ------------------------------------------------------------
    # google genai が利用可能か確認する
    # ------------------------------------------------------------
    try:
        from google import genai

        _ = genai
        return True
    except Exception:
        return False


# ------------------------------------------------------------
# preview helper
# ------------------------------------------------------------
def _render_numbered_preview_no_paging(lines: list[str]) -> str:
    # ------------------------------------------------------------
    # 行番号付きテキストを生成する
    # ------------------------------------------------------------
    return "\n".join([f"[{(i + 1):04d}] {lines[i]}" for i in range(len(lines))])


# ------------------------------------------------------------
# policy helper
# ------------------------------------------------------------
def render_policy_preview(*, mode: str) -> str:
    # ------------------------------------------------------------
    # 03_文章校正.py と同様
    # ------------------------------------------------------------
    analyze_base = get_analyze_instruction(mode)

    with st.expander("🧭 解析プロンプト設定（クリックで展開）", expanded=False):
        tab3, tab1, tab2 = st.tabs(["✍️ 追加プロンプト", "🧭 System", "📋 共通方針"])

        with tab1:
            st.markdown("#### 🧭 解析プロンプト（解析モード）")
            st.code(analyze_base, language="markdown")

        with tab2:
            st.markdown("#### 📋 共通方針（毎回付与）")
            st.code(COMMON_PROMPT.strip(), language="markdown")

        with tab3:
            st.markdown("#### ✍️ 追加プロンプト（任意）")
            extra = st.text_area(
                "追加プロンプトを入力",
                key="extra_user_prompt",
                placeholder="例）外来語はカタカナ優先。製品名や固有名詞は原文どおりに保持。",
                height=100,
            ) or ""

            return extra

    return ""


# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# サイドバー
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩

# ============================================================
# Sidebar（設定）
# ============================================================
with st.sidebar:
    st.header("設定")

    # ------------------------------------------------------------
    # モデル選択
    # ------------------------------------------------------------
    _ = render_text_model_picker(
        title="🧠 使用モデル",
        catalog=TEXT_MODEL_CATALOG,
        session_key=K_MODEL_KEY,
        default_key=DEFAULT_MODEL_KEY,
        page_name=PAGE_NAME,
        gemini_available=_gemini_available(),
    )

    # ------------------------------------------------------------
    # 解析モード
    # ------------------------------------------------------------
    st.caption("このページでは，中間テキスト校正のため，原則「解析文書校正」を使用してください。")

    options = list(MODE_DEFS.keys())
    default_index = options.index(WORD_EDIT_DEFAULT_MODE)

    st.radio(
        "🛠 解析モード",
        options=options,
        key=K_PROOF_MODE,
        help="\n\n".join([f"・{k}: {v['desc']}" for k, v in MODE_DEFS.items()]),
    )

    # ------------------------------------------------------------
    # ダウンロード形式
    # ------------------------------------------------------------
    _DL_LABELS = {
        "pdf": "PDF (.pdf)",
        "word": "Word (.docx)",
    }

    st.radio(
        "📦 ダウンロード形式（解析レポート）",
        options=list(_DL_LABELS.keys()),
        format_func=lambda k: _DL_LABELS[k],
        index=0,
        key=f"{PAGE_NAME}__dl_format_radio",
    )

    st.markdown("---")

    # ------------------------------------------------------------
    # Word解析オプション
    # ------------------------------------------------------------
    st.subheader("Word解析オプション")

    st.caption("「出力スタイル」は，続けて校正を行う時は「標準」で使用してください。")

    output_mode_label = st.radio(
        "出力スタイル",
        options=["簡素", "標準", "詳細"],
        index=1,
        horizontal=True,
        key=f"{PAGE_NAME}__output_mode_label",
        help=(
            "簡素：プレーン寄り\n"
            "標準：見出し/表などを読みやすく整形\n"
            "詳細：=== HEADING[...] === 等のマーカー付き"
        ),
    )

    if output_mode_label == "簡素":
        output_mode = "simple"
    elif output_mode_label == "標準":
        output_mode = "standard"
    else:
        output_mode = "detailed"

    st.caption("「この章の章番号」は，通常は 1 のままで使用してください。")

    base_chapter = st.number_input(
        "この章の章番号 (base_chapter)",
        min_value=1,
        max_value=50,
        value=1,
        step=1,
        key=f"{PAGE_NAME}__base_chapter",
    )

    st.caption("「結合セルの扱い」は，校正時は「横結合セルを <同左> にする」を推奨します。")

    merge_label = st.radio(
        "結合セルの扱い",
        options=["そのまま", "横結合セルを <同左> にする"],
        index=1,
        key=f"{PAGE_NAME}__merge_label",
    )

    use_same_left_placeholder = merge_label == "横結合セルを <同左> にする"

    st.caption("分割上限は，原則 30,000 で使用してください。")

    chunk_char_limit = st.slider(
        "📏 分割上限（文字数）",
        min_value=10000,
        max_value=50000,
        value=30000,
        step=5000,
        key=f"{PAGE_NAME}__chunk_char_limit",
        help="見出し・表の直前を優先して分割します。",
    )


# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　メイン処理　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪

# ============================================================
# 追加プロンプト
# ============================================================
st.divider()
st.subheader("プロンプトの追加設定（任意）")
extra_prompt = render_policy_preview(mode=st.session_state[K_PROOF_MODE])

st.divider()

# ============================================================
# ① Wordアップロード / 解析保存
# ============================================================
st.subheader("① Word解析して中間テキストを保存")

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

col_run1, col_info1 = st.columns([1, 3])

with col_run1:
    run_word_parse = st.button(
        "Word解析して保存",
        type="primary",
        key=f"{PAGE_NAME}__btn_parse_save",
        disabled=not input_result.confirmed,
    )

with col_info1:
    st.caption(
        "保存時には既存のファイルを削除し，新しい中間テキストを保存します。"
    )

# ============================================================
# Word解析実行
# ============================================================
if run_word_parse:

    if not input_result.confirmed:
        st.warning("Word ファイル（.docx）を選択してください。")
        st.stop()

    source_filename = str(input_result.file_name or "")

    # ============================================================
    # Wordファイルかどうかのチェック
    # ============================================================
    suffix = Path(source_filename).suffix.lower()

    if suffix != ".docx":
        st.error(
            "Word 以外のファイルが選択されました。Word（.docx）を選択してください。"
        )
        st.stop()

    try:
        src_doc = Document(
            BytesIO(input_result.data_bytes)
        )
    except Exception as e:
        st.error(f"Word ファイルの読み込みに失敗しました: {e}")
        st.stop()

    try:
        src_doc = Document(
            BytesIO(input_result.data_bytes)
        )
    except Exception as e:
        st.error(f"Word ファイルの読み込みに失敗しました: {e}")
        st.stop()


    #
    # 処理の実行
    #
    with st.status("Word解析と保存を実行中です…", expanded=False) as status:
        intermediate_text, stats = build_intermediate_text(
            src_doc,
            base_chapter=int(base_chapter),
            mode=output_mode,
            use_same_left_placeholder=bool(use_same_left_placeholder),
        )

        txt_base_name = source_filename.rsplit(".", 1)[0]

        if output_mode == "simple":
            mode_jp = "簡素"
        elif output_mode == "standard":
            mode_jp = "標準"
        else:
            mode_jp = "詳細"

        txt_name = f"{txt_base_name}_intermediate_{mode_jp}.txt"
        markers = ["<ここから見出し>", "<ここから表>"]

        chunks = chunk_text_by_markers(
            intermediate_text,
            int(chunk_char_limit),
            markers=markers,
        )

        planned_names = make_planned_filenames(
            txt_name,
            len(chunks),
        )

        if not chunks:
            status.update(label="保存失敗", state="error")
            st.error("中間テキストが空のため保存できませんでした。")
            st.stop()

        job_dir = save_word_edit_job(
            projects_root=PROJECTS_ROOT,
            user_sub=str(sub),
            source_filename=source_filename,
            output_mode=output_mode,
            base_chapter=int(base_chapter),
            use_same_left_placeholder=bool(use_same_left_placeholder),
            chunk_char_limit=int(chunk_char_limit),
            intermediate_text=intermediate_text,
            chunks=chunks,
            planned_names=planned_names,
        )

        status.update(label="保存完了", state="complete")

    st.success(
        f"Word解析を実行し，中間テキストを保存しました。"
        f"（job: {job_dir.name} / {len(chunks)}分割）"
    )
    st.rerun()

# ============================================================
# 現在保存されている job / ファイル一覧
# ============================================================
word_edit_root = get_word_edit_root(
    projects_root=PROJECTS_ROOT,
    user_sub=str(sub),
)
current_job_dir = resolve_current_job_dir(root_dir=word_edit_root)
saved_rows = list_saved_intermediate_files(job_dir=current_job_dir)

st.markdown("---")
st.subheader("② 保存済み中間テキストを選択")

if current_job_dir is not None:
    manifest = read_manifest(job_dir=current_job_dir)
    source_filename = str(manifest.get("source_filename") or "")
    created_at = str(manifest.get("created_at") or "")

    if source_filename or created_at:
        st.caption(
            f"現在の job: {current_job_dir.name}"
            f"{' / 元ファイル: ' + source_filename if source_filename else ''}"
            f"{' / 作成日時: ' + created_at if created_at else ''}"
        )

if not saved_rows:
    st.info("保存済みの中間テキストはありません。まず上で Word解析を実行してください。")
else:
    label_to_row = {row["label"]: row for row in saved_rows}
    radio_labels = list(label_to_row.keys())

    current_selected = str(st.session_state.get(K_SELECTED_LABEL) or "")

    if current_selected not in radio_labels:
        st.session_state[K_SELECTED_LABEL] = radio_labels[0]

    selected_label = st.radio(
        "校正対象の中間テキストを選択",
        options=radio_labels,
        key=K_SELECTED_LABEL,
        label_visibility="collapsed",
    )

    selected_row = label_to_row.get(selected_label)

    if selected_row is None:
        st.warning("選択中の中間テキストを取得できませんでした。")
        st.stop()

    selected_text = read_saved_text(path=selected_row["path"])
    selected_name = str(selected_row["filename"])

    # ------------------------------------------------------------
    # 選択中ファイルが変わったら、前回の校正結果をクリア
    # ------------------------------------------------------------
    prev_selected_name = str(st.session_state.get(K_SELECTED_NAME) or "")

    if prev_selected_name and prev_selected_name != selected_name:
        st.session_state[K_RESULT_PLAN_MD] = ""
        st.session_state[K_RESULT_NUMBERED_PREVIEW] = ""
        st.session_state[K_RESULT_USED_FILE_NAME] = ""
        st.session_state[K_RESULT_MODE] = ""
        st.session_state[K_RESULT_EXTRA_PROMPT] = ""
        st.session_state[K_RESULT_MODEL] = ""

    st.session_state[K_SELECTED_TEXT] = selected_text
    st.session_state[K_SELECTED_NAME] = selected_name


    st.caption(
        f"選択中: {selected_name} / {selected_row['chars']:,}文字 / "
        f"{selected_row['index']}/{selected_row['total']}"
    )

# ============================================================
# 選択済みプレビュー
# ============================================================
preview_text = str(st.session_state.get(K_SELECTED_TEXT) or "").strip()
preview_name = str(st.session_state.get(K_SELECTED_NAME) or "").strip()

if preview_text:
    preview_lines = to_numbered_lines(preview_text)

    st.markdown("##### 行番号付きプレビュー（選択中中間テキスト）")

    st.text_area(
        "原文（番号付きプレビュー）",
        value=_render_numbered_preview_no_paging(preview_lines),
        height=260,
        #key=f"{PAGE_NAME}__preview_text_area",
        label_visibility="collapsed",
    )

# ============================================================
# ③ 校正解析ボタン
# ============================================================
col_run2, col_info2 = st.columns([1, 3])

with col_run2:
    do_analyze = st.button(
        "解析（校正）",
        type="primary",
        key=f"{PAGE_NAME}__btn_analyze",
        disabled=not bool(preview_text),
    )

with col_info2:
    st.caption("選択した中間テキストに対して，校正方針（ページ/行/理由）を抽出します。")

if do_analyze:
    st.session_state[K_DO_ANALYZE] = True

# ============================================================
# 解析実行
# ============================================================
# plan_md: str = ""
# numbered_preview: str = ""

# ============================================================
# 解析実行
# ============================================================
want_analyze = bool(st.session_state.pop(K_DO_ANALYZE, False))

if want_analyze:
    src_text = str(st.session_state.get(K_SELECTED_TEXT) or "").strip()
    used_file_name = str(st.session_state.get(K_SELECTED_NAME) or "input.txt")

    if not src_text:
        st.warning("校正対象の中間テキストがありません。")
        st.stop()

    lines = to_numbered_lines(src_text)

    # ------------------------------------------------------------
    # model_key -> provider/model
    # ------------------------------------------------------------
    model_key = str(st.session_state.get(K_MODEL_KEY) or DEFAULT_MODEL_KEY)
    provider, chosen_model = _parse_model_key(model_key)

    if not provider or not chosen_model:
        st.error(f"モデル指定が不正です: {model_key}")
        st.stop()

    # ------------------------------------------------------------
    # 直近表示初期化
    # ------------------------------------------------------------
    st.session_state[K_LAST_MODEL] = chosen_model
    st.session_state[K_LAST_PROVIDER] = provider
    st.session_state[K_LAST_IN_TOK] = None
    st.session_state[K_LAST_OUT_TOK] = None
    st.session_state[K_LAST_COST_OBJ] = None
    st.session_state[K_LAST_NOTE] = ""
    st.session_state[K_LAST_RUN_ID] = ""
    st.session_state[K_LAST_RUN_ACTION] = ""

    # ------------------------------------------------------------
    # prompt 構築
    # ------------------------------------------------------------
    mode = str(st.session_state.get(K_PROOF_MODE) or WORD_EDIT_DEFAULT_MODE)

    system_prompt = build_system_prompt(
        mode=mode,
        extra=str(extra_prompt or ""),
    )

    numbered_preview = _render_numbered_preview_no_paging(lines)

    prompt = (
        "次の文章を解析し、校正方針（ページ/行/理由）を Markdown 表で出力してください。\n"
        "Markdown表以外は出力しないでください。\n\n"
        "【追加指示（任意）】\n"
        f"{(extra_prompt or '').strip()}\n\n"
        "【原文（行番号付き）】\n"
        f"{numbered_preview}\n"
    )

    # ------------------------------------------------------------
    # AI 実行（busy_run）
    # ------------------------------------------------------------
    try:
        with busy_run(
            projects_root=PROJECTS_ROOT,
            user_sub=str(sub),
            app_name=str(APP_NAME),
            page_name=str(PAGE_NAME),
            task_type="text",
            provider=provider,
            model=chosen_model,
            meta={
                "feature": "word_proofreading_policy",
                "action": "analyze_policy",
                "input_method": "word_edit_saved_text",
                "input_chars": len(src_text or ""),
                "lines": len(lines),
                "mode": mode,
                "dl_format": str(st.session_state.get(f"{PAGE_NAME}__dl_format_radio") or ""),
                "source_filename": used_file_name,
            },
        ) as br:
            st.session_state[K_LAST_RUN_ID] = br.run_id
            st.session_state[K_LAST_RUN_ACTION] = "analyze_policy"

            with st.spinner("解析中（校正方針を抽出）…"):
                res = call_text(
                    provider=provider,
                    model=chosen_model,
                    prompt=prompt,
                    system=system_prompt,
                    temperature=None,
                    max_output_tokens=None,
                    extra=None,
                )

            plan_md = (getattr(res, "text", "") or "").strip()

            pp = apply_text_result_to_busy(
                br=br,
                res=res,
                extract_text_in_out_tokens=extract_text_in_out_tokens,
                note_ok="ok",
                note_no_usage="no_usage",
                note_no_cost="no_cost",
            )

            st.session_state[K_LAST_IN_TOK] = pp.in_tokens
            st.session_state[K_LAST_OUT_TOK] = pp.out_tokens
            st.session_state[K_LAST_COST_OBJ] = pp.cost_obj
            st.session_state[K_LAST_NOTE] = pp.note

    except Exception as e:
        st.error(f"実行に失敗しました: {e}")
        st.stop()

    st.session_state[K_RESULT_PLAN_MD] = plan_md
    st.session_state[K_RESULT_NUMBERED_PREVIEW] = numbered_preview
    st.session_state[K_RESULT_USED_FILE_NAME] = used_file_name
    st.session_state[K_RESULT_MODE] = mode
    st.session_state[K_RESULT_EXTRA_PROMPT] = str(extra_prompt or "")
    st.session_state[K_RESULT_MODEL] = chosen_model

    st.success("解析が完了しました。行番号/理由つきで方針を表示します。")

# ============================================================
# 校正方針 表示・ダウンロード
# ============================================================
saved_plan_md = str(st.session_state.get(K_RESULT_PLAN_MD) or "").strip()

if saved_plan_md:
    saved_numbered_preview = str(
        st.session_state.get(K_RESULT_NUMBERED_PREVIEW) or ""
    )
    saved_used_file_name = str(
        st.session_state.get(K_RESULT_USED_FILE_NAME) or "word_intermediate.txt"
    )
    saved_mode = str(
        st.session_state.get(K_RESULT_MODE) or WORD_EDIT_DEFAULT_MODE
    )
    saved_extra_prompt = str(
        st.session_state.get(K_RESULT_EXTRA_PROMPT) or ""
    )
    saved_model = str(
        st.session_state.get(K_RESULT_MODEL) or ""
    )

    # ============================================================
    # 校正方針 表示
    # ============================================================
    st.subheader("📋 校正方針")

    html_table = md_table_to_html(saved_plan_md)
    inject_proof_table_css()
    st.markdown(html_table, unsafe_allow_html=True)

    # ============================================================
    # 実行サマリ
    # ============================================================
    render_run_summary_compact(
        projects_root=PROJECTS_ROOT,
        run_id=st.session_state.get(K_LAST_RUN_ID),
        model=st.session_state.get(K_LAST_MODEL),
        in_tokens=st.session_state.get(K_LAST_IN_TOK),
        out_tokens=st.session_state.get(K_LAST_OUT_TOK),
        cost=st.session_state.get(K_LAST_COST_OBJ),
        note=str(st.session_state.get(K_LAST_NOTE) or ""),
        show_divider=True,
    )

    # ============================================================
    # ダウンロード
    # ============================================================
    st.divider()
    st.subheader("③ 解析レポート（校正結果）をダウンロード")

    file_base = (saved_used_file_name or "word_intermediate").rsplit(".", 1)[0]
    mode_label = saved_mode.replace(" ", "")

    if mode_label:
        file_stub = f"校正結果_{file_base}_[{mode_label}]"
    else:
        file_stub = f"校正結果_{file_base}"

    in_t = st.session_state.get(K_LAST_IN_TOK)
    out_t = st.session_state.get(K_LAST_OUT_TOK)

    if isinstance(in_t, int) and isinstance(out_t, int):
        usage_summary = {
            "input_tokens": int(in_t),
            "output_tokens": int(out_t),
            "total_tokens": int(in_t + out_t),
        }
    else:
        usage_summary = {}

    fx = get_default_usd_jpy()
    usd_jpy = float(fx.usd_jpy)

    def _format_cost_lines_stub(*args: Any, **kwargs: Any) -> list[str]:
        return ["概算: —（このレポートでは推計しません）"]

    dl_choice_key = str(
        st.session_state.get(f"{PAGE_NAME}__dl_format_radio") or "pdf"
    )

    if dl_choice_key == "pdf":
        pdf_bytes = build_policy_pdf_bytes_core(
            original_numbered_preview=saved_numbered_preview,
            plan_md=saved_plan_md,
            model=saved_model,
            mode=saved_mode,
            extra_prompt=saved_extra_prompt,
            src_name=saved_used_file_name or "word_intermediate.txt",
            usage_summary=usage_summary,
            usd_jpy=usd_jpy,
            format_cost_lines=_format_cost_lines_stub,
        )

        if pdf_bytes:
            st.download_button(
                "PDFとして保存",
                data=pdf_bytes,
                file_name=f"{file_stub}.pdf",
                mime="application/pdf",
                key=f"{PAGE_NAME}__dl_pdf_{file_stub}",
            )
        else:
            st.warning(
                "PDF を生成できませんでした。`pip install reportlab` を実行し、"
                "CIDフォント（HeiseiMin/HeiseiKakuGo）が使えるか確認してください。"
            )

    else:
        data_docx, ext = build_policy_docx_bytes_core(
            original_numbered_preview=saved_numbered_preview,
            plan_md=saved_plan_md,
            model=saved_model,
            mode=saved_mode,
            extra_prompt=saved_extra_prompt,
            src_name=saved_used_file_name or "word_intermediate.txt",
            usage_summary=usage_summary,
            usd_jpy=usd_jpy,
            format_cost_lines=_format_cost_lines_stub,
        )

        st.download_button(
            "Word（.docx）として保存" if ext == ".docx" else "テキスト（.txt）として保存",
            data=data_docx,
            file_name=f"{file_stub}{ext}",
            mime=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if ext == ".docx"
                else "text/plain"
            ),
            key=f"{PAGE_NAME}__dl_word_{file_stub}",
        )

# ============================================================
# 初期案内
# ============================================================
if (not preview_text) and (not want_analyze):
    st.info("上で Word解析を実行するか、既存の中間テキストを選択してください。")