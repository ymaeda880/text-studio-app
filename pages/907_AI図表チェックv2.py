# -*- coding: utf-8 -*-
# text_studio_app/pages/907_AI図表チェック.py
# ============================================================
# 🧠 図表の参照照合チェック（AI使用）
#
# 機能：
# - ① PDFから「図」「表」を含む文を抽出する
# - ② 抽出結果を画面表示し、JSON / CSVでダウンロードする
# - ③ AIで「タイトル / 本文参照 / 未分類」に分類する
# - ④ 分類結果を画面表示し、JSON / CSVでダウンロードする
# - ⑤ 分類結果をもとにAIで照合する
# - ⑥ 照合結果を画面表示し、CSV / JSON / XLSXでダウンロードする
#
# 方針：
# - ローカル側では caption / reference 分類をしない
# - 分類AIと照合AIを分ける
# - use_container_width は使わない
# - st.form は使わない
# - st.button()/st.download_button() に width 引数は使わない
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# imports（3rd party）
# ============================================================
import fitz
import pandas as pd
import streamlit as st

# ============================================================
# sys.path（テンプレ準拠）
# ============================================================
_THIS = Path(__file__).resolve()
APP_DIR = _THIS.parents[1]
PROJ_DIR = _THIS.parents[2]
MONO_ROOT = _THIS.parents[3]

# ------------------------------------------------------------
# MONO_ROOT 妥当性チェック
# ------------------------------------------------------------
if not (MONO_ROOT / "common_lib").is_dir():
    raise RuntimeError(
        "MONO_ROOT の解釈が不正です（common_lib が見つかりません）。\n"
        f"  this_file : {_THIS}\n"
        f"  MONO_ROOT  : {MONO_ROOT}\n"
        "対処：pages の階層（parents[3]）前提が崩れていないか確認してください。"
    )

# ------------------------------------------------------------
# import path 追加
# ------------------------------------------------------------
for p in (MONO_ROOT, PROJ_DIR, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PROJECTS_ROOT = MONO_ROOT
APP_NAME = _THIS.parents[1].name
PAGE_NAME = _THIS.stem

# ============================================================
# common_lib（ログイン / UI / AI / busy）
# ============================================================
from common_lib.sessions.page_entry import page_session_heartbeat
from common_lib.ui.banner_lines import render_banner_line_by_key
from common_lib.ui.ui_basics import subtitle
from common_lib.busy import busy_run
from common_lib.ai.routing import call_text
from common_lib.ai.usage_extract import extract_text_in_out_tokens
from common_lib.busy.apply_text_result import apply_text_result_to_busy
from common_lib.ui import render_run_summary_compact
from common_lib.ui.model_picker import render_text_model_picker
from common_lib.ai.models import TEXT_MODEL_CATALOG, DEFAULT_TEXT_MODEL_KEY
from common_lib.pdf_tools.text_extract.detect import detect_pdf_kind_from_bytes

# ============================================================
# app config
# ============================================================
from config.config import has_gemini_api_key

# ============================================================
# lib（ページ別テキスト抽出）
# ============================================================
from lib.toc_check.toc_segments import (
    pdf_to_text_per_page,
    extract_single_page_label,
)

# ============================================================
# lib（AI図表チェック）
# ============================================================
from lib.ai_chart_check.extract import extract_figure_table_sentences
from lib.ai_chart_check.prompt import (
    build_ai_input_payload,
    build_classify_payload,
    build_check_payload,
    build_system_text,
    build_classify_prompt_text,
    build_check_prompt_text,
)
from lib.ai_chart_check.parse import (
    extract_json_object,
    df_from_list,
    checks_to_df,
    make_xlsx_bytes,
)

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="🧠 図表の参照照合チェック（AI）",
    page_icon="🧠",
    layout="wide",
)

# ============================================================
# Banner / heartbeat
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
    st.title("🧠 図表の参照照合チェック")

with right:
    st.success(f"✅ ログイン中: **{sub}**")

subtitle("（AI使用 / 抽出 → 分類 → 照合）")

# ============================================================
# 説明
# ============================================================
st.caption(
    "まずPDFから「図」「表」を含む文を抽出し、次にAIでタイトル・本文参照に分類し、最後に分類結果をAIで照合します。"
)
st.caption(
    "分類と照合を分けることで、大きなPDFでも対応関係がずれにくい構成にしています。"
)
st.caption(
    "AIを使用するため、アップロードするPDFの内容に機密情報が含まれないか確認してください。"
)

