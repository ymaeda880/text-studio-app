# -*- coding: utf-8 -*-
# pages/24_ChatGPT風_QA.py
from __future__ import annotations
import streamlit as st
from openai import OpenAI
import docx
import io
import os
import json

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

# --- OpenAIクライアント ---
api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
if not api_key:
    st.error("OpenAI APIキーが設定されていません。`.streamlit/secrets.toml` に OPENAI_API_KEY を追加してください。")
    st.stop()
client = OpenAI(api_key=api_key)

# =========================
# 入力ソース：ファイル or テキスト貼り付け
# =========================
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
                # Wordから本文テキストを抽出
                doc = docx.Document(uploaded)
                source_text = "\n".join(
                    [p.text for p in doc.paragraphs if p.text.strip()]
                )
                source_kind = "Word(.docx)"

            elif ext in ("txt", "md"):
                raw = uploaded.read()
                source_text = raw.decode("utf-8", errors="ignore")
                source_kind = f"テキストファイル（.{ext})"

            elif ext == "json":
                raw = uploaded.read()
                # JSONとしてロード→整形してテキスト化
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
        # 貼り付けテキストがある場合は、こちらを優先ソースにする
        source_text = pasted
        source_kind = "貼り付けテキスト"
        st.info(f"📌 現在の質問対象は「{source_kind}」（約 {len(source_text)} 文字）です。")

# =========================
# 質問入力 & GPT呼び出し
# =========================
st.subheader("2️⃣ 質問する")

question = st.text_area(
    "質問を入力してください",
    placeholder="例：この文書で改訂された部分はどこ？ / このJSONで重要なキーは？ / このMarkdownの構成を要約して など",
    height=120,
)

col_run, col_info = st.columns([1, 2])

with col_run:
    run = st.button("GPTに質問する", type="primary", use_container_width=True)

with col_info:
    st.caption(
        "※ 入力ソースが複数ある場合は、貼り付けテキストが優先されます。"
        " ファイルだけで質問したい場合は、貼り付け欄を空にしてください。"
    )

if run:
    if not source_text.strip():
        st.error("先にファイルをアップロードするか、テキストを貼り付けてください。")
    elif not question.strip():
        st.error("質問を入力してください。")
    else:
        # 長すぎる場合はカット（モデル保護用）
        max_chars = 15000
        used_text = source_text[:max_chars]

        with st.spinner("GPTが回答を生成中..."):
            prompt = f"""
あなたは文書編集とデータ解釈に詳しいアシスタントです。
以下の本文（{source_kind}）を読み、ユーザーの質問に日本語で分かりやすく答えてください。

【質問】
{question}

【本文（先頭〜最大{max_chars}文字まで）】
{used_text}
"""

            res = client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは丁寧な日本語で説明するアシスタントです。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    },
                ],
            )
            answer = res.choices[0].message.content.strip()

        st.markdown("### 🧭 回答")
        st.write(answer)

if not source_text:
    st.info("まずファイルをアップロードするか、テキストを貼り付けてください。")
