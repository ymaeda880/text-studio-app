# -*- coding: utf-8 -*-
# text_studio_app/pages/21_翻訳.py
# ============================================================
# 🌐 翻訳
#
# ✅ 03_文章校正.py 正本テンプレ準拠
# - page_session_heartbeat は render_standard_page_header 側で実行
# - busy_run で ai_runs.db を記録
# - AI呼び出しは common_lib.ai.routing.call_text
# - providers 直叩き禁止
# - use_container_width は使わない
# - st.form は使わない
# - st.button()/st.download_button() に width 引数は使わない
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import sys
from typing import Any

# ============================================================
# imports（3rd party）
# ============================================================
import streamlit as st

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="Text Studio / 翻訳",
    page_icon="🌐",
    layout="wide",
)

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
# common_lib（File Input）
# ============================================================
from common_lib.ui.input_source import render_input_source

# ============================================================
# common_lib（Inbox保存）
# ============================================================
from common_lib.inbox.inbox_ops.ingest import ingest_to_inbox
from common_lib.inbox.inbox_common.types import (
    IngestRequest,
    InboxNotAvailable,
    QuotaExceeded,
    IngestFailed,
)

# ============================================================
# lib（テキスト読み込み）
# ============================================================
from lib.text_loaders import (
    extract_pdf_text,
    load_text_from_paste,
    load_text_generic,
)

# ============================================================
# lib（校正UIユーティリティ）
# ============================================================
from lib.proofreading.ui_utils import (
    display_pdf_bytes,
    to_numbered_lines,
)

# ============================================================
# lib（翻訳説明UI）
# ============================================================
from lib.translate.explanation import (
    render_translation_page_intro,
    render_translation_help_expander,
)

# ============================================================
# lib（翻訳プロンプト）
# ============================================================
from lib.translate.prompts import (
    TRANSLATE_TO_OTHER,
    TRANSLATION_DIRECTIONS,
    DEFAULT_TRANSLATION_DIRECTION,
    build_translation_system_prompt,
    build_translation_user_prompt,
)

# ============================================================
# lib（翻訳レポート出力）
# ============================================================
from lib.translate.report_builders import (
    build_translation_txt_bytes,
    build_translation_docx_bytes,
    build_translation_pdf_bytes,
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
    title="🌐 AI翻訳",
    subtitle_text="AIによる文書翻訳（InBox対応版）",
    default_banner_key="navy_dark",
)

# ============================================================
# ページ説明
# ============================================================
render_translation_page_intro()

# ============================================================
# ヘルプ
# ============================================================
render_translation_help_expander(
    theme=theme,
)


# ============================================================
# 定数
# ============================================================
DEFAULT_MODEL_KEY = DEFAULT_TEXT_MODEL_KEY
INBOX_PAGE_SIZE = 8

# ============================================================
# セッションキー（入力）
# ============================================================
K_SRC_TEXT = f"{PAGE_NAME}__src_text"
K_SRC_NAME = f"{PAGE_NAME}__src_name"
K_LAST_ACCEPTED_INPUT_SIG = f"{PAGE_NAME}__last_accepted_input_sig"

st.session_state.setdefault(K_SRC_TEXT, "")
st.session_state.setdefault(K_SRC_NAME, "")
st.session_state.setdefault(K_LAST_ACCEPTED_INPUT_SIG, "")

# ============================================================
# セッションキー（設定）
# ============================================================
K_MODEL_KEY = f"{PAGE_NAME}__model_key"
K_TRANSLATION_DIRECTION = f"{PAGE_NAME}__translation_direction"
K_OTHER_TARGET_LANGUAGE = f"{PAGE_NAME}__other_target_language"
K_EXTRA_PROMPT = f"{PAGE_NAME}__extra_prompt"

st.session_state.setdefault(K_MODEL_KEY, DEFAULT_MODEL_KEY)
st.session_state.setdefault(K_TRANSLATION_DIRECTION, DEFAULT_TRANSLATION_DIRECTION)
st.session_state.setdefault(K_EXTRA_PROMPT, "")

# ============================================================
# セッションキー（busy_run）
# ============================================================
K_LAST_RUN_ID = f"{PAGE_NAME}__last_run_id"
K_LAST_RUN_ACTION = f"{PAGE_NAME}__last_run_action"

st.session_state.setdefault(K_LAST_RUN_ID, "")
st.session_state.setdefault(K_LAST_RUN_ACTION, "")

