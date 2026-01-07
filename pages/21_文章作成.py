# -*- coding: utf-8 -*-
# pages/21_文章作成.py
from __future__ import annotations

import os
import json
from typing import Optional, Dict

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
    page_title="📝 文章作成（GPT / Gemini）",
    page_icon="📝",
    layout="wide",
)
st.title("📝 文章作成（GPT / Gemini）")

st.caption(
    "元となる文章（Word / txt / json / md / 貼り付け）＋ テンプレ（メール/報告書など）＋ 追加指示をつないで、文章を生成します。"
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
        help="出力の“上限”です。大きくすると長文が出せますが、料金と時間も増えやすくなります。",
    )

    st.caption(f"為替レート（概算）: {DEFAULT_USDJPY:.2f} JPY/USD")


# ============================================================
# API clients (OpenAI / Gemini)
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


# ============================================================
# Templates
# ============================================================
TEMPLATES: Dict[str, str] = {
    "メール文（ビジネス）": """あなたはビジネス文書の作成に長けたアシスタントです。
丁寧で簡潔、誤解が生じにくいメール文を日本語で作成してください。
・件名も作る
・敬語は過不足なく
・箇条書きを適切に使う
・必要なら「念のため」「差し支えなければ」等のクッション言葉を入れる
""",
    "メール文（同僚）": """あなたは社内向けの連絡文（同僚宛て）の作成に長けたアシスタントです。
砕けすぎず、しかし堅すぎないトーンで、日本語のメール/チャット文を作成してください。
・要点→詳細→依頼（あれば）の順
・読みやすさ重視（短い段落、箇条書き）
""",
    "報告書(一般）": """あなたは報告書の作成に長けたアシスタントです。
以下の元となる文章や素材をまとめる形で，報告書を作成してください。
・箇条書きではなく，書き下し文で書いてください．
・自然な流れの一連の書き下し文で書いてください．
""",
    "報告書": """あなたは報告書の作成に長けたアシスタントです。
以下の元となる文章や素材を踏まえて、日本語で分かりやすく、構造化された報告書を作成してください。
・結論（要約）→背景→観察/事実→分析→提案/次アクション
・必要なら見出しを付ける
・主観と事実を分ける
""",
    "議事メモ": """あなたは議事メモの作成に長けたアシスタントです。
元文章を踏まえ、意思決定・宿題・論点が分かる形で、日本語で議事メモを作成してください。
・決定事項
・未決事項/論点
・ToDo（担当/期限が分かるなら明記）
""",
    "プレゼン用スライド": """あなたはスライドの作成に長けたアシスタントです。
以下の元となる文章を踏まえ、日本語でプレゼン用スライドを作成してください。
・パワーポイントにコピペできる形式で出してください．
""",
}


def build_final_prompt(
    *,
    template_name: str,
    base_text_kind: str,
    base_text: str,
    additional_instruction: str,
    max_chars: int,
) -> str:
    tmpl = TEMPLATES.get(template_name, "")
    used_text = (base_text or "")[:max_chars]

    add = (additional_instruction or "").strip()
    add_block = f"\n\n【追加の指示（任意）】\n{add}\n" if add else ""

    return f"""{tmpl.strip()}

あなたは日本語で文章を作成します。次の素材を踏まえて、指定の目的に合う最終文章を作成してください。
重要: 素材にない事実は捏造しないでください。不明な点は、断定せずに「不明」としてください。

【元となる文章（{base_text_kind} / 先頭〜最大{max_chars}文字）】
{used_text}{add_block}

【出力要件】
・読みやすい段落構成
・冗長さを避ける
・必要なら箇条書き
""".strip()


# ============================================================
# Input source (TEXT FIRST)
# ============================================================
st.subheader("1️⃣ 元となる文章の入力")

# 先に「テキスト貼り付け」を出してデフォルトにする（tabs の先頭がデフォルト）
tab_text, tab_file = st.tabs(["📝 テキストを直接貼り付け（推奨）", "📂 ファイルをアップロード"])

source_text: str = ""
source_kind: str = ""

with tab_text:
    pasted = st.text_area(
        "元となる文章を貼り付け",
        height=260,
        placeholder="ここに元となる文章を貼り付けてください。（メール下書き、メモ、Wordからコピペ等）",
    )
    if pasted.strip():
        source_text = pasted
        source_kind = "貼り付けテキスト"
        st.info(f"📌 入力済み: {source_kind}（約 {len(source_text)} 文字）")

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
                file_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                file_kind = "Word(.docx)"
            elif ext in ("txt", "md"):
                raw = uploaded.read()
                file_text = raw.decode("utf-8", errors="ignore")
                file_kind = f"テキストファイル（.{ext})"
            elif ext == "json":
                raw = uploaded.read()
                obj = json.loads(raw.decode("utf-8", errors="ignore"))
                file_text = json.dumps(obj, ensure_ascii=False, indent=2)
                file_kind = "JSONファイル（.json）"
            else:
                file_text = ""
                file_kind = ""
        except Exception as e:
            st.error(f"ファイルの読み込みに失敗しました: {e}")
            file_text = ""
            file_kind = ""

        # 「貼り付け」が空のときだけファイルを採用（貼り付け優先）
        if file_text and not source_text.strip():
            source_text = file_text
            source_kind = file_kind
            st.success(f"✅ {source_kind} を読み込みました（約 {len(source_text)} 文字）")

        if file_text:
            with st.expander("読み込んだ本文（先頭部分を確認）", expanded=False):
                preview = file_text[:1000]
                if len(file_text) > 1000:
                    preview += "\n…（省略）"
                st.code(preview, language="text")