# ============================================================
# Session state
# ============================================================
def _ensure_state() -> None:
    # ------------------------------------------------------------
    # 実行情報
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_chart_last_run_id", "")
    st.session_state.setdefault("ai_chart_last_model", "")
    st.session_state.setdefault("ai_chart_last_provider", "")
    st.session_state.setdefault("ai_chart_last_in_tok", None)
    st.session_state.setdefault("ai_chart_last_out_tok", None)
    st.session_state.setdefault("ai_chart_last_cost_obj", None)
    st.session_state.setdefault("ai_chart_last_note", "")

    # ------------------------------------------------------------
    # 抽出結果
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_chart_source_file", "")
    st.session_state.setdefault("ai_chart_items", [])
    st.session_state.setdefault("ai_chart_payload", {})
    st.session_state.setdefault("ai_chart_input_json", "")
    st.session_state.setdefault("ai_chart_pages_rows", [])

    # ------------------------------------------------------------
    # 分類結果
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_chart_classify_result", {})
    st.session_state.setdefault("ai_chart_classify_json", "")
    st.session_state.setdefault("ai_chart_classify_answer_text", "")

    # ------------------------------------------------------------
    # 照合結果
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_chart_check_result", {})
    st.session_state.setdefault("ai_chart_check_json", "")
    st.session_state.setdefault("ai_chart_check_answer_text", "")

    # ------------------------------------------------------------
    # AI送信内容
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_chart_last_system_text", "")
    st.session_state.setdefault("ai_chart_last_prompt_text", "")

    # ------------------------------------------------------------
    # モデル設定
    # ------------------------------------------------------------
    st.session_state.setdefault("ai_chart_model_key", DEFAULT_TEXT_MODEL_KEY)
    st.session_state.setdefault("ai_chart_max_output_tokens", 16000)


_ensure_state()

# ============================================================
# helpers（model）
# ============================================================
def _parse_model_key(model_key: str) -> Tuple[str, str]:
    # ------------------------------------------------------------
    # provider:model を分解
    # ------------------------------------------------------------
    if ":" not in model_key:
        return ("openai", model_key.strip())

    provider, model = model_key.split(":", 1)
    return (provider.strip(), model.strip())


# ============================================================
# helpers（Gemini）
# ============================================================
def _gemini_available() -> bool:
    # ------------------------------------------------------------
    # Gemini SDK import 可否
    # ------------------------------------------------------------
    try:
        from google import genai  # type: ignore
        _ = genai
        return True
    except Exception:
        return False


# ============================================================
# helpers（chunk）
# ============================================================
def _split_items(
    *,
    items: List[Dict[str, Any]],
    chunk_size: int,
) -> List[List[Dict[str, Any]]]:
    # ------------------------------------------------------------
    # items を chunk に分割
    # ------------------------------------------------------------
    return [
        items[i : i + chunk_size]
        for i in range(0, len(items), chunk_size)
    ]


# ============================================================
# helpers（reset）
# ============================================================
def _clear_after_extract_state() -> None:
    # ------------------------------------------------------------
    # 抽出後、分類・照合結果をクリア
    # ------------------------------------------------------------
    st.session_state.ai_chart_classify_result = {}
    st.session_state.ai_chart_classify_json = ""
    st.session_state.ai_chart_classify_answer_text = ""

    st.session_state.ai_chart_check_result = {}
    st.session_state.ai_chart_check_json = ""
    st.session_state.ai_chart_check_answer_text = ""

    st.session_state.ai_chart_last_run_id = ""
    st.session_state.ai_chart_last_model = ""
    st.session_state.ai_chart_last_provider = ""
    st.session_state.ai_chart_last_in_tok = None
    st.session_state.ai_chart_last_out_tok = None
    st.session_state.ai_chart_last_cost_obj = None
    st.session_state.ai_chart_last_note = ""
    st.session_state.ai_chart_last_system_text = ""
    st.session_state.ai_chart_last_prompt_text = ""


def _clear_after_classify_state() -> None:
    # ------------------------------------------------------------
    # 分類後、照合結果をクリア
    # ------------------------------------------------------------
    st.session_state.ai_chart_check_result = {}
    st.session_state.ai_chart_check_json = ""
    st.session_state.ai_chart_check_answer_text = ""


# ============================================================
# helpers（merge）
# ============================================================
def _merge_classify_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    # ------------------------------------------------------------
    # 分類結果を統合
    # ------------------------------------------------------------
    titles: List[Dict[str, Any]] = []
    references: List[Dict[str, Any]] = []
    unclassified_items: List[Dict[str, Any]] = []

    for r in results:
        if not isinstance(r, dict):
            continue

        titles.extend(r.get("titles") if isinstance(r.get("titles"), list) else [])
        references.extend(r.get("references") if isinstance(r.get("references"), list) else [])
        unclassified_items.extend(
            r.get("unclassified_items") if isinstance(r.get("unclassified_items"), list) else []
        )

    return {
        "schema": "figure_table_classify_merged_v1",
        "summary": {
            "num_titles": len(titles),
            "num_references": len(references),
            "num_unclassified": len(unclassified_items),
            "comment": "分類結果をchunk単位のAI出力から統合しました。",
        },
        "titles": titles,
        "references": references,
        "unclassified_items": unclassified_items,
    }