# ============================================================
# セッションキー（usage/cost）
# ============================================================
K_LAST_IN_TOK = f"{PAGE_NAME}__last_in_tok"
K_LAST_OUT_TOK = f"{PAGE_NAME}__last_out_tok"
K_LAST_COST_OBJ = f"{PAGE_NAME}__last_cost_obj"
K_LAST_MODEL = f"{PAGE_NAME}__last_model"
K_LAST_PROVIDER = f"{PAGE_NAME}__last_provider"
K_LAST_NOTE = f"{PAGE_NAME}__last_note"

st.session_state.setdefault(K_LAST_IN_TOK, None)
st.session_state.setdefault(K_LAST_OUT_TOK, None)
st.session_state.setdefault(K_LAST_COST_OBJ, None)
st.session_state.setdefault(K_LAST_MODEL, "")
st.session_state.setdefault(K_LAST_PROVIDER, "")
st.session_state.setdefault(K_LAST_NOTE, "")

# ============================================================
# セッションキー（翻訳結果）
# ============================================================
K_LAST_TRANSLATED_TEXT = f"{PAGE_NAME}__last_translated_text"
K_LAST_NUMBERED_PREVIEW = f"{PAGE_NAME}__last_numbered_preview"
K_LAST_USED_FILE_NAME = f"{PAGE_NAME}__last_used_file_name"
K_LAST_DIRECTION = f"{PAGE_NAME}__last_direction"
K_LAST_CHOSEN_MODEL = f"{PAGE_NAME}__last_chosen_model"

st.session_state.setdefault(K_LAST_TRANSLATED_TEXT, "")
st.session_state.setdefault(K_LAST_NUMBERED_PREVIEW, "")
st.session_state.setdefault(K_LAST_USED_FILE_NAME, "")
st.session_state.setdefault(K_LAST_DIRECTION, "")
st.session_state.setdefault(K_LAST_CHOSEN_MODEL, "")

# ------------------------------------------------------------
# 番号なし翻訳結果 / 要約結果
# ------------------------------------------------------------
K_LAST_TRANSLATED_TEXT_PLAIN = f"{PAGE_NAME}__last_translated_text_plain"
K_LAST_SUMMARY_TEXT = f"{PAGE_NAME}__last_summary_text"

st.session_state.setdefault(K_LAST_TRANSLATED_TEXT_PLAIN, "")
st.session_state.setdefault(K_LAST_SUMMARY_TEXT, "")

# ============================================================
# セッションキー（生成済みファイル）
# ============================================================
K_LAST_TXT_BYTES = f"{PAGE_NAME}__last_txt_bytes"
K_LAST_DOCX_BYTES = f"{PAGE_NAME}__last_docx_bytes"
K_LAST_PDF_BYTES = f"{PAGE_NAME}__last_pdf_bytes"
K_LAST_TXT_NAME = f"{PAGE_NAME}__last_txt_name"
K_LAST_DOCX_NAME = f"{PAGE_NAME}__last_docx_name"
K_LAST_PDF_NAME = f"{PAGE_NAME}__last_pdf_name"
K_LAST_REPORT_ORIGIN = f"{PAGE_NAME}__last_report_origin"

st.session_state.setdefault(K_LAST_TXT_BYTES, None)
st.session_state.setdefault(K_LAST_DOCX_BYTES, None)
st.session_state.setdefault(K_LAST_PDF_BYTES, None)
st.session_state.setdefault(K_LAST_TXT_NAME, "")
st.session_state.setdefault(K_LAST_DOCX_NAME, "")
st.session_state.setdefault(K_LAST_PDF_NAME, "")
st.session_state.setdefault(K_LAST_REPORT_ORIGIN, {})

# ============================================================
# セッションキー（要約設定）
# ============================================================
K_SUMMARY_MODE = f"{PAGE_NAME}__summary_mode"
K_SUMMARY_LENGTH = f"{PAGE_NAME}__summary_length"

st.session_state.setdefault(K_SUMMARY_MODE, "要約なし")
st.session_state.setdefault(K_SUMMARY_LENGTH, "300字程度")

# ============================================================
# helper：model_key -> provider / model
# ============================================================
def _parse_model_key(model_key: str) -> tuple[str, str]:
    if ":" not in model_key:
        return ("openai", model_key.strip())

    provider, model = model_key.split(":", 1)
    return (provider.strip(), model.strip())


# ============================================================
# helper：Gemini availability
# ============================================================
@lru_cache(maxsize=1)
def _gemini_available() -> bool:
    try:
        from google import genai
        _ = genai
        return True
    except Exception:
        return False


# ============================================================
# helper：番号付きプレビュー
# ============================================================
def _render_numbered_preview_no_paging(lines: list[str]) -> str:
    return "\n".join([f"[{(i + 1):04d}] {lines[i]}" for i in range(len(lines))])

