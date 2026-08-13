# -*- coding: utf-8 -*-
# text_studio_app/pages/18_AIチャット.py
# ------------------------------------------------------------
# 💬 AIチャット
#
# ✅ 新テンプレ準拠（正本）：
# - page_session_heartbeat でログイン/heartbeat
# - busy_run で ai_runs.db を必ず記録
# - 実行サマリ（開始/終了/経過）は render_run_summary_compact に委譲して表示（ai_runs.db 正本）
# - AI呼び出しは common_lib.ai.routing.call_text のみ（providers 直叩き禁止）
# - tokens/cost は「返ってきた範囲」で br.set_usage / br.set_cost に反映（推計しない）
# - cost 表示は common_lib.ai.costs.ui（計算しない）
#
# UI方針：
# - use_container_width は使わない
# - st.form は使わない
# - st.button()/st.download_button() に width 引数は使わない
# ------------------------------------------------------------

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# ============================================================
# 説明UI
# ============================================================
from lib.explanations.exp_AIchat import (
    render_ai_chat_page_intro,
    render_ai_chat_help_expander,
)

# ============================================================
# sys.path（テンプレ準拠：common_lib を import できるように）
# - MONO_ROOT / PROJ_DIR / APP_DIR を sys.path に入れる
# - PROJECTS_ROOT は MONO_ROOT（全ページで意味を揃える）
# ============================================================
_THIS = Path(__file__).resolve()
APP_DIR = _THIS.parents[1]
PROJ_DIR = _THIS.parents[2]
MONO_ROOT = _THIS.parents[3]

# ------------------------------------------------------------
# MONO_ROOT 妥当性チェック（ズレ事故の再発防止）
# - MONO_ROOT は common_lib を含む “モノレポ根” であること
# - 崩れている場合は静かに別DB/別Storagesへ流れるのが最悪なので、例外で止める
# ------------------------------------------------------------
if not (MONO_ROOT / "common_lib").is_dir():
    raise RuntimeError(
        "MONO_ROOT の解釈が不正です（common_lib が見つかりません）。\n"
        f"  this_file : {_THIS}\n"
        f"  MONO_ROOT  : {MONO_ROOT}\n"
        "対処：pages の階層（parents[3]）前提が崩れていないか確認してください。"
    )


