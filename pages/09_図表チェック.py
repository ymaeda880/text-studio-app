# -*- coding: utf-8 -*-
# text_studio_app/pages/09_図表チェック.py
# ============================================================
# 🖼️ 図表の参照照合チェック（ローカル照合 / 非AI）
#
# ✅ 非AIテンプレ準拠：
# - render_standard_page_header でログイン/heartbeat
# - AI は一切使わない（ローカル照合のみ）
# - busy_run / 実行時間測定は行わない（AIページ専用）
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
import io
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import List
from collections import defaultdict

# ============================================================
# imports（3rd party）
# ============================================================
import fitz
import pandas as pd
import streamlit as st

# ============================================================
# sys.path（テンプレ準拠：common_lib を import できるように）
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
# common_lib（正本：ログイン/heartbeat + UI）
# ============================================================
from common_lib.pdf_tools.text_extract.detect import detect_pdf_kind_from_bytes
from common_lib.ui.page_header import render_standard_page_header
from common_lib.ui.input_source import render_input_source

# ============================================================
# lib（説明UI）
# ============================================================
from lib.chart_check.explanation import (
    render_chart_check_page_intro,
    render_chart_check_help_expander,
)

# ============================================================
# lib（図表チェック：ローカル照合）
# ============================================================
from lib.toc_check.toc_segments import (
    pdf_to_text_per_page,
    extract_single_page_label,
)

from lib.chart_check.extractors import (
    EXTRACT_RE,
    judge_hits_in_page,
)

from lib.chart_check.helpers import (
    base_key,
    index_pages_by_key,
    ref_aggregate_for_view,
    caption_info_first_by_key,
    aggregate_ref_info,
    make_crosscheck_rows,
    protect_for_excel_csv,
    protect_for_excel_xlsx,
    is_continuation_group,
    series_and_index,
    first_caption_row,
)

from lib.chart_check.summary_export import build_summary_xlsx_bytes

from lib.chart_check.ai_summary import (
    build_ai_summary_xlsx_bytes,
    build_ai_summary_jsonl_bytes,
)

from lib.chart_check.job_store import save_ai_summary_jsonl_job

# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　ヘッダー　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪

# ============================================================
# ページ設定（必須・統一）
# ============================================================
st.set_page_config(
    page_title="Text Studio",
    page_icon="🖼️",
    layout="wide",
)

# ============================================================
# 共通ヘッダー
# - settings.toml から BANNER_KEY を取得
# - banner / theme / login を描画
# - page_session_heartbeat を実行
# - title / subtitle / ログイン状態を描画
# ============================================================
sub, theme, BANNER_KEY, settings = render_standard_page_header(
    st_module=st,
    projects_root=PROJECTS_ROOT,
    app_dir=APP_DIR,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
    title="🖼️ 図表チェック",
    subtitle_text="パターンマッチングによる図表参照チェック",
    default_banner_key="navy_dark",
)

# ============================================================
# ページ説明
# ============================================================
render_chart_check_page_intro()

# ============================================================
# ヘルプ
# ============================================================
render_chart_check_help_expander(
    theme=theme,
)


# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪
# ============================================================
# ＜＜＜＜＜＜　前処理　
# ============================================================
# 🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪🟪


# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# 定数　／　session_state
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩

# ============================================================
# ダウンロード結果の保持（download_button 再実行対策）
# ============================================================
DL_STATE_KEY = f"{PAGE_NAME}__chart_check_downloads"


# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# helper関数（Streamlit UI）
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩

# ============================================================
# helper：保存済みダウンロードをサイドバーへ描画
# ============================================================
def _render_saved_downloads_sidebar() -> None:
    # ------------------------------------------------------------
    # download_button の再実行対策として session_state に保存した
    # bytes をサイドバーに再描画する
    # ------------------------------------------------------------
    saved = st.session_state.get(DL_STATE_KEY)
    if not saved:
        return

    with st.sidebar:
        st.markdown("### AI入力用サマリーダウンロード")

        if saved.get("ai_summary_xlsx_bytes"):
            st.download_button(
                "📙 AI用サマリーをダウンロード",
                data=saved["ai_summary_xlsx_bytes"],
                file_name=saved["ai_summary_xlsx_filename"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        if saved.get("ai_summary_jsonl_bytes"):
            st.download_button(
                "📄 AI用サマリーJSONLをダウンロード",
                data=saved["ai_summary_jsonl_bytes"],
                file_name=saved["ai_summary_jsonl_filename"],
                mime="application/jsonl",
            )

        st.markdown("### CSV ダウンロード")

        for item in saved.get("csv_items", []):
            st.download_button(
                item["label"],
                data=item["data"],
                file_name=item["file_name"],
                mime="text/csv",
            )


# ============================================================
# helper：保存済みの主要結果をメイン画面へ描画
# ============================================================
def _render_saved_result_downloads_main() -> None:
    # ------------------------------------------------------------
    # 主要結果だけをメイン画面下部に表示する
    # ------------------------------------------------------------
    saved = st.session_state.get(DL_STATE_KEY)
    if not saved:
        return

    st.subheader("③ 結果をダウンロード")

    if saved.get("summary_xlsx_bytes"):
        st.download_button(
            "📗 サマリーをダウンロード",
            data=saved["summary_xlsx_bytes"],
            file_name=saved["summary_xlsx_filename"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if saved.get("xlsx_bytes"):
        st.download_button(
            "📘 突き合わせ結果をダウンロード",
            data=saved["xlsx_bytes"],
            file_name=saved["xlsx_filename"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩
# ============================================================
# サイドバー
# ============================================================
# 🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩

# ============================================================
# Sidebar（オプション）
# ============================================================
with st.sidebar:
    st.markdown("### オプション")

    ctx_chars = st.slider(
        "参照の前後コンテキスト文字数",
        10,
        300,
        60,
        5,
    )

    ai_prev_text_max_chars = st.number_input(
        "AI用：前テキスト最大文字数",
        min_value=50,
        max_value=2000,
        value=300,
        step=50,
    )

    ai_next_text_max_chars = st.number_input(
        "AI用：後テキスト最大文字数",
        min_value=50,
        max_value=2000,
        value=300,
        step=50,
    )

    show_debug = st.checkbox(
        "内部情報（デバッグ）を表示",
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
st.subheader("① PDFファイルの設定")

input_result = render_input_source(
    projects_root=PROJECTS_ROOT,
    user_sub=sub,
    page_name=PAGE_NAME,
    key_prefix=f"{PAGE_NAME}__chart_input",
    allowed_sources=["upload", "inbox"],
    upload_types=["pdf"],
    inbox_kinds=None,
    inbox_extensions=["pdf"],
    input_label="入力方法",
    upload_label="PDF ファイル（.pdf）をアップロードしてください",
    inbox_page_size=8,
)

# ============================================================
# 選択ファイル変更時は前回DL結果をクリア
# ============================================================
DL_SOURCE_KEY = f"{PAGE_NAME}__chart_check_selected_source"

_input_prefix = f"{PAGE_NAME}__chart_input"
_input_method = st.session_state.get(f"{_input_prefix}__input_method")

if _input_method == "upload":
    _uploaded = st.session_state.get(f"{_input_prefix}__uploader")

    if _uploaded is not None:
        selected_source = (
            f"upload:"
            f"{getattr(_uploaded, 'name', '')}:"
            f"{getattr(_uploaded, 'size', '')}"
        )
    else:
        selected_source = ""

elif _input_method == "inbox":
    selected_source = (
        "inbox:"
        + str(
            st.session_state.get(
                f"{_input_prefix}__inbox_picker_selected_item_id"
            )
            or ""
        )
    )

else:
    selected_source = ""

if selected_source and st.session_state.get(DL_SOURCE_KEY) != selected_source:
    st.session_state[DL_SOURCE_KEY] = selected_source
    st.session_state.pop(DL_STATE_KEY, None)

    st.info("選択ファイルが変更されました。先に「選択ファイルを読み込む」を押してください。")
    st.stop()

if not input_result.confirmed:
    _render_saved_downloads_sidebar()
    st.info("まずチェックするファイルを設定してください。")
    st.stop()

# ============================================================
# 図表チェック
# ============================================================
st.divider()
st.subheader('② 図表チェック')
run = st.button(
    "チェックを実行",
    type="primary",
    key=f"{PAGE_NAME}__run_chart_check",
)

# ============================================================
# 実行トリガ（未実行時は保存済みDLだけ表示）
# ============================================================
if not run:
    _render_saved_result_downloads_main()
    _render_saved_downloads_sidebar()
    st.stop()

# ============================================================
# 新規実行時は前回DL結果をクリア
# ============================================================
st.session_state.pop(DL_STATE_KEY, None)

# ============================================================
# PDF種別チェック（画像PDFは対象外）
# ============================================================
pdf_bytes = input_result.data_bytes

pdf_kind, page_count = detect_pdf_kind_from_bytes(
    fitz=fitz,
    pdf_bytes=pdf_bytes,
)

if pdf_kind == "image":
    st.warning("⚠️ このPDFは画像PDFのため、図表チェックは実行できません。テキストPDFをアップロードしてください。")
    st.stop()

# ============================================================
# PDF → ページ別テキスト
# ============================================================
with tempfile.TemporaryDirectory() as td:
    pdf_path = Path(td) / "input.pdf"
    pdf_path.write_bytes(input_result.data_bytes)
    pages_text: List[str] = pdf_to_text_per_page(pdf_path)

st.success(f"PDF 読み込み完了：ページ数 {len(pages_text)}")

# ============================================================
# 全ページ走査：頁ラベル + 図表（見出し/参照）抽出
# ============================================================
page_labels, per_page_rows = [], []

for i, ptxt in enumerate(pages_text, start=1):
    label, matched = extract_single_page_label(ptxt)
    page_labels.append(label)
    per_page_rows.append(
        {
            "pdf_page": i,
            "page_label": label or "-",
            "matched_line": matched or "-",
            "has_label": label is not None,
        }
    )

df_per_page_labels = pd.DataFrame(per_page_rows)

caption_rows, ref_rows = [], []

for i, ptxt in enumerate(pages_text, start=1):
    page_label = page_labels[i - 1] if (i - 1) < len(page_labels) and page_labels[i - 1] else "-"
    captions, refs = judge_hits_in_page(ptxt, ctx=ctx_chars)

    for h in captions:
        caption_rows.append(
            {
                "pdf_page": i,
                "page_label": page_label,
                **h,
            }
        )

    for r in refs:
        ref_rows.append(
            {
                "pdf_page": i,
                "page_label": page_label,
                **r,
            }
        )

df_captions = pd.DataFrame(caption_rows)
df_refs = pd.DataFrame(ref_rows)

# ============================================================
# 表示：ページラベル / 図表見出し
# ============================================================
st.subheader("📑 各ページの頁ラベル")
st.dataframe(df_per_page_labels)

st.subheader("🖼️ 図/表/図表 見出し")
st.dataframe(df_captions)

# ============================================================
# 図表番号の品質チェック（重複・飛び・開始番号・続き判定）
# ============================================================
st.markdown("### ✅ 図表番号のチェック（重複・飛び・開始）")

if df_captions.empty or "図表番号" not in df_captions.columns:
    st.info("図表番号の検査対象がありません（df_captions が空です）。")
    cont_rows, dup_rows = [], []
    gap_rows, start_rows = [], []

else:
    # ------------------------------------------------------------
    # 重複 / 続き判定
    # ------------------------------------------------------------
    cont_rows, dup_rows = [], []

    for k, g in df_captions.groupby("図表キー"):
        if len(g) <= 1:
            continue

        g2 = g.sort_values("pdf_page")

        if is_continuation_group(g2):
            cont_rows.append(
                {
                    "図表キー": k,
                    "図表タイトル": " | ".join(
                        [str(x) for x in g2["見出しタイトル"].fillna("").tolist()]
                    ),
                    "pdf頁一覧": ",".join(
                        [str(int(x)) for x in g2["pdf_page"].dropna().astype(int).tolist()]
                    ),
                    "頁ラベル一覧": ",".join(
                        [str(x) for x in g2["page_label"].fillna("").tolist()]
                    ),
                    "備考": "（続きのページとみなす）",
                }
            )
        else:
            dup_rows.append(
                {
                    "図表キー": k,
                    "見出しタイトル一覧": " | ".join(
                        [str(x) for x in g2["見出しタイトル"].fillna("").tolist()]
                    ),
                    "pdf頁一覧": ",".join(
                        [str(int(x)) for x in g2["pdf_page"].dropna().astype(int).tolist()]
                    ),
                    "頁ラベル一覧": ",".join(
                        [str(x) for x in g2["page_label"].fillna("").tolist()]
                    ),
                    "備考": "（真の重複の可能性）",
                }
            )

    # ------------------------------------------------------------
    # 重複 / 続き判定の表示
    # ------------------------------------------------------------
    if cont_rows:
        st.info("🔵 以下は **同番号の連続ページ** と判定しました（重複扱いしません）。")
        st.dataframe(pd.DataFrame(cont_rows))

    if dup_rows:
        st.warning("🟠 図表番号の**真の重複**が見つかりました。")
        st.dataframe(pd.DataFrame(dup_rows))
    elif not cont_rows:
        st.success("🟢 図表番号の重複はありません。")

    # ------------------------------------------------------------
    # 系列別に番号を収集
    # ------------------------------------------------------------
    series_map = defaultdict(list)

    for _, r in df_captions.iterrows():
        key = str(r.get("図表キー"))
        pdfp = r.get("pdf_page")
        series, idx, kind = series_and_index(key)

        if idx is None:
            continue

        series_map[(kind, series)].append(
            (
                int(idx),
                key,
                int(pdfp) if pd.notna(pdfp) else 10**9,
            )
        )

    # ------------------------------------------------------------
    # 開始番号 / 欠番チェック
    # ------------------------------------------------------------
    gap_rows, start_rows = [], []

    for (kind, series), items in series_map.items():
        items_sorted = sorted(items, key=lambda x: (x[0], x[2]))
        idxs = [i for i, _, _ in items_sorted]
        starts_at = idxs[0] if idxs else None

        if starts_at is not None and starts_at != 1:
            start_rows.append(
                {
                    "種別": kind,
                    "系列": series or "(単一番号)",
                    "開始番号": starts_at,
                    "期待": 1,
                    "存在番号": ",".join(map(str, idxs)),
                }
            )

        if len(idxs) >= 2:
            missing = []

            for a, b in zip(idxs, idxs[1:]):
                if b - a > 1:
                    missing.extend(range(a + 1, b))

            if missing:
                gap_rows.append(
                    {
                        "種別": kind,
                        "系列": series or "(単一番号)",
                        "欠番": ",".join(map(str, missing)),
                        "存在番号": ",".join(map(str, idxs)),
                    }
                )

    # ------------------------------------------------------------
    # 開始番号 / 欠番チェックの表示
    # ------------------------------------------------------------
    if not gap_rows and not start_rows:
        st.success("🟢 連番の飛びは無く、各系列の開始番号も 1 になっています。")
    else:
        if start_rows:
            st.warning("🟠 系列の開始番号が 1 でないものが見つかりました。")
            st.dataframe(pd.DataFrame(start_rows))

        if gap_rows:
            st.warning("🟠 連番に欠番（飛び）が見つかりました。")
            st.dataframe(pd.DataFrame(gap_rows))

# ============================================================
# 本文参照表示
# ============================================================
st.subheader("🔗 本文中の 図/表/図表 参照")
st.dataframe(df_refs)

# ============================================================
# 突き合わせ：図表見出し ↔ 本文参照
# ============================================================
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

all_captions_referenced = len(missing_in_refs) == 0
has_refs_without_caption = len(missing_in_captions) > 0

# ============================================================
# 突き合わせ結果：サマリー
# ============================================================
st.subheader("🔎 突き合わせ結果（図表の見出し ↔ テキスト中の参照）")

c1, c2 = st.columns(2)

with c1:
    st.markdown("**① 全ての図表見出しが本文で引用されているか？**")
    st.write(
        "→ **{}**".format(
            "はい（全て引用あり）✅"
            if all_captions_referenced
            else "いいえ（未引用あり）⚠️"
        )
    )

with c2:
    st.markdown("**② 本文に参照があるが見出しが無いものはないか？**")
    st.write(
        "→ **{}**".format(
            "はい（全て見出しあり）✅"
            if not has_refs_without_caption
            else "いいえ（見出しなしの参照あり）⚠️"
        )
    )

# ============================================================
# 参照情報集約
# ============================================================
ref_lbls, ref_pdfs, ref_texts, ref_hi = ref_aggregate_for_view(
    df_refs,
    base_key_func=base_key,
)

# ============================================================
# 引用されている見出し一覧
# ============================================================
ref_base_keys_view = set(ref_lbls.keys())
referenced_keys = sorted(
    k
    for k in cap_idx.keys()
    if base_key(k) in ref_base_keys_view
)

rows_view = []

for k in referenced_keys:
    ci = first_caption_row(df_captions, k)
    bk = base_key(k)

    rows_view.append(
        {
            "図表キー": k,
            "図表タイトル": ci["図表タイトル"],
            "頁": ci["頁"],
            "pdf頁": ci["pdf頁"],
            "参照頁ラベル": ref_lbls.get(bk, ""),
            "参照pdf頁": ref_pdfs.get(bk, ""),
            "参照テキスト": ref_texts.get(bk, ""),
            "参照テキスト(強調)": ref_hi.get(bk, ""),
            "_sort": ci["pdf頁"],
        }
    )

df_referenced_view = (
    pd.DataFrame(
        rows_view,
        columns=[
            "図表キー",
            "図表タイトル",
            "頁",
            "pdf頁",
            "参照頁ラベル",
            "参照pdf頁",
            "参照テキスト",
            "参照テキスト(強調)",
            "_sort",
        ],
    )
    .sort_values("_sort", kind="mergesort")
    .drop(columns=["_sort"])
)

# ============================================================
# 突き合わせ結果：表示
# ============================================================
st.markdown("#### 🔵 引用されている見出し（見出しあり＋本文参照あり）")
st.dataframe(df_referenced_view)

st.markdown("#### 🟠 未引用の見出し（見出しはあるが本文参照が見つからない）")

df_missing_caption_refs = pd.DataFrame(
    [
        {
            "図表キー": k,
            "見出しページ": cap_idx.get(k, []),
            "参照ページ": ref_idx.get(k, []),
        }
        for k in missing_in_refs
    ]
)

st.dataframe(df_missing_caption_refs)

st.markdown("#### 🔵 見出しなしの参照（本文に参照はあるが対応する見出しが無い）")

df_orphan_refs = pd.DataFrame(
    [
        {
            "図表キー": k,
            "参照ページ": ref_idx.get(k, []),
            "見出しページ": cap_idx.get(k, []),
        }
        for k in missing_in_captions
    ]
)

st.dataframe(df_orphan_refs)

# ============================================================
# XLSX（突き合わせ＋重複/続き）生成
# ============================================================
cap_info = caption_info_first_by_key(
    df_captions,
    df_per_page_labels,
)

ref_page_labels, ref_pdf_pages, ref_texts2, ref_highlight_texts = aggregate_ref_info(
    df_refs,
    base_key_func=base_key,
)

ref_base_keys_x = set(ref_page_labels.keys())

referenced_keys_x = sorted(
    k
    for k in cap_idx.keys()
    if base_key(k) in ref_base_keys_x
)

df_referenced_captions_x = make_crosscheck_rows(
    referenced_keys_x,
    caption_src=True,
    cap_info=cap_info,
    ref_page_labels=ref_page_labels,
    ref_pdf_pages=ref_pdf_pages,
    ref_texts=ref_texts2,
    ref_highlight_texts=ref_highlight_texts,
    base_key_func=base_key,
)

df_missing_caption_refs_x = make_crosscheck_rows(
    sorted(missing_in_refs),
    caption_src=True,
    cap_info=cap_info,
    ref_page_labels=ref_page_labels,
    ref_pdf_pages=ref_pdf_pages,
    ref_texts=ref_texts2,
    ref_highlight_texts=ref_highlight_texts,
    base_key_func=base_key,
)

df_orphan_refs_x = make_crosscheck_rows(
    sorted(missing_in_captions),
    caption_src=False,
    cap_info=cap_info,
    ref_page_labels=ref_page_labels,
    ref_pdf_pages=ref_pdf_pages,
    ref_texts=ref_texts2,
    ref_highlight_texts=ref_highlight_texts,
    base_key_func=base_key,
)

dup_df = (
    pd.DataFrame(dup_rows)
    if dup_rows
    else pd.DataFrame(
        columns=[
            "図表キー",
            "見出しタイトル一覧",
            "pdf頁一覧",
            "頁ラベル一覧",
            "備考",
        ]
    )
)

cont_df = (
    pd.DataFrame(cont_rows)
    if cont_rows
    else pd.DataFrame(
        columns=[
            "図表キー",
            "図表タイトル",
            "pdf頁一覧",
            "頁ラベル一覧",
            "備考",
        ]
    )
)

# ============================================================
# XLSX bytes 生成
# ============================================================
_xlsx_output = BytesIO()

with pd.ExcelWriter(_xlsx_output, engine="openpyxl") as writer:
    pd.DataFrame(
        {
            "項目": [
                "全て引用済みか？",
                "見出しなしの参照はないか？",
            ],
            "結果": [
                "はい（全て引用あり）✅"
                if all_captions_referenced
                else "いいえ（未引用あり）⚠️",
                "はい（見出しなし参照なし）✅"
                if not has_refs_without_caption
                else "いいえ（見出しなし参照あり）⚠️",
            ],
        }
    ).to_excel(writer, sheet_name="サマリー", index=False)

    df_referenced_captions_x.to_excel(writer, sheet_name="引用見出し", index=False)
    df_missing_caption_refs_x.to_excel(writer, sheet_name="未引用見出し", index=False)
    df_orphan_refs_x.to_excel(writer, sheet_name="見出しなし参照", index=False)

    dup_df.to_excel(writer, sheet_name="重複（疑い）", index=False)
    cont_df.to_excel(writer, sheet_name="続き判定", index=False)

    pd.DataFrame(start_rows).to_excel(
        writer,
        sheet_name="開始番号チェック",
        index=False,
    )

    pd.DataFrame(gap_rows).to_excel(
        writer,
        sheet_name="欠番チェック",
        index=False,
    )

_xlsx_bytes = _xlsx_output.getvalue()

# ============================================================
# サマリー XLSX bytes 生成
# ============================================================
_summary_xlsx_bytes = build_summary_xlsx_bytes(
    df_referenced_captions_x=df_referenced_captions_x,
    df_missing_caption_refs_x=df_missing_caption_refs_x,
    df_orphan_refs_x=df_orphan_refs_x,
)

# ============================================================
# AI用サマリー bytes 生成
# ============================================================
_ai_summary_xlsx_bytes = build_ai_summary_xlsx_bytes(
    df_captions=df_captions,
    df_refs=df_refs,
    pages_text=pages_text,
    prev_text_max_chars=int(ai_prev_text_max_chars),
    next_text_max_chars=int(ai_next_text_max_chars),
)

_ai_summary_jsonl_bytes = build_ai_summary_jsonl_bytes(
    df_captions=df_captions,
    df_refs=df_refs,
    pages_text=pages_text,
    prev_text_max_chars=int(ai_prev_text_max_chars),
    next_text_max_chars=int(ai_next_text_max_chars),
)

# ============================================================
# AI用サマリーJSONLを内部保存
# ============================================================
base = input_result.file_name.rsplit(".", 1)[0]
ai_summary_jsonl_filename = f"図表照合AI用サマリー_{base}.jsonl"

try:
    ai_summary_job_dir = save_ai_summary_jsonl_job(
        projects_root=PROJECTS_ROOT,
        user_sub=str(sub),
        source_filename=input_result.file_name,
        jsonl_filename=ai_summary_jsonl_filename,
        jsonl_bytes=_ai_summary_jsonl_bytes,
        page_count=len(pages_text),
        caption_count=len(df_captions),
        ref_count=len(df_refs),
        prev_text_max_chars=int(ai_prev_text_max_chars),
        next_text_max_chars=int(ai_next_text_max_chars),
    )

    st.success(
        f"✅ AIサマリーJSONLを内部保存しました。"
        f"（job: {ai_summary_job_dir.name}）"
    )

except Exception as e:
    st.error(f"❌ AIサマリーJSONLの内部保存に失敗しました: {e}")

# ============================================================
# ダウンロードファイル名
# ============================================================
xlsx_filename = f"図表照合_{base}.xlsx"
summary_xlsx_filename = f"図表照合サマリー_{base}.xlsx"
ai_summary_xlsx_filename = f"図表照合AI用サマリー_{base}.xlsx"

# ============================================================
# ダウンロード用 CSV bytes 生成
# ============================================================
csv_items = []

for df, name in [
    (df_per_page_labels, "per_page_labels.csv"),
    (df_captions, "figure_table_captions.csv"),
    (df_refs, "figure_table_references.csv"),
]:
    if not df.empty:
        df2 = df.copy()

        if "page_label" in df2.columns:
            df2["page_label"] = df2["page_label"].map(protect_for_excel_csv)

        buf = io.StringIO()
        df2.to_csv(buf, index=False)

        csv_items.append(
            {
                "label": f"📥 {name}",
                "data": buf.getvalue().encode("utf-8-sig"),
                "file_name": name,
            }
        )

# ============================================================
# ダウンロード結果を session_state に保存
# ============================================================
st.session_state[DL_STATE_KEY] = {
    "summary_xlsx_bytes": _summary_xlsx_bytes,
    "summary_xlsx_filename": summary_xlsx_filename,
    "xlsx_bytes": _xlsx_bytes,
    "xlsx_filename": xlsx_filename,
    "ai_summary_xlsx_bytes": _ai_summary_xlsx_bytes,
    "ai_summary_xlsx_filename": ai_summary_xlsx_filename,
    "ai_summary_jsonl_bytes": _ai_summary_jsonl_bytes,
    "ai_summary_jsonl_filename": ai_summary_jsonl_filename,
    "csv_items": csv_items,
}

# ============================================================
# Main（主要結果DL）＋ Sidebar（その他DL）
# ============================================================
st.divider()
_render_saved_result_downloads_main()

st.sidebar.divider()
_render_saved_downloads_sidebar()

# ============================================================
# デバッグ
# ============================================================
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.code(f"EXTRACT_RE = {EXTRACT_RE.pattern}")
    st.caption("マッチを含む1行抽出＋⟪強調⟫＋excerpt付き。")