# ============================================================
# helpers（AI call）
# ============================================================
def _run_call_text_with_busy(
    *,
    sub: str,
    provider: str,
    model: str,
    system_text: str,
    prompt_text: str,
    feature: str,
    action: str,
    meta: Dict[str, Any],
) -> str:
    # ------------------------------------------------------------
    # busy_run付きで call_text を実行
    # ------------------------------------------------------------
    st.session_state.ai_chart_last_in_tok = None
    st.session_state.ai_chart_last_out_tok = None
    st.session_state.ai_chart_last_cost_obj = None
    st.session_state.ai_chart_last_provider = str(provider)
    st.session_state.ai_chart_last_model = str(model)

    with busy_run(
        projects_root=PROJECTS_ROOT,
        user_sub=str(sub),
        app_name=str(APP_NAME),
        page_name=str(PAGE_NAME),
        task_type="text",
        provider=str(provider),
        model=str(model),
        meta={
            "feature": feature,
            "action": action,
            **meta,
            "prompt_chars": int(len(prompt_text)),
        },
    ) as br:
        res = call_text(
            provider=str(provider),
            model=str(model),
            prompt=str(prompt_text),
            system=str(system_text),
            temperature=None,
            max_output_tokens=int(st.session_state.get("ai_chart_max_output_tokens") or 0),
            extra=None,
        )

        answer_text = (getattr(res, "text", "") or "").strip()

        if not answer_text:
            br.add_finish_meta(note="empty")
            raise RuntimeError("AIの回答が空でした。")

        pp = apply_text_result_to_busy(
            br=br,
            res=res,
            extract_text_in_out_tokens=extract_text_in_out_tokens,
            note_ok="ok",
            note_no_usage="no_usage",
            note_no_cost="no_cost",
        )

        st.session_state.ai_chart_last_in_tok = pp.in_tokens
        st.session_state.ai_chart_last_out_tok = pp.out_tokens
        st.session_state.ai_chart_last_cost_obj = pp.cost_obj
        st.session_state.ai_chart_last_note = str(pp.note or "")

        br.add_finish_meta(note=str(pp.note or "ok"))
        st.session_state.ai_chart_last_run_id = br.run_id

    return answer_text


# ============================================================
# Sidebar（設定）
# ============================================================
with st.sidebar:
    st.header("設定")

    # ------------------------------------------------------------
    # モデル選択
    # ------------------------------------------------------------
    gem_ok = bool(has_gemini_api_key()) and bool(_gemini_available())

    model_key = render_text_model_picker(
        title="🧠 使用モデル",
        catalog=TEXT_MODEL_CATALOG,
        session_key="ai_chart_model_key",
        default_key=DEFAULT_TEXT_MODEL_KEY,
        page_name=PAGE_NAME,
        gemini_available=gem_ok,
    )

    provider, model = _parse_model_key(str(model_key or DEFAULT_TEXT_MODEL_KEY))

    # ------------------------------------------------------------
    # 最大出力トークン
    # ------------------------------------------------------------
    max_output_tokens = st.number_input(
        "最大出力トークン（上限）",
        min_value=1024,
        max_value=30000,
        value=16000,  # ★ここを追加（デフォルト値）
        step=512,
        key="ai_chart_max_output_tokens",
    )

    # ------------------------------------------------------------
    # 抽出オプション
    # ------------------------------------------------------------
    st.divider()
    st.subheader("抽出オプション")

    include_context = st.checkbox(
        "前後文もcontextとして付ける",
        value=True,
    )

    max_sentence_chars = st.slider(
        "1文あたり最大文字数",
        min_value=100,
        max_value=2000,
        value=800,
        step=100,
    )

    max_context_chars = st.slider(
        "前後文context最大文字数",
        min_value=50,
        max_value=1000,
        value=300,
        step=50,
    )

    max_items_to_ai = st.slider(
        "AI分類へ渡す最大抽出文数",
        min_value=20,
        max_value=1000,
        value=1000,
        step=20,
    )

    classify_chunk_size = st.slider(
        "AI分類chunkサイズ",
        min_value=10,
        max_value=100,
        value=50,
        step=10,
    )

    debug_mode = st.checkbox(
        "デバッグ表示",
        value=False,
    )

