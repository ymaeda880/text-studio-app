# -*- coding: utf-8 -*-
# pages/19_AIチャット（要約機能）.py
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
# 追加機能（履歴縮約）：
# - 概算トークン表示（文字数ベース）
#   * 12,000超 → 🟡
#   * 15,000超 → 🔴
# - 方式A：✂️ 直近N件にカット（履歴そのものを削除）N=20
# - 方式B：🧠 直近K件を残して、それ以前（過去＋過去要約）を1つに再要約 K=12
#   * 要約は system メッセージとして先頭1件に固定
#
# UI方針：
# - use_container_width は使わない
# - st.form は使わない
# - st.button()/st.download_button() に width 引数は使わない
# ------------------------------------------------------------

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

# ============================================================
# 履歴縮約パラメータ（変更しやすい：ここだけ触れば良い）
#
# ■ 目的
# - チャット履歴が肥大化してトークン上限に近づくのを防ぐ
# - ユーザー操作で「物理カット」または「要約縮約」を選べるようにする
# - 警告表示（🟡/🔴）により、送信前に入力サイズを把握できるようにする
#
# ■ 設計方針
# - 数値はすべて「UI・挙動調整用のパラメータ」としてここに集約
# - ロジック側にはマジックナンバーを埋め込まない
# - 変更時はこのブロックのみ修正すれば全体に反映される
# ============================================================

# 方式A：履歴を物理的に削除して、直近 N 件だけ残す
# - 表示上も完全に消える
# - トークン節約効果が最も高いが、過去文脈は失われる
#CUT_N = 20
CUT_N = 3

# 方式B：直近 K 件を残し、それ以前の履歴を 1 件の system 要約に置き換える
# - 文脈は維持されるが、要約分のトークンは常に含まれる
# - KEEP_K は「ユーザーが直感的に覚えていられる会話量」を目安に設定
# KEEP_K = 12
KEEP_K = 3

# 概算トークン数（入力：system + prompt）がこの値を超えたら警告表示（🟡）
# - まだ送信は可能だが、要約・カットを検討すべき水準
WARN_YELLOW = 12000

# 概算トークン数（入力：system + prompt）がこの値を超えたら強い警告（🔴）
# - モデル上限に近づいており、失敗・自動切り詰めのリスクが高い
# - 履歴縮約を強く推奨する水準
WARN_RED = 15000


# 概算トークン（日本語目安）：1 token ≒ 1.5 chars
TOK_PER_CHAR = 1 / 1.5

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
    page_title="💬 Text Studio / AIチャット（要約機能）",
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
    st.title("💬 AIチャット（要約機能付き）")
with right:
    st.success(f"✅ ログイン中: **{sub}**")

st.caption(
    "文書を会話のコンテキスト（前提）としてセットすることもできます。"
    " 文書がなくても通常のチャットとして使えます。"
)

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

def _build_prompt_from_history(latest_user_text: str) -> str:
    doc_text = _get_doc_context_text()

    lines: List[str] = []
    for m in st.session_state.chat_messages:
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"ユーザー: {content}")
        elif role == "assistant":
            lines.append(f"アシスタント: {content}")
        else:
            lines.append(f"{role}: {content}")

    history_block = "\n".join(lines).strip()

    parts: List[str] = []
    if doc_text:
        parts.append(doc_text)
    if history_block:
        parts.append("【これまでの会話】\n" + history_block)
    parts.append("【今回のユーザー発話】\n" + latest_user_text)
    parts.append("【指示】\n丁寧な日本語で回答してください。必要なら確認質問を最小限にしてください。")

    return "\n\n".join(parts).strip()

# ============================================================
# 概算トークン（目安）関連（正本ロジック：文字数ベース）
# ============================================================
def _estimate_tokens_from_chars(chars: int) -> int:
    if chars <= 0:
        return 0
    return int(chars * TOK_PER_CHAR)

def _estimate_next_input_tokens(*, draft_text: str) -> Tuple[int, int]:
    """
    次にAIへ送る想定の入力（system+prompt）の概算トークン数を返す。
    Returns: (tokens_est, chars_total)
    """
    has_doc = bool(_get_doc_context_text().strip())
    sys_text = _build_system_instructions(has_doc)
    prm_text = _build_prompt_from_history(draft_text or "")
    total_chars = len(sys_text) + len(prm_text)
    return _estimate_tokens_from_chars(total_chars), total_chars

# ============================================================
# 履歴縮約（方式A / 方式B）
# ============================================================
def _cut_history_last_n(*, n: int) -> None:
    """
    方式A：履歴そのものを直近n件にカット（表示も消える）
    """
    msgs = st.session_state.get("chat_messages", []) or []
    st.session_state.chat_messages = msgs[-n:]

def _summary_format_instruction() -> str:
    """
    要約テンプレ（固定）
    """
    return (
        "【要約形式】\n"
        "・要約（5〜10行）\n"
        "・決定事項\n"
        "・未決事項\n"
        "・用語/前提（重要な制約のみ）\n"
        "・次アクション（あれば）\n"
    )

