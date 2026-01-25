# -*- coding: utf-8 -*-
# pages/21_AI文章作成.py
# ============================================================
# 📝 文章作成（テンプレ準拠 / GPT・Gemini 共通）
#
# 目的：
# - 元文章（貼り付け / ファイル）＋用途テンプレ＋追加指示 → 最終文章を生成
#
# ✅ テンプレ準拠（AI実行 + busy 記録）：
# - AI呼び出しは common_lib.ai（provider差を吸収）
# - busy（ai_runs.db）を with busy_run で必ず記録
# - tokens / cost は「返ってきた範囲のみ」表示（推計しない）
# - 実行結果の反映は apply_text_result_to_busy に寄せる
#
# UI方針：
# - use_container_width は使わない
# - st.form は使わない
# - st.button()/st.download_button() に width 引数は使わない
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Tuple
from functools import lru_cache

# ============================================================
# imports（third-party）
# ============================================================
import streamlit as st
import docx

# ============================================================
# パス設定（common_lib を import できるように）
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
# common_lib.ai（正本）
# ============================================================
from common_lib.ai import call_text  # type: ignore
from common_lib.ai.usage_extract import extract_text_in_out_tokens  # type: ignore

# ============================================================
# common_lib UI / auth（正本）
# ============================================================
from common_lib.sessions.page_entry import page_session_heartbeat  # type: ignore
from common_lib.ui.ui_basics import subtitle  # type: ignore
from common_lib.ui.banner_lines import render_banner_line_by_key  # type: ignore
from common_lib.ui import render_run_summary_compact  # type: ignore
from common_lib.ui.model_picker import render_text_model_picker  # type: ignore
from common_lib.ai.models import TEXT_MODEL_CATALOG, DEFAULT_TEXT_MODEL_KEY  # type: ignore

# ============================================================
# busy（正本）
# ============================================================
from common_lib.busy import busy_run  # type: ignore
from common_lib.busy.apply_text_result import apply_text_result_to_busy  # type: ignore

# ============================================================
# ページ設定（最初に1回だけ）
# ============================================================
st.set_page_config(
    page_title="📝 AI文章作成",
    page_icon="📝",
    layout="wide",
)

# ============================================================
# バナー（上部）
# ============================================================
render_banner_line_by_key("purple_light")

# ============================================================
# ログイン / heartbeat（正本）
# ============================================================
sub = page_session_heartbeat(
    st,
    PROJECTS_ROOT,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
)

# ============================================================
# タイトル
# ============================================================
left, right = st.columns([2, 1])
with left:
    st.title("📝 AI文章作成")
with right:
    st.success(f"✅ ログイン中: **{sub}**")

subtitle("AIで文章を作成")
st.caption(
    "元となる文章（貼り付け / Word / txt / json / md）＋ テンプレ（メール/報告書など）＋ 追加指示をつないで、文章を生成します。"
)

# ============================================================
# セッションキー（最小）
# ============================================================
K_MODEL_KEY = f"{PAGE_NAME}__model_key"
K_SYSTEM = f"{PAGE_NAME}__system"
K_ADDITIONAL = f"{PAGE_NAME}__additional"
K_MAX_OUT_TOK = f"{PAGE_NAME}__max_output_tokens"

K_LAST_ANSWER = f"{PAGE_NAME}__last_answer"
K_LAST_IN_TOK = f"{PAGE_NAME}__last_in_tok"
K_LAST_OUT_TOK = f"{PAGE_NAME}__last_out_tok"
K_LAST_COST_OBJ = f"{PAGE_NAME}__last_cost_obj"
K_LAST_MODEL = f"{PAGE_NAME}__last_model"
K_LAST_NOTE = f"{PAGE_NAME}__last_note"
K_LAST_RUN_ID = f"{PAGE_NAME}__last_run_id"

# ============================================================
# 初期化
# ============================================================
st.session_state.setdefault(K_MODEL_KEY, DEFAULT_TEXT_MODEL_KEY)
st.session_state.setdefault(K_SYSTEM, "あなたは丁寧な日本語で文章を作成するアシスタントです。")
st.session_state.setdefault(K_ADDITIONAL, "")
st.session_state.setdefault(K_MAX_OUT_TOK, 4000)