# ============================================================
# 入力（PDFアップロード）
# ============================================================
uploaded = st.file_uploader(
    "PDF をアップロード",
    type=["pdf"],
)

col_extract, col_classify, col_check = st.columns([1, 1, 1])

with col_extract:
    extract_run = st.button(
        "① 文を抽出",
        type="primary",
    )

with col_classify:
    classify_run = st.button(
        "② AIで分類",
        disabled=not bool(st.session_state.get("ai_chart_items")),
    )

with col_check:
    check_run = st.button(
        "③ 分類結果を照合",
        disabled=not bool(st.session_state.get("ai_chart_classify_result")),
    )

# ============================================================
# ① 文抽出
# ============================================================
if extract_run:
    if uploaded is None:
        st.warning("PDF ファイル（.pdf）をアップロードしてください。")
        st.stop()

    suffix = Path(uploaded.name).suffix.lower()

    if suffix != ".pdf":
        st.error("PDF 以外のファイルがアップロードされました。PDF（.pdf）をドロップしてください。")
        st.stop()

    _clear_after_extract_state()

    pdf_bytes = uploaded.getvalue()

    pdf_kind, page_count = detect_pdf_kind_from_bytes(
        fitz=fitz,
        pdf_bytes=pdf_bytes,
    )

    if pdf_kind == "image":
        st.warning(
            "⚠️ このPDFは画像PDFのため、テキスト抽出できません。"
            " OCR済みPDFまたはテキストPDFをアップロードしてください。"
        )
        st.stop()

    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / "input.pdf"
        pdf_path.write_bytes(pdf_bytes)
        pages_text: List[str] = pdf_to_text_per_page(pdf_path)

    page_labels: List[Optional[str]] = []
    page_rows: List[Dict[str, Any]] = []

    for i, page_text in enumerate(pages_text, start=1):
        label, matched = extract_single_page_label(page_text)
        page_labels.append(label)

        page_rows.append(
            {
                "pdf_page": i,
                "page_label": label,
                "matched_line": matched or "",
                "chars": len(page_text or ""),
            }
        )

    items = extract_figure_table_sentences(
        pages_text=pages_text,
        page_labels=page_labels,
        include_context=bool(include_context),
        max_sentence_chars=int(max_sentence_chars),
        max_context_chars=int(max_context_chars),
    )

    if not items:
        st.warning("「図」または「表」を含む文が見つかりませんでした。")
        st.stop()

    items_for_ai = items[: int(max_items_to_ai)]

    payload = build_ai_input_payload(
        source_file=uploaded.name,
        items=items_for_ai,
    )

    input_json_text = json.dumps(payload, ensure_ascii=False, indent=2)

    st.session_state.ai_chart_source_file = str(uploaded.name)
    st.session_state.ai_chart_items = items_for_ai
    st.session_state.ai_chart_payload = payload
    st.session_state.ai_chart_input_json = input_json_text
    st.session_state.ai_chart_pages_rows = page_rows

    st.success(
        f"抽出完了：PDFページ数 {len(pages_text)} / 抽出文 {len(items)} 件 / AI分類対象 {len(items_for_ai)} 件"
    )

    if len(items) > len(items_for_ai):
        st.warning(
            f"抽出文が {len(items)} 件ありました。AI分類対象は先頭 {len(items_for_ai)} 件に制限しています。"
        )

# ============================================================
# 抽出結果の表示・ダウンロード
# ============================================================
items_saved = st.session_state.get("ai_chart_items") or []
payload_saved = st.session_state.get("ai_chart_payload") or {}
input_json_saved = str(st.session_state.get("ai_chart_input_json") or "")
pages_rows_saved = st.session_state.get("ai_chart_pages_rows") or []
source_file_saved = str(st.session_state.get("ai_chart_source_file") or "")

if items_saved:
    st.divider()
    st.subheader("① 抽出結果")

    df_input_items = pd.DataFrame(items_saved)
    df_pages = pd.DataFrame(pages_rows_saved)

    st.caption("以下がAI分類へ渡す候補文です。まだAIには送信していません。")
    st.dataframe(df_input_items)

    base_for_extract = Path(source_file_saved or "input").stem

    extract_csv_buf = io.StringIO()
    df_input_items.to_csv(extract_csv_buf, index=False)

    page_csv_buf = io.StringIO()
    df_pages.to_csv(page_csv_buf, index=False)

    with st.sidebar:
        st.divider()
        st.subheader("抽出結果DL")

        st.download_button(
            "📄 抽出文CSV",
            data=extract_csv_buf.getvalue().encode("utf-8-sig"),
            file_name=f"AI図表チェック_抽出文_{base_for_extract}.csv",
            mime="text/csv",
        )

        st.download_button(
            "🧾 AI分類入力JSON",
            data=input_json_saved.encode("utf-8"),
            file_name=f"AI図表チェック_classify_input_{base_for_extract}.json",
            mime="application/json",
        )

        st.download_button(
            "📑 ページラベルCSV",
            data=page_csv_buf.getvalue().encode("utf-8-sig"),
            file_name=f"AI図表チェック_ページラベル_{base_for_extract}.csv",
            mime="text/csv",
        )

