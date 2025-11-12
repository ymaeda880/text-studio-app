# pages/20_校正.py — 解析（校正方針：ページ/行/理由）→ 本校正
# （PDFが画像PDFなら警告して停止／OCR機能は削除）
from __future__ import annotations
from typing import List, Tuple, Dict
from pathlib import Path
import sys

import streamlit as st
from openai import OpenAI

# ===== 共有ライブラリ（common_lib）をパスに追加 =====
PROJECTS_ROOT = Path(__file__).resolve().parents[3]  # or 3 for pages
if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))

# 料金見積りユーティリティ
from common_lib.openai.costs import (
    ChatUsage,
    estimate_chat_cost,
    render_chat_only_summary,
    DEFAULT_USDJPY,
)

# === lib の利用（読込 / 貼り付け整形） ※OCRなし ===
from lib.text_loaders import (
    load_text_generic, extract_pdf_text, load_text_from_paste
)

# ------------------------------------------------------------
# モード定義
# ------------------------------------------------------------
MODE_DEFS: Dict[str, Dict[str, str]] = {
    "厳格校正": {
        "desc": "助詞・主述一致・冗長/重複・語順・誤字脱字・用語誤用・文体不統一まで広く対象。意味は変えず最適化。",
        "analyze_inst": (
            "あなたは厳密な日本語校正リーダーです。以下の番号付きテキストを読み、"
            "『何をどのように直すべきか』を、具体的な理由とともに一覧化してください。"
            "行頭の [page:line] を必ず参照して位置を示し、過度な意訳は避けてください。"
            "助詞（てにおは）、主述一致、冗長、重複、語順、誤字脱字、用語誤用、文体の不統一に特に注意。"
            "出力は **Markdownの表** で、列は次の順：Page | Line | Issue | Original | Suggestion | Reason。"
            "Original は該当箇所の短い抜粋（最大20字）に留めてください。"
        ),
        "proofread_inst": (
            "あなたは厳密な日本語校正者です。以下を徹底してください：\n"
            "- てにおは、助詞、主述一致、誤字脱字、表記ゆれを修正\n"
            "- 用語誤用の是正・語順の自然化（意味は変えない）\n"
            "- 冗長・重複を圧縮し、文体を統一（尊敬/丁寧/常体の混在を解消）\n"
            "- 出力は校正後の本文のみ（前置き不要）"
        ),
    },
    "簡易校正（ミス最小修正）": {
        "desc": "明白なミスのみ（てにおは・助詞・誤字脱字・明確な変換ミス）。語順や言い換えは極力しない。",
        "analyze_inst": (
            "あなたは日本語の軽微校正リーダーです。以下の番号付きテキストから、"
            "『明白なミス（てにおは・助詞の誤り、誤字脱字、明確な変換ミス）』のみを抽出してください。"
            "語順変更やスタイル統一などの裁量的変更は提案しないでください。"
            "出力は **Markdownの表** で、列は次の順：Page | Line | Issue | Original | Suggestion | Reason。"
            "Original は短い抜粋（最大20字）。Reason は“明白な誤り”である根拠を簡潔に。"
        ),
        "proofread_inst": (
            "あなたは日本語の軽微校正者です。以下を徹底してください：\n"
            "- 明白なミスのみ修正（てにおは・助詞・誤字脱字・明確な変換ミス）\n"
            "- 語順の大きな変更や言い換えは避ける（意味・文体は最大限維持）\n"
            "- 出力は校正後の本文のみ（前置き不要）"
        ),
    },
}

# ------------------------------------------------------------
# UI定数
# ------------------------------------------------------------
st.set_page_config(page_title="Text Studio / 校正", page_icon="📝", layout="wide")

MODEL_OPTIONS = ["gpt-5-mini", "gpt-5-nano"]
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_MODE = "厳格校正"
LINES_PER_PAGE = 40  # 1ページあたりの表示行数

# セッション初期化
if "chat_model" not in st.session_state:
    st.session_state["chat_model"] = DEFAULT_MODEL
if "proof_mode" not in st.session_state:
    st.session_state["proof_mode"] = DEFAULT_MODE
if "tok_in_total" not in st.session_state:
    st.session_state["tok_in_total"] = 0
if "tok_out_total" not in st.session_state:
    st.session_state["tok_out_total"] = 0

# ------------------------------------------------------------
# 表示ユーティリティ
# ------------------------------------------------------------
def display_pdf_bytes(data: bytes, height: int = 600):
    """Streamlit PDF表示（streamlit[pdf] があれば st.pdf）。なければ iframe 埋め込み。"""
    try:
        st.pdf(data, height=height)  # Streamlit 1.31+ / streamlit[pdf]
    except Exception:
        import base64
        b64 = base64.b64encode(data).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}px"></iframe>',
            unsafe_allow_html=True
        )

