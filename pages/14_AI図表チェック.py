# -*- coding: utf-8 -*-
# text_studio_app/pages/14_AI図表チェック.py
# ============================================================
# 🧠 AI図表チェック（AI用サマリーJSONL → 意味照合）
#
# 機能：
# - 09_図表チェック.py が出力した AI用サマリーJSONL を入力する
# - 「図表タイトル」「前テキスト」「参照テキスト」「後テキスト」をAIに送る
# - 図表キーの参照が意味的に正しいかをAIで判定する
# - JSONLをchunkに分けて順次AI送信する
# - 進捗を (1/5), (2/5) のように表示する
# - 結果を画面表示し、xlsxでダウンロードする
#
# 方針：
# - AIには抽出をさせない
# - 09_図表チェック.py のAI用JSONLを正本入力にする
# - 1引用 = 1行 = 1判定
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
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ============================================================
# imports（3rd party）
# ============================================================
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
# 入力方式
# ============================================================
INPUT_FILE = "📁 ファイルから"
INPUT_INBOX = "📥 Inboxから"
INPUT_INTERNAL = "💾 内部保存から"
INBOX_PAGE_SIZE = 8

# ============================================================
# common_lib（ログイン / UI / AI / busy）
# ============================================================
from common_lib.ui.page_header import render_standard_page_header
from common_lib.ui import render_run_summary_compact
from common_lib.ui.model_picker import render_text_model_picker
from common_lib.ai.models import TEXT_MODEL_CATALOG, DEFAULT_TEXT_MODEL_KEY

from common_lib.inbox.inbox_ui.file_picker import render_inbox_file_picker_no_toggle
from common_lib.inbox.inbox_ui.file_picker import InboxPickedFile

# ============================================================
# app config
# ============================================================
from config.config import has_gemini_api_key

# ============================================================
# lib（AI参照チェック）
# ============================================================
from lib.ai_reference_check.jsonl_io import (
    load_ai_summary_jsonl_bytes,
    df_to_ai_records,
)
from lib.ai_reference_check.chunking import split_records_by_count
from lib.ai_reference_check.prompt import (
    build_reference_check_system_text,
    build_reference_check_payload,
    build_reference_check_prompt_text,
)
from lib.ai_reference_check.parse import (
    extract_json_object,
    checks_from_result_objects,
    checks_to_df,
    merge_input_and_checks,
    make_reference_check_xlsx_bytes,
)

from lib.ai_reference_check.job_store import (
    is_jsonl_like_file,
    get_chart_check_root,
    read_manifest,
    resolve_current_job_dir,
    list_saved_ai_summary_jsonl_files,
)

from lib.ai_reference_check.session_state import (
    ensure_ai_reference_check_state,
    clear_ai_reference_loaded_state,
    clear_ai_reference_result_state,
)

from lib.ai_reference_check.input_state import (
    set_ai_reference_input_candidate,
    clear_ai_reference_input_candidate,
    update_ai_reference_input_candidate_if_changed,
)

from lib.ai_reference_check.input_validation import (
    stop_if_invalid_jsonl_input,
)

from lib.ai_reference_check.ai_runner import (
    run_reference_check_call_text_with_busy,
)

from lib.ai_reference_check.explanation import (
    render_ai_reference_check_intro,
    render_ai_reference_check_help_expander,
)

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="🧠 AI図表チェック",
    page_icon="🧠",
    layout="wide",
)

# ============================================================
# 共通ヘッダー
# - settings.toml から BANNER_KEY を取得
# - banner / theme / intro CSS を描画
# - page_session_heartbeat を実行
# - title / subtitle / ログイン状態を描画
# ============================================================
sub, theme, BANNER_KEY, settings = render_standard_page_header(
    st_module=st,
    projects_root=PROJECTS_ROOT,
    app_dir=APP_DIR,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
    title="🧠 AI図表チェック",
    subtitle_text="AI用サマリーJSONL → AIによる図表参照のチェック",
    default_banner_key="purple_light",
)



# ============================================================
# ページ説明
# ============================================================
render_ai_reference_check_intro()

# ============================================================
# ヘルプ
# ============================================================
render_ai_reference_check_help_expander(
    theme=theme,
)

# ============================================================
# Session state
# ============================================================
ensure_ai_reference_check_state()

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
# helpers（DataFrame表示）
# ============================================================
def _arrow_safe_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
    # ------------------------------------------------------------
    # Arrow警告回避
    # 頁番号系の列に int と "" が混在するため、表示時だけ文字列化する
    # ------------------------------------------------------------
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    out = df.copy()

    for col in ["pdf頁", "参照pdf頁", "pdf_page", "参照pdf_page"]:
        if col in out.columns:
            out[col] = out[col].astype(str)

    return out



# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# サイドバー
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
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
        session_key="ai_ref_model_key",
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
        step=512,
        key="ai_ref_max_output_tokens",
    )

    # ------------------------------------------------------------
    # AI送信設定
    # ------------------------------------------------------------
    st.divider()
    st.subheader("AI送信設定")

    chunk_size = st.number_input(
        "1回に送る最大件数",
        min_value=1,
        max_value=100,
        value=20,
        step=1,
    )

    max_records_to_ai = st.number_input(
        "AIへ送る最大行数",
        min_value=1,
        max_value=10000,
        value=10000,
        step=100,
    )

    debug_mode = st.checkbox(
        "デバッグ表示",
        value=False,
    )

# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　メイン処理　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪

# ============================================================
# 解析ファイル設定
# ============================================================
st.subheader("① JSONLファイルの設定")
# ============================================================
# 入力（ファイル / Inbox / 内部保存）
# ============================================================
picked_method = st.radio(
    "入力方法(AI用サマリーJSONLを選択してください．)",
    [INPUT_FILE, INPUT_INBOX, INPUT_INTERNAL],
    index=2,
    key="ai_ref_input_method",
    horizontal=True,
)

# ------------------------------------------------------------
# ① ファイルから
# ------------------------------------------------------------
if picked_method == INPUT_FILE:
    uploaded = st.file_uploader(
        "09_図表チェック.py で作成した AI用サマリーJSONL をアップロード",
        type=["jsonl", "json"],
        key=f"{PAGE_NAME}__jsonl_uploader",
    )

    if uploaded is not None:
        data_bytes = uploaded.getvalue()
        filename = uploaded.name or "input.jsonl"
        sig = f"file:{filename}:{len(data_bytes)}"

        stop_if_invalid_jsonl_input(
            filename=filename,
            data_bytes=data_bytes,
            invalid_message="JSONL / JSON ファイルのみ使用できます。",
            empty_message="ファイルの読み込みに失敗しました（0バイト）。もう一度選択してください。",
        )

        update_ai_reference_input_candidate_if_changed(
            data_bytes=data_bytes,
            filename=filename,
            sig=sig,
        )

        st.success(f"入力候補を読み込みました：{filename}")

# ------------------------------------------------------------
# ② Inboxから
# ------------------------------------------------------------
elif picked_method == INPUT_INBOX:
    picked: InboxPickedFile | None = render_inbox_file_picker_no_toggle(
        projects_root=PROJECTS_ROOT,
        user_sub=str(sub),
        key_prefix=f"{PAGE_NAME}_ai_ref_inbox_picker",
        page_size=INBOX_PAGE_SIZE,
        kinds=["text"],
        show_kind_in_label=True,
        show_added_at_in_label=True,
    )

    if picked is not None:
        data_bytes = picked.data_bytes or b""
        filename = picked.original_name or "inbox_input.jsonl"
        item_id = str(picked.item_id or "")
        sig = f"inbox:{item_id}:{filename}:{len(data_bytes)}"

        st.session_state.ai_ref_inbox_bytes = data_bytes
        st.session_state.ai_ref_inbox_name = filename
        st.session_state.ai_ref_inbox_item_id = item_id

        stop_if_invalid_jsonl_input(
            filename=filename,
            data_bytes=data_bytes,
            invalid_message="Inboxから読み込めるのは .jsonl / .json のみです。",
            empty_message="Inboxファイルが空です。別のファイルを選択してください。",
        )

        update_ai_reference_input_candidate_if_changed(
            data_bytes=data_bytes,
            filename=filename,
            sig=sig,
        )

        st.success(f"Inboxから入力候補を読み込みました：{filename}")