else:
    st.info("PDFをアップロードして、まず「① 文を抽出」を押してください。")

# ============================================================
# ② AI分類
# ============================================================
if classify_run:
    if not items_saved:
        st.warning("先に「① 文を抽出」を実行してください。")
        st.stop()

    _clear_after_classify_state()

    system_text = build_system_text()
    chunks = _split_items(
        items=items_saved,
        chunk_size=int(classify_chunk_size),
    )

    classify_results: List[Dict[str, Any]] = []
    raw_answers: List[str] = []

    progress = st.progress(0)
    status = st.empty()

    try:
        for idx, chunk_items in enumerate(chunks, start=1):
            status.info(f"AI分類中：chunk {idx} / {len(chunks)}")

            chunk_payload = build_classify_payload(
                source_file=source_file_saved,
                chunk_index=idx,
                chunk_total=len(chunks),
                items=chunk_items,
            )

            prompt_text = build_classify_prompt_text(chunk_payload)

            st.session_state.ai_chart_last_system_text = system_text
            st.session_state.ai_chart_last_prompt_text = prompt_text

            answer_text = _run_call_text_with_busy(
                sub=str(sub),
                provider=str(provider),
                model=str(model),
                system_text=system_text,
                prompt_text=prompt_text,
                feature="ai_figure_table_check",
                action="classify_figure_table_sentences",
                meta={
                    "source_file": source_file_saved,
                    "chunk_index": int(idx),
                    "chunk_total": int(len(chunks)),
                    "chunk_items": int(len(chunk_items)),
                },
            )

            raw_answers.append(answer_text)

            try:
                classify_results.append(extract_json_object(answer_text))
            except Exception as e:
                st.error(f"AI分類応答JSONの解析に失敗しました: {e}")

                with st.expander("AI分類応答（生テキスト）", expanded=True):
                    st.text_area(
                        "AI分類応答",
                        value=answer_text,
                        height=420,
                        key=f"debug_classify_raw_answer_{idx}",
                    )

                st.stop()

            progress.progress(idx / len(chunks))

    except Exception as e:
        st.error(f"AI分類でエラー: {e}")
        st.stop()

    merged = _merge_classify_results(classify_results)

    st.session_state.ai_chart_classify_result = merged
    st.session_state.ai_chart_classify_json = json.dumps(merged, ensure_ascii=False, indent=2)
    st.session_state.ai_chart_classify_answer_text = "\n\n--- chunk ---\n\n".join(raw_answers)

    status.success("AI分類が完了しました。")

# ============================================================
# 分類結果の表示・ダウンロード
# ============================================================
classify_result_saved = st.session_state.get("ai_chart_classify_result") or {}