# ============================================================
# helper：翻訳結果から行番号を除去
# ============================================================
def _strip_number_prefix(text: str) -> str:
    """
    [0001] のような行番号を除去し、
    番号なしの翻訳結果を返す。
    """

    # ------------------------------------------------------------
    # 行単位で番号を除去
    # ------------------------------------------------------------
    cleaned_lines = []

    for line in str(text or "").splitlines():
        stripped = line.strip()

        if (
            len(stripped) >= 7
            and stripped.startswith("[")
            and stripped[5:7] == "] "
        ):
            cleaned_lines.append(stripped[7:])
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()

# ============================================================
# helper：生成済みファイルをクリア
# ============================================================
def _clear_generated_files() -> None:
    st.session_state[K_LAST_TXT_BYTES] = None
    st.session_state[K_LAST_DOCX_BYTES] = None
    st.session_state[K_LAST_PDF_BYTES] = None
    st.session_state[K_LAST_TXT_NAME] = ""
    st.session_state[K_LAST_DOCX_NAME] = ""
    st.session_state[K_LAST_PDF_NAME] = ""
    st.session_state[K_LAST_REPORT_ORIGIN] = {}


# ============================================================
# helper：翻訳結果をクリア
# ============================================================
def _clear_translation_result() -> None:
    st.session_state[K_LAST_TRANSLATED_TEXT] = ""
    st.session_state[K_LAST_NUMBERED_PREVIEW] = ""
    st.session_state[K_LAST_USED_FILE_NAME] = ""
    st.session_state[K_LAST_DIRECTION] = ""
    st.session_state[K_LAST_CHOSEN_MODEL] = ""
    # ------------------------------------------------------------
    # 番号なし翻訳結果 / 要約結果をクリア
    # ------------------------------------------------------------
    st.session_state[K_LAST_TRANSLATED_TEXT_PLAIN] = ""
    st.session_state[K_LAST_SUMMARY_TEXT] = ""
    _clear_generated_files()


# ============================================================
# helper：追加プロンプト
# ============================================================
def render_extra_prompt() -> str:
    return (
        st.text_area(
            "追加プロンプト（任意）",
            key=K_EXTRA_PROMPT,
            placeholder="例）専門用語は原文に近く訳す。固有名詞は原文表記を残す。",
            height=100,
        )
        or ""
    )


# ============================================================
# サイドバー
# ============================================================
with st.sidebar:

    # ------------------------------------------------------------
    # モデル選択
    # ------------------------------------------------------------
    _ = render_text_model_picker(
        title="🧠 使用モデル選択",
        catalog=TEXT_MODEL_CATALOG,
        session_key=K_MODEL_KEY,
        default_key=DEFAULT_MODEL_KEY,
        page_name=PAGE_NAME,
        gemini_available=_gemini_available(),
    )


# ============================================================
# メイン：追加プロンプト
# ============================================================
st.divider()
extra_prompt = render_extra_prompt()

# ============================================================
# メイン：入力設定
# ============================================================
st.divider()
st.subheader("① 翻訳する文章の設定")

input_result = render_input_source(
    projects_root=PROJECTS_ROOT,
    user_sub=sub,
    page_name=PAGE_NAME,
    key_prefix=f"{PAGE_NAME}__translation_input",
    allowed_sources=["paste", "upload", "inbox"],
    upload_types=["docx", "txt", "pdf"],
    inbox_kinds=None,
    inbox_extensions=["docx", "txt", "pdf"],
    input_label="入力方法　(InBoxのファイルを翻訳するときは「inboxから」を選択してください．)",
    paste_label="ここに本文を貼り付け",
    upload_label=".docx / .txt / .pdf をアップロード",
    inbox_page_size=INBOX_PAGE_SIZE,
)

if not input_result.confirmed:
    st.info("まず翻訳するテキストを設定してください。")
    st.stop()

# ============================================================
# メイン：翻訳方法の設定
# ============================================================
st.divider()
st.subheader("② 翻訳方法の設定")

# ------------------------------------------------------------
# 翻訳方向
# ------------------------------------------------------------
selected_translation_direction = st.radio(
    "翻訳方向",
    options=TRANSLATION_DIRECTIONS,
    key=K_TRANSLATION_DIRECTION,
    horizontal=True,
)

# ------------------------------------------------------------
# その他の言語
# ------------------------------------------------------------
if selected_translation_direction == TRANSLATE_TO_OTHER:
    st.text_input(
        "翻訳先の言語",
        key=K_OTHER_TARGET_LANGUAGE,
        placeholder="例）イタリア語，中国語，韓国語，ポルトガル語",
    )

# ------------------------------------------------------------
# 要約設定
# ------------------------------------------------------------
st.markdown("##### 要約")