# ------------------------------------------------------------
# ③ 内部保存から
# ------------------------------------------------------------
else:
    chart_check_root = get_chart_check_root(
        projects_root=PROJECTS_ROOT,
        user_sub=str(sub),
    )

    current_job_dir = resolve_current_job_dir(
        root_dir=chart_check_root,
    )

    saved_rows = list_saved_ai_summary_jsonl_files(
        job_dir=current_job_dir,
    )

    if current_job_dir is not None:
        manifest = read_manifest(job_dir=current_job_dir)
        source_filename = str(manifest.get("source_filename") or "")
        created_at = str(manifest.get("created_at") or "")

        st.caption(
            f"現在の job: {current_job_dir.name}"
            f"{' / 元PDF: ' + source_filename if source_filename else ''}"
            f"{' / 作成日時: ' + created_at if created_at else ''}"
        )

    if not saved_rows:
        st.info("内部保存されたAI用サマリーJSONLはありません。まず 09_図表チェック.py で作成・保存してください。")
    else:
        label_to_row = {row["label"]: row for row in saved_rows}
        radio_labels = list(label_to_row.keys())

        selected_label = st.radio(
            "内部保存されたAI用サマリーJSONLを選択",
            options=radio_labels,
            key=f"{PAGE_NAME}__internal_jsonl_radio",
        )

        selected_row = label_to_row.get(selected_label)

        if selected_row is not None:
            path = selected_row["path"]
            filename = str(selected_row["filename"])

            data_bytes = path.read_bytes()
            sig = f"internal:{path}:{len(data_bytes)}"

            stop_if_invalid_jsonl_input(
                filename=filename,
                data_bytes=data_bytes,
                invalid_message="内部保存から読み込めるのは .jsonl / .json のみです。",
                empty_message="内部保存ファイルが空です。",
            )

            update_ai_reference_input_candidate_if_changed(
                data_bytes=data_bytes,
                filename=filename,
                sig=sig,
            )

            st.success(f"内部保存から入力候補を読み込みました：{filename}")



# ============================================================
# 入力確定 / AI実行ボタン
# ============================================================

input_name = str(st.session_state.get("ai_ref_input_name") or "")
input_bytes = st.session_state.get("ai_ref_input_bytes") or b""

if input_name:
    st.caption(f"現在の入力候補: {input_name} / {len(input_bytes):,} bytes")

# ------------------------------------------------------------
# JSONL読み込みボタン
# ------------------------------------------------------------
load_run = st.button(
    "JSONLファイルを読み込む",
    type="primary",
    disabled=not bool(input_bytes),
)

# ============================================================
# ① JSONL読み込み
# ============================================================
if load_run:
    input_name = str(st.session_state.get("ai_ref_input_name") or "")
    input_bytes = st.session_state.get("ai_ref_input_bytes") or b""

    stop_if_invalid_jsonl_input(
        filename=input_name,
        data_bytes=input_bytes,
        invalid_message="JSONL / JSON ファイルのみ使用できます。",
        empty_message="AI用サマリーJSONLを選択してください。",
    )

    clear_ai_reference_loaded_state()

    df_input, errors = load_ai_summary_jsonl_bytes(data=input_bytes)

    if errors:
        st.error("JSONLの読み込み・検証で問題がありました。")
        for e in errors:
            st.write(f"- {e}")

        if df_input.empty:
            st.stop()

    if df_input.empty:
        st.warning("JSONLから有効なデータを読み込めませんでした。")
        st.stop()

    records = df_to_ai_records(df=df_input)

    if not records:
        st.warning("AI判定対象のrecordsを作成できませんでした。")
        st.stop()

    records = records[: int(max_records_to_ai)]

    st.session_state.ai_ref_source_file = input_name
    st.session_state.ai_ref_input_df = df_input.iloc[: len(records)].copy()
    st.session_state.ai_ref_records = records

    st.success(
        f"JSONL読み込み完了：{len(df_input)} 行 / AI判定対象 {len(records)} 行"
    )

    st.rerun()

    if len(df_input) > len(records):
        st.warning(
            f"入力行が {len(df_input)} 行あります。AI判定対象は先頭 {len(records)} 行に制限しています。"
        )

# ============================================================
# 入力データ表示
# ============================================================
df_input_saved = st.session_state.get("ai_ref_input_df")
records_saved = st.session_state.get("ai_ref_records") or []
source_file_saved = str(st.session_state.get("ai_ref_source_file") or "")

if isinstance(df_input_saved, pd.DataFrame) and not df_input_saved.empty:
    st.divider()
    st.markdown("#### 入力データ")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("入力行数", len(df_input_saved))

    with c2:
        st.metric("AI判定対象", len(records_saved))

    with c3:
        st.metric("入力ファイル", source_file_saved or "-")

    st.caption("AI用サマリーJSONLを読み込んだ結果です。1行が1つの図表参照判定対象です。")

    # ------------------------------------------------------------
    # Arrow警告回避
    # pdf頁 に int と "" が混在するため文字列化する
    # ------------------------------------------------------------
    st.dataframe(
        _arrow_safe_df_for_display(df_input_saved)
    )

else:
    st.info("まずAI用サマリーJSONLをアップロードして、「① JSONLを読み込む」を押してください。")

