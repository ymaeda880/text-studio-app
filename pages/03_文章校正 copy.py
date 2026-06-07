# -*- coding: utf-8 -*-
# text_studio_app/pages/03_文章校正.py
# ============================================================
# 📝 文章校正（解析：校正方針の抽出）
#
# ✅ 新テンプレ準拠（正本）：
# - page_session_heartbeat でログイン/heartbeat
# - busy_run で ai_runs.db を必ず記録
# - AI呼び出しは common_lib.ai.routing（providers 直叩き禁止）
# - tokens/cost は「返ってきた範囲」で busy/UI に反映（推計しない）
# - 後処理（tokens/cost/busy反映）は common_lib.busy.apply_text_result に寄せる
# - 実行サマリは render_run_summary_compact（テンプレと同じ“顔”）
#
# UI方針：
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
import sys
from typing import Any
from io import BytesIO

# ============================================================
# imports（3rd party）
# ============================================================
import streamlit as st

# ============================================================
# ページ設定
# - st.set_page_config は最初に1回だけ実行する
# ============================================================
st.set_page_config(
    page_title="Text Studio / 文章校正",
    page_icon="📝",
    layout="wide",
)

# ============================================================
# パス設定
# - common_lib / app lib を import できるようにする
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
# - header / banner / theme / login
# ============================================================
from common_lib.ui.page_header import render_standard_page_header

# ============================================================
# common_lib（AI実行管理）
# - busy_run / 実行サマリ / usage反映
# ============================================================
from common_lib.busy import busy_run
from common_lib.busy.apply_text_result import apply_text_result_to_busy
from common_lib.ui import render_run_summary_compact
from common_lib.ai.usage_extract import extract_text_in_out_tokens

# ============================================================
# common_lib（AI routing / model）
# - providers 直叩き禁止
# ============================================================
from common_lib.ai.routing import call_text
from common_lib.ai.models import TEXT_MODEL_CATALOG, DEFAULT_TEXT_MODEL_KEY
from common_lib.ui.model_picker import render_text_model_picker

# ============================================================
# common_lib（費用・為替）
# - ページ側で為替入力はさせない
# ============================================================
from common_lib.ai.costs.fx import get_default_usd_jpy

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
# lib（校正プロンプト）
# ============================================================
from lib.proofreading.prompts import (
    COMMON_PROMPT,
    MODE_DEFS,
    build_system_prompt,
    get_analyze_instruction,
)

# ============================================================
# lib（校正説明UI）
# ============================================================
from lib.proofreading.explanation import (
    render_proofreading_page_intro,
    render_proofreading_help_expander,
)

# ============================================================
# lib（校正UIユーティリティ）
# ============================================================
from lib.proofreading.ui_utils import (
    display_pdf_bytes,
    inject_proof_table_css,
    md_table_to_html,
    to_numbered_lines,
)

# ============================================================
# lib（校正レポート出力）
# ============================================================
from lib.proofreading.report_builders import (
    build_policy_docx_bytes as build_policy_docx_bytes_core,
    build_policy_pdf_bytes as build_policy_pdf_bytes_core,
)

# ============================================================
# 共通ヘッダー
# - settings.toml から BANNER_KEY を取得
# - banner / theme / intro CSS を描画
# - page_session_heartbeat を実行
# - title / subtitle / ログイン状態を描画
# ============================================================
sub, theme, BANNER_KEY, settings = render_standard_page_header(
    st_module=st,
    projects_root=PROJECTS_ROOT,
    app_dir=APP_DIR,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
    title="📝 文章校正",
    subtitle_text="AIによる文章校正（InBox対応版）",
    default_banner_key="navy_dark",
)

# ============================================================
# ページ説明
# ============================================================
render_proofreading_page_intro()