st.radio(
    "要約",
    options=[
        "要約なし",
        "要約あり",
    ],
    key=K_SUMMARY_MODE,
    horizontal=True,
    label_visibility="collapsed",
)

st.radio(
    "要約の長さ",
    options=[
        "300字程度",
        "600字程度",
        "1000字程度",
    ],
    key=K_SUMMARY_LENGTH,
    horizontal=True,
)

# ============================================================
# メイン：翻訳ボタン
# ============================================================
st.divider()
st.subheader("③ 翻訳")

run_clicked = st.button(
    "翻訳",
    type="primary",
    key=f"{PAGE_NAME}__run_translation",
)

# ============================================================
# 入力確定時：テキスト化
# ============================================================
input_sig = (
    f"{input_result.source_type}|"
    f"{input_result.file_name}|"
    f"{len(input_result.data_bytes or b'')}|"
    f"{len(input_result.text or '')}"
)

if (
    input_result.confirmed
    and st.session_state[K_LAST_ACCEPTED_INPUT_SIG] != input_sig
):

    # ------------------------------------------------------------
    # 前回結果クリア
    # ------------------------------------------------------------
    _clear_translation_result()

    # ------------------------------------------------------------
    # 初期値
    # ------------------------------------------------------------
    src_text_new = ""
    used_file_name_new = input_result.file_name or "input.txt"

    # ------------------------------------------------------------
    # paste
    # ------------------------------------------------------------
    if input_result.source_type == "paste":
        src_text_new = load_text_from_paste(
            input_result.text,
            normalize=True,
            collapse_blanks=False,
            keep_blank_lines=1,
            trim_trailing=True,
        )
        used_file_name_new = "pasted_text.txt"

    # ------------------------------------------------------------
    # upload / inbox
    # ------------------------------------------------------------
    else:
        data_bytes = input_result.data_bytes or b""

        if not data_bytes:
            st.warning("ファイルの読み込みに失敗しました（0バイト）。")
            st.stop()

        fn = input_result.file_name or "input_file"
        lower = fn.lower()

        if lower.endswith(".pdf"):
            st.subheader("📄 PDFプレビュー")
            display_pdf_bytes(
                data_bytes,
                height=600,
            )

            try:
                stats = extract_pdf_text(data_bytes)
            except RuntimeError as e:
                st.error(str(e))
                st.stop()

            if int(stats.get("visible", 0)) < 20:
                st.warning(
                    "このPDFは画像PDF（テキスト層なし）と判定しました。"
                    "OCRツールでテキスト化してから再度お試しください。"
                )
                st.stop()

            src_text_new = str(stats.get("text") or "").strip()

        else:
            pseudo = BytesIO(data_bytes)
            pseudo.name = fn

            try:
                src_text_new = load_text_generic(pseudo)
            except RuntimeError as e:
                st.error(str(e))
                st.stop()

            src_text_new = str(src_text_new or "").strip()

        used_file_name_new = fn

    # ------------------------------------------------------------
    # 入力チェック
    # ------------------------------------------------------------
    if not str(src_text_new or "").strip():
        st.warning("テキストを取得できませんでした。別の入力でお試しください。")
        st.stop()

    # ------------------------------------------------------------
    # session_stateへ確定
    # ------------------------------------------------------------
    st.session_state[K_SRC_TEXT] = str(src_text_new or "").strip()
    st.session_state[K_SRC_NAME] = used_file_name_new
    st.session_state[K_LAST_ACCEPTED_INPUT_SIG] = input_sig

# ============================================================
# プレビュー表示
# ============================================================
confirmed_text = str(st.session_state.get(K_SRC_TEXT) or "").strip()
preview_text = confirmed_text

if preview_text:
    lines = to_numbered_lines(preview_text)

    st.markdown("##### 番号付きプレビュー（テキスト表示）")
    st.text_area(
        "原文（番号付きプレビュー）",
        value=_render_numbered_preview_no_paging(lines),
        height=260,
        label_visibility="collapsed",
    )

# ============================================================
# 何も結果が無い場合だけ停止
# ============================================================
if (
    not run_clicked
    and not st.session_state.get(K_LAST_TRANSLATED_TEXT)
):
    st.stop()

