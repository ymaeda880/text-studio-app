# -*- coding: utf-8 -*-
# pages/24_ChatGPT風_QA.py
from __future__ import annotations

import os
import io
import json
from typing import Optional

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
    page_title="💬 質問ページ（Word / テキスト / JSON / Markdown）",
    page_icon="💬",
    layout="wide",
)

st.title("💬 ChatGPT風：文書を読ませて質問")

st.caption(
    "Word（.docx）だけでなく、.txt / .json / .md も読み込んで質問できます。"
    " そのままテキストを貼り付けてもOKです。"
)

# ============================================================
# Sidebar: model / cost settings
# ============================================================
with st.sidebar:
    st.header("設定")

    # --- モデル選択（GPT / Gemini） ---
    OPENAI_MODELS = ["gpt-5-mini", "gpt-5-nano"]
    GEMINI_MODELS = ["gemini-2.0-flash"]

    model_options = list(OPENAI_MODELS)
    if has_gemini_api_key():
        model_options += GEMINI_MODELS

    chat_model = st.radio(
        "モデル",
        model_options,
        index=0,
        help="Gemini は API キー設定時のみ表示されます。",
    )

    max_output_tokens = st.number_input(
        "最大出力トークン（上限）",
        min_value=256,
        max_value=20000,
        value=4000,
        step=256,
    )

    st.caption(f"為替レート（概算）: {DEFAULT_USDJPY:.2f} JPY/USD")


# ============================================================
# API clients (OpenAI / Gemini)
# ============================================================
def get_openai_client() -> OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    if not api_key:
        raise RuntimeError("OpenAI APIキーが設定されていません。`.streamlit/secrets.toml` に OPENAI_API_KEY を追加してください。")
    return OpenAI(api_key=api_key)

def is_gemini_model(m: str) -> bool:
    return m.startswith("gemini-")


# ============================================================
# 入力ソース：ファイル or テキスト貼り付け
# ============================================================
st.subheader("1️⃣ 文書の入力方法")

tab_file, tab_text = st.tabs(["📂 ファイルをアップロード", "📝 テキストを直接貼り付け"])

source_text: str = ""
source_kind: str = ""

with tab_file:
    uploaded = st.file_uploader(
        "Word / テキスト / JSON / Markdown ファイルをアップロード",
        type=["docx", "txt", "json", "md"],
    )

    if uploaded is not None:
        file_name = uploaded.name
        ext = file_name.lower().rsplit(".", 1)[-1]

        try:
            if ext == "docx":
                doc = docx.Document(uploaded)
                source_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                source_kind = "Word(.docx)"

            elif ext in ("txt", "md"):
                raw = uploaded.read()
                source_text = raw.decode("utf-8", errors="ignore")
                source_kind = f"テキストファイル（.{ext})"

            elif ext == "json":
                raw = uploaded.read()
                obj = json.loads(raw.decode("utf-8", errors="ignore"))
                source_text = json.dumps(obj, ensure_ascii=False, indent=2)
                source_kind = "JSONファイル（.json）"

        except Exception as e:
            st.error(f"ファイルの読み込みに失敗しました: {e}")

        if source_text:
            st.success(f"✅ {source_kind} を読み込みました（約 {len(source_text)} 文字）")
            with st.expander("読み込んだ本文（先頭部分を確認）", expanded=False):
                preview = source_text[:1000]
                if len(source_text) > 1000:
                    preview += "\n…（省略）"
                st.code(preview, language="text")

with tab_text:
    pasted = st.text_area(
        "テキスト / JSON / Markdown を直接貼り付け",
        height=250,
        placeholder="ここに直接テキストを貼り付けても構いません。（Word からコピペ / JSON / Markdown など）",
    )
    if pasted.strip():
        source_text = pasted
        source_kind = "貼り付けテキスト"
        st.info(f"📌 現在の質問対象は「{source_kind}」（約 {len(source_text)} 文字）です。")


# ============================================================
# 質問入力 & 実行
# ============================================================
st.subheader("2️⃣ 質問する")

question = st.text_area(
    "質問を入力してください",
    placeholder="例：この文書で改訂された部分はどこ？ / このJSONで重要なキーは？ / このMarkdownの構成を要約して など",
    height=120,
)

