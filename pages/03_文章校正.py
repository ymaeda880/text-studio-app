# -*- coding: utf-8 -*-
# pages/03_文章校正.py
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
# imports（stdlib / typing）
# ============================================================
from pathlib import Path
import sys
from typing import Any
from functools import lru_cache

# ============================================================
# imports（3rd party）
# ============================================================
import streamlit as st

# ============================================================
# ページ設定（最初に1回だけ）
# ============================================================
st.set_page_config(page_title="Text Studio / 文章校正", page_icon="📝", layout="wide")

# ============================================================
# パス設定（テンプレ準拠）
# ============================================================
_THIS = Path(__file__).resolve()
APP_DIR = _THIS.parents[1]
PROJ_DIR = _THIS.parents[2]
MONO_ROOT = _THIS.parents[3]

for p in (MONO_ROOT, PROJ_DIR, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PROJECTS_ROOT = MONO_ROOT
APP_NAME = _THIS.parents[1].name
PAGE_NAME = _THIS.stem

# ============================================================
# common_lib（ログイン / busy / UI）
# ============================================================
from common_lib.sessions.page_entry import page_session_heartbeat
from common_lib.busy import busy_run
from common_lib.ui.banner_lines import render_banner_line_by_key
from common_lib.ui import render_run_summary_compact

# ============================================================
# common_lib（AI：routing）
# ============================================================
from common_lib.ai.routing import call_text

# ============================================================
# common_lib（モデル選択：テンプレ準拠）
# ============================================================
from common_lib.ui.model_picker import render_text_model_picker
from common_lib.ai.models import TEXT_MODEL_CATALOG, DEFAULT_TEXT_MODEL_KEY

# ============================================================
# common_lib（usage 抽出 / busy 後処理：テンプレ準拠）
# ============================================================
from common_lib.ai.usage_extract import extract_text_in_out_tokens
from common_lib.busy.apply_text_result import apply_text_result_to_busy

# ============================================================
# common_lib（fx：ページ入力はさせない）
# ============================================================
from common_lib.ai.costs.fx import get_default_usd_jpy
from common_lib.ui.ui_basics import subtitle

# ============================================================
# lib（読込 / 貼り付け整形）※OCRなし
# ============================================================
from lib.text_loaders import (
    load_text_generic,
    extract_pdf_text,
    load_text_from_paste,
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
# lib（ヘルプ）
# ============================================================
from lib.proofreading.explanation import render_proofreading_help_expander

# ============================================================
# lib（UIユーティリティ）
# ============================================================
from lib.proofreading.ui_utils import (
    display_pdf_bytes,
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

# ============================================================
# common_lib Inbox（picker）
# ============================================================
from common_lib.inbox.inbox_ui.file_picker import render_inbox_file_picker_no_toggle
from common_lib.inbox.inbox_ui.file_picker import InboxPickedFile

# ============================================================
# 定数
# ============================================================
DEFAULT_MODEL_KEY = DEFAULT_TEXT_MODEL_KEY
DEFAULT_MODE = "通常校正"
INBOX_DEFAULT_MODE = "解析文書校正（通常校正）"
INBOX_PAGE_SIZE = 8

# ============================================================
# バナー / ログイン（テンプレ準拠）
# ============================================================
render_banner_line_by_key("purple_light")

sub = page_session_heartbeat(
    st,
    PROJECTS_ROOT,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
)

left, right = st.columns([2, 1])
with left:
    st.title("📝 文章の校正")
with right:
    st.success(f"✅ ログイン中: **{sub}**")
subtitle("InBox対応版")
# ============================================================
# 説明（caption）
# ============================================================
st.caption(
    "word解析による中間テキストをinboxから読み込む時は，下の「入力方法」で「Inboxから」を選んでください．"
    "「Inboxから」を選んだ時は，「解析モード」は自動的に「解析文書（標準）校正（通常校正）」にセットされますので，そのまま校正を行ってください．"
)
st.caption(
    "テキストを貼り付ける時には，下の「入力方法」で「貼り付けテキスト」を選んでください．"
    "この場合の「解析モード」は「通常校正」にセットされます．"
    "「厳格校正」や「簡易校正」に変更する時は，サイドバーの解析モードを変更してください．"
)
st.caption(
    "テキストファイルをdropする時は，下の「入力方法」で「ファイルから」を選んでください．"
    "一度に校正するテキストは30,000文字程度に区切って（30,000文字以下のファイルをdropして）校正を行ってください．"
)
st.caption("個人情報や機密情報の入力は避けてください．")

st.markdown(
    "この文章校正アプリは， **継続的なプロンプトの調整が必要**です．"
    "不適切な（誤った）指摘がAIよりなされたときは，"
    "その時のwordの元ファイル，校正方針のPDFファイルを保存し，**管理者へ報告**してください．"
    "プロンプトの調整を行います．ご協力よろしくお願いします．"
)

st.markdown(
"AIそのものも日々能力向上を続けています。"
"近い将来には、文章校正においても、利用者が十分に満足できる水準の結果を、短時間で提供できるようになると考えられます。"
)


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
# セッションキー（ファイル選択変更検知）
# - 次のファイルを選んだ瞬間に、確定プレビューを消す
# ============================================================
K_LAST_FILE_SIG = f"{PAGE_NAME}__last_file_sig"
st.session_state.setdefault(K_LAST_FILE_SIG, "")

# ============================================================
# セッションキー（ファイル候補：選択中プレビュー用）
# - ファイル選択時にここへ読み込み、未解析でもプレビュー表示する
# - 「①解析（ファイル）」押下で K_SRC_TEXT に確定コピーする
# ============================================================
K_FILE_CAND_TEXT = f"{PAGE_NAME}__file_cand_text"
K_FILE_CAND_NAME = f"{PAGE_NAME}__file_cand_name"
K_FILE_CAND_SIG = f"{PAGE_NAME}__file_cand_sig"

st.session_state.setdefault(K_FILE_CAND_TEXT, "")
st.session_state.setdefault(K_FILE_CAND_NAME, "")
st.session_state.setdefault(K_FILE_CAND_SIG, "")


# ============================================================
# セッションキー（busy_run）
# ============================================================
K_LAST_RUN_ID = f"{PAGE_NAME}__last_run_id"
K_LAST_RUN_ACTION = f"{PAGE_NAME}__last_run_action"

st.session_state.setdefault(K_LAST_RUN_ID, "")
st.session_state.setdefault(K_LAST_RUN_ACTION, "")

# ============================================================
# セッションキー（Inbox picker の選択保持）
# ============================================================
K_INBOX_BYTES = f"{PAGE_NAME}_inbox_bytes"
K_INBOX_NAME = f"{PAGE_NAME}_inbox_name"
K_INBOX_KIND = f"{PAGE_NAME}_inbox_kind"
K_INBOX_ITEM = f"{PAGE_NAME}_inbox_item_id"
K_INBOX_ADDED = f"{PAGE_NAME}_inbox_added_at"

st.session_state.setdefault(K_INBOX_BYTES, b"")
st.session_state.setdefault(K_INBOX_NAME, "")
st.session_state.setdefault(K_INBOX_KIND, "")
st.session_state.setdefault(K_INBOX_ITEM, "")
st.session_state.setdefault(K_INBOX_ADDED, "")

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

# ============================================================
# 入力方式（radio）
# ============================================================
K_INPUT_METHOD = f"{PAGE_NAME}_input_method"
INPUT_PASTE = "📝 貼り付けテキスト"
INPUT_FILE = "📁 ファイルから"
INPUT_INBOX = "📥 Inboxから"
st.session_state.setdefault(K_INPUT_METHOD, INPUT_PASTE)


def _on_change_input_method() -> None:
    # ------------------------------------------------------------
    # 入力方式の切替に応じてモードを自動セット
    # ------------------------------------------------------------
    m = st.session_state.get(K_INPUT_METHOD, INPUT_PASTE)
    if m == INPUT_INBOX:
        st.session_state["proof_mode"] = INBOX_DEFAULT_MODE
    else:
        st.session_state["proof_mode"] = DEFAULT_MODE


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


# ============================================================
# ヘルプ
# ============================================================
render_proofreading_help_expander()

# ============================================================
# Sidebar（設定）
# ============================================================
with st.sidebar:
    st.header("設定")

    # ------------------------------------------------------------
    # モデル選択（テンプレ準拠）
    # - Gemini の有効/無効をページ側で厳密判定しない（表示は常に可能）
    # - 実行時エラーは common_lib 側で扱う
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
    st.caption("「解析モード」は，word解析で作成した中間ファイルを構成するときは，「解析文書校正」を選択してください．")
    st.radio(
        "🛠 解析モード",
        options=list(MODE_DEFS.keys()),
        key="proof_mode",
        help="\n\n".join([f"・{k}: {v['desc']}" for k, v in MODE_DEFS.items()]),
    )

    # ------------------------------------------------------------
    # ダウンロード形式
    # ------------------------------------------------------------
    _DL_LABELS = {"pdf": "PDF (.pdf)", "word": "Word (.docx)"}
    dl_choice_key = st.radio(
        "📦 ダウンロード形式（解析レポート）",
        options=list(_DL_LABELS.keys()),
        format_func=lambda k: _DL_LABELS[k],
        index=0,
        key="dl_format_radio",
    )

# ============================================================
# extra prompt（expander内のテキストエリア）
# ============================================================
extra_prompt = render_policy_preview(mode=st.session_state["proof_mode"])

st.divider()

# ============================================================
# 確定済み入力（①解析ボタンで確定した正本）だけを参照
# - プレビューは「確定済み(K_SRC_TEXT)」のみ表示する
# ============================================================
src_text = str(st.session_state.get(K_SRC_TEXT) or "").strip()
used_file_name: str | None = None
if src_text:
    used_file_name = str(st.session_state.get(K_SRC_NAME) or "").strip() or "input.txt"


# ============================================================
# 入力（radio：貼り付け / ファイル / Inbox）
# ============================================================
picked_method = st.radio(
    "入力方法　(InBoxのファイルを構成するときは「inboxから」を選択してください．)",
    [INPUT_PASTE, INPUT_FILE, INPUT_INBOX],
    key=K_INPUT_METHOD,
    horizontal=True,
    on_change=_on_change_input_method,
)

# ============================================================
# ① ファイルから
# ============================================================
if picked_method == INPUT_FILE:
    up = st.file_uploader(
        ".docx / .txt / .pdf をアップロード",
        type=["docx", "txt", "pdf"],
        key=f"{PAGE_NAME}_uploader",
    )

    col_mode, col_btn = st.columns([3, 1])
    with col_mode:
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

    with col_btn:
        do_analyze_file = st.button(
            "① 解析（ファイル）",
            type="primary",
            disabled=not up,
            key="btn_analyze_file",
        )

    if up:
  
        # ------------------------------------------------------------
        # ファイル選択シグネチャ（選択が変わったら候補/確定をクリア）
        # ------------------------------------------------------------
        sig = f"{up.name}:{getattr(up, 'size', 0)}"
        if str(st.session_state.get(K_LAST_FILE_SIG) or "") != sig:
            st.session_state[K_LAST_FILE_SIG] = sig

            # 確定（前のプレビュー）を必ず消す
            st.session_state[K_SRC_TEXT] = ""
            st.session_state[K_SRC_NAME] = ""
            st.session_state[K_DO_ANALYZE] = False

            # 候補もクリア
            st.session_state[K_FILE_CAND_TEXT] = ""
            st.session_state[K_FILE_CAND_NAME] = ""
            st.session_state[K_FILE_CAND_SIG] = ""

        # ------------------------------------------------------------
        # 候補の読み込み（未解析でもプレビューに出す）
        # - up.read() は使わない（rerunで空になりやすい）
        # ------------------------------------------------------------
        data_bytes = up.getvalue()
        if not data_bytes:
            st.warning("ファイルの読み込みに失敗しました（0バイト）。もう一度選択してください。")
            st.stop()

        fn = up.name or "input.txt"
        lower = fn.lower()

        cand_text = ""
        if lower.endswith(".pdf"):
            # PDFはプレビューも表示
            st.subheader("📄 PDFプレビュー")
            display_pdf_bytes(data_bytes, height=600)

            try:
                stats = extract_pdf_text(data_bytes)
            except RuntimeError as e:
                st.error(str(e))
                st.stop()

            if int(stats.get("visible", 0)) < 20:
                st.warning("このPDFは画像PDF（テキスト層なし）と判定しました。OCRツールでテキスト化してから再度お試しください。")
                st.stop()

            cand_text = (stats.get("text") or "").strip()

        else:
            from io import BytesIO
            pseudo = BytesIO(data_bytes)
            pseudo.name = fn
            try:
                cand_text = load_text_generic(pseudo)
            except RuntimeError as e:
                st.error(str(e))
                st.stop()
            cand_text = str(cand_text or "").strip()

        if not cand_text:
            st.warning("テキストを取得できませんでした。別のファイルでお試しください。")
            st.stop()

        # 候補として保存（未解析プレビュー用）
        st.session_state[K_FILE_CAND_TEXT] = cand_text
        st.session_state[K_FILE_CAND_NAME] = fn
        st.session_state[K_FILE_CAND_SIG] = sig

        # ------------------------------------------------------------
        # 「①解析（ファイル）」押下：候補 → 確定
        # ------------------------------------------------------------
        if do_analyze_file:
            st.session_state[K_SRC_TEXT] = str(st.session_state.get(K_FILE_CAND_TEXT) or "")
            st.session_state[K_SRC_NAME] = str(st.session_state.get(K_FILE_CAND_NAME) or "input.txt")
            st.session_state[K_DO_ANALYZE] = True
            st.rerun()


# ============================================================
# ② 貼り付けテキスト（デフォルト）
# ============================================================
elif picked_method == INPUT_PASTE:
    pasted = st.text_area(
        "ここに本文を貼り付け",
        height=260,
        key="pasted_text",
        placeholder="ここに本文を貼り付けてください（改行は保持されます）。",
    )

    col_mode2, col_btn2 = st.columns([3, 1])
    with col_mode2:
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
                display:inline-block;
                border:1px solid #f0b76a;
                white-space:nowrap;
            ">
                🧭 解析モード：{current_mode}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_btn2:
        do_analyze_paste = st.button(
            "① 解析（貼り付け）",
            type="primary",
            key="btn_analyze_paste",
        )

    if do_analyze_paste:
        if not str(pasted or "").strip():
            st.warning("テキストを貼り付けてください。")
            st.stop()

        src_text = load_text_from_paste(
            pasted,
            normalize=True,
            collapse_blanks=False,
            keep_blank_lines=1,
            trim_trailing=True,
        )
        used_file_name = "pasted_text.txt"

        st.session_state[K_SRC_TEXT] = str(src_text or "").strip()
        st.session_state[K_SRC_NAME] = used_file_name
        st.session_state[K_DO_ANALYZE] = True

# ============================================================
# ③ Inboxから
# ============================================================
else:
    picked: InboxPickedFile | None = render_inbox_file_picker_no_toggle(
        projects_root=PROJECTS_ROOT,
        user_sub=sub,
        key_prefix=f"{PAGE_NAME}_proof_inbox_picker",
        page_size=INBOX_PAGE_SIZE,
        kinds=["text"],
        show_kind_in_label=True,
        show_added_at_in_label=True,
    )

    if picked is not None:
        st.session_state[K_INBOX_BYTES] = picked.data_bytes or b""
        st.session_state[K_INBOX_NAME] = picked.original_name or "inbox_text.txt"
        st.session_state[K_INBOX_KIND] = picked.kind or "text"
        st.session_state[K_INBOX_ITEM] = str(picked.item_id or "")
        st.session_state[K_INBOX_ADDED] = str(getattr(picked, "added_at", "") or "")
        st.success("✅ Inbox から読み込みました（選択結果を保持しました）")

    kept_bytes: bytes = st.session_state.get(K_INBOX_BYTES, b"") or b""
    kept_name: str = st.session_state.get(K_INBOX_NAME, "") or ""


    # ------------------------------------------------------------
    # Inbox「選択ファイルを読み込む」結果（K_INBOX_BYTES）→ 候補プレビューへ反映
    # - readボタンがどこにあっても、bytes が更新されればここで候補を作る
    # - rerun ループ防止：K_FILE_CAND_SIG で同一アイテムは再処理しない
    # ------------------------------------------------------------
    inbox_item_id = str(st.session_state.get(K_INBOX_ITEM) or "")
    inbox_sig = f"inbox:{inbox_item_id}:{len(kept_bytes)}"

    if kept_bytes and inbox_item_id and str(st.session_state.get(K_FILE_CAND_SIG) or "") != inbox_sig:
        cand_text = str(_decode_text_bytes(kept_bytes) or "").strip()

        if cand_text:
            # 前の確定（解析用）プレビューを消して、候補を表示させる
            st.session_state[K_SRC_TEXT] = ""
            st.session_state[K_SRC_NAME] = ""
            st.session_state[K_DO_ANALYZE] = False

            # 候補プレビューを作る
            st.session_state[K_FILE_CAND_TEXT] = cand_text
            st.session_state[K_FILE_CAND_NAME] = kept_name or "inbox_text.txt"
            st.session_state[K_FILE_CAND_SIG] = inbox_sig

            st.rerun()


    col_mode3, col_btn3 = st.columns([3, 1])

    with col_mode3:
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

    with col_btn3:
        analyze_inbox_clicked = st.button(
            "① 解析（Inbox）",
            type="primary",
            disabled=(not bool(kept_bytes)),
            key="btn_analyze_inbox",
        )

    if analyze_inbox_clicked:
        if not kept_bytes:
            st.warning("Inbox からテキストを選択してください。")
            st.stop()

        try:
            txt = _decode_text_bytes(kept_bytes)
            src_text_new = str(txt or "").strip()
            used_file_name = kept_name or "inbox_text.txt"

            if not src_text_new:
                st.warning("テキストが空でした（0文字）。別のファイルを選択してください。")
                st.stop()

            # ①解析押下で確定
            st.session_state[K_SRC_TEXT] = src_text_new
            st.session_state[K_SRC_NAME] = used_file_name
            st.session_state[K_DO_ANALYZE] = True

            st.success("Inbox テキストを確定しました。解析を開始します。")

        except Exception as e:
            st.error(f"Inbox テキストの読み込み/変換に失敗しました: {e}")
            st.stop()


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
candidate_text = str(st.session_state.get(K_FILE_CAND_TEXT) or "").strip()
preview_text = confirmed_text or candidate_text

if preview_text:
    lines = to_numbered_lines(preview_text)

    st.subheader("👀 行番号付きプレビュー（テキスト表示）")
    st.text_area(
        "原文（番号付きプレビュー）",
        value=_render_numbered_preview_no_paging(lines),
        height=260,
    )

want_analyze = bool(st.session_state.pop(K_DO_ANALYZE, False))


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
                "input_method": str(picked_method),
                "input_chars": len(src_text or ""),
                "lines": len(lines),
                "mode": mode,
                "dl_format": str(st.session_state.get("dl_format_radio") or ""),
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
    # ダウンロード（PDF or Word）
    # - レポート生成側が usd_jpy を要求するため、fx正本から取得して渡す（ページ入力はしない）
    # - cost は推計しない（builders側の表示仕様に従う）
    # ============================================================
    st.markdown("### ⤵️ 解析レポートをダウンロード")

    file_base = (used_file_name or "pasted_text").rsplit(".", 1)[0]
    mode_label = mode.replace(" ", "")
    file_stub = f"校正結果_{file_base}_[{mode_label}]" if mode_label else f"校正結果_{file_base}"

    in_t = st.session_state.get(K_LAST_IN_TOK)
    out_t = st.session_state.get(K_LAST_OUT_TOK)

    # 取れた範囲のみ渡す（推計しない）
    # - 未取得を 0 埋めすると「0トークン」と誤解されやすいので空 dict にする
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

    # builders に渡す formatter（推計しない：未取得なら「—」）
    def _format_cost_lines_stub(*args: Any, **kwargs: Any) -> list[str]:
        return ["概算: —（このレポートでは推計しません）"]

    if str(dl_choice_key) == "pdf":
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
        if pdf_bytes:
            st.download_button(
                "PDF（.pdf）として保存",
                data=pdf_bytes,
                file_name=f"{file_stub}.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{file_stub}",
            )
        else:
            st.warning(
                "PDF を生成できませんでした。`pip install reportlab` を実行し、"
                "CIDフォント（HeiseiMin/HeiseiKakuGo）が使えるか確認してください。"
            )
    else:
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
        st.download_button(
            "Word（.docx）として保存" if ext == ".docx" else "テキスト（.txt）として保存",
            data=data_docx,
            file_name=f"{file_stub}{ext}",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if ext == ".docx"
            else "text/plain",
            key=f"dl_word_{file_stub}",
        )

# ------------------------------------------------------------
# 何も入力が無いときだけ案内を出す
# ------------------------------------------------------------
if (not preview_text) and (not want_analyze):
    st.info("入力（📝/📁/📥）から本文を指定して『① 解析』を実行してください。")