# ============================================================
# AI判定ボタン
# - 入力データ一覧の下に表示
# ============================================================
st.divider()
st.subheader("② AIで図表参照チェック")
run_ai = st.button(
    "AIで図表チェック",
    disabled=not bool(st.session_state.get("ai_ref_records")),
)
# ============================================================
# ② AI判定
# ============================================================
if run_ai:
    if not records_saved:
        st.warning("先に「① JSONLを読み込む」を実行してください。")
        st.stop()

    clear_ai_reference_result_state()

    system_text = build_reference_check_system_text()

    chunks = split_records_by_count(
        records=records_saved,
        chunk_size=int(chunk_size),
    )

    if not chunks:
        st.warning("AIへ送るデータがありません。")
        st.stop()

    result_objects: List[Dict[str, Any]] = []
    raw_answers: List[str] = []
    usage_rows: List[Dict[str, Any]] = []

    progress = st.progress(0)
    status = st.empty()

    try:
        for idx, chunk_records in enumerate(chunks, start=1):
            status.info(f"AI判定中：{idx}/{len(chunks)}")

            payload = build_reference_check_payload(
                source_file=source_file_saved,
                chunk_index=idx,
                chunk_total=len(chunks),
                records=chunk_records,
            )

            prompt_text = build_reference_check_prompt_text(payload)

            st.session_state.ai_ref_last_system_text = system_text
            st.session_state.ai_ref_last_prompt_text = prompt_text

            with st.spinner(f"AIが図表参照を判定中... {idx}/{len(chunks)}"):

                answer_text, usage_row = run_reference_check_call_text_with_busy(
                    projects_root=PROJECTS_ROOT,
                    user_sub=str(sub),
                    app_name=str(APP_NAME),
                    page_name=str(PAGE_NAME),
                    provider=str(provider),
                    model=str(model),
                    system_text=system_text,
                    prompt_text=prompt_text,
                    max_output_tokens=int(st.session_state.get("ai_ref_max_output_tokens") or 0),
                    feature="ai_reference_check",
                    action="judge_figure_table_reference_context",
                    meta={
                        "source_file": source_file_saved,
                        "chunk_index": int(idx),
                        "chunk_total": int(len(chunks)),
                        "chunk_records": int(len(chunk_records)),
                    },
                )

            raw_answers.append(answer_text)
            usage_row["chunk_index"] = int(idx)
            usage_row["chunk_total"] = int(len(chunks))
            usage_row["records"] = int(len(chunk_records))
            usage_rows.append(usage_row)

            try:
                one_result = extract_json_object(answer_text)
            except Exception as e:
                st.error(f"AI応答JSONの解析に失敗しました: {e}")

                with st.expander("AI応答（生テキスト）", expanded=True):
                    st.text_area(
                        "AI応答",
                        value=answer_text,
                        height=420,
                        key=f"debug_ai_ref_raw_answer_{idx}",
                    )

                st.stop()

            # ----------------------------------------------------
            # chunk_index を各checkに補完
            # ----------------------------------------------------
            checks = one_result.get("checks")
            if isinstance(checks, list):
                for c in checks:
                    if isinstance(c, dict):
                        c["chunk_index"] = int(idx)

            result_objects.append(one_result)
            progress.progress(idx / len(chunks))

    except Exception as e:
        st.error(f"AI判定でエラー: {e}")
        st.stop()

    checks = checks_from_result_objects(result_objects=result_objects)
    df_checks = checks_to_df(checks=checks)

    df_result = merge_input_and_checks(
        df_input=st.session_state.ai_ref_input_df,
        df_checks=df_checks,
    )

    xlsx_bytes = make_reference_check_xlsx_bytes(
        df_result=df_result,
        df_input=st.session_state.ai_ref_input_df,
        df_checks=df_checks,
        usage_rows=usage_rows,
    )

    st.session_state.ai_ref_result_objects = result_objects
    st.session_state.ai_ref_raw_answers = raw_answers
    st.session_state.ai_ref_checks_df = df_checks
    st.session_state.ai_ref_result_df = df_result
    st.session_state.ai_ref_xlsx_bytes = xlsx_bytes
    st.session_state.ai_ref_usage_rows = usage_rows

    status.success("AI判定が完了しました。")

# ============================================================
# AI判定結果表示
# ============================================================
df_result_saved = st.session_state.get("ai_ref_result_df")
df_checks_saved = st.session_state.get("ai_ref_checks_df")
xlsx_bytes_saved = st.session_state.get("ai_ref_xlsx_bytes") or b""
usage_rows_saved = st.session_state.get("ai_ref_usage_rows") or []