if not source_text.strip():
    st.warning("まだ入力がありません。貼り付けるかファイルをアップロードしてください。")


# ============================================================
# Generation controls
# ============================================================
st.subheader("2️⃣ 文章生成")

col_a, col_b = st.columns([1, 2], vertical_alignment="top")
with col_a:
    template_name = st.radio(
        "テンプレ",
        list(TEMPLATES.keys()),
        index=0,
        help="用途に合わせた“固定プロンプト”を選びます。",
    )
with col_b:
    additional_instruction = st.text_area(
        "追加の指示（任意）",
        height=140,
        placeholder="例：『もう少し短く』『箇条書きを多めに』『結びに次アクションを入れて』など",
    )

run = st.button("📝 文章生成", type="primary")


# ============================================================
# Execute
# ============================================================
if run:
    if not source_text.strip():
        st.error("先に元となる文章を入力してください。")
        st.stop()

    max_chars = 15000
    final_prompt = build_final_prompt(
        template_name=template_name,
        base_text_kind=source_kind or "不明",
        base_text=source_text,
        additional_instruction=additional_instruction,
        max_chars=max_chars,
    )

    answer = ""
    used_gemini = is_gemini_model(chat_model)

    # usage（取れない場合もあるので推定 fallback）
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    note = ""

    with st.spinner("AIが文章を生成中..."):
        if used_gemini:
            if not has_gemini_api_key():
                st.error("Gemini APIキーが設定されていません。Gemini を使うにはキー設定が必要です。")
                st.stop()

            responder = GeminiResponder()
            result = responder.complete(
                model=chat_model,
                system_instruction="あなたは丁寧な日本語で文章を作成するアシスタントです。",
                user_content=final_prompt,
                max_output_tokens=int(max_output_tokens),
            )
            answer = (result.text or "").strip()

            # Gemini は usage が取れないことが多いので推定
            input_tokens = int(estimate_tokens_from_text(final_prompt))
            output_tokens = int(estimate_tokens_from_text(answer))
            note = "（Gemini: トークン推定）"

        else:
            # --- OpenAI (Responses API) ---
            try:
                client = get_openai_client()
            except Exception as e:
                st.error(str(e))
                st.stop()

            # Responses API に統一
            resp = client.responses.create(
                model=chat_model,
                input=[
                    {"role": "system", "content": "あなたは丁寧な日本語で文章を作成するアシスタントです。"},
                    {"role": "user", "content": final_prompt},
                ],
                max_output_tokens=int(max_output_tokens),
            )

            # テキスト抽出（SDKバージョン差に強め）
            answer = ""
            try:
                # まずは便利プロパティ
                if hasattr(resp, "output_text") and resp.output_text:
                    answer = str(resp.output_text).strip()
            except Exception:
                pass

            if not answer:
                # 最後の手段: output を走査
                try:
                    # resp.output は list のはず
                    for item in getattr(resp, "output", []) or []:
                        for c in getattr(item, "content", []) or []:
                            if getattr(c, "type", None) in ("output_text", "text"):
                                answer += getattr(c, "text", "") or ""
                    answer = answer.strip()
                except Exception:
                    answer = ""

            # usage（取れるなら採用）
            try:
                u = getattr(resp, "usage", None)
                if u is not None:
                    input_tokens = int(getattr(u, "input_tokens", 0) or 0)
                    output_tokens = int(getattr(u, "output_tokens", 0) or 0)
            except Exception:
                input_tokens = None
                output_tokens = None

            # 取れなければ推定
            if not input_tokens:
                input_tokens = int(estimate_tokens_from_text(final_prompt))
                note = "（OpenAI: トークン推定）"
            if not output_tokens:
                output_tokens = int(estimate_tokens_from_text(answer))
                note = "（OpenAI: トークン推定）"

    # --- Answer ---
    st.markdown("### ✅ 生成結果")
    st.write(answer)

    # --- Cost ---
    try:
        cost = estimate_chat_cost(
            chat_model,
            ChatUsage(input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens or 0)),
            rate=DEFAULT_USDJPY,
        )
        st.markdown("### 💰 料金（概算）")
        st.write(f"- モデル: **{chat_model}**")
        st.write(f"- テンプレ: **{template_name}**")
        st.write(f"- Input tokens: {int(input_tokens or 0):,}")
        st.write(f"- Output tokens: {int(output_tokens or 0):,}")
        st.info(f"📊 概算: **¥{cost['jpy']:,.2f}**（${cost['usd']:.6f}）{note}")
    except Exception as e:
        st.warning(f"料金計算に失敗しました: {e}")

    with st.expander("🔧 実際に送ったプロンプト（確認用）", expanded=False):
        st.code(final_prompt, language="text")