if isinstance(classify_result_saved, dict) and classify_result_saved:
    st.divider()
    st.subheader("② AI分類結果")

    classify_summary = classify_result_saved.get("summary")
    if not isinstance(classify_summary, dict):
        classify_summary = {}

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("タイトル候補", classify_summary.get("num_titles", 0))

    with c2:
        st.metric("参照候補", classify_summary.get("num_references", 0))

    with c3:
        st.metric("未分類", classify_summary.get("num_unclassified", 0))

    df_titles = df_from_list(classify_result_saved.get("titles"))
    df_refs = df_from_list(classify_result_saved.get("references"))
    df_unclassified = df_from_list(classify_result_saved.get("unclassified_items"))

    tab_c1, tab_c2, tab_c3 = st.tabs(
        [
            "タイトル候補",
            "本文参照候補",
            "未分類",
        ]
    )

    with tab_c1:
        st.dataframe(df_titles)

    with tab_c2:
        st.dataframe(df_refs)

    with tab_c3:
        st.dataframe(df_unclassified)

    base_for_classify = Path(source_file_saved or "input").stem

    titles_csv_buf = io.StringIO()
    df_titles.to_csv(titles_csv_buf, index=False)

    refs_csv_buf = io.StringIO()
    df_refs.to_csv(refs_csv_buf, index=False)

    unclassified_csv_buf = io.StringIO()
    df_unclassified.to_csv(unclassified_csv_buf, index=False)

    classify_json_text = json.dumps(classify_result_saved, ensure_ascii=False, indent=2)

    check_payload_preview = build_check_payload(
        source_file=source_file_saved,
        titles=classify_result_saved.get("titles") if isinstance(classify_result_saved.get("titles"), list) else [],
        references=classify_result_saved.get("references") if isinstance(classify_result_saved.get("references"), list) else [],
        unclassified_items=classify_result_saved.get("unclassified_items") if isinstance(classify_result_saved.get("unclassified_items"), list) else [],
    )

    check_payload_json_text = json.dumps(check_payload_preview, ensure_ascii=False, indent=2)

    with st.sidebar:
        st.divider()
        st.subheader("分類結果DL")

        st.download_button(
            "🧾 分類結果JSON",
            data=classify_json_text.encode("utf-8"),
            file_name=f"AI図表チェック_classify_result_{base_for_classify}.json",
            mime="application/json",
        )

        st.download_button(
            "📄 タイトル候補CSV",
            data=titles_csv_buf.getvalue().encode("utf-8-sig"),
            file_name=f"AI図表チェック_titles_{base_for_classify}.csv",
            mime="text/csv",
            disabled=df_titles.empty,
        )

        st.download_button(
            "📄 参照候補CSV",
            data=refs_csv_buf.getvalue().encode("utf-8-sig"),
            file_name=f"AI図表チェック_refs_{base_for_classify}.csv",
            mime="text/csv",
            disabled=df_refs.empty,
        )

        st.download_button(
            "📄 未分類CSV",
            data=unclassified_csv_buf.getvalue().encode("utf-8-sig"),
            file_name=f"AI図表チェック_unclassified_{base_for_classify}.csv",
            mime="text/csv",
            disabled=df_unclassified.empty,
        )

        st.download_button(
            "🧾 照合入力JSON",
            data=check_payload_json_text.encode("utf-8"),
            file_name=f"AI図表チェック_check_input_{base_for_classify}.json",
            mime="application/json",
        )

