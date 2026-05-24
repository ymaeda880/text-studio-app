# -*- coding: utf-8 -*-
# text_studio_app/pages/906_図表チェックv2.py
# ============================================================
# 🖼️ 図表チェックv2（AI文脈判定）
#
# ✅ 03_文章校正.py テンプレ準拠：
# - page_session_heartbeat でログイン/heartbeat
# - 入力UIは 貼り付け / ファイル / Inbox
# - AI呼び出しは common_lib.ai.routing.call_text
# - busy_run で ai_runs.db を記録
# - tokens/cost は返ってきた範囲だけ表示
#
# ✅ 図表チェック方針：
# - 図表抽出は lib.chart_check.extractors を使用
# - AIには抽出させず、文脈的な番号ずれ判定だけを担当させる
#
# UI方針：
# - use_container_width は使わない
# - st.form は使わない
# - st.button()/st.download_button() に width 引数は使わない
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib / typing）
# ============================================================
import json
import sys
from io import BytesIO
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

# ============================================================
# imports（3rd party）
# ============================================================
import pandas as pd
import streamlit as st

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="Text Studio / 図表チェックv2",
    page_icon="🖼️",
    layout="wide",
)

# ============================================================
# パス設定
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
# common_lib（ログイン / busy / UI）
# ============================================================
from common_lib.sessions.page_entry import page_session_heartbeat
from common_lib.busy import busy_run
from common_lib.ui.banner_lines import render_banner_line_by_key
from common_lib.ui import render_run_summary_compact
from common_lib.ui.ui_basics import subtitle

# ============================================================
# common_lib（AI）
# ============================================================
from common_lib.ai.routing import call_text
from common_lib.ui.model_picker import render_text_model_picker
from common_lib.ai.models import TEXT_MODEL_CATALOG, DEFAULT_TEXT_MODEL_KEY
from common_lib.ai.usage_extract import extract_text_in_out_tokens
from common_lib.busy.apply_text_result import apply_text_result_to_busy

# ============================================================
# lib（入力）
# ============================================================
from lib.text_loaders import (
    load_text_generic,
    load_text_from_paste,
)

# ============================================================
# common_lib Inbox
# ============================================================
from common_lib.inbox.inbox_ui.file_picker import render_inbox_file_picker_no_toggle
from common_lib.inbox.inbox_ui.file_picker import InboxPickedFile

# ============================================================
# lib（図表チェック）
# ============================================================
from lib.chart_check.extractors import judge_hits_in_page
from lib.chart_check.helpers import (
    base_key,
    index_pages_by_key,
)

# ============================================================
# lib（AIプロンプト）
# ============================================================
from lib.chart_check.ai_prompts import (
    FIGURE_TABLE_CHECK_SYSTEM_PROMPT,
    build_figure_table_check_prompt,
)

# ============================================================
# 定数
# ============================================================
DEFAULT_MODEL_KEY = DEFAULT_TEXT_MODEL_KEY
INBOX_PAGE_SIZE = 8

# ============================================================
# バナー / ログイン
# ============================================================
render_banner_line_by_key("purple_light")

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
    st.title("🖼️ 図表チェックv2")
with right:
    st.success(f"✅ ログイン中: **{sub}**")

subtitle("図表タイトルと本文引用の文脈ずれをAIでチェック")

# ============================================================
# 説明
# ============================================================
st.caption(
    "Word解析後の中間テキストを読み込み、図表タイトル一覧と本文中の図表参照を抽出します。"
    "そのうえで、AIにより本文の文脈と図表タイトルが対応しているかを確認します。"
)
st.caption(
    "図表番号の一次抽出はプログラムで行い、AIには文脈的なずれの判定だけを行わせます。"
)
st.caption("個人情報や機密情報の入力は避けてください。")