def to_numbered_lines(raw: str) -> List[str]:
    return raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")

def page_and_line(idx: int, lines_per_page: int) -> Tuple[int, int]:
    page = idx // lines_per_page + 1
    line_in_page = idx % lines_per_page + 1
    return page, line_in_page

def render_preview_with_numbers(lines: List[str], lines_per_page: int) -> str:
    return "\n".join(f"[{(i//lines_per_page)+1}:{(i%lines_per_page)+1:02d}] {t}" for i, t in enumerate(lines))

# ------------------------------------------------------------
# OpenAIクライアントと使用量抽出
# ------------------------------------------------------------
def openai_client() -> OpenAI:
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def _add_usage_from_resp(resp) -> Tuple[int, int]:
    u = getattr(resp, "usage", None) or {}
    prompt = getattr(u, "prompt_tokens", None) if hasattr(u, "prompt_tokens") else u.get("prompt_tokens", 0)
    completion = getattr(u, "completion_tokens", None) if hasattr(u, "completion_tokens") else u.get("completion_tokens", 0)
    try:
        prompt = int(prompt or 0)
    except Exception:
        prompt = 0
    try:
        completion = int(completion or 0)
    except Exception:
        completion = 0
    return prompt, completion

# ------------------------------------------------------------
# 追加：方針プレビュー＆追加プロンプト
# ------------------------------------------------------------
def get_analyze_instruction(mode: str) -> str:
    return MODE_DEFS.get(mode, MODE_DEFS["厳格校正"])["analyze_inst"]

def get_proofread_instruction(mode: str, keep_layout: bool) -> str:
    base = MODE_DEFS.get(mode, MODE_DEFS["厳格校正"])["proofread_inst"]
    if keep_layout:
        base = base + "\n- 改行・段落は可能な限り維持"
    return base

def build_sys_inst(base: str, extra: str) -> str:
    extra = (extra or "").strip()
    return base + ("\n- 追加指示（厳守）: " + extra if extra else "")

def render_policy_preview(*, mode: str, keep_layout: bool) -> str:
    analyze_base = get_analyze_instruction(mode)
    proofread_base = get_proofread_instruction(mode, keep_layout=keep_layout)

    st.subheader("🧭 校正方針の確認")
    st.caption(MODE_DEFS[mode]["desc"])
    with st.expander("解析で使うプロンプト（System）", expanded=False):
        st.code(analyze_base, language="markdown")
    with st.expander("本校正で使うプロンプト（System）", expanded=False):
        st.code(proofread_base, language="markdown")

    st.markdown("**✍️ 追加プロンプト（任意）**")
    st.caption("特記事項（例：外来語はカタカナ優先／製品名は原文どおり／全角英数字は半角に など）を追記できます。")
    extra = st.text_area(
        "追加プロンプト",
        key="extra_user_prompt",
        placeholder="例）外来語の表記はカタカナ優先。製品名や固有名詞は原文どおりに保持。",
        height=100,
    )
    return extra or ""

# ------------------------------------------------------------
# 解析（校正方針）
# ------------------------------------------------------------
def analyze_issues(model: str, lines: List[str], lines_per_page: int, mode: str, extra: str) -> Tuple[str, ChatUsage]:
    client = openai_client()
    md_tables: List[str] = []
    used_in = used_out = 0

    total_pages = (len(lines) + lines_per_page - 1) // lines_per_page
    sys_inst_template = build_sys_inst(get_analyze_instruction(mode), extra)

    for pg in range(total_pages):
        start = pg * lines_per_page
        end = min((pg + 1) * lines_per_page, len(lines))
        page_chunk = [f"[{(i//lines_per_page)+1}:{(i%lines_per_page)+1:02d}] {lines[i]}" for i in range(start, end)]
        page_text = "\n".join(page_chunk)

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_inst_template},
                {"role": "user", "content": f"次のテキスト（このページのみ）を解析してください：\n---\n{page_text}"},
            ],
        )
        md_tables.append(resp.choices[0].message.content.strip())
        pin, pout = _add_usage_from_resp(resp)
        used_in += pin; used_out += pout

    out = []
    for i, tbl in enumerate(md_tables, 1):
        out.append(f"#### Page {i}\n\n{tbl}\n")
    return "\n".join(out), ChatUsage(input_tokens=used_in, output_tokens=used_out)