for p in (MONO_ROOT, PROJ_DIR, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PROJECTS_ROOT = MONO_ROOT
APP_NAME = _THIS.parents[1].name
PAGE_NAME = _THIS.stem

# ============================================================
# Page
# ============================================================
st.set_page_config(
    page_title="💬 Text Studio / AIチャット",
    page_icon="💬",
    layout="wide",
)

# ============================================================
# common_lib（正本）
# ============================================================
from common_lib.sessions.page_entry import page_session_heartbeat
from common_lib.ui.banner_lines import render_banner_line_by_key
from common_lib.busy import busy_run
from common_lib.ai.routing import call_text
from common_lib.ui import render_run_summary_compact
from common_lib.io import read_doc_context_from_bytes, read_doc_context_from_text



from common_lib.ai.usage_extract import extract_text_in_out_tokens
from common_lib.busy.apply_text_result import apply_text_result_to_busy

# （Geminiの選択肢を出すかどうかはUI都合なので、既存configの判定は残す）
from config.config import has_gemini_api_key

from common_lib.ui.model_picker import render_text_model_picker
from common_lib.ai.models import TEXT_MODEL_CATALOG, DEFAULT_TEXT_MODEL_KEY
from functools import lru_cache

# ============================================================
# Banner + heartbeat
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
    st.title("💬 AIチャット")
with right:
    st.success(f"✅ ログイン中: **{sub}**")

st.caption(
    "文書を会話のコンテキスト（前提）としてセットすることもできます。"
    " 文書がなくても通常のチャットとして使えます。"
)

# ============================================================
# ページ説明
# ============================================================
render_ai_chat_page_intro()
render_ai_chat_help_expander()

# ============================================================
# AI送信用履歴の制限
# ============================================================
# 画面表示・JSON保存・TXT保存では全履歴を保持する．
# AIへ送信する履歴だけを，直近10往復・最大30,000文字に制限する．
PROMPT_HISTORY_MAX_MESSAGES = 20
PROMPT_HISTORY_MAX_CHARS = 30000

# ============================================================
# Session state
# ============================================================
def _ensure_state() -> None:
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []  # List[Dict[str,str]]
    if "chat_draft_key" not in st.session_state:
        st.session_state.chat_draft_key = 0
    if "doc_context" not in st.session_state:
        st.session_state.doc_context = None

    # 直近ターン（cost/usage表示用：推計しない）
    st.session_state.setdefault("chat_last_run_id", "")
    st.session_state.setdefault("chat_last_model", "")
    st.session_state.setdefault("chat_last_provider", "")
    st.session_state.setdefault("chat_last_in_tok", None)
    st.session_state.setdefault("chat_last_out_tok", None)
    st.session_state.setdefault("chat_last_cost_obj", None)
    st.session_state.setdefault("chat_last_note", "")

    # 直近ターン：最後にAIへ送った system / prompt（全文・検証用）
    st.session_state.setdefault("chat_last_system_text", "")
    st.session_state.setdefault("chat_last_prompt_text", "")


    # モデルキー（テンプレ準拠：provider:model を session_state で保持）
    st.session_state.setdefault("chat_model_key", DEFAULT_TEXT_MODEL_KEY)
    # 最大出力トークン（テンプレ準拠：session_state 正本）
    st.session_state.setdefault("chat_max_output_tokens", 8000)

    # AIへ送信した履歴の範囲
    st.session_state.setdefault("chat_last_history_message_count", 0)
    st.session_state.setdefault("chat_last_history_char_count", 0)
    st.session_state.setdefault("chat_last_history_truncated", False)

_ensure_state()

# ============================================================
# Helpers
# ============================================================

def _get_doc_context_text() -> str:
    ctx = st.session_state.get("doc_context")
    if not ctx:
        return ""
    kind = (ctx.get("kind") or "").strip()
    text = (ctx.get("text") or "").strip()
    if not text:
        return ""
    max_chars = 15000
    used = text[:max_chars]
    return f"【会話の前提文書：{kind}（先頭〜最大{max_chars}文字）】\n{used}\n"

def _build_system_instructions(has_doc: bool) -> str:
    base = "あなたは丁寧な日本語で説明するアシスタントです。"
    if has_doc:
        base += (
            "\n\n以下の『前提文書』に基づく質問には文書に沿って答え、"
            "文書にないことは推測せず不明と言ってください。"
        )
    return base

def _parse_model_key(model_key: str) -> tuple[str, str]:
    if ":" not in model_key:
        return ("openai", model_key.strip())
    p, m = model_key.split(":", 1)
    return (p.strip(), m.strip())

@lru_cache(maxsize=1)
def _gemini_available() -> bool:
    try:
        from google import genai  # google-genai
        _ = genai
        return True
    except Exception:
        return False


def _history_role_label(role: str) -> str:
    """
    履歴をプロンプトへ入れる際の役割名を返す．
    """
    normalized_role = str(role or "").strip()

    if normalized_role == "user":
        return "ユーザー"

    if normalized_role == "assistant":
        return "アシスタント"

    if normalized_role == "system":
        return "システム"

    return normalized_role or "不明"


def _build_limited_history_block() -> tuple[str, int, int, bool]:
    """
    AIへ送信する会話履歴を作成する．

    方針：
    - 画面表示用の chat_messages 自体は変更しない
    - 新しい履歴を優先する
    - 最大20メッセージ（おおむね10往復）に制限する
    - 合計30,000文字以内に制限する
    - 最新メッセージ1件だけで上限を超える場合は末尾を残す
    """

    all_messages = (
        st.session_state.get("chat_messages", [])
        or []
    )

    # ------------------------------------------------------------
    # まず直近の最大メッセージ数に制限する
    # ------------------------------------------------------------
    recent_messages = all_messages[
        -PROMPT_HISTORY_MAX_MESSAGES:
    ]

    selected_reversed: List[str] = []
    used_chars = 0
    truncated = len(all_messages) > len(recent_messages)

    # ------------------------------------------------------------
    # 新しい履歴から文字数上限内へ収める
    # ------------------------------------------------------------
    for message in reversed(recent_messages):
        if not isinstance(message, dict):
            continue

        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()

        if not content:
            continue

        label = _history_role_label(role)
        block = f"{label}: {content}"
        additional_chars = len(block)

        if selected_reversed:
            additional_chars += 1

        # --------------------------------------------------------
        # そのまま追加できる場合
        # --------------------------------------------------------
        if (
            used_chars + additional_chars
            <= PROMPT_HISTORY_MAX_CHARS
        ):
            selected_reversed.append(block)
            used_chars += additional_chars
            continue

        truncated = True

        # --------------------------------------------------------
        # まだ1件も入っていない場合は，
        # 最新メッセージの末尾だけを残す
        # --------------------------------------------------------
        if not selected_reversed:
            prefix = f"{label}: …（前半省略）"
            available_chars = max(
                0,
                PROMPT_HISTORY_MAX_CHARS - len(prefix),
            )

            if available_chars > 0:
                shortened_content = content[-available_chars:]
                shortened_block = (
                    prefix
                    + shortened_content
                )

                selected_reversed.append(shortened_block)
                used_chars = len(shortened_block)

        break

    selected_blocks = list(reversed(selected_reversed))
    history_block = "\n".join(selected_blocks).strip()

    return (
        history_block,
        len(selected_blocks),
        len(history_block),
        truncated,
    )


def _build_prompt_from_history(
    latest_user_text: str,
) -> str:
    """
    AIへ送信するプロンプトを作成する．

    方針：
    - 文書コンテキストを含める
    - 会話履歴は直近10往復・最大30,000文字に制限する
    - 今回の質問・指示は履歴とは別に1回だけ追加する
    """

    doc_text = _get_doc_context_text()

    (
        history_block,
        history_message_count,
        history_char_count,
        history_truncated,
    ) = _build_limited_history_block()

    # ------------------------------------------------------------
    # デバッグ・確認用
    # ------------------------------------------------------------
    st.session_state[
        "chat_last_history_message_count"
    ] = history_message_count

    st.session_state[
        "chat_last_history_char_count"
    ] = history_char_count

    st.session_state[
        "chat_last_history_truncated"
    ] = history_truncated

    # ------------------------------------------------------------
    # プロンプト組み立て
    # ------------------------------------------------------------
    parts: List[str] = []

    if doc_text:
        parts.append(doc_text)

    if history_block:
        history_title = "【これまでの会話】"

        if history_truncated:
            history_title += (
                "\n"
                "※古い履歴は送信上限により省略しています．"
            )

        parts.append(
            history_title
            + "\n"
            + history_block
        )

    parts.append(
        "【今回の質問・指示】\n"
        + latest_user_text
    )

    parts.append(
        "【指示】\n"
        "丁寧な日本語で回答してください．"
        "必要なら確認質問を最小限にしてください．"
    )

    return "\n\n".join(parts).strip()



# ============================================================
# History helpers（保存/復元：正本ロジック）
# ============================================================

def _history_payload_v1(*, messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    履歴保存用 payload（schema=chat_history_v1）を作る。
    doc_context も含めて保存する。
    """
    mk_payload = str(st.session_state.get("chat_model_key") or DEFAULT_TEXT_MODEL_KEY)
    p_payload, m_payload = _parse_model_key(mk_payload)

    return {
        "schema": "chat_history_v1",
        "provider": p_payload,
        "model": m_payload,
        "doc_context": st.session_state.get("doc_context"),
        "messages": messages,
    }


def _history_as_text_v1(*, messages: List[Dict[str, str]]) -> str:
    """
    人間が読みやすい TXT 形式にする（復元用ではない）。
    """
    lines: List[str] = []

    ctx = st.session_state.get("doc_context")
    if ctx and (ctx.get("text") or "").strip():
        kind = ctx.get("kind", "")
        text = ctx.get("text", "")
        head = text[:1000]
        lines.append(f"【前提文書: {kind} / 約 {len(text)} 文字 / 先頭1000文字】\n{head}")
        lines.append("")

    for m in messages:
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "").rstrip()
        if not content:
            continue
        if role == "user":
            lines.append("ユーザー:\n" + content)
        elif role == "assistant":
            lines.append("AI:\n" + content)
        else:
            lines.append(f"{role}:\n" + content)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _validate_messages_v1(obj: Any) -> bool:
    """
    messages（List[Dict]）の最低限バリデーション。
    """
    if not isinstance(obj, list):
        return False
    for m in obj:
        if not isinstance(m, dict):
            return False
        if m.get("role") not in ("user", "assistant", "system"):
            return False
        if not isinstance(m.get("content", ""), str):
            return False
    return True


def _load_history_json_bytes(raw: bytes) -> Tuple[List[Dict[str, str]], Optional[Dict[str, Any]]]:
    """
    履歴JSON（bytes）を読み込み、(messages, doc_context) を返す。
    受け付ける形式：
    - dict形式: {"schema":..., "messages":[...], "doc_context":...}
    - list形式:  [...]（messages だけ）
    """
    loaded = json.loads(raw.decode("utf-8", errors="ignore"))

    restored_docctx = None
    msgs = None

    if isinstance(loaded, dict):
        restored_docctx = loaded.get("doc_context")
        if "messages" in loaded:
            msgs = loaded.get("messages")
    else:
        msgs = loaded

    if not _validate_messages_v1(msgs):
        raise RuntimeError("このJSONは履歴形式として不正です（messagesの構造を確認してください）。")

    if isinstance(restored_docctx, dict):
        # kind/text/meta を許容（metaは無くてもOK）
        kind = restored_docctx.get("kind")
        text = restored_docctx.get("text")
        if not (isinstance(kind, str) and isinstance(text, str) and text.strip()):
            restored_docctx = None
    else:
        restored_docctx = None

    return msgs, restored_docctx


def _apply_restored_history(
    *,
    messages: List[Dict[str, str]],
    doc_context: Optional[Dict[str, Any]],
) -> None:
    """
    session_state に履歴を適用し、直近表示系はリセットする。
    """
    st.session_state.chat_messages = messages
    st.session_state.doc_context = doc_context

    # 直近情報はリセット（推計しない）
    st.session_state.chat_last_run_id = ""
    st.session_state.chat_last_model = ""
    st.session_state.chat_last_provider = ""
    st.session_state.chat_last_in_tok = None
    st.session_state.chat_last_out_tok = None
    st.session_state.chat_last_cost_obj = None
    st.session_state.chat_last_note = ""

    # 入力欄クリア：key を進める
    st.session_state.chat_draft_key = (st.session_state.get("chat_draft_key", 0) or 0) + 1



# ============================================================
# Sidebar: settings + history save/restore
# ============================================================
with st.sidebar:
    st.header("設定")

    # ------------------------------------------------------------
    # モデル選択（テンプレ準拠：render_text_model_picker）
    # - 既存の has_gemini_api_key() は「UIに出すか」の判断として残す
    # - ただし import できない環境では gemini を無効化（事故防止）
    # ------------------------------------------------------------
    gem_ok = bool(has_gemini_api_key()) and bool(_gemini_available())

    model_key = render_text_model_picker(
        title="🧠 使用モデル",
        catalog=TEXT_MODEL_CATALOG,
        session_key="chat_model_key",
        default_key=DEFAULT_TEXT_MODEL_KEY,
        page_name=PAGE_NAME,
        gemini_available=gem_ok,
    )

    provider, model = _parse_model_key(str(model_key or DEFAULT_TEXT_MODEL_KEY))
 

    max_output_tokens = st.number_input(
        "最大出力トークン（上限）",
        min_value=256,
        max_value=20000,
        step=256,
        key="chat_max_output_tokens",
    )

    debug_mode = st.toggle("デバッグ表示", value=False)

    st.divider()


    if st.button("会話履歴をクリア", key="btn_reset_chat"):
        st.session_state.pop("chat_messages", None)
        st.session_state.pop("chat_draft_key", None)
        st.session_state.pop("chat_last_run_id", None)
        st.session_state.pop("chat_last_model", None)
        st.session_state.pop("chat_last_provider", None)
        st.session_state.pop("chat_last_in_tok", None)
        st.session_state.pop("chat_last_out_tok", None)
        st.session_state.pop("chat_last_cost_obj", None)

        st.session_state.pop("chat_last_system_text", None)
        st.session_state.pop("chat_last_prompt_text", None)

        _ensure_state()
        st.rerun()


    if st.button("文書コンテキストをクリア", key="btn_clear_docctx"):
        st.session_state.pop("doc_context", None)
        st.session_state.doc_context = None
        st.rerun()


    # ============================================================
    # 履歴：ダウンロード / アップロード（JSON / TXT）
    # ============================================================
    st.divider()
    st.subheader("履歴（保存/復元）")

    # ------------------------------------------------------------
    # ダウンロードファイル名
    # - 拡張子は入力させず，JSON / TXT 側で自動付与する
    # - 未入力の場合は従来どおり chat_history を使用する
    # ------------------------------------------------------------
    history_file_name = st.text_input(
        "保存ファイル名",
        value="",
        placeholder="chat_history",
        key="history_file_name",
        help="拡張子は不要です。未入力の場合は chat_history になります。",
    )

    history_file_name = history_file_name.strip()

    if not history_file_name:
        history_file_name = "chat_history"

    messages = st.session_state.get("chat_messages", []) or []

    payload = _history_payload_v1(messages=messages)
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    txt_str = _history_as_text_v1(messages=messages)

    st.download_button(
        "⬇️ 履歴をJSONでダウンロード",
        data=json_str.encode("utf-8"),
        file_name=f"{history_file_name}.json",
        mime="application/json",
        disabled=(len(messages) == 0),
        key="dl_history_json",
    )

    st.download_button(
        "⬇️ 履歴をテキストでダウンロード",
        data=txt_str.encode("utf-8"),
        file_name=f"{history_file_name}.txt",
        mime="text/plain",
        disabled=(len(messages) == 0),
        key="dl_history_txt",
    )

    st.caption("※ JSONは復元用の正本、TXTは読みやすいログです。")

    up = st.file_uploader(
        "⬆️ 履歴JSONをアップロードして復元",
        type=["json"],
        key="upl_history_json",
        help="chat_history.json（schema=chat_history_v1）をアップロードしてください。",
    )

    restore_clicked = st.button(
        "✅ このJSONで履歴を復元",
        type="primary",
        disabled=(up is None),
        key="btn_restore_history",
        help="アップロードしたJSONを読み込み、履歴を置き換えます。",
    )

    if restore_clicked:
        try:
            raw = up.read() if up is not None else b""
            if not raw:
                st.error("アップロードされたJSONが空です。もう一度アップロードしてください。")
                st.stop()

            msgs, docctx = _load_history_json_bytes(raw)
            _apply_restored_history(messages=msgs, doc_context=docctx)

            doc_note = ""
            if docctx and (docctx.get("text") or "").strip():
                doc_note = f" / doc_context: {docctx.get('kind','')} / 約 {len(docctx.get('text',''))} 文字"

            st.success(f"✅ 履歴を復元しました（{len(msgs)}件）。{doc_note}")
            st.rerun()

        except Exception as e:
            st.error(f"履歴JSONの読み込みに失敗しました: {e}")


# ============================================================
# 1) 文書コンテキスト（任意）
# ============================================================
st.subheader("1️⃣ 文書コンテキスト（任意）")
st.caption("ここでセットした文書は、会話の前提（参考資料）として毎ターン参照されます。")

tab_file, tab_text = st.tabs(["📂 ファイルをアップロード", "📝 テキストを直接貼り付け"])

# ------------------------------------------------------------
# temp（UI側の一時保持）
# ------------------------------------------------------------
tmp_dc = None  # common_lib.io.DocContext を想定（to_dict() を持つ）

with tab_file:
    uploaded = st.file_uploader(
        "Word / テキスト / JSON / Markdown / PDF ファイルをアップロード（任意）",
        type=["docx", "txt", "json", "md", "pdf"],
        key="ctx_file_uploader",
    )

    if uploaded is not None:
        try:
            # ------------------------------------------------------------
            # 正本：common_lib.io に委譲（拡張子分岐・decode・抽出はここでしない）
            # ------------------------------------------------------------
            tmp_dc = read_doc_context_from_bytes(
                file_name=uploaded.name,
                data=uploaded.read(),
                max_chars=15000,
            )
            st.success(f"✅ 読み込みOK: {uploaded.name}（{len(tmp_dc.text):,} chars）")
        except Exception as e:
            st.error(f"ファイルの読み込みに失敗しました: {e}")
            tmp_dc = None

with tab_text:
    pasted = st.text_area(
        "テキスト / JSON / Markdown を直接貼り付け（任意）",
        height=180,
        placeholder="ここに貼り付けたテキストを、会話の前提文書としてセットできます。",
        key="ctx_text_paste",
    )
    if pasted.strip():
        try:
            # ------------------------------------------------------------
            # 正本：貼り付けも common_lib.io に委譲（正規化・文字数制限）
            # ------------------------------------------------------------
            tmp_dc = read_doc_context_from_text(
                raw_text=pasted,
                max_chars=15000,
                kind="貼り付けテキスト",
            )
        except Exception as e:
            st.error(f"貼り付けテキストの処理に失敗しました: {e}")
            tmp_dc = None

col_set, col_show = st.columns([1, 2])
with col_set:
    if st.button("この文書を会話にセット", disabled=(tmp_dc is None)):
        # ------------------------------------------------------------
        # 保存（session_state の正本形式：kind/text/meta）
        # ------------------------------------------------------------
        st.session_state.doc_context = tmp_dc.to_dict()
        st.success(f"✅ 文書コンテキストをセットしました（{tmp_dc.kind} / 約 {len(tmp_dc.text):,} 文字）")

with col_show:
    ctx = st.session_state.get("doc_context")
    if ctx and (ctx.get("text") or "").strip():
        kind = ctx.get("kind", "")
        text = ctx.get("text", "")
        st.info(f"📌 現在の文書コンテキスト：{kind}（約 {len(text):,} 文字）")

        # meta（あれば）を軽く表示（必要最低限）
        meta = ctx.get("meta") if isinstance(ctx, dict) else None
        if isinstance(meta, dict):
            truncated = bool(meta.get("truncated"))
            if truncated:
                st.caption("※ この文書は最大文字数制限により途中でカットされています。")

        with st.expander("文書コンテキスト（先頭）", expanded=False):
            preview = text[:1000] + ("\n…（省略）" if len(text) > 1000 else "")
            st.code(preview, language="text")
    else:
        st.caption("（文書コンテキストは未設定）")

st.divider()

# ============================================================
# 2) Chat UI
# ============================================================
st.subheader("2️⃣ AIとの会話")

# 履歴表示
for m in st.session_state.chat_messages:
    with st.chat_message(m.get("role", "assistant")):
        st.write(m.get("content", ""))

# ------------------------------------------------------------
# 質問・指示入力欄
# - 初回は「質問・指示」
# - 会話開始後は「追加の質問・指示」
# ------------------------------------------------------------
has_chat_history = len(st.session_state.chat_messages) > 0

input_label = (
    "追加の質問・指示"
    if has_chat_history
    else "質問・指示"
)

input_placeholder = (
    "続けて質問や指示を入力し，「送信」を押してください（Shift+Enterで改行）．"
    if has_chat_history
    else "質問や指示を入力し，「送信」を押してください（Shift+Enterで改行）．"
)

draft_key = f"chat_draft_{st.session_state.chat_draft_key}"

user_text = st.text_area(
    input_label,
    key=draft_key,
    height=70,
    placeholder=input_placeholder,
)

col_send, col_hint = st.columns([1, 4])
with col_send:
    send = st.button("送信", type="primary")
with col_hint:
    st.caption("※ 文書コンテキストをセットしている場合、会話の前提として毎ターン参照されます。")

if debug_mode:
    history_message_count = int(
        st.session_state.get(
            "chat_last_history_message_count",
            0,
        )
        or 0
    )

    history_char_count = int(
        st.session_state.get(
            "chat_last_history_char_count",
            0,
        )
        or 0
    )

    history_truncated = bool(
        st.session_state.get(
            "chat_last_history_truncated",
            False,
        )
    )

    st.caption(
        "AI送信用履歴："
        f"{history_message_count}件 / "
        f"{history_char_count:,}文字"
        + (
            " / 古い履歴を省略"
            if history_truncated
            else " / 省略なし"
        )
    )


# ============================================================
# Debug / Inspect：最後にAIへ送ったプロンプト（全文）
# ============================================================
last_sys = str(st.session_state.get("chat_last_system_text") or "")
last_prm = str(st.session_state.get("chat_last_prompt_text") or "")

if last_sys.strip() or last_prm.strip():
    with st.expander("🧾 最後にAIへ送ったプロンプト（全文）", expanded=False):
        full_text = (
            "=== SYSTEM ===\n"
            + (last_sys.strip() + "\n" if last_sys.strip() else "(none)\n")
            + "\n"
            + "=== PROMPT ===\n"
            + (last_prm.strip() + "\n" if last_prm.strip() else "(none)\n")
        )

        st.download_button(
            "⬇️ プロンプト全文を .txt でダウンロード",
            data=full_text.encode("utf-8"),
            file_name="last_prompt.txt",
            mime="text/plain",
            key="dl_last_prompt_txt",
        )

        st.text_area(
            "送信内容（SYSTEM + PROMPT）",
            value=full_text,
            height=320,
            key="ta_last_prompt_full",
        )


if send:
    if not (user_text or "").strip():
        st.warning("質問・指示が空です。")
        st.stop()

    user_text = user_text.strip()

    # ------------------------------------------------------------
    # prompt/system
    # - 今回の発話を履歴へ追加する前にプロンプトを作る
    # - これにより今回の発話の二重送信を防ぐ
    # ------------------------------------------------------------
    prompt = _build_prompt_from_history(
        user_text,
    )

    has_doc = bool(
        _get_doc_context_text().strip()
    )

    system = _build_system_instructions(
        has_doc,
    )

    # ------------------------------------------------------------
    # 画面表示・保存用の全履歴へ追加
    # ------------------------------------------------------------
    st.session_state.chat_messages.append(
        {
            "role": "user",
            "content": user_text,
        }
    )

    # 入力欄クリア用
    next_draft_key_value = (
        st.session_state.chat_draft_key + 1
    )


    

    # ------------------------------------------------------------
    # デバッグ用：最後にAIへ送った system / prompt を保存（全文）
    # ------------------------------------------------------------
    st.session_state["chat_last_system_text"] = str(system or "")
    st.session_state["chat_last_prompt_text"] = str(prompt or "")


    # 初期化（推計しない）
    st.session_state.chat_last_in_tok = None
    st.session_state.chat_last_out_tok = None
    st.session_state.chat_last_cost_obj = None
    mk = str(st.session_state.get("chat_model_key") or DEFAULT_TEXT_MODEL_KEY)
    provider, model = _parse_model_key(mk)

    st.session_state.chat_last_model = str(model)
    st.session_state.chat_last_provider = str(provider)


    try:
        with busy_run(
            projects_root=PROJECTS_ROOT,
            user_sub=str(sub),
            app_name=str(APP_NAME),
            page_name=str(PAGE_NAME),
            task_type="text",
            provider=str(provider),
            model=str(model),
            meta={
                "feature": "ai_chat",
                "action": "chat_turn",
                "has_doc_context": bool(has_doc),
                "history_turns": int(len(st.session_state.chat_messages)),
                "prompt_chars": int(len(prompt)),
            },
        ) as br:
            with st.spinner("AIが回答を生成中..."):
                res = call_text(
                    provider=str(provider),
                    model=str(model),
                    prompt=str(prompt),
                    system=str(system),
                    temperature=None,
                    max_output_tokens=int(st.session_state.get("chat_max_output_tokens") or 0),
                    extra=None,
                )

            answer = (getattr(res, "text", "") or "").strip()

            if not answer:
                st.error("回答が空でした。")
                br.add_finish_meta(note="empty")
                st.stop()

            # ------------------------------------------------------------
            # 後処理（テンプレ準拠：正本に委譲）
            # - usage/cost は取れた範囲のみ busy に反映（推計しない）
            # ------------------------------------------------------------
            pp = apply_text_result_to_busy(
                br=br,
                res=res,
                extract_text_in_out_tokens=extract_text_in_out_tokens,
                note_ok="ok",
                note_no_usage="no_usage",
                note_no_cost="no_cost",
            )

            st.session_state.chat_last_in_tok = pp.in_tokens
            st.session_state.chat_last_out_tok = pp.out_tokens
            st.session_state.chat_last_cost_obj = pp.cost_obj
            st.session_state.chat_last_note = str(pp.note or "")

            br.add_finish_meta(note=str(pp.note or "ok"))
            st.session_state.chat_last_run_id = br.run_id



    except Exception as e:
        st.error(f"AI呼び出しでエラー: {e}")
        st.stop()

    # 表示用履歴に追加
    st.session_state.chat_messages.append({"role": "assistant", "content": answer})

    # 入力欄クリア：key を進めて rerun
    st.session_state.chat_draft_key = next_draft_key_value
    st.rerun()

# ============================================================
# 3) 直近ターン（テンプレ“顔”：tokens / cost / run）
# ============================================================
#st.divider()
#st.subheader("3️⃣ 直近ターン（tokens / cost / run）")

last_run_id = str(st.session_state.get("chat_last_run_id") or "").strip()
last_model = str(st.session_state.get("chat_last_model") or "").strip()

in_tok = st.session_state.get("chat_last_in_tok")
out_tok = st.session_state.get("chat_last_out_tok")
cost_obj = st.session_state.get("chat_last_cost_obj")
note = str(st.session_state.get("chat_last_note") or "")

if not last_run_id:
    st.caption("（まだ実行がありません）")
else:
    render_run_summary_compact(
        projects_root=PROJECTS_ROOT,
        run_id=last_run_id,
        model=last_model,
        in_tokens=(int(in_tok) if isinstance(in_tok, int) else None),
        out_tokens=(int(out_tok) if isinstance(out_tok, int) else None),
        cost=cost_obj,
        note=note,
        show_divider=True,
    )