def _build_summary_prompt(*, old_msgs: List[Dict[str, str]]) -> str:
    """
    過去パートを要約させるプロンプト（累積要約前提）
    """
    history_text = "\n".join(
        f"{(m.get('role') or '').strip()}: {(m.get('content') or '').strip()}"
        for m in old_msgs
        if (m.get("content") or "").strip()
    ).strip()

    return (
        "以下はこれまでの会話履歴です。\n"
        "後続の会話で必要な前提として、次の形式で要約してください。\n"
        "推測や新規の情報追加はせず、会話に書かれている事実のみを整理してください。\n\n"
        + _summary_format_instruction()
        + "\n【会話履歴】\n"
        + history_text
    ).strip()

def _summarize_history_keep_k(*, provider: str, model: str, keep_k: int) -> None:
    """
    方式B：直近K件を残し、それ以前（過去＋過去要約）を1つに再要約し、
          systemメッセージとして先頭1件に固定する。
    """
    msgs = st.session_state.get("chat_messages", []) or []
    if len(msgs) <= keep_k:
        raise RuntimeError("要約するほど履歴がありません。")

    old_msgs = msgs[:-keep_k]
    recent_msgs = msgs[-keep_k:]

    summary_prompt = _build_summary_prompt(old_msgs=old_msgs)

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
            "action": "summarize_history",
            "kept_recent": int(keep_k),
            "old_msgs": int(len(old_msgs)),
            "recent_msgs": int(len(recent_msgs)),
            "summary_prompt_chars": int(len(summary_prompt)),
        },
    ) as br:
        res = call_text(
            provider=str(provider),
            model=str(model),
            prompt=str(summary_prompt),
            system=None,
            temperature=None,
            max_output_tokens=None,
            extra=None,
        )

        summary_text = (getattr(res, "text", "") or "").strip()

        pp = apply_text_result_to_busy(
            br=br,
            res=res,
            extract_text_in_out_tokens=extract_text_in_out_tokens,
            note_ok="ok",
            note_no_usage="no_usage",
            note_no_cost="no_cost",
        )

        br.add_finish_meta(note=str(pp.note or "ok"))

    if not summary_text:
        raise RuntimeError("要約結果が空でした。")

    st.session_state.chat_messages = (
        [{
            "role": "system",
            "content": "【これまでの会話の要約】\n" + summary_text,
        }]
        + recent_msgs
    )

# ============================================================
# History helpers（保存/復元：正本ロジック）
# ============================================================
def _history_payload_v1(*, messages: List[Dict[str, str]]) -> Dict[str, Any]:
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
        kind = restored_docctx.get("kind")
        text = restored_docctx.get("text")
        if not (isinstance(kind, str) and isinstance(text, str) and text.strip()):
            restored_docctx = None
    else:
        restored_docctx = None

    return msgs, restored_docctx

def _apply_restored_history(*, messages: List[Dict[str, str]], doc_context: Optional[Dict[str, Any]]) -> None:
    st.session_state.chat_messages = messages
    st.session_state.doc_context = doc_context

    st.session_state.chat_last_run_id = ""
    st.session_state.chat_last_model = ""
    st.session_state.chat_last_provider = ""
    st.session_state.chat_last_in_tok = None
    st.session_state.chat_last_out_tok = None
    st.session_state.chat_last_cost_obj = None
    st.session_state.chat_last_note = ""

    st.session_state.chat_draft_key = (st.session_state.get("chat_draft_key", 0) or 0) + 1