# ============================================================
# 翻訳実行
# ============================================================
if run_clicked:

    # ------------------------------------------------------------
    # 入力取得
    # ------------------------------------------------------------
    src_text = str(st.session_state.get(K_SRC_TEXT) or "").strip()
    used_file_name = str(st.session_state.get(K_SRC_NAME) or "input.txt")

    if not src_text:
        st.error("翻訳するテキストがありません。")
        st.stop()

    # ------------------------------------------------------------
    # 番号付き原文
    # ------------------------------------------------------------
    lines = to_numbered_lines(src_text)
    numbered_preview = _render_numbered_preview_no_paging(lines)

    # ------------------------------------------------------------
    # モデル
    # ------------------------------------------------------------
    model_key = str(st.session_state.get(K_MODEL_KEY) or DEFAULT_MODEL_KEY)
    provider, chosen_model = _parse_model_key(model_key)

    if not provider or not chosen_model:
        st.error(f"モデル指定が不正です: {model_key}")
        st.stop()

    # ------------------------------------------------------------
    # 翻訳方向
    # ------------------------------------------------------------
    selected_direction = str(
        st.session_state.get(K_TRANSLATION_DIRECTION)
        or DEFAULT_TRANSLATION_DIRECTION
    )

    # ------------------------------------------------------------
    # その他の言語を実際の翻訳方向へ変換
    # ------------------------------------------------------------
    if selected_direction == TRANSLATE_TO_OTHER:

        other_target_language = str(
            st.session_state.get(K_OTHER_TARGET_LANGUAGE)
            or ""
        ).strip()

        if not other_target_language:
            st.error(
                "「その他の言語」を選択した場合は，"
                "翻訳先の言語を入力してください．"
            )
            st.stop()

        if other_target_language.endswith("に翻訳"):
            direction = other_target_language
        else:
            direction = f"{other_target_language}に翻訳"

    else:
        direction = selected_direction

    # ------------------------------------------------------------
    # usage 表示を初期化
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
    # 生成済みファイルをクリア
    # ------------------------------------------------------------
    _clear_generated_files()

    # ------------------------------------------------------------
    # prompt
    # ------------------------------------------------------------
    system_prompt = build_translation_system_prompt(
        direction=direction,
        extra=str(extra_prompt or ""),
    )

    prompt = build_translation_user_prompt(
        numbered_preview=numbered_preview,
        direction=direction,
        extra=str(extra_prompt or ""),
    )

    # ------------------------------------------------------------
    # AI 実行
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
                "feature": "translation",
                "action": "translate_text",
                "input_method": str(input_result.source_type),
                "input_chars": len(src_text or ""),
                "lines": len(lines),
                "direction": direction,
            },
        ) as br:
            st.session_state[K_LAST_RUN_ID] = br.run_id
            st.session_state[K_LAST_RUN_ACTION] = "translate_text"

            with st.spinner("翻訳中…"):
                res = call_text(
                    provider=provider,
                    model=chosen_model,
                    prompt=prompt,
                    system=system_prompt,
                    temperature=None,
                    max_output_tokens=None,
                    extra=None,
                )

            translated_text = (getattr(res, "text", "") or "").strip()

            # ------------------------------------------------------------
            # 番号なし翻訳結果を作成
            # ------------------------------------------------------------
            translated_text_plain = _strip_number_prefix(translated_text)

            # ------------------------------------------------------------
            # 要約結果の初期値
            # ------------------------------------------------------------
            summary_text = ""

            # ------------------------------------------------------------
            # 要約ありの場合だけ要約を実行
            # ------------------------------------------------------------
            if str(st.session_state.get(K_SUMMARY_MODE) or "要約なし") == "要約あり":

                summary_length = str(
                    st.session_state.get(K_SUMMARY_LENGTH)
                    or "300字程度"
                )

                summary_prompt = (
                    f"次の翻訳結果を、日本語で{summary_length}に要約してください。\n\n"
                    f"【翻訳結果】\n"
                    f"{translated_text_plain}"
                )

                with st.spinner("要約中…"):
                    summary_res = call_text(
                        provider=provider,
                        model=chosen_model,
                        prompt=summary_prompt,
                        system="あなたは文章を簡潔で正確に要約する専門家です。",
                        temperature=None,
                        max_output_tokens=None,
                        extra=None,
                    )

                summary_text = (
                    getattr(summary_res, "text", "")
                    or ""
                ).strip()


            # ------------------------------------------------------------
            # 翻訳結果を保持
            # ------------------------------------------------------------
            st.session_state[K_LAST_TRANSLATED_TEXT] = translated_text
            st.session_state[K_LAST_NUMBERED_PREVIEW] = numbered_preview
            st.session_state[K_LAST_USED_FILE_NAME] = used_file_name
            st.session_state[K_LAST_DIRECTION] = direction
            st.session_state[K_LAST_CHOSEN_MODEL] = model_key

            # ------------------------------------------------------------
            # 番号なし翻訳結果 / 要約結果を保持
            # ------------------------------------------------------------
            st.session_state[K_LAST_TRANSLATED_TEXT_PLAIN] = translated_text_plain
            st.session_state[K_LAST_SUMMARY_TEXT] = summary_text

            # ------------------------------------------------------------
            # usage / cost
            # ------------------------------------------------------------
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

