# -*- coding: utf-8 -*-
# pages/701_AIチャット.py
from __future__ import annotations

import os
import json
from typing import Optional, List, Dict, Any

import streamlit as st
import docx
from openai import OpenAI

from config.config import has_gemini_api_key, DEFAULT_USDJPY, estimate_tokens_from_text
from lib.gemini_responder import GeminiResponder
from lib.costs_new import estimate_chat_cost, ChatUsage


# ============================================================
# Page
# ============================================================
st.set_page_config(
    page_title="💬 AIチャット（GPT / Gemini）",
    page_icon="💬",
    layout="wide",
)

st.title("💬 AIチャット（GPT / Gemini）")
st.caption(
    "文書を会話のコンテキスト（前提）としてセットすることもできます。"
    " 文書がなくても通常のチャットとして使えます。"
)


# ============================================================
# Sidebar: settings
# ============================================================
with st.sidebar:
    st.header("設定")

    OPENAI_MODELS = ["gpt-5-mini", "gpt-5-nano"]
    GEMINI_MODELS = ["gemini-2.0-flash"]

    model_options = list(OPENAI_MODELS)
    if has_gemini_api_key():
        model_options += GEMINI_MODELS

    chat_model = st.radio(
        "モデル",
        model_options,
        index=2,
        help="Gemini は API キー設定時のみ表示されます。",
    )

    max_output_tokens = st.number_input(
        "最大出力トークン（上限）",
        min_value=256,
        max_value=20000,
        value=1000,
        step=256,
    )

    debug_mode = st.toggle("デバッグ表示", value=False)

    st.caption(f"為替レート（概算）: {DEFAULT_USDJPY:.2f} JPY/USD")

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("会話をリセット"):
            st.session_state.pop("chat_messages", None)
            st.session_state.pop("chat_costs", None)
            st.session_state.pop("openai_prev_response_id", None)
            st.rerun()

    with col_b:
        if st.button("文書コンテキストをクリア"):
            st.session_state.pop("doc_context", None)
            st.rerun()


# ============================================================
# Helpers
# ============================================================
def get_openai_client() -> OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    if not api_key:
        raise RuntimeError(
            "OpenAI APIキーが設定されていません。`.streamlit/secrets.toml` に OPENAI_API_KEY を追加してください。"
        )
    return OpenAI(api_key=api_key)


def is_gemini_model(m: str) -> bool:
    return m.startswith("gemini-")


def _ensure_state() -> None:
    if "chat_messages" not in st.session_state:
        # 表示用の履歴（systemは保持しない／表示もしない）
        st.session_state.chat_messages = []  # List[Dict[str,str]]
    if "chat_costs" not in st.session_state:
        st.session_state.chat_costs = []  # 1ターンごとの概算ログ
    if "chat_draft_key" not in st.session_state:
        st.session_state.chat_draft_key = 0
    # OpenAI Responses API の会話継続ID
    if "openai_prev_response_id" not in st.session_state:
        st.session_state.openai_prev_response_id = None


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


def _build_openai_instructions() -> str:
    """
    Responses API は previous_response_id を使う場合でも
    instructions は「前回のinstructionsを引き継がない」仕様なので毎回渡す。
    """
    base = "あなたは丁寧な日本語で説明するアシスタントです。"
    doc_text = _get_doc_context_text()
    if doc_text:
        base += (
            "\n\n以下は会話の前提となる参考文書です。"
            "この文書に基づく質問には文書に沿って答え、文書にないことは推測せず不明と言ってください。\n\n"
            + doc_text
        )
    return base


def _build_gemini_prompt_from_history(latest_user_text: str) -> str:
    """
    GeminiResponder.complete は system_instruction + user_content なので
    user_content側に履歴をまとめて渡して会話継続を擬似的に実現。
    """
    doc_text = _get_doc_context_text()

    lines = []
    for m in st.session_state.chat_messages:
        role = m.get("role")
        if role == "user":
            lines.append(f"ユーザー: {m.get('content','')}")
        elif role == "assistant":
            lines.append(f"アシスタント: {m.get('content','')}")

    history_block = "\n".join(lines).strip()

    parts = []
    if doc_text:
        parts.append(
            "以下は会話の前提となる参考文書です。"
            "この文書に基づく質問には文書に沿って答え、文書にないことは推測せず不明と言ってください。\n\n"
            + doc_text
        )
    if history_block:
        parts.append("【これまでの会話】\n" + history_block)
    parts.append("【今回のユーザー発話】\n" + latest_user_text)
    parts.append("【指示】\n丁寧な日本語で回答してください。必要なら確認質問を最小限にしてください。")

    return "\n\n".join(parts).strip()


