# -*- coding: utf-8 -*-
# pages/24_ChatGPT風_QA.py
from __future__ import annotations
import streamlit as st
from openai import OpenAI
import docx, io, os

st.set_page_config(page_title="💬 Word質問ページ（gpt-5-mini）", page_icon="💬", layout="wide")
st.title("💬 ChatGPT風：Wordを読ませて質問")

st.caption("Word（.docx）をアップロードし、質問を入力してください。ChatGPTのように自然に答えます。")

# --- OpenAIクライアント ---
api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
if not api_key:
    st.error("OpenAI APIキーが設定されていません。`.streamlit/secrets.toml` に OPENAI_API_KEY を追加してください。")
    st.stop()
client = OpenAI(api_key=api_key)

# --- ファイルアップロード ---
uploaded = st.file_uploader("Wordファイル（.docx）をアップロード", type=["docx"])

if uploaded:
    # Wordから本文テキストを抽出
    doc = docx.Document(uploaded)
    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    st.success(f"✅ ファイルを読み込みました（約 {len(text)} 文字）")

    # --- 質問入力 ---
    question = st.text_area("質問を入力してください", placeholder="例：この文書で改訂された部分はどこ？")

    if st.button("GPTに質問する") and question.strip():
        with st.spinner("GPTが回答を生成中..."):
            prompt = f"""
あなたは学術レポート編集の専門家です。
次のWord本文を読み、質問に日本語で答えてください。
質問: {question}

本文:
{text[:15000]}   # （※モデル制限のため15,000文字まで送信）
"""
            res = client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたは丁寧な日本語で説明するアシスタントです。"},
                    {"role": "user", "content": prompt}
                ],
            )
            answer = res.choices[0].message.content.strip()
            st.markdown("### 🧭 回答")
            st.write(answer)

else:
    st.info("まず Word ファイルをアップロードしてください。")