# ------------------------------------------------------------
# 本校正
# ------------------------------------------------------------
def proofread(model: str, content: str, keep_layout: bool, want_report: bool, mode: str, extra: str) -> Tuple[str, ChatUsage]:
    client = openai_client()
    CHUNK = 6000
    chunks = [content[i:i+CHUNK] for i in range(0, len(content), CHUNK)] or [content]

    fixed_parts: List[str] = []
    used_in = used_out = 0
    sys_inst = build_sys_inst(get_proofread_instruction(mode, keep_layout=keep_layout), extra)

    for chunk in chunks:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_inst},
                {"role": "user", "content": f"次の本文を校正してください：\n---\n{chunk}"},
            ],
        )
        fixed_parts.append(resp.choices[0].message.content.strip())
        pin, pout = _add_usage_from_resp(resp)
        used_in += pin; used_out += pout

    fixed_text = ("\n\n" if keep_layout else "\n").join(fixed_parts).strip()

    if want_report:
        rep_inst = (
            "次の原文と校正後本文の差分観点で、主な修正ポイントを最大8項目で箇条書きに。\n"
            "例：助詞/活用、語順、冗長/重複、誤字脱字、文体統一、用語誤用など。"
        )
        rep_user = f"原文:\n{content[:4000]}\n\n校正後:\n{fixed_text[:4000]}"
        rep = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": rep_inst},
                {"role": "user", "content": rep_user},
            ],
        )
        fixed_text += f"\n\n---\n【修正ポイント（要約）】\n{rep.choices[0].message.content.strip()}"
        pin, pout = _add_usage_from_resp(rep)
        used_in += pin; used_out += pout

    return fixed_text, ChatUsage(input_tokens=used_in, output_tokens=used_out)

# ------------------------------------------------------------
# 画面
# ------------------------------------------------------------
st.title("📝 校正 — 解析（ページ/行/理由） → 本校正")
st.write("最初に**方針**を確認/追記してから、入力（ファイル or 貼り付け）を選んでください。")

with st.sidebar:
    st.header("設定")
    st.radio(
        "🧠 使用モデル",
        MODEL_OPTIONS,
        index=MODEL_OPTIONS.index(st.session_state["chat_model"]),
        key="chat_model",
    )

    from common_lib.openai.costs import MODEL_PRICES_USD
    sel_model = st.session_state["chat_model"]
    if sel_model in MODEL_PRICES_USD:
        price_in = MODEL_PRICES_USD[sel_model]["in"] / 1000
        price_out = MODEL_PRICES_USD[sel_model]["out"] / 1000
        st.markdown(
            f"""
            **💲 単価 (USD / 1K tokens)**  
            - 入力: `${price_in:.5f}`  
            - 出力: `${price_out:.5f}`
            """
        )
    else:
        st.info("単価情報が未登録のモデルです。")

    st.selectbox(
        "🛠 校正モード",
        list(MODE_DEFS.keys()),
        index=list(MODE_DEFS.keys()).index(st.session_state.get("proof_mode", DEFAULT_MODE)),
        key="proof_mode",
        help="\n\n".join([f"・{k}: {v['desc']}" for k, v in MODE_DEFS.items()]),
    )
    st.caption(f"説明：{MODE_DEFS[st.session_state['proof_mode']]['desc']}")

    keep_formatting = st.checkbox("改行・段落を保持（本校正時）", value=True)
    show_report = st.checkbox("本校正後に『修正ポイント要約』も付与", value=False)
    lpp = st.number_input("ページ行数（表示用）", min_value=20, max_value=100, value=LINES_PER_PAGE, step=5)

extra_prompt = render_policy_preview(
    mode=st.session_state["proof_mode"],
    keep_layout=keep_formatting,
)
st.markdown("---")

# ===== 入力方法の選択（ファイル / 貼り付け） =====
tab_file, tab_paste = st.tabs(["📁 ファイルから", "📝 貼り付けテキスト"])

src_text = ""
used_file_name = None

# ---------- ファイル入力 ----------
with tab_file:
    col_u, col_btn1, col_btn2 = st.columns([3, 1, 1])
    with col_u:
        up = st.file_uploader(".docx / .txt / .pdf をアップロード", type=["docx", "txt", "pdf"])
    with col_btn1:
        do_analyze_file = st.button("① 解析（ファイル）", type="secondary", use_container_width=True, disabled=not up, key="btn_analyze_file")
    with col_btn2:
        do_fix_file = st.button("② 本校正（ファイル）", type="primary", use_container_width=True, disabled=not up, key="btn_fix_file")

    if up:
        used_file_name = up.name
        name = up.name.lower()
        if name.endswith(".pdf"):
            # PDFは表示 → テキスト層チェック（なければ警告＆停止）
            data = up.read()
            try:
                stats = extract_pdf_text(data)
            except RuntimeError as e:
                st.error(str(e)); st.stop()

            st.subheader("📄 PDFプレビュー")
            display_pdf_bytes(data, height=600)

            if int(stats.get("visible", 0)) < 20:
                st.warning("このPDFは画像PDF（テキスト層なし）と判定しました。OCRツールでテキスト化してから再度お試しください。")
                st.stop()
            else:
                src_text = (stats.get("text") or "").strip()
        else:
            # txt / docx は通常読込
            try:
                src_text = load_text_generic(up)
            except RuntimeError as e:
                st.error(str(e)); st.stop()