# ============================================================
# セッションキー（入力）
# ============================================================
K_SRC_TEXT = f"{PAGE_NAME}__src_text"
K_SRC_NAME = f"{PAGE_NAME}__src_name"
K_DO_ANALYZE = f"{PAGE_NAME}__do_analyze"

st.session_state.setdefault(K_SRC_TEXT, "")
st.session_state.setdefault(K_SRC_NAME, "")
st.session_state.setdefault(K_DO_ANALYZE, False)

# ============================================================
# セッションキー（候補プレビュー）
# ============================================================
K_FILE_CAND_TEXT = f"{PAGE_NAME}__file_cand_text"
K_FILE_CAND_NAME = f"{PAGE_NAME}__file_cand_name"
K_FILE_CAND_SIG = f"{PAGE_NAME}__file_cand_sig"
K_LAST_FILE_SIG = f"{PAGE_NAME}__last_file_sig"

st.session_state.setdefault(K_FILE_CAND_TEXT, "")
st.session_state.setdefault(K_FILE_CAND_NAME, "")
st.session_state.setdefault(K_FILE_CAND_SIG, "")
st.session_state.setdefault(K_LAST_FILE_SIG, "")

# ============================================================
# セッションキー（Inbox）
# ============================================================
K_INBOX_BYTES = f"{PAGE_NAME}__inbox_bytes"
K_INBOX_NAME = f"{PAGE_NAME}__inbox_name"
K_INBOX_ITEM = f"{PAGE_NAME}__inbox_item_id"

st.session_state.setdefault(K_INBOX_BYTES, b"")
st.session_state.setdefault(K_INBOX_NAME, "")
st.session_state.setdefault(K_INBOX_ITEM, "")

# ============================================================
# セッションキー（AI / usage）
# ============================================================
K_MODEL_KEY = f"{PAGE_NAME}__model_key"
K_LAST_RUN_ID = f"{PAGE_NAME}__last_run_id"
K_LAST_IN_TOK = f"{PAGE_NAME}__last_in_tok"
K_LAST_OUT_TOK = f"{PAGE_NAME}__last_out_tok"
K_LAST_COST_OBJ = f"{PAGE_NAME}__last_cost_obj"
K_LAST_MODEL = f"{PAGE_NAME}__last_model"
K_LAST_PROVIDER = f"{PAGE_NAME}__last_provider"
K_LAST_NOTE = f"{PAGE_NAME}__last_note"

st.session_state.setdefault(K_MODEL_KEY, DEFAULT_MODEL_KEY)
st.session_state.setdefault(K_LAST_RUN_ID, "")
st.session_state.setdefault(K_LAST_IN_TOK, None)
st.session_state.setdefault(K_LAST_OUT_TOK, None)
st.session_state.setdefault(K_LAST_COST_OBJ, None)
st.session_state.setdefault(K_LAST_MODEL, "")
st.session_state.setdefault(K_LAST_PROVIDER, "")
st.session_state.setdefault(K_LAST_NOTE, "")

# ============================================================
# セッションキー（入力方式）
# ============================================================
K_INPUT_METHOD = f"{PAGE_NAME}__input_method"
INPUT_PASTE = "📝 貼り付けテキスト"
INPUT_FILE = "📁 ファイルから"
INPUT_INBOX = "📥 Inboxから"

st.session_state.setdefault(K_INPUT_METHOD, INPUT_PASTE)


# ============================================================
# helper：model_key -> provider/model
# ============================================================
def _parse_model_key(model_key: str) -> tuple[str, str]:
    if ":" not in model_key:
        return ("openai", model_key.strip())

    p, m = model_key.split(":", 1)
    return (p.strip(), m.strip())


# ============================================================
# helper：Gemini availability
# ============================================================
@lru_cache(maxsize=1)
def _gemini_available() -> bool:
    try:
        from google import genai
        _ = genai
        return True
    except Exception:
        return False