# ============================================================
# Sidebar: settings + history save/restore + 履歴縮約UI
# ============================================================
with st.sidebar:
    st.header("設定")

    # ------------------------------------------------------------
    # モデル選択（テンプレ準拠：render_text_model_picker）
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

    # ------------------------------------------------------------
    # 会話リセット / 文書クリア（縦並び）
    # ------------------------------------------------------------
    if st.button("会話をリセット", key="btn_reset_chat"):
        st.session_state.pop("chat_messages", None)
        st.session_state.pop("chat_draft_key", None)
        st.session_state.pop("chat_last_run_id", None)
        st.session_state.pop("chat_last_model", None)
        st.session_state.pop("chat_last_provider", None)
        st.session_state.pop("chat_last_in_tok", None)
        st.session_state.pop("chat_last_out_tok", None)
        st.session_state.pop("chat_last_cost_obj", None)
        st.session_state.pop("chat_last_note", None)

        st.session_state.pop("chat_last_system_text", None)
        st.session_state.pop("chat_last_prompt_text", None)

        _ensure_state()
        st.rerun()

    if st.button("文書コンテキストをクリア", key="btn_clear_docctx"):
        st.session_state.pop("doc_context", None)
        st.session_state.doc_context = None
        st.rerun()

    # ------------------------------------------------------------
    # 概算トークン表示（次回送信の入力：system + prompt）
    # ------------------------------------------------------------
    st.divider()
    st.subheader("入力サイズ目安（概算）")

    draft_key_for_est = f"chat_draft_{st.session_state.get('chat_draft_key', 0)}"
    draft_now = str(st.session_state.get(draft_key_for_est, "") or "")
    est_tok, est_chars = _estimate_next_input_tokens(draft_text=draft_now)

    if est_tok >= WARN_RED:
        st.error(f"🔴 概算トークン: {est_tok:,} / chars: {est_chars:,}")
    elif est_tok >= WARN_YELLOW:
        st.warning(f"🟡 概算トークン: {est_tok:,} / chars: {est_chars:,}")
    else:
        st.success(f"🟢 概算トークン: {est_tok:,} / chars: {est_chars:,}")

    st.caption("※ 文字数からの概算です（目安）。")

    # ------------------------------------------------------------
    # 履歴縮約（2方式）
    # ------------------------------------------------------------
    st.divider()
    st.subheader("履歴の縮約")

    if st.button(f"✂️ 直近 {CUT_N} 件にカット", key="btn_cut_history"):
        _cut_history_last_n(n=CUT_N)
        st.rerun()

    if st.button("🧠 要約して短く", key="btn_summarize_history"):
        try:
            _summarize_history_keep_k(provider=str(provider), model=str(model), keep_k=KEEP_K)
            st.rerun()
        except Exception as e:
            st.error(str(e))

    # ============================================================
    # 履歴：ダウンロード / アップロード（JSON / TXT）
    # ============================================================
    st.divider()
    st.subheader("履歴（保存/復元）")

    messages = st.session_state.get("chat_messages", []) or []

    payload = _history_payload_v1(messages=messages)
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    txt_str = _history_as_text_v1(messages=messages)

    st.download_button(
        "⬇️ 履歴をJSONでダウンロード",
        data=json_str.encode("utf-8"),
        file_name="chat_history.json",
        mime="application/json",
        disabled=(len(messages) == 0),
        key="dl_history_json",
    )

    st.download_button(
        "⬇️ 履歴をテキストでダウンロード",
        data=txt_str.encode("utf-8"),
        file_name="chat_history.txt",
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

tmp_dc = None  # common_lib.io.DocContext（to_dict を持つ想定）

with tab_file:
    uploaded = st.file_uploader(
        "Word / テキスト / JSON / Markdown / PDF ファイルをアップロード（任意）",
        type=["docx", "txt", "json", "md", "pdf"],
        key="ctx_file_uploader",
    )

    if uploaded is not None:
        try:
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
        st.session_state.doc_context = tmp_dc.to_dict()
        st.success(f"✅ 文書コンテキストをセットしました（{tmp_dc.kind} / 約 {len(tmp_dc.text):,} 文字）")

with col_show:
    ctx = st.session_state.get("doc_context")
    if ctx and (ctx.get("text") or "").strip():
        kind = ctx.get("kind", "")
        text = ctx.get("text", "")
        st.info(f"📌 現在の文書コンテキスト：{kind}（約 {len(text):,} 文字）")

        meta = ctx.get("meta") if isinstance(ctx, dict) else None
        if isinstance(meta, dict):
            if bool(meta.get("truncated")):
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
st.subheader("2️⃣ チャット")

for m in st.session_state.chat_messages:
    with st.chat_message(m.get("role", "assistant")):
        st.write(m.get("content", ""))

draft_key = f"chat_draft_{st.session_state.chat_draft_key}"
user_text = st.text_area(
    "メッセージ",
    key=draft_key,
    height=90,
    placeholder="ここに入力して「送信」を押してください（Shift+Enterで改行）。",
)

col_send, col_hint = st.columns([1, 4])
with col_send:
    send = st.button("送信", type="primary")
with col_hint:
    st.caption("※ 文書コンテキストをセットしている場合、会話の前提として毎ターン参照されます。")

if debug_mode:
    st.caption("デバッグはこの下に出ます（送信後の結果など）。")

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
        st.warning("メッセージが空です。")
        st.stop()

    user_text = user_text.strip()

    st.session_state.chat_messages.append({"role": "user", "content": user_text})

    next_draft_key_value = st.session_state.chat_draft_key + 1

    prompt = _build_prompt_from_history(user_text)
    has_doc = bool(_get_doc_context_text().strip())
    system = _build_system_instructions(has_doc)

    st.session_state["chat_last_system_text"] = str(system or "")
    st.session_state["chat_last_prompt_text"] = str(prompt or "")

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

    st.session_state.chat_messages.append({"role": "assistant", "content": answer})

    st.session_state.chat_draft_key = next_draft_key_value
    st.rerun()

# ============================================================
# 3) 直近ターン（テンプレ“顔”：tokens / cost / run）
# ============================================================
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