# ============================================================
# 翻訳結果表示
# ============================================================
if st.session_state.get(K_LAST_TRANSLATED_TEXT):

    if run_clicked:
        st.success("翻訳が完了しました。")

    #st.subheader("📋 翻訳結果")

    # ------------------------------------------------------------
    # 翻訳結果（番号付き）
    # ------------------------------------------------------------
    st.subheader("📋 翻訳結果（番号付き）")

    st.text_area(
        "翻訳結果（番号付き）",
        value=str(st.session_state.get(K_LAST_TRANSLATED_TEXT) or ""),
        height=260,
        label_visibility="collapsed",
    )

    # ------------------------------------------------------------
    # 翻訳結果（番号なし）
    # ------------------------------------------------------------
    st.subheader("📋 翻訳結果")

    st.text_area(
        "翻訳結果",
        value=str(st.session_state.get(K_LAST_TRANSLATED_TEXT_PLAIN) or ""),
        height=260,
        label_visibility="collapsed",
    )

    # ------------------------------------------------------------
    # 要約結果
    # ------------------------------------------------------------
    if str(st.session_state.get(K_LAST_SUMMARY_TEXT) or "").strip():

        st.subheader("📋 要約")

        st.text_area(
            "要約",
            value=str(st.session_state.get(K_LAST_SUMMARY_TEXT) or ""),
            height=180,
            label_visibility="collapsed",
        )




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
# ダウンロード / Inbox保存
# ============================================================
if st.session_state.get(K_LAST_TRANSLATED_TEXT):

    st.divider()
    st.markdown("### ④ 翻訳結果をダウンロード")

    # ------------------------------------------------------------
    # file name
    # ------------------------------------------------------------
    file_base = (
        str(st.session_state.get(K_LAST_USED_FILE_NAME) or "pasted_text")
    ).rsplit(".", 1)[0]

    last_direction = str(
        st.session_state.get(K_LAST_DIRECTION)
        or ""
    ).strip()

    # ------------------------------------------------------------
    # 翻訳先言語ごとのファイル名ラベル
    # ------------------------------------------------------------
    direction_file_labels = {
        "日本語に翻訳": "to_ja",
        "英語に翻訳": "to_en",
        "フランス語に翻訳": "to_fr",
        "ドイツ語に翻訳": "to_de",
        "スペイン語に翻訳": "to_es",
    }

    direction_label = direction_file_labels.get(last_direction)

    # ------------------------------------------------------------
    # その他の言語
    # ------------------------------------------------------------
    if not direction_label:
        custom_language = last_direction

        if custom_language.endswith("に翻訳"):
            custom_language = custom_language[:-4].strip()

        direction_label = (
            f"to_{custom_language}"
            if custom_language
            else "to_other"
        )

    # ------------------------------------------------------------
    # ファイル名に使用できない文字を置換
    # ------------------------------------------------------------
    for unsafe_char in (
        "/",
        "\\",
        ":",
        "*",
        "?",
        '"',
        "<",
        ">",
        "|",
        " ",
    ):
        direction_label = direction_label.replace(
            unsafe_char,
            "_",
        )

    file_stub = (
        f"翻訳結果_{file_base}_{direction_label}"
        if direction_label
        else f"翻訳結果_{file_base}"
    )

    # ------------------------------------------------------------
    # usage
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # generate txt
    # ------------------------------------------------------------
    if not st.session_state.get(K_LAST_TXT_BYTES):
        st.session_state[K_LAST_TXT_BYTES] = build_translation_txt_bytes(
            original_numbered_preview=str(st.session_state.get(K_LAST_NUMBERED_PREVIEW) or ""),
            model=str(st.session_state.get(K_LAST_CHOSEN_MODEL) or ""),
            direction=str(st.session_state.get(K_LAST_DIRECTION) or ""),
            extra_prompt=str(st.session_state.get(K_EXTRA_PROMPT) or ""),
            src_name=str(st.session_state.get(K_LAST_USED_FILE_NAME) or "pasted_text.txt"),
            usage_summary=usage_summary,
            translated_text_numbered=
                str(
                    st.session_state.get(
                        K_LAST_TRANSLATED_TEXT
                    ) or ""
                ),

            translated_text=
                str(
                    st.session_state.get(
                        K_LAST_TRANSLATED_TEXT_PLAIN
                    ) or ""
                ),

            summary_text=
                str(
                    st.session_state.get(
                        K_LAST_SUMMARY_TEXT
                    ) or ""
                ),
        )
        st.session_state[K_LAST_TXT_NAME] = f"{file_stub}.txt"

    # ------------------------------------------------------------
    # generate docx
    # ------------------------------------------------------------
    if not st.session_state.get(K_LAST_DOCX_BYTES):
        data_docx, ext = build_translation_docx_bytes(
            original_numbered_preview=str(st.session_state.get(K_LAST_NUMBERED_PREVIEW) or ""),
            model=str(st.session_state.get(K_LAST_CHOSEN_MODEL) or ""),
            direction=str(st.session_state.get(K_LAST_DIRECTION) or ""),
            extra_prompt=str(st.session_state.get(K_EXTRA_PROMPT) or ""),
            src_name=str(st.session_state.get(K_LAST_USED_FILE_NAME) or "pasted_text.txt"),
            usage_summary=usage_summary,

            translated_text_numbered=
                str(
                    st.session_state.get(
                        K_LAST_TRANSLATED_TEXT
                    ) or ""
                ),

            translated_text=
                str(
                    st.session_state.get(
                        K_LAST_TRANSLATED_TEXT_PLAIN
                    ) or ""
                ),

            summary_text=
                str(
                    st.session_state.get(
                        K_LAST_SUMMARY_TEXT
                    ) or ""
                ),
        )
        st.session_state[K_LAST_DOCX_BYTES] = data_docx
        st.session_state[K_LAST_DOCX_NAME] = f"{file_stub}{ext}"

    # ------------------------------------------------------------
    # generate pdf
    # ------------------------------------------------------------
    if not st.session_state.get(K_LAST_PDF_BYTES):
        st.session_state[K_LAST_PDF_BYTES] = build_translation_pdf_bytes(
            original_numbered_preview=str(st.session_state.get(K_LAST_NUMBERED_PREVIEW) or ""),
            model=str(st.session_state.get(K_LAST_CHOSEN_MODEL) or ""),
            direction=str(st.session_state.get(K_LAST_DIRECTION) or ""),
            extra_prompt=str(st.session_state.get(K_EXTRA_PROMPT) or ""),
            src_name=str(st.session_state.get(K_LAST_USED_FILE_NAME) or "pasted_text.txt"),
            usage_summary=usage_summary,
            translated_text_numbered=
                str(
                    st.session_state.get(
                        K_LAST_TRANSLATED_TEXT
                    ) or ""
                ),

            translated_text=
                str(
                    st.session_state.get(
                        K_LAST_TRANSLATED_TEXT_PLAIN
                    ) or ""
                ),

            summary_text=
                str(
                    st.session_state.get(
                        K_LAST_SUMMARY_TEXT
                    ) or ""
                ),
        )
        st.session_state[K_LAST_PDF_NAME] = f"{file_stub}.pdf"

    # ------------------------------------------------------------
    # origin
    # ------------------------------------------------------------
    if not st.session_state.get(K_LAST_REPORT_ORIGIN):
        st.session_state[K_LAST_REPORT_ORIGIN] = {
            "app": APP_NAME,
            "page": PAGE_NAME,
            "source_filename": str(st.session_state.get(K_LAST_USED_FILE_NAME) or ""),
            "direction": str(st.session_state.get(K_LAST_DIRECTION) or ""),
            "model": str(st.session_state.get(K_LAST_CHOSEN_MODEL) or ""),
        }

    # ------------------------------------------------------------
    # download columns
    # ------------------------------------------------------------
    col_txt_dl, col_word_dl, col_pdf_dl = st.columns(3)

    with col_txt_dl:
        if st.session_state.get(K_LAST_TXT_BYTES):
            st.download_button(
                "Textとして保存",
                data=st.session_state[K_LAST_TXT_BYTES],
                file_name=st.session_state[K_LAST_TXT_NAME],
                mime="text/plain",
                key=f"{PAGE_NAME}__dl_txt",
                on_click="ignore",
            )
        else:
            st.warning("Textを生成できませんでした。")

    with col_word_dl:
        if st.session_state.get(K_LAST_DOCX_BYTES):
            st.download_button(
                "Wordとして保存",
                data=st.session_state[K_LAST_DOCX_BYTES],
                file_name=st.session_state[K_LAST_DOCX_NAME],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"{PAGE_NAME}__dl_word",
                on_click="ignore",
            )
        else:
            st.warning("Wordを生成できませんでした。")

    with col_pdf_dl:
        if st.session_state.get(K_LAST_PDF_BYTES):
            st.download_button(
                "PDFとして保存",
                data=st.session_state[K_LAST_PDF_BYTES],
                file_name=st.session_state[K_LAST_PDF_NAME],
                mime="application/pdf",
                key=f"{PAGE_NAME}__dl_pdf",
                on_click="ignore",
            )
        else:
            st.warning("PDFを生成できませんでした。")

    # ------------------------------------------------------------
    # inbox columns
    # ------------------------------------------------------------
    st.markdown("### ⑤ 翻訳結果をInboxへ保存")

    col_txt_inbox, col_word_inbox, col_pdf_inbox = st.columns(3)

    with col_txt_inbox:
        if st.button(
            "TextをInboxへ保存",
            type="secondary",
            key=f"{PAGE_NAME}__save_txt_to_inbox",
        ):
            try:
                txt_data = st.session_state.get(K_LAST_TXT_BYTES)
                txt_filename = st.session_state.get(K_LAST_TXT_NAME)
                origin_base = dict(st.session_state.get(K_LAST_REPORT_ORIGIN) or {})

                if not txt_data or not txt_filename:
                    st.error("❌ Textが生成されていないため保存できません。")
                    st.stop()

                origin = dict(origin_base)
                origin["action"] = "translation_report_txt"

                ingest_to_inbox(
                    projects_root=PROJECTS_ROOT,
                    req=IngestRequest(
                        user_sub=sub,
                        filename=txt_filename,
                        data=txt_data,
                        tags_json='["text_studio/translation_report/txt"]',
                        origin=origin,
                    ),
                )

                st.success("TextをInboxに保存しました。")

            except InboxNotAvailable:
                st.error("❌ Inbox が存在しません。ストレージ接続を確認してください。")

            except QuotaExceeded as e:
                st.error(
                    f"❌ 容量オーバーです。"
                    f" 現在={e.current} / 追加={e.incoming} / 上限={e.quota}"
                )

            except IngestFailed as e:
                st.error(f"❌ Inbox への保存に失敗しました: {e}")

    with col_word_inbox:
        if st.button(
            "WordをInboxへ保存",
            type="secondary",
            key=f"{PAGE_NAME}__save_word_to_inbox",
        ):
            try:
                docx_data = st.session_state.get(K_LAST_DOCX_BYTES)
                docx_filename = st.session_state.get(K_LAST_DOCX_NAME)
                origin_base = dict(st.session_state.get(K_LAST_REPORT_ORIGIN) or {})

                if not docx_data or not docx_filename:
                    st.error("❌ Wordが生成されていないため保存できません。")
                    st.stop()

                origin = dict(origin_base)
                origin["action"] = "translation_report_word"

                ingest_to_inbox(
                    projects_root=PROJECTS_ROOT,
                    req=IngestRequest(
                        user_sub=sub,
                        filename=docx_filename,
                        data=docx_data,
                        tags_json='["text_studio/translation_report/word"]',
                        origin=origin,
                    ),
                )

                st.success("WordをInboxに保存しました。")

            except InboxNotAvailable:
                st.error("❌ Inbox が存在しません。ストレージ接続を確認してください。")

            except QuotaExceeded as e:
                st.error(
                    f"❌ 容量オーバーです。"
                    f" 現在={e.current} / 追加={e.incoming} / 上限={e.quota}"
                )

            except IngestFailed as e:
                st.error(f"❌ Inbox への保存に失敗しました: {e}")

    with col_pdf_inbox:
        if st.button(
            "PDFをInboxへ保存",
            type="secondary",
            key=f"{PAGE_NAME}__save_pdf_to_inbox",
        ):
            try:
                pdf_data = st.session_state.get(K_LAST_PDF_BYTES)
                pdf_filename = st.session_state.get(K_LAST_PDF_NAME)
                origin_base = dict(st.session_state.get(K_LAST_REPORT_ORIGIN) or {})

                if not pdf_data or not pdf_filename:
                    st.error("❌ PDFが生成されていないため保存できません。")
                    st.stop()

                origin = dict(origin_base)
                origin["action"] = "translation_report_pdf"

                ingest_to_inbox(
                    projects_root=PROJECTS_ROOT,
                    req=IngestRequest(
                        user_sub=sub,
                        filename=pdf_filename,
                        data=pdf_data,
                        tags_json='["text_studio/translation_report/pdf"]',
                        origin=origin,
                    ),
                )

                st.success("PDFをInboxに保存しました。")

            except InboxNotAvailable:
                st.error("❌ Inbox が存在しません。ストレージ接続を確認してください。")

            except QuotaExceeded as e:
                st.error(
                    f"❌ 容量オーバーです。"
                    f" 現在={e.current} / 追加={e.incoming} / 上限={e.quota}"
                )

            except IngestFailed as e:
                st.error(f"❌ Inbox への保存に失敗しました: {e}")