st.session_state.setdefault(K_LAST_ANSWER, "")
st.session_state.setdefault(K_LAST_IN_TOK, None)
st.session_state.setdefault(K_LAST_OUT_TOK, None)
st.session_state.setdefault(K_LAST_COST_OBJ, None)
st.session_state.setdefault(K_LAST_MODEL, "")
st.session_state.setdefault(K_LAST_NOTE, "")
st.session_state.setdefault(K_LAST_RUN_ID, None)

# ============================================================
# provider / model_key utilities
# ============================================================
def _parse_model_key(model_key: str) -> Tuple[str, str]:
    if ":" not in model_key:
        return ("openai", model_key)
    p, m = model_key.split(":", 1)
    return p.strip(), m.strip()


@lru_cache(maxsize=1)
def _gemini_available() -> bool:
    """
    Gemini 利用可否の判定（google-genai が import できるか）
    - sidebar 再描画ごとに import されるのを防ぐためキャッシュする
    """
    try:
        from google import genai  # type: ignore  # google-genai
        _ = genai
        return True
    except Exception:
        return False

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

# ============================================================
# Prompt builder（ページ固有ロジック）
# ============================================================
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
# Sidebar（モデル選択 / system / max tokens）
# ============================================================
with st.sidebar:
    st.header("設定")

    model_key = render_text_model_picker(
        title="モデル選択",
        catalog=TEXT_MODEL_CATALOG,
        session_key=K_MODEL_KEY,
        default_key=DEFAULT_TEXT_MODEL_KEY,
        page_name=PAGE_NAME,
        gemini_available=_gemini_available(),
    )

    st.divider()

    st.text_area("System（任意）", key=K_SYSTEM, height=120)

    st.number_input(
        "最大出力トークン（上限）",
        min_value=256,
        max_value=20000,
        value=int(st.session_state.get(K_MAX_OUT_TOK) or 4000),
        step=256,
        key=K_MAX_OUT_TOK,
        help="※ backend が対応している場合のみ上限として有効。推計や概算表示はしません。",
    )

# ============================================================
# Input source（TEXT FIRST）
# ============================================================
st.subheader("1️⃣ 元となる文章の入力")

tab_text, tab_file = st.tabs(["📝 テキストを直接貼り付け（推奨）", "📂 ファイルをアップロード"])

source_text: str = ""
source_kind: str = ""

# ------------------------------------------------------------
# tab: text paste（優先）
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# tab: file upload（貼り付けが空のときだけ採用）
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# no input warning
# ------------------------------------------------------------
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
    st.text_area(
        "追加の指示（任意）",
        height=140,
        placeholder="例：『もう少し短く』『箇条書きを多めに』『結びに次アクションを入れて』など",
        key=K_ADDITIONAL,
    )

run = st.button("📝 文章生成", type="primary")

