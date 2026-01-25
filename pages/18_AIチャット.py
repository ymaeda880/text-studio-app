# -*- coding: utf-8 -*-
# pages/18_AIチャット.py
# ------------------------------------------------------------
# 💬 AIチャット（GPT / Gemini）
#
# ✅ 新テンプレ準拠（正本）：
# - page_session_heartbeat でログイン/heartbeat
# - busy_run で ai_runs.db を必ず記録
# - get_run で開始/終了/経過を表示（ai_runs.db 正本）
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
# sys.path（テンプレ準拠：common_lib を import できるように）
# - MONO_ROOT / PROJ_DIR / APP_DIR を sys.path に入れる
# - PROJECTS_ROOT は MONO_ROOT（全ページで意味を揃える）
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
# Page
# ============================================================
st.set_page_config(
    page_title="💬 AIチャット（GPT / Gemini）",
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
    st.title("💬 AIチャット（GPT / Gemini）")
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

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("会話をリセット", key="btn_reset_chat"):
            st.session_state.pop("chat_messages", None)
            st.session_state.pop("chat_draft_key", None)
            st.session_state.pop("chat_last_run_id", None)
            st.session_state.pop("chat_last_model", None)
            st.session_state.pop("chat_last_provider", None)
            st.session_state.pop("chat_last_in_tok", None)
            st.session_state.pop("chat_last_out_tok", None)
            st.session_state.pop("chat_last_cost_obj", None)
            _ensure_state()
            st.rerun()

    with col_b:
        if st.button("文書コンテキストをクリア", key="btn_clear_docctx"):
            st.session_state.pop("doc_context", None)
            st.session_state.doc_context = None
            st.rerun()

    # ============================================================
    # 履歴：ダウンロード / アップロード（JSON / TXT）
    # ============================================================
    st.divider()
    st.subheader("履歴（保存/復元）")

    messages = st.session_state.get("chat_messages", []) or []

    mk_payload = str(st.session_state.get("chat_model_key") or DEFAULT_TEXT_MODEL_KEY)
    p_payload, m_payload = _parse_model_key(mk_payload)

    payload = {
        "schema": "chat_history_v1",
        "provider": p_payload,
        "model": m_payload,
        "doc_context": st.session_state.get("doc_context"),  # 前提文書も保存
        "messages": messages,
    }


    def _history_as_text(msgs: List[Dict[str, str]]) -> str:
        lines: List[str] = []

        ctx = st.session_state.get("doc_context")
        if ctx and (ctx.get("text") or "").strip():
            kind = ctx.get("kind", "")
            text = ctx.get("text", "")
            head = text[:1000]
            lines.append(f"【前提文書: {kind} / 約 {len(text)} 文字 / 先頭1000文字】\n{head}")
            lines.append("")

        for m in msgs:
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

    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    txt_str = _history_as_text(messages)

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

    def _validate_messages(obj: Any) -> bool:
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

    restore_clicked = st.button(
        "✅ このJSONで履歴を復元",
        type="primary",
        disabled=(up is None),
        key="btn_restore_history",
        help="アップロードしたJSONを読み込み、履歴を置き換えます。",
    )

    if restore_clicked:
        try:
            raw = up.read()
            if not raw:
                st.error("アップロードされたJSONが空です。もう一度アップロードしてください。")
                st.stop()

            loaded = json.loads(raw.decode("utf-8", errors="ignore"))

            restored_docctx = None
            if isinstance(loaded, dict):
                restored_docctx = loaded.get("doc_context")

            if isinstance(loaded, dict) and "messages" in loaded:
                msgs = loaded.get("messages")
            else:
                msgs = loaded

            if not _validate_messages(msgs):
                st.error("このJSONは履歴形式として不正です（messagesの構造を確認してください）。")
                st.stop()

            st.session_state.chat_messages = msgs

            if isinstance(restored_docctx, dict):
                kind = restored_docctx.get("kind")
                text = restored_docctx.get("text")
                if isinstance(kind, str) and isinstance(text, str) and text.strip():
                    st.session_state.doc_context = {"kind": kind, "text": text}
                else:
                    st.session_state.doc_context = None
            else:
                st.session_state.doc_context = None

            # 直近情報はリセット
            st.session_state.chat_last_run_id = ""
            st.session_state.chat_last_model = ""
            st.session_state.chat_last_provider = ""
            st.session_state.chat_last_in_tok = None
            st.session_state.chat_last_out_tok = None
            st.session_state.chat_last_cost_obj = None

            st.session_state.chat_draft_key = (st.session_state.get("chat_draft_key", 0) or 0) + 1

            doc_note = ""
            ctx2 = st.session_state.get("doc_context")
            if ctx2 and (ctx2.get("text") or "").strip():
                doc_note = f" / doc_context: {ctx2.get('kind','')} / 約 {len(ctx2.get('text',''))} 文字"

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

tmp_text: str = ""
tmp_kind: str = ""

with tab_file:
    uploaded = st.file_uploader(
        "Word / テキスト / JSON / Markdown ファイルをアップロード（任意）",
        type=["docx", "txt", "json", "md"],
        key="ctx_file_uploader",
    )

    if uploaded is not None:
        file_name = uploaded.name
        ext = file_name.lower().rsplit(".", 1)[-1]
        try:
            if ext == "docx":
                try:
                    import docx  # type: ignore
                except Exception as e:
                    st.error("`.docx` を読むには python-docx が必要です。`pip install python-docx` を確認してください。")
                    raise e
                doc = docx.Document(uploaded)
                tmp_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                tmp_kind = "Word(.docx)"
            elif ext in ("txt", "md"):
                raw = uploaded.read()
                tmp_text = raw.decode("utf-8", errors="ignore")
                tmp_kind = f"テキストファイル（.{ext})"
            elif ext == "json":
                raw = uploaded.read()
                obj = json.loads(raw.decode("utf-8", errors="ignore"))
                tmp_text = json.dumps(obj, ensure_ascii=False, indent=2)
                tmp_kind = "JSONファイル（.json）"
        except Exception as e:
            st.error(f"ファイルの読み込みに失敗しました: {e}")

with tab_text:
    pasted = st.text_area(
        "テキスト / JSON / Markdown を直接貼り付け（任意）",
        height=180,
        placeholder="ここに貼り付けたテキストを、会話の前提文書としてセットできます。",
        key="ctx_text_paste",
    )
    if pasted.strip():
        tmp_text = pasted
        tmp_kind = "貼り付けテキスト"

col_set, col_show = st.columns([1, 2])
with col_set:
    if st.button("この文書を会話にセット", disabled=not bool((tmp_text or "").strip())):
        st.session_state.doc_context = {"kind": tmp_kind, "text": tmp_text}
        st.success(f"✅ 文書コンテキストをセットしました（{tmp_kind} / 約 {len(tmp_text)} 文字）")

with col_show:
    ctx = st.session_state.get("doc_context")
    if ctx and (ctx.get("text") or "").strip():
        st.info(f"📌 現在の文書コンテキスト：{ctx.get('kind','')}（約 {len(ctx.get('text',''))} 文字）")
        with st.expander("文書コンテキスト（先頭）", expanded=False):
            t = (ctx.get("text") or "")
            preview = t[:1000] + ("\n…（省略）" if len(t) > 1000 else "")
            st.code(preview, language="text")
    else:
        st.caption("（文書コンテキストは未設定）")

st.divider()

# ============================================================
# 2) Chat UI
# ============================================================
st.subheader("2️⃣ チャット")

# 履歴表示
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

if send:
    if not (user_text or "").strip():
        st.warning("メッセージが空です。")
        st.stop()

    user_text = user_text.strip()

    # 表示用履歴に追加
    st.session_state.chat_messages.append({"role": "user", "content": user_text})

    # 入力欄クリア用
    next_draft_key_value = st.session_state.chat_draft_key + 1

    # prompt/system（ページ責務：組み立て）
    prompt = _build_prompt_from_history(user_text)
    has_doc = bool(_get_doc_context_text().strip())
    system = _build_system_instructions(has_doc)

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