# ============================================================
# ヘルプ
# ============================================================
render_proofreading_help_expander(
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
# 定数（モデル / モード / Inbox）
# ============================================================
DEFAULT_MODEL_KEY = DEFAULT_TEXT_MODEL_KEY
DEFAULT_MODE = "通常校正"
INBOX_DEFAULT_MODE = "解析文書校正（通常校正）"
INBOX_PAGE_SIZE = 8

# ============================================================
# セッションキー（入力共通）
# ============================================================
K_SRC_TEXT = "proof_src_text"
K_SRC_NAME = "proof_src_name"
K_DO_ANALYZE = "proof_do_analyze"

st.session_state.setdefault(K_SRC_TEXT, "")
st.session_state.setdefault(K_SRC_NAME, "")
st.session_state.setdefault(K_DO_ANALYZE, False)

# ============================================================
# セッションキー（busy_run）
# ============================================================
K_LAST_RUN_ID = f"{PAGE_NAME}__last_run_id"
K_LAST_RUN_ACTION = f"{PAGE_NAME}__last_run_action"

st.session_state.setdefault(K_LAST_RUN_ID, "")
st.session_state.setdefault(K_LAST_RUN_ACTION, "")

# ============================================================
# セッションキー（usage/cost：推計しない）
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
# セッションキー（生成済みレポート保持）
# ============================================================
K_LAST_PDF_BYTES = f"{PAGE_NAME}__last_pdf_bytes"
K_LAST_DOCX_BYTES = f"{PAGE_NAME}__last_docx_bytes"
K_LAST_PDF_NAME = f"{PAGE_NAME}__last_pdf_name"
K_LAST_DOCX_NAME = f"{PAGE_NAME}__last_docx_name"
K_LAST_REPORT_ORIGIN = f"{PAGE_NAME}__last_report_origin"

st.session_state.setdefault(K_LAST_PDF_BYTES, None)
st.session_state.setdefault(K_LAST_DOCX_BYTES, None)
st.session_state.setdefault(K_LAST_PDF_NAME, "")
st.session_state.setdefault(K_LAST_DOCX_NAME, "")
st.session_state.setdefault(K_LAST_REPORT_ORIGIN, {})

# ============================================================
# セッションキー（テンプレ準拠：model_key）
# ============================================================
K_MODEL_KEY = f"{PAGE_NAME}__model_key"
st.session_state.setdefault(K_MODEL_KEY, DEFAULT_MODEL_KEY)

# ============================================================
# セッションキー（サイドバー）
# ============================================================
st.session_state.setdefault("proof_mode", DEFAULT_MODE)
st.session_state.setdefault("pasted_text", "")
st.session_state.setdefault("extra_user_prompt", "")


def _on_change_input_method() -> None:
    # ------------------------------------------------------------
    # 入力方式の切替に応じてモードを自動セット
    # ------------------------------------------------------------
    m = st.session_state.get(K_INPUT_METHOD, INPUT_PASTE)
    if m == INPUT_INBOX:
        st.session_state["proof_mode"] = INBOX_DEFAULT_MODE
    else:
        st.session_state["proof_mode"] = DEFAULT_MODE


# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# helper関数
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩

# ============================================================
# helper：model_key -> (provider, model)
# ============================================================
def _parse_model_key(model_key: str) -> tuple[str, str]:
    if ":" not in model_key:
        return ("openai", model_key.strip())
    p, m = model_key.split(":", 1)
    return (p.strip(), m.strip())

# ============================================================
# helper：Gemini availability（テンプレ準拠）
# - sidebar 再描画ごとの import を避けるためキャッシュ
# ============================================================
@lru_cache(maxsize=1)
def _gemini_available() -> bool:
    try:
        from google import genai  # google-genai
        _ = genai
        return True
    except Exception:
        return False

# ============================================================
# helper：Inbox bytes -> text
# ============================================================
def _decode_text_bytes(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("utf-8", errors="replace")


# ============================================================
# helper：番号付きプレビュー（pagingなし）
# ============================================================
def _render_numbered_preview_no_paging(lines: list[str]) -> str:
    return "\n".join([f"[{(i + 1):04d}] {lines[i]}" for i in range(len(lines))])


# ============================================================
# 解析プロンプト表示（expander）
# ============================================================
def render_policy_preview(*, mode: str) -> str:
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


# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# サイドバー
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩

# ============================================================
# Sidebar（設定）
# ============================================================
with st.sidebar:
    #st.header("設定")

    # ------------------------------------------------------------
    # モデル選択（テンプレ準拠）
    # - Gemini の有効/無効をページ側で厳密判定しない（表示は常に可能）
    # - 実行時エラーは common_lib 側で扱う
    # ------------------------------------------------------------
    _ = render_text_model_picker(
        title="🧠 使用モデル選択",
        catalog=TEXT_MODEL_CATALOG,
        session_key=K_MODEL_KEY,
        default_key=DEFAULT_MODEL_KEY,
        page_name=PAGE_NAME,
        gemini_available=_gemini_available(),
    )
   
    # ------------------------------------------------------------
    # 解析モード
    # ------------------------------------------------------------
    st.caption("「解析モード」は，word解析で作成した中間ファイルを構成するときは，「解析文書校正」を選択してください．")
    st.radio(
        "🛠 解析モード",
        options=list(MODE_DEFS.keys()),
        key="proof_mode",
        help="\n\n".join([f"・{k}: {v['desc']}" for k, v in MODE_DEFS.items()]),
    )


# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　メイン処理　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪

# ============================================================
# extra prompt（expander内のテキストエリア）
# ============================================================
st.divider()
st.subheader("プロンプトの追加設定（任意）")
extra_prompt = render_policy_preview(mode=st.session_state["proof_mode"])

st.divider()
st.subheader("① 校正文章の設定")

# ============================================================
# 入力ソース選択（正本UI）
# - paste / upload / inbox のUIだけ common_lib に寄せる
# - ファイル内容の解釈・抽出はこのページ側で行う
# ============================================================
input_result = render_input_source(
    projects_root=PROJECTS_ROOT,
    user_sub=sub,
    page_name=PAGE_NAME,
    key_prefix=f"{PAGE_NAME}__proof_input",
    allowed_sources=["paste", "upload", "inbox"],
    upload_types=["docx", "txt", "pdf"],
    inbox_kinds=None,
    inbox_extensions=["docx", "txt", "pdf"],
    input_label="入力方法　(InBoxのファイルを校正するときは「inboxから」を選択してください．)",
    paste_label="ここに本文を貼り付け",
    upload_label=".docx / .txt / .pdf をアップロード",
    #confirm_button_label="① 解析",
    inbox_page_size=INBOX_PAGE_SIZE,
)

if not input_result.confirmed:
    st.info("まず校正テキストを設定してください。")
    st.stop()

# ============================================================
# 解析ボタン
# ============================================================

st.divider()
st.subheader("② 文章校正")
run_clicked = st.button(
    "文章校正",
    type="primary",
    key=f"{PAGE_NAME}__run_proof",
)




if not run_clicked:
    st.stop()


current_mode = st.session_state.get("proof_mode", DEFAULT_MODE)
st.markdown(
    f"""
    <div style="
        padding:6px 10px;
        border-radius:6px;
        background-color:#ffe9c6;
        color:#8a4b0f;
        font-weight:bold;
        font-size:0.95rem;
        border:1px solid #f0b76a;
        white-space:nowrap;
        display:inline-block;
    ">
        🧭 解析モード：{current_mode}
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
        "<div style='height:16px'></div>",
        unsafe_allow_html=True,
    )


# ============================================================
# 入力確定時：ページ側でテキスト化する
# - common_lib はファイルをそのまま返すだけ
# ============================================================
K_LAST_ACCEPTED_INPUT_SIG = f"{PAGE_NAME}__last_accepted_input_sig"

st.session_state.setdefault(
    K_LAST_ACCEPTED_INPUT_SIG,
    "",
)

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

    #st.session_state[K_LAST_ACCEPTED_INPUT_SIG] = input_sig

    src_text_new = ""
    used_file_name_new = input_result.file_name or "input.txt"

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
    # 解析用正本へ確定
    # - テキスト化に成功した後だけ処理済み signature を記録する
    # ------------------------------------------------------------
    st.session_state[K_SRC_TEXT] = str(src_text_new or "").strip()
    st.session_state[K_SRC_NAME] = used_file_name_new
    st.session_state[K_DO_ANALYZE] = True
    st.session_state[K_LAST_ACCEPTED_INPUT_SIG] = input_sig

# ============================================================
# 解析の実行
# ============================================================
plan_md: str = ""
numbered_preview: str = ""

# ------------------------------------------------------------
# プレビュー表示テキスト
# - 確定（K_SRC_TEXT）があればそれを表示
# - 無ければ、ファイル候補（K_FILE_CAND_TEXT）を表示
# ------------------------------------------------------------
confirmed_text = str(st.session_state.get(K_SRC_TEXT) or "").strip()
preview_text = confirmed_text

if preview_text:
    lines = to_numbered_lines(preview_text)

    st.markdown("##### 行番号付きプレビュー（テキスト表示）")
    st.text_area(
        "原文（番号付きプレビュー）",
        value=_render_numbered_preview_no_paging(lines),
        height=260,
        label_visibility="collapsed",
    )

# ------------------------------------------------------------
# 解析実行フラグ
# - 「文章校正」ボタンを押したら、同じ入力でも再実行できるようにする
# - 入力確定時の K_DO_ANALYZE は初回入力処理用として残す
# ------------------------------------------------------------
want_analyze = bool(run_clicked)


if want_analyze:

    # ------------------------------------------------------------
    # 解析の正本は「確定（K_SRC_TEXT）」のみ
    # - プレビュー用の lines（preview_text由来）とは別に作る
    # ------------------------------------------------------------
    src_text = str(st.session_state.get(K_SRC_TEXT) or "").strip()
    used_file_name = str(st.session_state.get(K_SRC_NAME) or "input.txt")
    lines = to_numbered_lines(src_text)

    # ------------------------------------------------------------
    # model_key -> provider/model（テンプレ準拠）
    # ------------------------------------------------------------
    model_key = str(st.session_state.get(K_MODEL_KEY) or DEFAULT_MODEL_KEY)
    provider, chosen_model = _parse_model_key(model_key)
    if not provider or not chosen_model:
        st.error(f"モデル指定が不正です: {model_key}")
        st.stop()

    # ------------------------------------------------------------
    # 直近表示を初期化（推計しない）
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
    # System / prompt（ページ責務：方針の組み立て）
    # ------------------------------------------------------------
    mode = str(st.session_state.get("proof_mode") or DEFAULT_MODE)

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
    # AI 実行（busy_run）＋ 後処理は正本へ（apply_text_result_to_busy）
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
                "feature": "proofreading_policy",
                "action": "analyze_policy",
                "input_method": str(input_result.source_type),
                "input_chars": len(src_text or ""),
                "lines": len(lines),
                "mode": mode,
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

    st.success("解析が完了しました。行番号/理由つきで方針を表示します。")

    # ============================================================
    # 校正方針 表示
    # ============================================================
    st.subheader("📋 校正方針")
    html_table = md_table_to_html(plan_md)
    inject_proof_table_css()
    st.markdown(html_table, unsafe_allow_html=True)

    # ============================================================
    # 実行サマリ（テンプレと同じ“顔”）
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
    # ダウンロード / Inbox保存
    # ============================================================
    st.divider()
    st.markdown("### ③ 校正方針をダウンロード")

    file_base = (used_file_name or "pasted_text").rsplit(".", 1)[0]
    mode_label = mode.replace(" ", "")
    file_stub = f"校正結果_{file_base}_[{mode_label}]" if mode_label else f"校正結果_{file_base}"

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

    pdf_bytes = build_policy_pdf_bytes_core(
        original_numbered_preview=numbered_preview,
        plan_md=plan_md,
        model=chosen_model,
        mode=mode,
        extra_prompt=extra_prompt,
        src_name=used_file_name or "pasted_text.txt",
        usage_summary=usage_summary,
        usd_jpy=usd_jpy,
        format_cost_lines=_format_cost_lines_stub,
    )

    data_docx, ext = build_policy_docx_bytes_core(
        original_numbered_preview=numbered_preview,
        plan_md=plan_md,
        model=chosen_model,
        mode=mode,
        extra_prompt=extra_prompt,
        src_name=used_file_name or "pasted_text.txt",
        usage_summary=usage_summary,
        usd_jpy=usd_jpy,
        format_cost_lines=_format_cost_lines_stub,
    )

    pdf_name = f"{file_stub}.pdf"
    docx_name = f"{file_stub}{ext}"

    # ------------------------------------------------------------
    # 生成済みデータを session_state に保持
    # - download_button / inbox保存ボタンを続けて押せるようにする
    # ------------------------------------------------------------
    st.session_state[K_LAST_PDF_BYTES] = pdf_bytes
    st.session_state[K_LAST_DOCX_BYTES] = data_docx
    st.session_state[K_LAST_PDF_NAME] = pdf_name
    st.session_state[K_LAST_DOCX_NAME] = docx_name
    st.session_state[K_LAST_REPORT_ORIGIN] = {
        "app": APP_NAME,
        "page": PAGE_NAME,
        "source_filename": used_file_name,
        "mode": mode,
        "model": chosen_model,
    }

    # ------------------------------------------------------------
    # 4ボタン横並び
    # ------------------------------------------------------------
    col_pdf_dl, col_word_dl, col_pdf_inbox, col_word_inbox = st.columns(4)

    with col_pdf_dl:
        if st.session_state.get(K_LAST_PDF_BYTES):
            st.download_button(
                "PDFとして保存",
                data=st.session_state[K_LAST_PDF_BYTES],
                file_name=st.session_state[K_LAST_PDF_NAME],
                mime="application/pdf",
                key=f"{PAGE_NAME}__dl_pdf_{file_stub}",
                on_click="ignore",
            )
        else:
            st.warning("PDFを生成できませんでした。")

    with col_word_dl:
        st.download_button(
            "Wordとして保存",
            data=st.session_state[K_LAST_DOCX_BYTES],
            file_name=st.session_state[K_LAST_DOCX_NAME],
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"{PAGE_NAME}__dl_word_{file_stub}",
            on_click="ignore",
        )

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
                origin["action"] = "proofreading_report_pdf"

                ingest_to_inbox(
                    projects_root=PROJECTS_ROOT,
                    req=IngestRequest(
                        user_sub=sub,
                        filename=pdf_filename,
                        data=pdf_data,
                        tags_json='["text_studio/proofreading_report/pdf"]',
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
                origin["action"] = "proofreading_report_word"

                ingest_to_inbox(
                    projects_root=PROJECTS_ROOT,
                    req=IngestRequest(
                        user_sub=sub,
                        filename=docx_filename,
                        data=docx_data,
                        tags_json='["text_studio/proofreading_report/word"]',
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
        
# ------------------------------------------------------------
# 何も入力が無いときだけ案内を出す
# ------------------------------------------------------------
if (not preview_text) and (not want_analyze):
    st.info("入力（📝/📁/📥）から本文を指定して『① 解析』を実行してください。")