def _safe_response_text_from_responses_api(resp: Any) -> str:
    """
    Responses API の返り値から「見つかる限りの text を全部拾う」版。
    SDK/モデル差分で output の構造が変わっても拾えるようにする。
    """

    # 1) SDKの便利プロパティがあるなら最優先
    t = getattr(resp, "output_text", None)
    if isinstance(t, str) and t.strip():
        return t.strip()

    # 2) resp を dict 化（できれば）
    try:
        d = resp.model_dump()
    except Exception:
        try:
            d = resp.dict()
        except Exception:
            d = None

    def _collect_text(x: Any, acc: List[str]) -> None:
        """
        dict/list/object を再帰的に辿って、"text" というキー/属性を見つけたら回収する。
        """
        if x is None:
            return

        # str
        if isinstance(x, str):
            if x.strip():
                acc.append(x)
            return

        # list/tuple
        if isinstance(x, (list, tuple)):
            for it in x:
                _collect_text(it, acc)
            return

        # dict
        if isinstance(x, dict):
            # 典型パターン： {"type":"output_text","text":"..."}
            if isinstance(x.get("text"), str) and x.get("text", "").strip():
                acc.append(x["text"])
            # 他も再帰
            for v in x.values():
                _collect_text(v, acc)
            return

        # object（SDKのTyped objectなど）
        # "text" 属性があれば拾う
        txt = getattr(x, "text", None)
        if isinstance(txt, str) and txt.strip():
            acc.append(txt)

        # 代表的な属性を再帰
        for attr in ("output", "content", "message", "choices", "items", "data"):
            v = getattr(x, attr, None)
            if v is not None:
                _collect_text(v, acc)

    acc: List[str] = []
    if d is not None:
        _collect_text(d, acc)
    else:
        _collect_text(resp, acc)

    # かぶりやゴミを減らす（完全一致のみ簡易除去）
    seen = set()
    uniq = []
    for s in acc:
        s2 = s.strip()
        if not s2:
            continue
        if s2 in seen:
            continue
        seen.add(s2)
        uniq.append(s2)

    return "\n".join(uniq).strip()


def _add_turn_cost(model: str, input_tokens: int, output_tokens: int, note: str) -> None:
    try:
        cost = estimate_chat_cost(
            model,
            ChatUsage(input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens or 0)),
            rate=DEFAULT_USDJPY,
        )
        st.session_state.chat_costs.append(
            {
                "model": model,
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
                "usd": float(cost.get("usd", 0.0)),
                "jpy": float(cost.get("jpy", 0.0)),
                "note": note or "",
            }
        )
    except Exception:
        st.session_state.chat_costs.append(
            {
                "model": model,
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
                "usd": 0.0,
                "jpy": 0.0,
                "note": "（料金計算失敗）",
            }
        )


# ============================================================
# State init
# ============================================================
_ensure_state()

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

# 入力欄（クリアは key を変える方式）
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

# （デバッグ表示領域：常に出すと邪魔なので toggle 時だけ）
if debug_mode:
    st.caption("デバッグはこの下に出ます（送信後の結果など）。")

