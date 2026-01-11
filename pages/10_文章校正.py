# pages/10_文章校正.py — 解析（校正方針：ページ/行/理由）オンリー極簡版
# ・原文は「1行=1行」を厳密保持してテーブル化（CJK折返し/長語ZWSP）
# ・校正方針はMarkdown表をパースしてPDF/Word上の表に整形
# ・ダウンロード形式は PDF または Word のどちらか（デフォルト PDF）
# ・OpenAI / Gemini をサイドバーで切替可能（GeminiはGEMINI_API_KEY必須）
# ・API使用量（tokens）と概算コスト（USD/JPY）を計算して表示＆レポートに埋め込み

from __future__ import annotations

from pathlib import Path
from typing import List, Dict

import sys
import streamlit as st

# ===== 共有ライブラリ（common_lib）をパスに追加 =====
PROJECTS_ROOT = Path(__file__).resolve().parents[3]  # pages -> projects root
if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))

# === lib の利用（読込 / 貼り付け整形） ※OCRなし ===
from lib.text_loaders import (
    load_text_generic,
    extract_pdf_text,
    load_text_from_paste,
)

from lib.proofreading.prompts import (
    MODE_DEFS,
    COMMON_PROMPT,
    get_analyze_instruction,
    build_system_prompt,
)

from lib.proofreading.explanation import render_proof_policy_logic_expander, render_proofreading_intro

# === 価格・為替・概算（config）===
from config.config import (
    DEFAULT_USDJPY,
    estimate_tokens_from_text,
    get_usdjpy,
    estimate_cost_usd,
    usd_to_jpy,
    format_cost_lines,
)

# === 切り出し済み（lib/proofreading）===
from lib.proofreading.ui_utils import (
    display_pdf_bytes,
    to_numbered_lines,
    render_preview_with_numbers,
    md_table_to_html,
    inject_proof_table_css,
)

from lib.proofreading.analyzer import analyze_issues as analyze_issues_core

from lib.proofreading.report_builders import (
    build_policy_docx_bytes as build_policy_docx_bytes_core,
    build_policy_pdf_bytes as build_policy_pdf_bytes_core,
)

# ------------------------------------------------------------
# UI定数
# ------------------------------------------------------------
st.set_page_config(page_title="Text Studio / 解析（校正方針）", page_icon="📝", layout="wide")

DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_MODE = "通常校正"
DEFAULT_LINES_PER_PAGE = 40  # 1ページあたりの表示行数（擬似割り付け）

# ---- Gemini Key（任意）----
GEMINI_API_KEY = None
try:
    if "GEMINI_API_KEY" in st.secrets and str(st.secrets["GEMINI_API_KEY"]).strip():
        GEMINI_API_KEY = str(st.secrets["GEMINI_API_KEY"]).strip()
except Exception:
    GEMINI_API_KEY = None

GEMINI_ENABLED = bool(GEMINI_API_KEY)

# ---- モデル候補（Geminiも追加）----
MODEL_OPTIONS = [
    "gpt-5-mini",
    "gpt-5-nano",
    "gemini-2.0-flash",
]

# セッション初期化
st.session_state.setdefault("chat_model", DEFAULT_MODEL)
st.session_state.setdefault("proof_mode", DEFAULT_MODE)
st.session_state.setdefault("chat_model_last_valid", st.session_state["chat_model"])
st.session_state.setdefault("chat_model_picker", st.session_state["chat_model"])
st.session_state.setdefault("gemini_disabled_notice", False)

# ------------------------------------------------------------
# サイドバー：モデル選択の制御（Gemini未設定なら選択不可）
# ------------------------------------------------------------
def _model_label(x: str) -> str:
    if x.startswith("gemini") and not GEMINI_ENABLED:
        return f"{x}（GEMINI_API_KEY 未設定）"
    return x


def _on_change_chat_model():
    picked = st.session_state.get("chat_model_picker", DEFAULT_MODEL)
    if picked.startswith("gemini") and not GEMINI_ENABLED:
        st.session_state["gemini_disabled_notice"] = True
        st.session_state["chat_model_picker"] = st.session_state.get("chat_model_last_valid", DEFAULT_MODEL)
    else:
        st.session_state["chat_model_last_valid"] = picked
        st.session_state["gemini_disabled_notice"] = False
        st.session_state["chat_model"] = picked