# ---------- 貼り付け入力 ----------
with tab_paste:
    pasted = st.text_area(
        "ここに本文を貼り付け",
        height=260,
        placeholder="ここに本文を貼り付けてください（改行は保持されます）。"
    )
    col_p1, col_p2, col_opts = st.columns([1, 1, 2])
    with col_opts:
        normalize = st.checkbox("改行とBOMを正規化", value=True, key="opt_norm")
        collapse = st.checkbox("連続空行を圧縮", value=False, key="opt_collapse")
        keep_blanks = st.number_input("空行の上限（圧縮時）", 1, 5, 1, key="opt_keep_blanks")
        trim_tail = st.checkbox("行末スペースを除去", value=True, key="opt_trim_tail")

    with col_p1:
        do_analyze_paste = st.button("① 解析（貼り付け）", type="secondary", use_container_width=True, disabled=not pasted.strip(), key="btn_analyze_paste")
    with col_p2:
        do_fix_paste = st.button("② 本校正（貼り付け）", type="primary", use_container_width=True, disabled=not pasted.strip(), key="btn_fix_paste")

    if pasted:
        src_text = load_text_from_paste(
            pasted,
            normalize=normalize,
            collapse_blanks=collapse,
            keep_blank_lines=int(keep_blanks),
            trim_trailing=trim_tail,
        )
        used_file_name = "pasted_text.txt"

# ===== 共通：ここから解析/本校正の実行（ファイル or 貼り付け） =====
if src_text:
    lines = to_numbered_lines(src_text)
    st.subheader("👀 行番号付きプレビュー")
    st.caption(f"表示上のページ行数: {LINES_PER_PAGE} 行/ページ（擬似割り付け）")
    st.text_area("原文（番号付きプレビュー）", value=render_preview_with_numbers(lines, LINES_PER_PAGE), height=260)

    run_in = run_out = 0
    want_analyze = (locals().get("do_analyze_file") or locals().get("do_analyze_paste"))
    want_fix     = (locals().get("do_fix_file") or locals().get("do_fix_paste"))

    if want_analyze:
        with st.spinner("解析中（校正方針を抽出）…"):
            plan_md, usage = analyze_issues(
                st.session_state["chat_model"], lines, LINES_PER_PAGE,
                mode=st.session_state["proof_mode"], extra=extra_prompt
            )
        st.success("解析が完了しました。ページ/行/理由つきで方針を表示します。")
        st.subheader("📋 校正方針（まず何をどう直すか）")
        st.markdown(plan_md, unsafe_allow_html=False)
        run_in += usage.input_tokens; run_out += usage.output_tokens

    if want_fix:
        with st.spinner("本校正の実行中…"):
            result, usage = proofread(
                model=st.session_state["chat_model"],
                content=src_text,
                keep_layout=keep_formatting,
                want_report=show_report,
                mode=st.session_state["proof_mode"],
                extra=extra_prompt,
            )
        st.success("校正完了！下の結果をコピー/ダウンロードできます。")
        st.subheader("🧾 校正結果")
        st.text_area("校正結果", value=result, height=420)
        st.download_button(
            "校正結果をダウンロード (.txt)",
            data=result.encode("utf-8"),
            file_name=f"proofread_{(used_file_name or 'output').rsplit('.',1)[0]}.txt",
            mime="text/plain",
        )
        run_in += usage.input_tokens; run_out += usage.output_tokens

    # セッション累計へ反映 & 料金表示
    if want_analyze or want_fix:
        st.session_state["tok_in_total"] += run_in
        st.session_state["tok_out_total"] += run_out

        st.markdown("## 💰 使用量と概算費用")
        render_chat_only_summary(
            title="今回ランの概算",
            model=st.session_state["chat_model"],
            in_tokens=run_in,
            out_tokens=run_out,
        )
        usage_cost = estimate_chat_cost(
            st.session_state["chat_model"],
            ChatUsage(input_tokens=run_in, output_tokens=run_out),
        )
        st.caption(
            f"今回ラン tokens: in={run_in:,} / out={run_out:,} → "
            f"USD ${usage_cost['usd']:.6f} ≈ JPY {usage_cost['jpy']:.2f} "
            f"(rate={DEFAULT_USDJPY:.2f})"
        )
        st.divider()
        st.markdown("### セッション累計（このページでの合算）")
        render_chat_only_summary(
            title="累計の概算",
            model=st.session_state["chat_model"],
            in_tokens=st.session_state["tok_in_total"],
            out_tokens=st.session_state["tok_out_total"],
        )
else:
    st.info("入力タブ（📁/📝）から本文を指定して『① 解析』→『② 本校正』の順に実行してください。")