# ============================================================
# helper：bytes -> text
# ============================================================
def _decode_text_bytes(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("utf-8", errors="replace")


# ============================================================
# helper：番号付きプレビュー
# ============================================================
def _to_numbered_preview(text: str) -> str:
    lines = str(text or "").splitlines()
    return "\n".join([f"[{i + 1:04d}] {line}" for i, line in enumerate(lines)])


# ============================================================
# helper：AI JSON parse
# ============================================================
def _parse_ai_json(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json\n", "", 1).strip()

    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {"raw": raw}
    except Exception:
        return {"raw": raw}


# ============================================================
# helper：抽出結果作成
# ============================================================
def _extract_from_text(src_text: str, ctx_chars: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    captions, refs = judge_hits_in_page(src_text, ctx=ctx_chars)

    caption_rows = [{"text_page": 1, "page_label": "-", **h} for h in captions]
    ref_rows = [{"text_page": 1, "page_label": "-", **r} for r in refs]

    return pd.DataFrame(caption_rows), pd.DataFrame(ref_rows)


# ============================================================
# helper：機械チェック作成
# ============================================================
def _build_machine_checks(df_captions: pd.DataFrame, df_refs: pd.DataFrame) -> Dict[str, Any]:
    cap_idx = index_pages_by_key(df_captions)
    ref_idx = index_pages_by_key(df_refs)

    cap_keys_full: set[str] = set()
    ref_keys_full: set[str] = set()

    if (not df_captions.empty) and ("図表キー" in df_captions.columns):
        cap_keys_full = set(df_captions["図表キー"].dropna().astype(str))

    if (not df_refs.empty) and ("図表キー" in df_refs.columns):
        ref_keys_full = set(df_refs["図表キー"].dropna().astype(str))

    cap_base_keys = {base_key(k) for k in cap_keys_full}
    ref_base_keys = {base_key(k) for k in ref_keys_full}

    missing_in_refs = sorted(
        k
        for k in cap_keys_full
        if not ((k in ref_keys_full) or (base_key(k) in ref_base_keys))
    )

    missing_in_captions = sorted(
        k
        for k in ref_keys_full
        if not ((k in cap_keys_full) or (base_key(k) in cap_base_keys))
    )

    return {
        "missing_in_references": [
            {
                "label": k,
                "caption_locations": cap_idx.get(k, []),
                "reference_locations": ref_idx.get(k, []),
            }
            for k in missing_in_refs
        ],
        "references_without_title": [
            {
                "label": k,
                "reference_locations": ref_idx.get(k, []),
                "caption_locations": cap_idx.get(k, []),
            }
            for k in missing_in_captions
        ],
    }


# ============================================================
# helper：AI入力payload作成
# ============================================================
def _build_ai_payload(
    *,
    src_name: str,
    df_captions: pd.DataFrame,
    df_refs: pd.DataFrame,
    machine_checks: Dict[str, Any],
) -> Dict[str, Any]:
    titles: List[Dict[str, Any]] = []
    references: List[Dict[str, Any]] = []

    if not df_captions.empty:
        for _, r in df_captions.iterrows():
            titles.append(
                {
                    "kind": str(r.get("図表種類", "")),
                    "label": str(r.get("図表キー", "")),
                    "shown_label": str(r.get("図表番号", "")),
                    "title": str(r.get("見出しタイトル", "")),
                    "line_text": str(r.get("matched_line", "")),
                    "excerpt": str(r.get("excerpt", "")),
                }
            )

    if not df_refs.empty:
        for _, r in df_refs.iterrows():
            references.append(
                {
                    "kind": str(r.get("図表種類", "")),
                    "label": str(r.get("図表キー", "")),
                    "shown_label": str(r.get("図表番号", "")),
                    "reference_text": str(r.get("参照テキスト", "")),
                    "line_text": str(r.get("行テキスト", "")),
                    "context": str(r.get("excerpt", "")),
                }
            )

    return {
        "source_name": src_name,
        "titles": titles,
        "references": references,
        "machine_checks": machine_checks,
    }


# ============================================================
# Sidebar（設定）
# ============================================================
with st.sidebar:
    st.header("設定")

    _ = render_text_model_picker(
        title="🧠 使用モデル",
        catalog=TEXT_MODEL_CATALOG,
        session_key=K_MODEL_KEY,
        default_key=DEFAULT_MODEL_KEY,
        page_name=PAGE_NAME,
        gemini_available=_gemini_available(),
    )

    st.markdown("### 抽出設定")
    ctx_chars = st.slider(
        "参照の前後コンテキスト文字数",
        10,
        300,
        80,
        5,
    )

    show_payload = st.checkbox("AI入力JSONを表示", value=False)
    show_raw_ai = st.checkbox("AI生JSONを表示", value=False)

# ============================================================
# 入力方式
# ============================================================
picked_method = st.radio(
    "入力方法",
    [INPUT_PASTE, INPUT_FILE, INPUT_INBOX],
    key=K_INPUT_METHOD,
    horizontal=True,
)

# ============================================================
# 入力：ファイル
# ============================================================
if picked_method == INPUT_FILE:
    up = st.file_uploader(
        "word解析を行ったテキストファイル（.txt） をアップロード",
        type=["txt"],
        key=f"{PAGE_NAME}__uploader",
    )

    do_analyze_file = st.button(
        "① 解析（ファイル）",
        type="primary",
        disabled=not up,
        key=f"{PAGE_NAME}__btn_file",
    )

    if up:
        sig = f"{up.name}:{getattr(up, 'size', 0)}"

        if str(st.session_state.get(K_LAST_FILE_SIG) or "") != sig:
            st.session_state[K_LAST_FILE_SIG] = sig
            st.session_state[K_SRC_TEXT] = ""
            st.session_state[K_SRC_NAME] = ""
            st.session_state[K_DO_ANALYZE] = False
            st.session_state[K_FILE_CAND_TEXT] = ""
            st.session_state[K_FILE_CAND_NAME] = ""
            st.session_state[K_FILE_CAND_SIG] = ""

        data_bytes = up.getvalue()
        if not data_bytes:
            st.warning("ファイルが0バイトです。")
            st.stop()

        from io import BytesIO

        pseudo = BytesIO(data_bytes)
        pseudo.name = up.name or "input.txt"

        try:
            cand_text = str(load_text_generic(pseudo) or "").strip()
        except RuntimeError as e:
            st.error(str(e))
            st.stop()

        if not cand_text:
            st.warning("テキストを取得できませんでした。")
            st.stop()

        st.session_state[K_FILE_CAND_TEXT] = cand_text
        st.session_state[K_FILE_CAND_NAME] = up.name or "input.txt"
        st.session_state[K_FILE_CAND_SIG] = sig

        if do_analyze_file:
            st.session_state[K_SRC_TEXT] = cand_text
            st.session_state[K_SRC_NAME] = up.name or "input.txt"
            st.session_state[K_DO_ANALYZE] = True
            st.rerun()

# ============================================================
# 入力：貼り付け
# ============================================================
elif picked_method == INPUT_PASTE:
    pasted = st.text_area(
        "ここに中間テキストを貼り付け",
        height=260,
        key=f"{PAGE_NAME}__pasted_text",
        placeholder="Word解析後の中間テキストを貼り付けてください。",
    )

    do_analyze_paste = st.button(
        "① 解析（貼り付け）",
        type="primary",
        key=f"{PAGE_NAME}__btn_paste",
    )

    if do_analyze_paste:
        if not str(pasted or "").strip():
            st.warning("テキストを貼り付けてください。")
            st.stop()

        src_text = load_text_from_paste(
            pasted,
            normalize=True,
            collapse_blanks=False,
            keep_blank_lines=1,
            trim_trailing=True,
        )

        st.session_state[K_SRC_TEXT] = str(src_text or "").strip()
        st.session_state[K_SRC_NAME] = "pasted_text.txt"
        st.session_state[K_DO_ANALYZE] = True

# ============================================================
# 入力：Inbox
# ============================================================
else:
    picked: InboxPickedFile | None = render_inbox_file_picker_no_toggle(
        projects_root=PROJECTS_ROOT,
        user_sub=sub,
        key_prefix=f"{PAGE_NAME}__inbox_picker",
        page_size=INBOX_PAGE_SIZE,
        kinds=["text"],
        show_kind_in_label=True,
        show_added_at_in_label=True,
    )

    if picked is not None:
        st.session_state[K_INBOX_BYTES] = picked.data_bytes or b""
        st.session_state[K_INBOX_NAME] = picked.original_name or "inbox_text.txt"
        st.session_state[K_INBOX_ITEM] = str(picked.item_id or "")
        st.success("✅ Inbox から読み込みました。")

    kept_bytes: bytes = st.session_state.get(K_INBOX_BYTES, b"") or b""
    kept_name: str = st.session_state.get(K_INBOX_NAME, "") or ""

    do_analyze_inbox = st.button(
        "① 解析（Inbox）",
        type="primary",
        disabled=not bool(kept_bytes),
        key=f"{PAGE_NAME}__btn_inbox",
    )

    if kept_bytes:
        cand_text = str(_decode_text_bytes(kept_bytes) or "").strip()
        st.session_state[K_FILE_CAND_TEXT] = cand_text
        st.session_state[K_FILE_CAND_NAME] = kept_name or "inbox_text.txt"

    if do_analyze_inbox:
        if not kept_bytes:
            st.warning("Inbox からテキストを選択してください。")
            st.stop()

        src_text = str(_decode_text_bytes(kept_bytes) or "").strip()

        if not src_text:
            st.warning("テキストが空でした。")
            st.stop()

        st.session_state[K_SRC_TEXT] = src_text
        st.session_state[K_SRC_NAME] = kept_name or "inbox_text.txt"
        st.session_state[K_DO_ANALYZE] = True
        st.rerun()

# ============================================================
# プレビュー
# ============================================================
confirmed_text = str(st.session_state.get(K_SRC_TEXT) or "").strip()
candidate_text = str(st.session_state.get(K_FILE_CAND_TEXT) or "").strip()
preview_text = confirmed_text or candidate_text

if preview_text:
    st.subheader("👀 行番号付きプレビュー")
    st.text_area(
        "原文（番号付きプレビュー）",
        value=_to_numbered_preview(preview_text),
        height=260,
    )

# ============================================================
# 実行判定
# ============================================================
want_analyze = bool(st.session_state.pop(K_DO_ANALYZE, False))

# ============================================================
# 解析実行
# ============================================================
if want_analyze:
    src_text = str(st.session_state.get(K_SRC_TEXT) or "").strip()
    src_name = str(st.session_state.get(K_SRC_NAME) or "input.txt")

    if not src_text:
        st.warning("解析対象テキストがありません。")
        st.stop()

    # ------------------------------------------------------------
    # 抽出
    # ------------------------------------------------------------
    df_captions, df_refs = _extract_from_text(src_text, ctx_chars=ctx_chars)
    machine_checks = _build_machine_checks(df_captions, df_refs)

    # ------------------------------------------------------------
    # AI payload
    # ------------------------------------------------------------
    payload = _build_ai_payload(
        src_name=src_name,
        df_captions=df_captions,
        df_refs=df_refs,
        machine_checks=machine_checks,
    )

    if show_payload:
        with st.expander("🧪 AI入力JSON", expanded=False):
            st.json(payload)

    # ------------------------------------------------------------
    # モデル
    # ------------------------------------------------------------
    model_key = str(st.session_state.get(K_MODEL_KEY) or DEFAULT_MODEL_KEY)
    provider, chosen_model = _parse_model_key(model_key)

    if not provider or not chosen_model:
        st.error(f"モデル指定が不正です: {model_key}")
        st.stop()

    st.session_state[K_LAST_MODEL] = chosen_model
    st.session_state[K_LAST_PROVIDER] = provider
    st.session_state[K_LAST_IN_TOK] = None
    st.session_state[K_LAST_OUT_TOK] = None
    st.session_state[K_LAST_COST_OBJ] = None
    st.session_state[K_LAST_NOTE] = ""
    st.session_state[K_LAST_RUN_ID] = ""

    # ------------------------------------------------------------
    # prompt
    # ------------------------------------------------------------
    prompt = build_figure_table_check_prompt(payload)

    # ------------------------------------------------------------
    # AI実行
    # ------------------------------------------------------------
    try:
        with busy_run(
            projects_root=PROJECTS_ROOT,
            user_sub=str(sub),
            app_name=str(APP_NAME),
            page_name=str(PAGE_NAME),
            task_type="text",
            provider=provider,
            model=chosen_model,
            meta={
                "feature": "figure_table_check_v2",
                "action": "context_check",
                "input_method": str(picked_method),
                "input_chars": len(src_text),
                "titles": int(len(df_captions)),
                "references": int(len(df_refs)),
            },
        ) as br:
            st.session_state[K_LAST_RUN_ID] = br.run_id

            with st.spinner("AIで図表参照の文脈チェック中…"):
                res = call_text(
                    provider=provider,
                    model=chosen_model,
                    prompt=prompt,
                    system=FIGURE_TABLE_CHECK_SYSTEM_PROMPT,
                    temperature=None,
                    max_output_tokens=None,
                    extra=None,
                )

            ai_text = (getattr(res, "text", "") or "").strip()

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

    except Exception as e:
        st.error(f"AI実行に失敗しました: {e}")
        st.stop()

    # ------------------------------------------------------------
    # AI JSON parse
    # ------------------------------------------------------------
    ai_obj = _parse_ai_json(ai_text)

    # ------------------------------------------------------------
    # 表示：サマリー
    # ------------------------------------------------------------
    st.success("解析が完了しました。")

    st.subheader("📊 サマリー")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("図表タイトル数", len(df_captions))
    col2.metric("本文参照数", len(df_refs))
    col3.metric("未引用見出し", len(machine_checks.get("missing_in_references", [])))
    col4.metric("見出しなし参照", len(machine_checks.get("references_without_title", [])))

    # ------------------------------------------------------------
    # 表示：AI issues
    # ------------------------------------------------------------
    st.subheader("🧠 AI判定結果")

    issues = ai_obj.get("issues", []) if isinstance(ai_obj, dict) else []
    checks = ai_obj.get("checks", []) if isinstance(ai_obj, dict) else []

    if isinstance(issues, list) and issues:
        st.warning("AIが確認事項を検出しました。")
        st.dataframe(pd.DataFrame(issues))
    else:
        st.success("AI判定では明確な問題は検出されませんでした。")

    if isinstance(checks, list) and checks:
        with st.expander("✅ AIチェック詳細", expanded=False):
            st.dataframe(pd.DataFrame(checks))

    # ------------------------------------------------------------
    # 表示：機械チェック
    # ------------------------------------------------------------
    st.subheader("🔎 機械チェック結果")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 🟠 未引用の見出し")
        rows = machine_checks.get("missing_in_references", [])
        st.dataframe(pd.DataFrame(rows))

    with c2:
        st.markdown("#### 🔵 見出しなしの参照")
        rows = machine_checks.get("references_without_title", [])
        st.dataframe(pd.DataFrame(rows))

    # ------------------------------------------------------------
    # 表示：抽出一覧
    # ------------------------------------------------------------
    st.subheader("🖼️ 図表タイトル一覧")
    st.dataframe(df_captions)

    st.subheader("🔗 本文中の図表参照一覧")
    st.dataframe(df_refs)

    # ------------------------------------------------------------
    # 表示：AI生JSON
    # ------------------------------------------------------------
    if show_raw_ai:
        with st.expander("🧪 AI生出力", expanded=False):
            st.code(ai_text, language="json")

    # ------------------------------------------------------------
    # 実行サマリ
    # ------------------------------------------------------------
    render_run_summary_compact(
        projects_root=PROJECTS_ROOT,
        run_id=st.session_state.get(K_LAST_RUN_ID),
        model=st.session_state.get(K_LAST_MODEL),
        in_tokens=st.session_state.get(K_LAST_IN_TOK),
        out_tokens=st.session_state.get(K_LAST_OUT_TOK),
        cost=st.session_state.get(K_LAST_COST_OBJ),
        note=str(st.session_state.get(K_LAST_NOTE) or ""),
        show_divider=True,
    )

# ============================================================
# Sidebar：Excelダウンロード
# ============================================================
with st.sidebar:
    st.markdown("### 📘 結果ダウンロード")

    if "df_captions" in locals() and "df_refs" in locals() and "ai_text" in locals():
        xlsx_output = BytesIO()

        issues_df = pd.DataFrame(issues) if isinstance(issues, list) else pd.DataFrame()
        checks_df = pd.DataFrame(checks) if isinstance(checks, list) else pd.DataFrame()

        machine_missing_refs_df = pd.DataFrame(
            machine_checks.get("missing_in_references", [])
        )
        machine_orphan_refs_df = pd.DataFrame(
            machine_checks.get("references_without_title", [])
        )

        summary_df = pd.DataFrame(
            [
                {"項目": "入力ファイル名", "値": src_name},
                {"項目": "図表タイトル数", "値": len(df_captions)},
                {"項目": "本文参照数", "値": len(df_refs)},
                {"項目": "未引用見出し数", "値": len(machine_checks.get("missing_in_references", []))},
                {"項目": "見出しなし参照数", "値": len(machine_checks.get("references_without_title", []))},
                {"項目": "AI issues 数", "値": len(issues) if isinstance(issues, list) else 0},
                {"項目": "AI checks 数", "値": len(checks) if isinstance(checks, list) else 0},
            ]
        )

        raw_ai_df = pd.DataFrame([{"ai_raw_json": ai_text}])

        with pd.ExcelWriter(xlsx_output, engine="openpyxl") as writer:
            summary_df.to_excel(writer, sheet_name="サマリー", index=False)
            issues_df.to_excel(writer, sheet_name="AI判定_issues", index=False)
            checks_df.to_excel(writer, sheet_name="AI判定_checks", index=False)
            df_captions.to_excel(writer, sheet_name="図表タイトル一覧", index=False)
            df_refs.to_excel(writer, sheet_name="本文参照一覧", index=False)
            machine_missing_refs_df.to_excel(writer, sheet_name="未引用見出し", index=False)
            machine_orphan_refs_df.to_excel(writer, sheet_name="見出しなし参照", index=False)
            raw_ai_df.to_excel(writer, sheet_name="AI生出力", index=False)

        xlsx_bytes = xlsx_output.getvalue()

        file_base = src_name.rsplit(".", 1)[0] if src_name else "figure_table_check"
        xlsx_filename = f"図表チェックv2_{file_base}.xlsx"

        st.download_button(
            "📘 Excelダウンロード",
            data=xlsx_bytes,
            file_name=xlsx_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{PAGE_NAME}__download_xlsx",
        )
    else:
        st.caption("解析を実行するとダウンロード可能になります。")
        
# ============================================================
# 未入力案内
# ============================================================
if (not preview_text) and (not want_analyze):
    st.info("入力（貼り付け / ファイル / Inbox）から中間テキストを指定して『① 解析』を実行してください。")