if send:
    if not (user_text or "").strip():
        st.warning("メッセージが空です。")
        st.stop()

    user_text = user_text.strip()

    # 表示用履歴に追加
    st.session_state.chat_messages.append({"role": "user", "content": user_text})

    used_gemini = is_gemini_model(chat_model)

    answer = ""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    note = ""

    # 送信→生成が終わったら入力欄をクリアしたいので、先に次keyを準備
    next_draft_key_value = st.session_state.chat_draft_key + 1

    with st.spinner("AIが回答を生成中..."):
        if used_gemini:
            if not has_gemini_api_key():
                st.error("Gemini APIキーが設定されていません。Gemini を使うにはキー設定が必要です。")
                st.stop()

            responder = GeminiResponder()
            gemini_user_content = _build_gemini_prompt_from_history(user_text)

            result = responder.complete(
                model=chat_model,
                system_instruction="あなたは丁寧な日本語で説明するアシスタントです。",
                user_content=gemini_user_content,
                max_output_tokens=int(max_output_tokens),
            )
            answer = (result.text or "").strip()

            input_tokens = int(estimate_tokens_from_text(gemini_user_content))
            output_tokens = int(estimate_tokens_from_text(answer))
            note = "（Gemini: トークン推定）"

            if debug_mode:
                with st.expander("デバッグ：Gemini", expanded=False):
                    st.write({"len_answer": len(answer), "input_tokens_est": input_tokens, "output_tokens_est": output_tokens})

        else:
            # OpenAI：Responses API（継続会話は previous_response_id）
            try:
                client = get_openai_client()
            except Exception as e:
                st.error(str(e))
                st.stop()

            instructions = _build_openai_instructions()
            prev_id = st.session_state.get("openai_prev_response_id")

            try:
                # Responses API：previous_response_id で会話継続
                resp = client.responses.create(
                    model=chat_model,
                    instructions=instructions,
                    input=user_text,
                    previous_response_id=prev_id,
                    max_output_tokens=int(max_output_tokens),
                )
            except Exception as e:
                st.error(f"OpenAI API 呼び出しに失敗: {e}")
                st.stop()

            # 会話継続IDを保存（次ターン用）
            new_prev_id = getattr(resp, "id", None)
            if isinstance(new_prev_id, str) and new_prev_id.strip():
                st.session_state.openai_prev_response_id = new_prev_id

            # まず dump を保存（空でも必ず残す）
            try:
                st.session_state["last_openai_dump"] = resp.model_dump()
            except Exception:
                st.session_state["last_openai_dump"] = str(resp)

            if not answer:
                st.error("OpenAIの抽出結果が空でした。下のデバッグにレスポンス全体を表示します。")
                if st.session_state.get("debug_mode", False):
                    with st.expander("デバッグ：OpenAIレスポンス全体（model_dump）", expanded=True):
                        st.write(st.session_state.get("last_openai_dump"))
                st.stop()


            answer = _safe_response_text_from_responses_api(resp).strip()
            st.session_state["last_answer"] = answer

            # usage（取れれば実測、なければ推定）
            u = getattr(resp, "usage", None)
            if u is not None:
                # Responses API の usage は input_tokens / output_tokens が基本
                input_tokens = int(getattr(u, "input_tokens", 0) or 0)
                output_tokens = int(getattr(u, "output_tokens", 0) or 0)

            if not input_tokens:
                input_tokens = int(estimate_tokens_from_text(instructions + "\n\n" + user_text))
                note = "（OpenAI: トークン推定）"
            if not output_tokens:
                output_tokens = int(estimate_tokens_from_text(answer))
                note = "（OpenAI: トークン推定）"

            if debug_mode:
                with st.expander("デバッグ：OpenAI Responses", expanded=False):
                    st.write(
                        {
                            "prev_id_in": prev_id,
                            "resp_id_out": getattr(resp, "id", None),
                            "status": getattr(resp, "status", None),
                            "len_answer": len(answer),
                            "usage": {
                                "input_tokens": int(input_tokens or 0),
                                "output_tokens": int(output_tokens or 0),
                            },
                        }
                    )
                    if not answer:
                        st.warning("answer が空です。resp.output を表示します。")
                        try:
                            # SDK差分用に dict 化できれば出す
                            st.write(resp.model_dump())
                        except Exception:
                            st.write(str(resp))

    # answer が空なら、ここで止めて “空のassistant” を履歴に入れない
    if not answer:
        st.error("回答が空でした。デバッグ表示をONにして、OpenAIレスポンスを確認してください。")
        st.stop()

    # 表示用履歴に追加
    st.session_state.chat_messages.append({"role": "assistant", "content": answer})

    # 料金概算（1ターン）
    _add_turn_cost(
        model=chat_model,
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        note=note,
    )

    # 入力欄クリア：key を進めて rerun
    st.session_state.chat_draft_key = next_draft_key_value
    st.rerun()


# ============================================================
# 3) コスト表示（任意）
# ============================================================
st.divider()
st.subheader("3️⃣ 料金（概算）")

if st.session_state.chat_costs:
    total_jpy = sum(float(x.get("jpy", 0.0)) for x in st.session_state.chat_costs)
    total_usd = sum(float(x.get("usd", 0.0)) for x in st.session_state.chat_costs)

    last = st.session_state.chat_costs[-1]
    st.write(f"- 直近ターン: **¥{last.get('jpy',0.0):,.2f}**（${last.get('usd',0.0):.6f}） {last.get('note','')}")
    st.write(f"- 累計: **¥{total_jpy:,.2f}**（${total_usd:.6f}）")

    with st.expander("ターン別の内訳", expanded=False):
        for i, r in enumerate(st.session_state.chat_costs, start=1):
            st.write(
                f"{i:02d}. {r.get('model','')}  "
                f"in={int(r.get('input_tokens',0)):,} / out={int(r.get('output_tokens',0)):,}  "
                f"→ ¥{float(r.get('jpy',0.0)):,.2f}（${float(r.get('usd',0.0)):.6f}） {r.get('note','')}"
            )
else:
    st.caption("（まだ実行していません）")