if isinstance(df_result_saved, pd.DataFrame) and not df_result_saved.empty:
    st.divider()
    st.subheader("② AI図表参照判定結果")

    judgment_col = "AI判定"

    num_all = len(df_result_saved)
    num_ok = 0
    num_check = 0
    num_ng = 0
    num_skip = 0

    if judgment_col in df_result_saved.columns:
        num_ok = int((df_result_saved[judgment_col] == "OK").sum())
        num_check = int((df_result_saved[judgment_col] == "CHECK").sum())
        num_ng = int((df_result_saved[judgment_col] == "NG").sum())
        num_skip = int((df_result_saved[judgment_col] == "SKIP").sum())

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric("全件", num_all)

    with c2:
        st.metric("OK", num_ok)

    with c3:
        st.metric("CHECK", num_check)

    with c4:
        st.metric("NG", num_ng)

    with c5:
        st.metric("SKIP", num_skip)

    tab1, tab2, tab3 = st.tabs(
        [
            "判定結果",
            "要確認（CHECK/NG）",
            "usage",
        ]
    )

    with tab1:
        # ------------------------------------------------------------
        # Arrow警告回避
        # pdf頁 / 参照pdf頁 に int と "" が混在するため文字列化する
        # ------------------------------------------------------------
        st.dataframe(
            _arrow_safe_df_for_display(df_result_saved)
        )
    with tab2:
        if "AI判定" in df_result_saved.columns:
            df_review = df_result_saved[df_result_saved["AI判定"].isin(["CHECK", "NG"])].copy()
        else:
            df_review = pd.DataFrame()

        if df_review.empty:
            st.success("CHECK / NG はありません。")
        else:
            # ------------------------------------------------------------
            # Arrow警告回避
            # pdf頁 / 参照pdf頁 に int と "" が混在するため文字列化する
            # ------------------------------------------------------------
            st.dataframe(
                _arrow_safe_df_for_display(df_review)
            )

    with tab3:
        st.dataframe(pd.DataFrame(usage_rows_saved))

    base = Path(source_file_saved or "input").stem

    csv_buf = io.StringIO()
    df_result_saved.to_csv(csv_buf, index=False)

    result_json_text = json.dumps(
        st.session_state.get("ai_ref_result_objects") or [],
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    with st.sidebar:
        st.divider()
        st.subheader("結果DL")

        st.download_button(
            "📘 AI図表チェック結果（xlsx）",
            data=xlsx_bytes_saved,
            file_name=f"AI図表チェック_{base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.download_button(
            "📄 AI図表チェック結果（csv）",
            data=csv_buf.getvalue().encode("utf-8-sig"),
            file_name=f"AI図表チェック_{base}.csv",
            mime="text/csv",
        )

        st.download_button(
            "🧾 AI図表チェック結果JSON",
            data=result_json_text.encode("utf-8"),
            file_name=f"AI図表チェック_{base}.json",
            mime="application/json",
        )

# ============================================================
# 直近実行サマリ
# ============================================================
last_run_id = str(st.session_state.get("ai_ref_last_run_id") or "").strip()
last_model = str(st.session_state.get("ai_ref_last_model") or "").strip()

in_tok = st.session_state.get("ai_ref_last_in_tok")
out_tok = st.session_state.get("ai_ref_last_out_tok")
cost_obj = st.session_state.get("ai_ref_last_cost_obj")
note = str(st.session_state.get("ai_ref_last_note") or "")

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

    with st.expander("最後にAIへ送ったSYSTEM / PROMPT", expanded=False):
        full_prompt_debug = (
            "=== SYSTEM ===\n"
            + str(st.session_state.get("ai_ref_last_system_text") or "")
            + "\n\n=== PROMPT ===\n"
            + str(st.session_state.get("ai_ref_last_prompt_text") or "")
        )

        st.text_area(
            "SYSTEM / PROMPT",
            value=full_prompt_debug,
            height=420,
            key="debug_ai_ref_full_prompt",
        )

    with st.expander("AI応答 raw", expanded=False):
        raw_answers = st.session_state.get("ai_ref_raw_answers") or []
        st.text_area(
            "AI応答 raw",
            value="\n\n--- chunk ---\n\n".join([str(x) for x in raw_answers]),
            height=420,
            key="debug_ai_ref_raw_answers",
        )

    with st.expander("AI checks df", expanded=False):
        if isinstance(df_checks_saved, pd.DataFrame):
            st.dataframe(
                _arrow_safe_df_for_display(df_checks_saved)
            )
        else:
            st.write(df_checks_saved)