# ============================================================
# Execute（AI 実行）
# ============================================================
if run:
    if not source_text.strip():
        st.error("先に元となる文章を入力してください。")
        st.stop()

    # ------------------------------------------------------------
    # final prompt（ページ固有）
    # ------------------------------------------------------------
    max_chars = 15000
    final_prompt = build_final_prompt(
        template_name=template_name,
        base_text_kind=source_kind or "不明",
        base_text=source_text,
        additional_instruction=str(st.session_state.get(K_ADDITIONAL) or ""),
        max_chars=max_chars,
    )

    # ------------------------------------------------------------
    # model_key safe化（sidebar と同じ考え方）
    # ------------------------------------------------------------
    safe_model_key = (model_key or "").strip() or DEFAULT_TEXT_MODEL_KEY
    provider, model = _parse_model_key(safe_model_key)

    # ------------------------------------------------------------
    # system / max output tokens（任意）
    # ------------------------------------------------------------
    system = (st.session_state.get(K_SYSTEM) or "").strip() or None
    max_output_tokens = int(st.session_state.get(K_MAX_OUT_TOK) or 0) or None

    # ------------------------------------------------------------
    # 直近表示を初期化
    # ------------------------------------------------------------
    st.session_state[K_LAST_ANSWER] = ""
    st.session_state[K_LAST_IN_TOK] = None
    st.session_state[K_LAST_OUT_TOK] = None
    st.session_state[K_LAST_COST_OBJ] = None
    st.session_state[K_LAST_MODEL] = model
    st.session_state[K_LAST_NOTE] = ""
    st.session_state[K_LAST_RUN_ID] = None

    # ------------------------------------------------------------
    # busy_run + call_text（正本）
    # ------------------------------------------------------------
    with st.spinner("AI が文章を生成中..."):
        with busy_run(
            projects_root=PROJECTS_ROOT,
            user_sub=str(sub),
            app_name=APP_NAME,
            page_name=PAGE_NAME,
            task_type="text",
            provider=provider,
            model=model,
            meta={"max_output_tokens": max_output_tokens},
        ) as br:
            run_id = br.run_id
            st.session_state[K_LAST_RUN_ID] = run_id

            # ------------------------------------------------------------
            # call_text（max_output_tokens は backend 対応時のみ）
            # - 対応していない環境でも壊れないよう TypeError fallback
            # ------------------------------------------------------------
            try:
                if max_output_tokens is not None:
                    res = call_text(
                        provider=provider,
                        model=model,
                        prompt=final_prompt,
                        system=system,
                        max_output_tokens=max_output_tokens,
                    )
                else:
                    res = call_text(
                        provider=provider,
                        model=model,
                        prompt=final_prompt,
                        system=system,
                    )
            except TypeError:
                res = call_text(
                    provider=provider,
                    model=model,
                    prompt=final_prompt,
                    system=system,
                )

            answer = (getattr(res, "text", "") or "").strip()
            st.session_state[K_LAST_ANSWER] = answer

            # ------------------------------------------------------------
            # usage/cost の反映（推計しない）
            # ------------------------------------------------------------
            pp = apply_text_result_to_busy(
                br=br,
                res=res,
                extract_text_in_out_tokens=extract_text_in_out_tokens,
                note_ok="ok",
                note_no_usage="no_usage",
                note_no_cost="no_cost",
            )
            st.session_state[K_LAST_IN_TOK] = pp.in_tokens
            st.session_state[K_LAST_OUT_TOK] = pp.out_tokens
            st.session_state[K_LAST_COST_OBJ] = pp.cost_obj
            st.session_state[K_LAST_NOTE] = pp.note
            st.session_state[K_LAST_MODEL] = model

            # ------------------------------------------------------------
            # 回答が空のときの注意（推測しない）
            # ------------------------------------------------------------
            if not answer:
                st.session_state[K_LAST_NOTE] = (st.session_state.get(K_LAST_NOTE) or "") + " / empty_text"

# ============================================================
# Output（生成結果 + run summary）
# ============================================================
if st.session_state.get(K_LAST_ANSWER):
    st.divider()
    st.subheader("✅ 生成結果")
    st.write(st.session_state[K_LAST_ANSWER])

    render_run_summary_compact(
        projects_root=PROJECTS_ROOT,
        run_id=st.session_state.get(K_LAST_RUN_ID),
        model=st.session_state.get(K_LAST_MODEL),
        in_tokens=st.session_state.get(K_LAST_IN_TOK),
        out_tokens=st.session_state.get(K_LAST_OUT_TOK),
        cost=st.session_state.get(K_LAST_COST_OBJ),
        note=st.session_state.get(K_LAST_NOTE) or "",
        show_divider=True,
    )

    with st.expander("🔧 実際に送ったプロンプト（確認用）", expanded=False):
        # 生成後に source_text が変わる可能性があるため、直近の構築を再現する
        max_chars = 15000
        final_prompt_for_view = build_final_prompt(
            template_name=template_name,
            base_text_kind=source_kind or "不明",
            base_text=source_text,
            additional_instruction=str(st.session_state.get(K_ADDITIONAL) or ""),
            max_chars=max_chars,
        )
        st.code(final_prompt_for_view, language="text")