# ------------------------------------------------------------
# 解析プロンプト表示（expander）
# ------------------------------------------------------------
def render_policy_preview(*, mode: str) -> str:
    analyze_base = get_analyze_instruction(mode)

    with st.expander("🧭 解析プロンプト設定（クリックで展開）", expanded=False):
        tab3, tab1, tab2 = st.tabs([
            "✍️ 追加プロンプト",
            "🧭 System",
            "📋 共通方針",
        ])

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


# ------------------------------------------------------------
# 画面（解析のみ）
# ------------------------------------------------------------
st.title("📝 文章の校正（Gemini対応版）")

render_proofreading_intro()

# ここでタブ付き expander をまとめて描画
render_proof_policy_logic_expander()

# ------------------------------------------------------------
# サイドバー
# ------------------------------------------------------------
with st.sidebar:
    st.header("設定")

    st.radio(
        "🧠 使用モデル",
        MODEL_OPTIONS,
        key="chat_model_picker",
        format_func=_model_label,
        on_change=_on_change_chat_model,
    )

    if st.session_state.get("gemini_disabled_notice", False) and not GEMINI_ENABLED:
        st.warning("GEMINI_API_KEY が未設定のため Gemini は選択できません。（secrets.toml に GEMINI_API_KEY を設定してください）")

    # 実際に使うモデルを確定
    st.session_state["chat_model"] = st.session_state.get("chat_model_picker", DEFAULT_MODEL)

    st.selectbox(
        "🛠 解析モード",
        list(MODE_DEFS.keys()),
        key="proof_mode",
        help="\n\n".join([f"・{k}: {v['desc']}" for k, v in MODE_DEFS.items()]),
    )

    lpp = st.number_input("ページ行数（表示用）", min_value=20, max_value=100, value=DEFAULT_LINES_PER_PAGE, step=5)

    _DL_LABELS = {"pdf": "PDF (.pdf)", "word": "Word (.docx)"}
    dl_choice_key = st.radio(
        "📦 ダウンロード形式（解析レポート）",
        options=list(_DL_LABELS.keys()),
        format_func=lambda k: _DL_LABELS[k],
        index=0,
        key="dl_format_radio",
    )

# extra prompt（expander内のテキストエリア）
extra_prompt = render_policy_preview(mode=st.session_state["proof_mode"])
st.markdown("---")

LINES_PER_PAGE = int(lpp)

# ------------------------------------------------------------
# 入力（ファイル / 貼り付け）
# ------------------------------------------------------------
tab_paste, tab_file = st.tabs(["📝 貼り付けテキスト", "📁 ファイルから"])

src_text = ""
used_file_name = None

st.session_state.setdefault("pasted_text", "")

with tab_file:
    up = st.file_uploader(".docx / .txt / .pdf をアップロード", type=["docx", "txt", "pdf"])

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
        used_file_name = up.name
        name = up.name.lower()
        if name.endswith(".pdf"):
            data = up.read()
            try:
                stats = extract_pdf_text(data)
            except RuntimeError as e:
                st.error(str(e))
                st.stop()

            st.subheader("📄 PDFプレビュー")
            display_pdf_bytes(data, height=600)

            if int(stats.get("visible", 0)) < 20:
                st.warning("このPDFは画像PDF（テキスト層なし）と判定しました。OCRツールでテキスト化してから再度お試しください。")
                st.stop()
            else:
                src_text = (stats.get("text") or "").strip()
        else:
            try:
                src_text = load_text_generic(up)
            except RuntimeError as e:
                st.error(str(e))
                st.stop()

with tab_paste:
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
        if not pasted.strip():
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