# ============================================================
# ③ AI照合
# ============================================================
if check_run:
    if not isinstance(classify_result_saved, dict) or not classify_result_saved:
        st.warning("先に「② AIで分類」を実行してください。")
        st.stop()

    titles_for_check = classify_result_saved.get("titles")
    refs_for_check = classify_result_saved.get("references")
    unclassified_for_check = classify_result_saved.get("unclassified_items")

    if not isinstance(titles_for_check, list):
        titles_for_check = []

    if not isinstance(refs_for_check, list):
        refs_for_check = []

    if not isinstance(unclassified_for_check, list):
        unclassified_for_check = []

    # ------------------------------------------------------------
    # figure_key 正規化
    # ------------------------------------------------------------
    def _norm_figure_key(v: Any) -> str:
        return str(v or "").strip()

    # ------------------------------------------------------------
    # 照合対象キーを作成
    # - タイトル側と参照側の figure_key を統合
    # - 空欄キーは最後にまとめて要確認対象にする
    # ------------------------------------------------------------
    keys: List[str] = []

    for row in titles_for_check:
        if isinstance(row, dict):
            k = _norm_figure_key(row.get("figure_key"))
            if k and k not in keys:
                keys.append(k)

    for row in refs_for_check:
        if isinstance(row, dict):
            raw_key = _norm_figure_key(row.get("figure_key"))

            # ----------------------------------------------------
            # 「表3.1.5-22;図3.1.5-8」のような複数キーを分解
            # ----------------------------------------------------
            parts = [
                p.strip()
                for p in raw_key.replace("；", ";").split(";")
                if p.strip()
            ]

            for k in parts:
                if k and k not in keys:
                    keys.append(k)

    # ------------------------------------------------------------
    # キーを小分けにして照合
    # ------------------------------------------------------------
    key_chunk_size = 20
    key_chunks = [
        keys[i : i + key_chunk_size]
        for i in range(0, len(keys), key_chunk_size)
    ]

    if not key_chunks:
        st.warning("照合対象の figure_key がありません。")
        st.stop()

    system_text = build_system_text()

    all_check_results: List[Dict[str, Any]] = []
    raw_check_answers: List[str] = []

    progress = st.progress(0)
    status = st.empty()

    try:
        for idx, key_chunk in enumerate(key_chunks, start=1):
            status.info(f"AI照合中：chunk {idx} / {len(key_chunks)}")

            # ----------------------------------------------------
            # このchunkに属するタイトルを抽出
            # ----------------------------------------------------
            titles_chunk: List[Dict[str, Any]] = []
            for row in titles_for_check:
                if not isinstance(row, dict):
                    continue

                k = _norm_figure_key(row.get("figure_key"))
                if k in key_chunk:
                    titles_chunk.append(row)

            # ----------------------------------------------------
            # このchunkに属する参照を抽出
            # - 複数キー ; 区切りにも対応
            # ----------------------------------------------------
            refs_chunk: List[Dict[str, Any]] = []
            for row in refs_for_check:
                if not isinstance(row, dict):
                    continue

                raw_key = _norm_figure_key(row.get("figure_key"))
                parts = [
                    p.strip()
                    for p in raw_key.replace("；", ";").split(";")
                    if p.strip()
                ]

                if any(k in key_chunk for k in parts):
                    refs_chunk.append(row)

            # ----------------------------------------------------
            # 空figure_keyの未分類・参照は全chunkに入れない
            # - 入力肥大化を防ぐため、最後のchunkだけに入れる
            # ----------------------------------------------------
            unclassified_chunk: List[Dict[str, Any]] = []
            if idx == len(key_chunks):
                unclassified_chunk = unclassified_for_check

                for row in refs_for_check:
                    if not isinstance(row, dict):
                        continue

                    if not _norm_figure_key(row.get("figure_key")):
                        unclassified_chunk.append(
                            {
                                "source_item_id": row.get("source_item_id", ""),
                                "pdf_page": row.get("pdf_page", ""),
                                "page_label": row.get("page_label", ""),
                                "text": row.get("reference_text", ""),
                                "reason": "figure_key が空の参照候補",
                            }
                        )

            check_payload = build_check_payload(
                source_file=source_file_saved,
                titles=titles_chunk,
                references=refs_chunk,
                unclassified_items=unclassified_chunk,
            )

            prompt_text = build_check_prompt_text(check_payload)

            st.session_state.ai_chart_last_system_text = system_text
            st.session_state.ai_chart_last_prompt_text = prompt_text

            with st.spinner(f"AIが分類結果を照合中... chunk {idx} / {len(key_chunks)}"):
                answer_text = _run_call_text_with_busy(
                    sub=str(sub),
                    provider=str(provider),
                    model=str(model),
                    system_text=system_text,
                    prompt_text=prompt_text,
                    feature="ai_figure_table_check",
                    action="check_classified_figure_table_items_chunked",
                    meta={
                        "source_file": source_file_saved,
                        "chunk_index": int(idx),
                        "chunk_total": int(len(key_chunks)),
                        "keys": int(len(key_chunk)),
                        "titles": int(len(titles_chunk)),
                        "references": int(len(refs_chunk)),
                        "unclassified": int(len(unclassified_chunk)),
                    },
                )

            raw_check_answers.append(answer_text)

            try:
                one_result = extract_json_object(answer_text)
            except Exception as e:
                st.error(f"AI照合応答JSONの解析に失敗しました: {e}")

                with st.expander("AI照合応答（生テキスト）", expanded=True):
                    st.text_area(
                        "AI照合応答",
                        value=answer_text,
                        height=420,
                        key=f"debug_check_raw_answer_{idx}",
                    )

                st.stop()

            all_check_results.append(one_result)
            progress.progress(idx / len(key_chunks))

    except Exception as e:
        st.error(f"AI照合でエラー: {e}")
        st.stop()

    # ------------------------------------------------------------
    # 分割照合結果を統合
    # ------------------------------------------------------------
    merged_checks: List[Dict[str, Any]] = []

    for r in all_check_results:
        if not isinstance(r, dict):
            continue

        checks = r.get("checks")
        if isinstance(checks, list):
            merged_checks.extend([c for c in checks if isinstance(c, dict)])

    num_matches = 0
    num_warnings = 0

    for c in merged_checks:
        judgment = str(c.get("judgment") or "").strip()
        severity = str(c.get("severity") or "").strip()

        if judgment == "一致":
            num_matches += 1

        if severity != "OK":
            num_warnings += 1

    check_result = {
        "schema": "figure_table_reference_check_output_v1",
        "summary": {
            "num_titles": len(titles_for_check),
            "num_references": len(refs_for_check),
            "num_matches": num_matches,
            "num_warnings": num_warnings,
            "overall_comment": "figure_key単位で分割照合し、結果を統合しました。",
        },
        "checks": merged_checks,
    }

    st.session_state.ai_chart_check_result = check_result
    st.session_state.ai_chart_check_json = json.dumps(check_result, ensure_ascii=False, indent=2)
    st.session_state.ai_chart_check_answer_text = "\n\n--- chunk ---\n\n".join(raw_check_answers)

    status.success("AI照合が完了しました。")

# ============================================================
# 照合結果表示
# ============================================================
check_result_saved = st.session_state.get("ai_chart_check_result") or {}

