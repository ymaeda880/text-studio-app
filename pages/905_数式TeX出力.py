# pages/905_数式TeX出力.py
from __future__ import annotations

import base64
import os
import re
from io import BytesIO
from typing import Optional

import streamlit as st
from PIL import Image

from openai import OpenAI


# -----------------------------
# Helpers
# -----------------------------
def get_openai_api_key() -> Optional[str]:
    if "OPENAI_API_KEY" in st.secrets:
        return st.secrets["OPENAI_API_KEY"]
    return os.getenv("OPENAI_API_KEY")


def image_bytes_to_data_url(img_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def extract_latex_only(text: str) -> str:
    """
    モデル出力からコードのみを取り出す。
    優先順:
      1) ```latex ...``` / ```tex ... ``` / ``` ... ```
      2) $$ ... $$
      3) 全文
    """
    m = re.search(r"```(?:latex|tex)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    m2 = re.search(r"(\$\$.*?\$\$)", text, flags=re.DOTALL)
    if m2:
        return m2.group(1).strip()

    return text.strip()


def get_output_text_from_responses_api(resp) -> str:
    if hasattr(resp, "output_text") and isinstance(resp.output_text, str) and resp.output_text.strip():
        return resp.output_text

    chunks: list[str] = []
    try:
        for item in getattr(resp, "output", []) or []:
            content = getattr(item, "content", None)
            if not content:
                continue
            for c in content:
                ctype = getattr(c, "type", "")
                if ctype in ("output_text", "text"):
                    t = getattr(c, "text", None)
                    if t:
                        chunks.append(t)
    except Exception:
        pass

    return "\n".join(chunks).strip()


# -----------------------------
# Word-math normalization (Mac Word)
#  - keep \frac, \left, \right
#  - avoid \mathrm, \text, \operatorname
#  - ensure \sqrt is used (not bare sqrt)
# -----------------------------
_WORD_UNSAFE_HINTS = (
    r"\mathrm",
    r"\operatorname",
    r"\text",
    r"\Bigl",
    r"\Bigr",
    r"\bigl",
    r"\bigr",
    r"\Big",
    r"\big",
)


def _strip_mathrm(expr: str) -> str:
    # \mathrm{X} -> X（ネストは深追いしない）
    return re.sub(r"\\mathrm\s*\{([^{}]+)\}", r"\1", expr)


def _strip_text_like(expr: str) -> str:
    # \text{...} \operatorname{...} は Word で崩れやすいので、中身だけ残す
    expr = re.sub(r"\\operatorname\s*\{([^{}]+)\}", r"\1", expr)
    expr = re.sub(r"\\text\s*\{([^{}]+)\}", r"\1", expr)
    return expr


def normalize_for_word_math(expr: str) -> str:
    r"""
    Word数式（特にMac）で貼り付け崩れを起こしやすい表記を避ける。
    仕様（康男さん要件）:
      - \frac はそのまま使う
      - \left / \right はそのまま使う（消さない）
      - \mathrm / \text / \operatorname は避ける
      - bare sqrt -> \sqrt{...} に寄せる
      - display wrapper $$...$$ / \[...\] は外す（Word数式欄貼り付け用）
    """
    s = expr.strip()

    # display wrappers 제거（Word数式欄に貼る前提）
    s = re.sub(r"^\$\$\s*", "", s)
    s = re.sub(r"\s*\$\$$", "", s)
    s = re.sub(r"^\\\[\s*", "", s)
    s = re.sub(r"\s*\\\]$", "", s)

    # テキスト系は剥がす（left/right は維持）
    s = _strip_text_like(s)
    s = _strip_mathrm(s)

    # 重要：sqrt が裸なら \sqrt に直す
    s = re.sub(r"(?<!\\)sqrt\b", r"\\sqrt", s)

    # \sqrt(...) -> \sqrt{...} に寄せる
    s = re.sub(r"\\sqrt\(([^()]+)\)", r"\\sqrt{\1}", s)

    # よくある a/\sqrt{...} を \frac{a}{\sqrt{...}} に寄せる（簡易）
    # 例: QK^T/\sqrt{d_k} -> \frac{QK^T}{\sqrt{d_k}}
    s = re.sub(
        r"([A-Za-z0-9_^\{\}\\]+)\s*/\s*(\\sqrt\{[^}]+\})",
        r"\\frac{\1}{\2}",
        s
    )

    s = re.sub(r"\s+", " ", s).strip()
    return s


def detect_word_unsafe(expr: str) -> bool:
    return any(h in expr for h in _WORD_UNSAFE_HINTS)


# -----------------------------
# Prompt builders
# -----------------------------
def build_format_instruction(output_style: str) -> str:
    if output_style == "ディスプレイ数式（$$...$$）":
        return "必ず $$ ... $$ で包んだ LaTeX だけを返してください。説明は禁止。"
    if output_style == "インライン数式（$...$）":
        return "必ず $ ... $ で包んだ LaTeX だけを返してください。説明は禁止。"
    return "LaTeX コードだけを返してください（説明文は禁止、前後の文も禁止）。"


def build_word_math_instruction() -> str:
    r"""
    Word数式（特にMac）に貼って崩れないことを最優先にした指示。
    要件:
      - \frac, \sqrt, \left, \right はOK（むしろ推奨）
      - \mathrm, \text, \operatorname は禁止
      - sqrt を裸で出さない（必ず \sqrt）
    """
    return (
        "出力は『Word の数式欄に貼って崩れない』ことを最優先にしてください。\n"
        "次の表記は絶対に使わないでください: "
        r"\mathrm, \operatorname, \text, \Bigl, \Bigr, \bigl, \bigr." "\n"
        r"\\left と \\right は使用して構いません（括弧サイズ調整のため）。" "\n"
        "関数名（Attention, softmax など）はそのまま英字で出してください（装飾コマンド禁止）。\n"
        r"\frac と \sqrt と上付き/下付き（^, _）は使用可。" "\n"
        "除算は可能なら \\frac{...}{...} を優先してください。\n"
        r"平方根は必ず \sqrt{...} を使ってください（sqrt(...) や sqrt は禁止）。" "\n"
        "出力は『式コードのみ』で、余計な説明文は禁止。\n"
    )


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="🧮 数式画像 → TeX / Word数式", page_icon="🧮", layout="wide")
st.title("🧮 数式画像 → TeX / Word数式 出力")
st.caption("画像をアップロードすると、数式を読み取りコード化します（TeX もしくは Word数式向け表記）。")

with st.sidebar:
    st.header("設定")

    mode = st.radio(
        "出力モード",
        ["TeX（LaTeX）", "Word数式（\u200b\\frac・\\sqrt・\\left/\\right 推奨）"],
        index=0,
        help="Word数式（特にMac）で崩れやすい \\mathrm / \\text / \\operatorname を避け、\\frac・\\sqrt・\\left/\\right を維持します。",
    )

    model = st.selectbox(
        "モデル（画像入力対応が必要）",
        ["gpt-4.1-mini", "gpt-4.1"],
        index=0,
    )

    if mode == "TeX（LaTeX）":
        output_style = st.radio(
            "TeX 出力形式",
            ["コードのみ（推奨）", "ディスプレイ数式（$$...$$）", "インライン数式（$...$）"],
            index=0,
        )
    else:
        output_style = "コードのみ（推奨）"

    detail_hint = st.radio(
        "画像の詳細度ヒント",
        ["auto", "low", "high"],
        index=0,
    )

    st.divider()

    preview_w = st.slider(
        "画像プレビュー幅（px）",
        min_value=300,
        max_value=1400,
        value=750,
        step=50,
    )

    st.divider()
    st.write("APIキー")
    st.caption("`.streamlit/secrets.toml` の `OPENAI_API_KEY` または環境変数 `OPENAI_API_KEY` を使用します。")

api_key = get_openai_api_key()
if not api_key:
    st.error("OPENAI_API_KEY が見つかりません。secrets または環境変数に設定してください。")
    st.stop()

client = OpenAI(api_key=api_key)

uploaded = st.file_uploader("数式画像（PNG/JPG）をアップロード", type=["png", "jpg", "jpeg"])

colL, colR = st.columns([1, 1], gap="large")

if not uploaded:
    st.info("左上のアップローダから数式画像（PNG/JPG）を入れてください。")
    st.stop()

img_bytes = uploaded.getvalue()
mime = uploaded.type or "image/png"

try:
    img = Image.open(BytesIO(img_bytes))
except Exception:
    st.error("画像として読み込めませんでした。PNG/JPG を確認してください。")
    st.stop()

with colL:
    st.subheader("📷 入力画像")
    st.image(img, width=preview_w)
    st.caption(f"filename: {uploaded.name} / mime: {mime} / size: {len(img_bytes):,} bytes")

with colR:
    st.subheader("🧾 出力")

    btn_cols = st.columns([1, 1, 2])
    with btn_cols[0]:
        run = st.button("生成", type="primary")
    with btn_cols[1]:
        clear = st.button("クリア")

    if "out_code" not in st.session_state:
        st.session_state["out_code"] = ""
    if "out_mode" not in st.session_state:
        st.session_state["out_mode"] = mode

    if clear:
        st.session_state["out_code"] = ""
        st.session_state["out_mode"] = mode

    if run:
        with st.spinner("モデルに問い合わせ中…"):
            data_url = image_bytes_to_data_url(img_bytes, mime)

            system_hint = (
                "あなたは数式OCR/数式理解の専門家です。"
                "画像中の数式を正確にコード化してください。"
                "改行や aligned 等は必要な場合のみ使い、可読性も意識してください。"
            )

            if mode == "TeX（LaTeX）":
                fmt = build_format_instruction(output_style)
                user_prompt = (
                    f"{fmt}\n"
                    "- 読み取れない部分があれば、推定せずに `???` を入れてください。\n"
                    "- 余計な文章は出力しないでください。\n"
                )
            else:
                user_prompt = (
                    build_word_math_instruction()
                    + "- 読み取れない部分があれば、推定せずに `???` を入れてください。\n"
                )

            resp = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system_hint}]},
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": user_prompt},
                            {"type": "input_image", "image_url": data_url, "detail": detail_hint},
                        ],
                    },
                ],
            )

            out_text = get_output_text_from_responses_api(resp)
            code = extract_latex_only(out_text)

            # Wordモードの場合は後処理（\frac, \left, \right は維持）
            if mode != "TeX（LaTeX）":
                code = normalize_for_word_math(code)

            st.session_state["out_code"] = code
            st.session_state["out_mode"] = mode

    out_code = st.session_state.get("out_code", "").strip()
    out_mode = st.session_state.get("out_mode", mode)

    if out_code:
        if out_mode != "TeX（LaTeX）" and detect_word_unsafe(out_code):
            st.warning("Wordモードですが、崩れやすい表記が残っている可能性があります。")

        st.code(out_code, language="tex" if out_mode == "TeX（LaTeX）" else None)

        fname = "equation.tex" if out_mode == "TeX（LaTeX）" else "equation_word_math.txt"
        st.download_button(
            "⬇️ ダウンロード",
            data=out_code.encode("utf-8"),
            file_name=fname,
            mime="text/plain",
        )

        st.text_area("コピー用", out_code, height=180)

        if out_mode != "TeX（LaTeX）":
            st.caption("Mac版Wordの数式欄に貼る場合は、この出力（\\mathrm 等を含まない）を推奨します。")
    else:
        st.caption("ここに出力が表示されます。")