# ------------------------------------------------------------
# 解析の実行
# ------------------------------------------------------------
if src_text:
    lines = to_numbered_lines(src_text)

    st.subheader("👀 行番号付きプレビュー（テキスト表示）")
    st.caption(f"表示上のページ行数: {LINES_PER_PAGE} 行/ページ（擬似割り付け）")
    st.text_area("原文（番号付きプレビュー）", value=render_preview_with_numbers(lines, LINES_PER_PAGE), height=260)

    want_analyze = bool(locals().get("do_analyze_file") or locals().get("do_analyze_paste"))
    if want_analyze:
        with st.spinner("解析中（校正方針を抽出）…"):
            plan_md, usage = analyze_issues_core(
                model=st.session_state["chat_model"],
                lines=lines,
                lines_per_page=LINES_PER_PAGE,
                mode=st.session_state["proof_mode"],
                extra=extra_prompt,
                build_system_prompt=build_system_prompt,
                estimate_tokens_from_text=estimate_tokens_from_text,
                openai_api_key=st.secrets["OPENAI_API_KEY"],
                gemini_api_key=GEMINI_API_KEY,
            )

        st.success("解析が完了しました。ページ/行/理由つきで方針を表示します。")

        # -------------------------
        # usage / cost 表示
        # -------------------------
        st.markdown(
            """
            <style>
            div[data-testid="stMetricValue"] { font-size: 1.1rem; line-height: 1.3; }
            div[data-testid="stMetricLabel"] { font-size: 0.8rem; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        usd_jpy = get_usdjpy(DEFAULT_USDJPY)
        in_t = int(usage.get("input_tokens", 0))
        out_t = int(usage.get("output_tokens", 0))
        tot_t = int(usage.get("total_tokens", in_t + out_t))

        st.subheader("💰 API 使用量（概算）")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Input tokens", f"{in_t:,}")
        c2.metric("Output tokens", f"{out_t:,}")
        c3.metric("Total tokens", f"{tot_t:,}")

        usd = estimate_cost_usd(
            model=st.session_state["chat_model"],
            input_tokens=in_t,
            output_tokens=out_t,
        )

        if usd is None:
            c4.metric("Cost (USD)", "N/A")
            c5.metric("Cost (JPY)", "N/A")
        else:
            jpy = usd_to_jpy(usd, usd_jpy)
            c4.metric("Cost (USD)", f"${usd:,.6f}")
            c5.metric("Cost (JPY)", f"¥{jpy:,.2f}")

        st.markdown(
            f"""
            <div style="font-size:0.85rem; color:#666;">
                為替レート：USD/JPY = {usd_jpy:.1f}（参考値）
            </div>
            """,
            unsafe_allow_html=True,
        )

        # -------------------------
        # 校正方針 表示
        # -------------------------
        st.subheader("📋 校正方針（まず何をどう直すか）")

        html_table = md_table_to_html(plan_md)
        inject_proof_table_css()
        st.markdown(html_table, unsafe_allow_html=True)

        # -------------------------
        # ダウンロード（PDF or Word）
        # -------------------------
        st.markdown("### ⤵️ 解析レポートをダウンロード")
        numbered_preview = render_preview_with_numbers(lines, LINES_PER_PAGE)

        file_base = (used_file_name or "pasted_text").rsplit(".", 1)[0]
        mode_label = st.session_state.get("proof_mode", "").replace(" ", "")
        if mode_label:
            file_stub = f"校正結果_{file_base}_[{mode_label}]"
        else:
            file_stub = f"校正結果_{file_base}"

        if dl_choice_key == "pdf":
            pdf_bytes = build_policy_pdf_bytes_core(
                original_numbered_preview=numbered_preview,
                plan_md=plan_md,
                model=st.session_state["chat_model"],
                mode=st.session_state["proof_mode"],
                extra_prompt=extra_prompt,
                src_name=used_file_name or "pasted_text.txt",
                usage_summary={
                    "input_tokens": in_t,
                    "output_tokens": out_t,
                    "total_tokens": tot_t,
                },
                usd_jpy=usd_jpy,
                format_cost_lines=format_cost_lines,
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
                st.warning("PDF を生成できませんでした。`pip install reportlab` を実行し、CIDフォント（HeiseiMin/HeiseiKakuGo）が使えるか確認してください。")
        else:
            data_docx, ext = build_policy_docx_bytes_core(
                original_numbered_preview=numbered_preview,
                plan_md=plan_md,
                model=st.session_state["chat_model"],
                mode=st.session_state["proof_mode"],
                extra_prompt=extra_prompt,
                src_name=used_file_name or "pasted_text.txt",
                usage_summary={
                    "input_tokens": in_t,
                    "output_tokens": out_t,
                    "total_tokens": tot_t,
                },
                usd_jpy=usd_jpy,
                format_cost_lines=format_cost_lines,
            )
            st.download_button(
                "Word（.docx）として保存" if ext == ".docx" else "テキスト（.txt）として保存",
                data=data_docx,
                file_name=f"{file_stub}{ext}",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == ".docx" else "text/plain",
                key=f"dl_word_{file_stub}",
            )

else:
    st.info("入力タブ（📁/📝）から本文を指定して『① 解析』を実行してください。")