if isinstance(check_result_saved, dict) and check_result_saved:
    st.divider()
    st.subheader("③ AI照合結果")

    summary_obj = check_result_saved.get("summary")
    if not isinstance(summary_obj, dict):
        summary_obj = {}

    s1, s2, s3, s4 = st.columns(4)

    with s1:
        st.metric("タイトル数", summary_obj.get("num_titles", 0))

    with s2:
        st.metric("参照数", summary_obj.get("num_references", 0))

    with s3:
        st.metric("一致数", summary_obj.get("num_matches", 0))

    with s4:
        st.metric("警告数", summary_obj.get("num_warnings", 0))

    overall_comment = str(summary_obj.get("overall_comment") or "").strip()

    if overall_comment:
        st.info(overall_comment)

    df_checks = checks_to_df(check_result_saved.get("checks"))
    df_titles_final = df_from_list(classify_result_saved.get("titles"))
    df_refs_final = df_from_list(classify_result_saved.get("references"))
    df_unclassified_final = df_from_list(classify_result_saved.get("unclassified_items"))

    st.subheader("🔎 照合テーブル")

    if df_checks.empty:
        st.warning("照合結果 checks が空です。")
    else:
        st.dataframe(df_checks)

    base = Path(source_file_saved or "input").stem

    xlsx_bytes = make_xlsx_bytes(
        df_input_items=pd.DataFrame(items_saved),
        df_checks=df_checks,
        df_titles=df_titles_final,
        df_refs=df_refs_final,
        df_unclassified=df_unclassified_final,
        summary_obj=summary_obj,
    )

    result_json_text = json.dumps(check_result_saved, ensure_ascii=False, indent=2)

    csv_buf = io.StringIO()
    df_checks.to_csv(csv_buf, index=False)

    with st.sidebar:
        st.divider()
        st.subheader("照合結果DL")

        st.download_button(
            "📘 AI照合結果（xlsx）",
            data=xlsx_bytes,
            file_name=f"AI図表チェック_{base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.download_button(
            "📄 AI照合結果（csv）",
            data=csv_buf.getvalue().encode("utf-8-sig"),
            file_name=f"AI図表チェック_{base}.csv",
            mime="text/csv",
            disabled=df_checks.empty,
        )

        st.download_button(
            "🧾 AI照合結果JSON",
            data=result_json_text.encode("utf-8"),
            file_name=f"AI図表チェック_check_result_{base}.json",
            mime="application/json",
        )

# ============================================================
# 直近実行サマリ
# ============================================================
last_run_id = str(st.session_state.get("ai_chart_last_run_id") or "").strip()
last_model = str(st.session_state.get("ai_chart_last_model") or "").strip()

in_tok = st.session_state.get("ai_chart_last_in_tok")
out_tok = st.session_state.get("ai_chart_last_out_tok")
cost_obj = st.session_state.get("ai_chart_last_cost_obj")
note = str(st.session_state.get("ai_chart_last_note") or "")

if last_run_id:
    render_run_summary_compact(
        projects_root=PROJECTS_ROOT,
        run_id=last_run_id,
        model=last_model,
        in_tokens=(int(in_tok) if isinstance(in_tok, int) else None),
        out_tokens=(int(out_tok) if isinstance(out_tok, int) else None),
        cost=cost_obj,
        note=note,
        show_divider=True,
    )

# ============================================================
# デバッグ
# ============================================================
if debug_mode:
    st.divider()
    st.subheader("🧪 Debug")

    with st.expander("ページラベル", expanded=False):
        st.dataframe(pd.DataFrame(st.session_state.get("ai_chart_pages_rows") or []))

    with st.expander("AI分類入力JSON", expanded=False):
        st.text_area(
            "AI分類入力JSON",
            value=str(st.session_state.get("ai_chart_input_json") or ""),
            height=360,
            key="debug_ai_input_json",
        )

    with st.expander("AI分類結果JSON", expanded=False):
        st.text_area(
            "AI分類結果JSON",
            value=str(st.session_state.get("ai_chart_classify_json") or ""),
            height=360,
            key="debug_ai_classify_json",
        )

    with st.expander("AI照合結果JSON", expanded=False):
        st.text_area(
            "AI照合結果JSON",
            value=str(st.session_state.get("ai_chart_check_json") or ""),
            height=360,
            key="debug_ai_check_json",
        )

    with st.expander("最後にAIへ送ったSYSTEM / PROMPT", expanded=False):
        full_prompt_debug = (
            "=== SYSTEM ===\n"
            + str(st.session_state.get("ai_chart_last_system_text") or "")
            + "\n\n=== PROMPT ===\n"
            + str(st.session_state.get("ai_chart_last_prompt_text") or "")
        )

        st.text_area(
            "SYSTEM / PROMPT",
            value=full_prompt_debug,
            height=360,
            key="debug_full_prompt",
        )