col_run, col_info = st.columns([1, 2])

with col_run:
    run = st.button("AIに質問する", type="primary", use_container_width=True)

with col_info:
    st.caption(
        "※ 入力ソースが複数ある場合は、貼り付けテキストが優先されます。"
        " ファイルだけで質問したい場合は、貼り付け欄を空にしてください。"
    )


# ============================================================
# 実行ロジック
# ============================================================
def build_prompt(source_kind: str, question: str, used_text: str, max_chars: int) -> str:
    return f"""
あなたは文書編集とデータ解釈に詳しいアシスタントです。
以下の本文（{source_kind}）を読み、ユーザーの質問に日本語で分かりやすく答えてください。

【質問】
{question}

【本文（先頭〜最大{max_chars}文字まで）】
{used_text}
""".strip()


if run:
    if not source_text.strip():
        st.error("先にファイルをアップロードするか、テキストを貼り付けてください。")
        st.stop()
    if not question.strip():
        st.error("質問を入力してください。")
        st.stop()

    # 長すぎる場合はカット（モデル保護用）
    max_chars = 15000
    used_text = source_text[:max_chars]
    prompt = build_prompt(source_kind, question.strip(), used_text, max_chars)

    answer = ""
    used_gemini = is_gemini_model(chat_model)

    # usage（取れない場合もあるので Optional）
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    note = ""

    with st.spinner("AIが回答を生成中..."):
        if used_gemini:
            # --- Gemini ---
            if not has_gemini_api_key():
                st.error("Gemini APIキーが設定されていません。Gemini を使うにはキー設定が必要です。")
                st.stop()

            responder = GeminiResponder()
            result = responder.complete(
                model=chat_model,
                system_instruction="あなたは丁寧な日本語で説明するアシスタントです。",
                user_content=prompt,
                max_output_tokens=int(max_output_tokens),
            )
            answer = (result.text or "").strip()

            # Gemini は usage が取れないことが多いので推定
            input_tokens = int(estimate_tokens_from_text(prompt))
            output_tokens = int(estimate_tokens_from_text(answer))
            note = "（Gemini: トークン推定）"

        else:
            # --- OpenAI (GPT) ---
            try:
                client = get_openai_client()
            except Exception as e:
                st.error(str(e))
                st.stop()

            res = client.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": "あなたは丁寧な日本語で説明するアシスタントです。"},
                    {"role": "user", "content": prompt},
                ],
                # 互換のため max_tokens を指定（OpenAI側仕様変更があっても安全に倒す）
                max_tokens=int(max_output_tokens),
            )

            answer = (res.choices[0].message.content or "").strip()

            # usage が取れる場合はそれを使う
            try:
                u = res.usage
                if u is not None:
                    # SDKによりキー名が違う場合があるので両対応
                    input_tokens = int(getattr(u, "prompt_tokens", None) or getattr(u, "input_tokens", 0) or 0)
                    output_tokens = int(getattr(u, "completion_tokens", None) or getattr(u, "output_tokens", 0) or 0)
            except Exception:
                input_tokens = None
                output_tokens = None

            # 取れなければ推定にフォールバック
            if not input_tokens:
                input_tokens = int(estimate_tokens_from_text(prompt))
                note = "（OpenAI: トークン推定）"
            if not output_tokens:
                output_tokens = int(estimate_tokens_from_text(answer))
                note = "（OpenAI: トークン推定）"

    # --- 回答 ---
    st.markdown("### 🧭 回答")
    st.write(answer)

    # --- 料金表示（概算） ---
    try:
        cost = estimate_chat_cost(
            chat_model,
            ChatUsage(input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens or 0)),
            rate=DEFAULT_USDJPY,
        )
        st.markdown("### 💰 料金（概算）")
        st.write(f"- モデル: **{chat_model}**")
        st.write(f"- Input tokens: {int(input_tokens or 0):,}")
        st.write(f"- Output tokens: {int(output_tokens or 0):,}")
        st.info(f"📊 概算: **¥{cost['jpy']:,.2f}**（${cost['usd']:.6f}）{note}")
    except Exception as e:
        st.warning(f"料金計算に失敗しました: {e}")

if not source_text:
    st.info("まずファイルをアップロードするか、テキストを貼り付けてください。")
