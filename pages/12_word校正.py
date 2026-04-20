# -*- coding: utf-8 -*-
# text_studio_app/pages/12_word校正.py
# ============================================================
# 📄 Word校正
# ------------------------------------------------------------
# 役割:
# - Word(.docx) を解析して中間テキストを生成
# - 中間テキストを Storages/<sub>/word_edit_app/<job>/ に保存
# - 保存済み中間テキストを radio で選択
# - 選択した中間テキストを AI で校正解析
# - 校正方針の表示 / PDF・Word ダウンロード
#
# 方針:
# - Word解析部分は 04_word解析.py を参照
# - 校正UI/AI実行部分は 03_文章校正.py を参照
# - 1回の job だけ保持し、新規保存時は word_edit_app 配下を全削除
# - radio の一覧は毎回ファイルシステムから読み直す
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
from pathlib import Path
import sys
import json
import shutil
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List

# ============================================================
# imports（3rd party）
# ============================================================
import streamlit as st

try:
    from docx import Document
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="Text Studio / Word校正",
    page_icon="📄",
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
from common_lib.ai.costs.fx import get_default_usd_jpy

# ============================================================
# lib（Word解析）
# ============================================================
from lib.word_analysis.blocks import (
    Block,
    iter_block_items,
    classify_paragraph,
    classify_block,
)
from lib.word_analysis.headings import (
    is_heading_paragraph,
    detect_heading_level,
    format_heading_id,
)
from lib.word_analysis.tables import (
    table_to_json,
)
from lib.word_analysis.images import (
    get_image_filenames_from_paragraph,
)
from lib.word_analysis.chunking import (
    chunk_text_by_markers,
    make_planned_filenames,
)
from lib.word_analysis.explanation import render_word_analysis_help_expander

# ============================================================
# lib（校正プロンプト）
# ============================================================
from lib.proofreading.prompts import (
    MODE_DEFS,
    COMMON_PROMPT,
    get_analyze_instruction,
    build_system_prompt,
)

# ============================================================
# lib（ヘルプ / UI）
# ============================================================
from lib.proofreading.explanation import render_proofreading_help_expander
from lib.proofreading.ui_utils import (
    to_numbered_lines,
    md_table_to_html,
    inject_proof_table_css,
)

# ============================================================
# lib（レポートビルダー）
# ============================================================
from lib.proofreading.report_builders import (
    build_policy_docx_bytes as build_policy_docx_bytes_core,
    build_policy_pdf_bytes as build_policy_pdf_bytes_core,
)

# ============================================================
# 定数
# ============================================================
DEFAULT_MODEL_KEY = DEFAULT_TEXT_MODEL_KEY
DEFAULT_MODE = "通常校正"
WORD_EDIT_DEFAULT_MODE = "解析文書校正（通常校正）"

WORD_EDIT_APP_DIRNAME = "word_edit_app"
JOB_PREFIX = "job_"
MANIFEST_NAME = "manifest.json"

K_MODEL_KEY = f"{PAGE_NAME}__model_key"
K_SELECTED_LABEL = f"{PAGE_NAME}__selected_label"
K_SELECTED_TEXT = f"{PAGE_NAME}__selected_text"
K_SELECTED_NAME = f"{PAGE_NAME}__selected_name"
K_DO_ANALYZE = f"{PAGE_NAME}__do_analyze"
K_LAST_RUN_ID = f"{PAGE_NAME}__last_run_id"
K_LAST_RUN_ACTION = f"{PAGE_NAME}__last_run_action"
K_LAST_IN_TOK = f"{PAGE_NAME}__last_in_tok"
K_LAST_OUT_TOK = f"{PAGE_NAME}__last_out_tok"
K_LAST_COST_OBJ = f"{PAGE_NAME}__last_cost_obj"
K_LAST_MODEL = f"{PAGE_NAME}__last_model"
K_LAST_PROVIDER = f"{PAGE_NAME}__last_provider"
K_LAST_NOTE = f"{PAGE_NAME}__last_note"

K_PROOF_MODE = f"{PAGE_NAME}__proof_mode"

# ============================================================
# session_state 初期化
# ============================================================
st.session_state.setdefault(K_MODEL_KEY, DEFAULT_MODEL_KEY)
st.session_state.setdefault(K_PROOF_MODE, WORD_EDIT_DEFAULT_MODE)
st.session_state.setdefault("extra_user_prompt", "")
st.session_state.setdefault(K_SELECTED_LABEL, "")
st.session_state.setdefault(K_SELECTED_TEXT, "")
st.session_state.setdefault(K_SELECTED_NAME, "")
st.session_state.setdefault(K_DO_ANALYZE, False)
st.session_state.setdefault(K_LAST_RUN_ID, "")
st.session_state.setdefault(K_LAST_RUN_ACTION, "")
st.session_state.setdefault(K_LAST_IN_TOK, None)
st.session_state.setdefault(K_LAST_OUT_TOK, None)
st.session_state.setdefault(K_LAST_COST_OBJ, None)
st.session_state.setdefault(K_LAST_MODEL, "")
st.session_state.setdefault(K_LAST_PROVIDER, "")
st.session_state.setdefault(K_LAST_NOTE, "")

# ============================================================
# helper：model_key -> (provider, model)
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
# helper：Word編集用ルート
# ============================================================
def get_word_edit_root(*, projects_root: Path, user_sub: str) -> Path:
    # ------------------------------------------------------------
    # Storages/<sub>/word_edit_app
    # ------------------------------------------------------------
    return projects_root / "Storages" / str(user_sub) / WORD_EDIT_APP_DIRNAME


# ============================================================
# helper：job名生成
# ============================================================
def make_job_name() -> str:
    # ------------------------------------------------------------
    # 例: job_20260425_091026
    # ------------------------------------------------------------
    return f"{JOB_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}"


# ============================================================
# helper：word_edit_app 配下を空にする
# ============================================================
def clear_word_edit_root(*, root_dir: Path) -> None:
    # ------------------------------------------------------------
    # 既存 job をすべて削除し、空ディレクトリを再作成
    # ------------------------------------------------------------
    if root_dir.exists():
        shutil.rmtree(root_dir)
    root_dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# helper：manifest 保存
# ============================================================
def write_manifest(*, job_dir: Path, payload: Dict[str, Any]) -> None:
    # ------------------------------------------------------------
    # manifest.json を UTF-8 で保存
    # ------------------------------------------------------------
    manifest_path = job_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ============================================================
# helper：manifest 読込
# ============================================================
def read_manifest(*, job_dir: Path) -> Dict[str, Any]:
    # ------------------------------------------------------------
    # manifest.json を読み込む
    # ------------------------------------------------------------
    manifest_path = job_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ============================================================
# helper：現在 job を取得
# ============================================================
def resolve_current_job_dir(*, root_dir: Path) -> Path | None:
    # ------------------------------------------------------------
    # 原則 1 job だけだが、念のため複数あれば名前順の最後を採用
    # ------------------------------------------------------------
    if not root_dir.exists():
        return None

    job_dirs = [
        p for p in root_dir.iterdir()
        if p.is_dir() and p.name.startswith(JOB_PREFIX)
    ]
    if not job_dirs:
        return None

    job_dirs = sorted(job_dirs, key=lambda x: x.name)
    return job_dirs[-1]


# ============================================================
# helper：保存済み txt 一覧
# ============================================================
def list_saved_intermediate_files(*, job_dir: Path | None) -> List[Dict[str, Any]]:
    # ------------------------------------------------------------
    # manifest 優先で一覧構築
    # ------------------------------------------------------------
    if job_dir is None:
        return []

    manifest = read_manifest(job_dir=job_dir)
    files = manifest.get("files") or []

    rows: List[Dict[str, Any]] = []
    for row in files:
        filename = str(row.get("filename") or "").strip()
        if not filename:
            continue

        path = job_dir / filename
        if not path.exists():
            continue

        chars = int(row.get("chars") or 0)
        index = int(row.get("index") or 0)
        total = int(row.get("total") or 0)

        label = f"{index}/{total} | {filename} | {chars:,}文字"
        rows.append(
            {
                "label": label,
                "filename": filename,
                "path": path,
                "chars": chars,
                "index": index,
                "total": total,
            }
        )

    if rows:
        return rows

    # ------------------------------------------------------------
    # manifest が無い/壊れている場合のフォールバック
    # ------------------------------------------------------------
    txt_files = sorted(job_dir.glob("*.txt"))
    fallback_rows: List[Dict[str, Any]] = []

    for idx, path in enumerate(txt_files, start=1):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            text = ""

        chars = len(text)
        fallback_rows.append(
            {
                "label": f"{idx}/{len(txt_files)} | {path.name} | {chars:,}文字",
                "filename": path.name,
                "path": path,
                "chars": chars,
                "index": idx,
                "total": len(txt_files),
            }
        )

    return fallback_rows


# ============================================================
# helper：選択ファイル読込
# ============================================================
def read_saved_text(*, path: Path) -> str:
    # ------------------------------------------------------------
    # 保存済み中間テキストを読む
    # ------------------------------------------------------------
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


# ============================================================
# helper：job 保存
# ============================================================
def save_word_edit_job(
    *,
    projects_root: Path,
    user_sub: str,
    source_filename: str,
    output_mode: str,
    base_chapter: int,
    use_same_left_placeholder: bool,
    chunk_char_limit: int,
    intermediate_text: str,
    chunks: List[str],
    planned_names: List[str],
) -> Path:
    # ------------------------------------------------------------
    # 既存を全削除し、新規 job を 1 件だけ保存
    # ------------------------------------------------------------
    root_dir = get_word_edit_root(projects_root=projects_root, user_sub=user_sub)
    clear_word_edit_root(root_dir=root_dir)

    job_name = make_job_name()
    job_dir = root_dir / job_name
    job_dir.mkdir(parents=True, exist_ok=True)

    file_rows: List[Dict[str, Any]] = []

    for idx, (chunk, filename) in enumerate(zip(chunks, planned_names), start=1):
        out_path = job_dir / filename
        out_path.write_text(chunk, encoding="utf-8")

        file_rows.append(
            {
                "filename": filename,
                "chars": len(chunk),
                "index": idx,
                "total": len(chunks),
            }
        )

    manifest = {
        "job_name": job_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_filename": source_filename,
        "output_mode": output_mode,
        "base_chapter": int(base_chapter),
        "use_same_left_placeholder": bool(use_same_left_placeholder),
        "chunk_char_limit": int(chunk_char_limit),
        "total_chars": len(intermediate_text or ""),
        "file_count": len(file_rows),
        "files": file_rows,
    }
    write_manifest(job_dir=job_dir, payload=manifest)

    return job_dir


# ============================================================
# helper：番号付きプレビュー
# ============================================================
def _render_numbered_preview_no_paging(lines: list[str]) -> str:
    return "\n".join([f"[{(i + 1):04d}] {lines[i]}" for i in range(len(lines))])


# ============================================================
# 中間テキスト構築（04_word解析.py ベース）
# ============================================================
def build_intermediate_text(
    doc: Document,
    base_chapter: int,
    mode: str = "detailed",
    *,
    use_same_left_placeholder: bool,
) -> tuple[str, dict[str, int]]:
    # ------------------------------------------------------------
    # Word を中間テキストへ変換
    # ------------------------------------------------------------
    simple_mode = (mode == "simple")

    lines: List[str] = []
    stats = {"heading": 0, "paragraph": 0, "table": 0, "figure": 0}

    heading_counters = [0, 0, 0, 0]
    prev_block: Block | None = None
    pending_table_caption = None

    def _looks_like_heading_line(s: str) -> bool:
        if not s:
            return False

        t = s.strip()
        if not t:
            return False

        if "\n" in t or "\r" in t:
            return False

        for ch in ["。", "、", "，", "．", ".", ",", "!", "?", "！", "？", ":", "：", ";", "；"]:
            if ch in t:
                return False

        if len(t) < 2:
            return False
        if len(t) > 80:
            return False

        return True

    def append_blank() -> None:
        if simple_mode:
            lines.append("")

    for block in iter_block_items(doc):

        # ------------------------------------------------------------
        # Paragraph
        # ------------------------------------------------------------
        from docx.text.paragraph import Paragraph
        from docx.table import Table

        if isinstance(block, Paragraph):

            # --------------------------------------------------------
            # 見出し
            # --------------------------------------------------------
            if is_heading_paragraph(block):
                level = detect_heading_level(block)
                heading_id = format_heading_id(base_chapter, heading_counters, level)
                text = (block.text or "").strip()

                if text:
                    if mode == "simple":
                        append_blank()
                        lines.append(text)

                    elif mode == "standard":
                        if _looks_like_heading_line(text):
                            lines.append("<ここから見出し>")
                            lines.append(text)
                            lines.append("<ここまで見出し>")
                            lines.append("")
                            stats["heading"] += 1
                        else:
                            lines.append(text)
                            stats["paragraph"] += 1

                    else:
                        lines.append(f"=== HEADING[{heading_id}] {text} ===")
                        stats["heading"] += 1

                prev_block = block
                pending_table_caption = None
                continue

            # --------------------------------------------------------
            # 見出し以外
            # --------------------------------------------------------
            cat = classify_paragraph(block)

            if cat == "toc":
                prev_block = block
                pending_table_caption = None
                continue

            if cat == "table_caption":
                pending_table_caption = block
                prev_block = block
                continue

            # --------------------------------------------------------
            # 図
            # --------------------------------------------------------
            if cat == "figure":
                caption = (block.text or "").strip()
                img_files = get_image_filenames_from_paragraph(block)
                stats["figure"] += 1
                fig_id = stats["figure"]

                if mode == "simple":
                    append_blank()
                    if caption:
                        lines.append(caption)

                elif mode == "standard":
                    if caption:
                        lines.append("<ここから図>")
                        lines.append(caption)
                        lines.append("<ここまで図>")
                    else:
                        lines.append("<ここから図>")
                        lines.append("<ここまで図>")

                    if img_files:
                        lines.append(f"image_files: {', '.join(img_files)}")
                    else:
                        lines.append("image_files: (none)")

                else:
                    lines.append(f"=== FIGURE[{fig_id}] {caption} ===")
                    if img_files:
                        lines.append(f"image_files: {', '.join(img_files)}")
                    else:
                        lines.append("image_files: (none)")

                lines.append("")
                prev_block = block
                pending_table_caption = None
                continue

            # --------------------------------------------------------
            # 本文
            # --------------------------------------------------------
            text = (block.text or "").strip()
            if text:
                lines.append(text)
                stats["paragraph"] += 1

            prev_block = block
            pending_table_caption = None

        # ------------------------------------------------------------
        # Table
        # ------------------------------------------------------------
        elif isinstance(block, Table):
            cat = classify_block(block, prev_block)

            if cat == "table":
                stats["table"] += 1
                tbl_json = table_to_json(
                    block,
                    pending_table_caption,
                    use_same_left_placeholder=use_same_left_placeholder,
                )

                if mode in ("simple", "standard"):
                    append_blank()

                    cells = tbl_json.get("cells", [])
                    lines.append("<ここから表>")

                    raw_num = (tbl_json.get("table_number") or "").strip()
                    raw_title = (tbl_json.get("title") or "").strip()
                    tbl_num = "" if raw_num.lower() == "unknown" else raw_num

                    label = raw_title
                    if not label and tbl_num:
                        label = f"表 {tbl_num}".strip()

                    if label and (not label.lstrip().startswith("表")) and tbl_num:
                        label = f"表 {tbl_num} {label}".strip()

                    if label:
                        lines.append(label)

                    for row in cells:
                        processed = []
                        for x in row:
                            s = str(x).replace("\n", " ").replace("\r", " ")
                            s = " ".join(s.split())
                            processed.append(s)

                        row_text = ", ".join(processed)
                        lines.append(f"[{row_text}]")

                    lines.append("<ここまで表>")
                    lines.append("")

                else:
                    lines.append("")
                    tbl_num = tbl_json.get("table_number", "unknown")
                    tbl_title = tbl_json.get("title", "")
                    lines.append(f"=== TABLE {tbl_num} {tbl_title} ===")
                    lines.append("```json")
                    lines.append(json.dumps(tbl_json, ensure_ascii=False, indent=2))
                    lines.append("```")
                    lines.append("=== END_TABLE ===")
                    lines.append("")

                pending_table_caption = None
                prev_block = block
                continue

            prev_block = block
            pending_table_caption = None

        else:
            prev_block = block
            pending_table_caption = None

    intermediate_text = "\n".join(lines).strip() + "\n"
    return intermediate_text, stats


# ============================================================
# 解析プロンプト表示
# ============================================================
def render_policy_preview(*, mode: str) -> str:
    # ------------------------------------------------------------
    # 03_文章校正.py と同様
    # ------------------------------------------------------------
    analyze_base = get_analyze_instruction(mode)

    with st.expander("🧭 解析プロンプト設定（クリックで展開）", expanded=False):
        tab3, tab1, tab2 = st.tabs(["✍️ 追加プロンプト", "🧭 System", "📋 共通方針"])

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

left, right = st.columns([2, 1])
with left:
    st.title("📄 Word校正")
with right:
    st.success(f"✅ ログイン中: **{sub}**")

subtitle("Word解析 → 中間テキスト保存 → 校正解析")

st.caption(
    "このページでは，Word(.docx) の解析から校正方針の抽出までを一貫して行います．"
    "Word解析で作成した中間テキストは，Storages/<user>/word_edit_app/<job名>/ に保存されます．"
)
st.caption(
    "新しく Word解析を実行した時は，前回の中間テキスト一式を削除して，新しい job に置き換えます．"
)
st.caption(
    "保存済み中間テキストは下の radio から選択し，選択したファイルに対して校正解析を行います．"
)
st.caption("個人情報や機密情報の入力は避けてください．")

if not HAS_DOCX:
    st.error("python-docx がインポートできませんでした。`python-docx` をインストールしてください。")
    st.stop()

# ============================================================
# ヘルプ
# ============================================================
render_word_analysis_help_expander()
render_proofreading_help_expander()

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    # ------------------------------------------------------------
    # モデル選択
    # ------------------------------------------------------------
    st.header("設定")

    _ = render_text_model_picker(
        title="🧠 使用モデル",
        catalog=TEXT_MODEL_CATALOG,
        session_key=K_MODEL_KEY,
        default_key=DEFAULT_MODEL_KEY,
        page_name=PAGE_NAME,
        gemini_available=_gemini_available(),
    )

    # ------------------------------------------------------------
    # 解析モード
    # ------------------------------------------------------------
    st.caption("このページでは，中間テキスト校正のため，原則「解析文書校正」を使用してください。")
    options = list(MODE_DEFS.keys())

    default_index = options.index(WORD_EDIT_DEFAULT_MODE)

    st.radio(
        "🛠 解析モード",
        options=options,
        index=default_index,
        key=K_PROOF_MODE,
        help="\n\n".join([f"・{k}: {v['desc']}" for k, v in MODE_DEFS.items()]),
    )

    # ------------------------------------------------------------
    # ダウンロード形式
    # ------------------------------------------------------------
    _DL_LABELS = {"pdf": "PDF (.pdf)", "word": "Word (.docx)"}
    dl_choice_key = st.radio(
        "📦 ダウンロード形式（解析レポート）",
        options=list(_DL_LABELS.keys()),
        format_func=lambda k: _DL_LABELS[k],
        index=0,
        key=f"{PAGE_NAME}__dl_format_radio",
    )

    st.markdown("---")

    # ------------------------------------------------------------
    # Word解析オプション
    # ------------------------------------------------------------
    st.subheader("Word解析オプション")

    st.caption("「出力スタイル」は，続けて校正を行う時は「標準」で使用してください。")
    output_mode_label = st.radio(
        "出力スタイル",
        options=["簡素", "標準", "詳細"],
        index=1,
        horizontal=True,
        key=f"{PAGE_NAME}__output_mode_label",
        help=(
            "簡素：プレーン寄り\n"
            "標準：見出し/表などを読みやすく整形\n"
            "詳細：=== HEADING[...] === 等のマーカー付き"
        ),
    )

    if output_mode_label == "簡素":
        output_mode = "simple"
    elif output_mode_label == "標準":
        output_mode = "standard"
    else:
        output_mode = "detailed"

    st.caption("「この章の章番号」は，通常は 1 のままで使用してください。")
    base_chapter = st.number_input(
        "この章の章番号 (base_chapter)",
        min_value=1,
        max_value=50,
        value=1,
        step=1,
        key=f"{PAGE_NAME}__base_chapter",
    )

    st.caption("「結合セルの扱い」は，校正時は「横結合セルを <同左> にする」を推奨します。")
    merge_label = st.radio(
        "結合セルの扱い",
        options=["そのまま", "横結合セルを <同左> にする"],
        index=1,
        key=f"{PAGE_NAME}__merge_label",
    )
    use_same_left_placeholder = (merge_label == "横結合セルを <同左> にする")

    st.caption("分割上限は，原則 30,000 で使用してください。")
    chunk_char_limit = st.slider(
        "📏 分割上限（文字数）",
        min_value=10000,
        max_value=50000,
        value=30000,
        step=5000,
        key=f"{PAGE_NAME}__chunk_char_limit",
        help="見出し・表の直前を優先して分割します。",
    )

# ============================================================
# 追加プロンプト
# ============================================================
extra_prompt = render_policy_preview(mode=st.session_state[K_PROOF_MODE])

st.divider()

# ============================================================
# ① Wordアップロード / 解析保存
# ============================================================
st.subheader("① Word解析して中間テキストを保存")

uploaded_file = st.file_uploader(
    "Word ファイル（.docx）をアップロードしてください",
    type=["docx"],
    key=f"{PAGE_NAME}__word_uploader",
)

col_run1, col_info1 = st.columns([1, 3])

with col_run1:
    run_word_parse = st.button(
        "① Word解析して保存",
        type="primary",
        key=f"{PAGE_NAME}__btn_parse_save",
        disabled=(uploaded_file is None),
    )

with col_info1:
    st.caption(
        "保存時には既存の word_edit_app 配下を削除し，新しい job の中に分割済み中間テキストを保存します。"
    )

if run_word_parse:
    if uploaded_file is None:
        st.warning("Word ファイル（.docx）を選択してください。")
        st.stop()

    try:
        src_doc = Document(uploaded_file)
    except Exception as e:
        st.error(f"Word ファイルの読み込みに失敗しました: {e}")
        st.stop()

    with st.status("Word解析と保存を実行中です…", expanded=False) as status:
        intermediate_text, stats = build_intermediate_text(
            src_doc,
            base_chapter=int(base_chapter),
            mode=output_mode,
            use_same_left_placeholder=bool(use_same_left_placeholder),
        )

        txt_base_name = uploaded_file.name.rsplit(".", 1)[0]
        if output_mode == "simple":
            mode_jp = "簡素"
        elif output_mode == "standard":
            mode_jp = "標準"
        else:
            mode_jp = "詳細"

        txt_name = f"{txt_base_name}_intermediate_{mode_jp}.txt"
        markers = ["<ここから見出し>", "<ここから表>"]

        chunks = chunk_text_by_markers(
            intermediate_text,
            int(chunk_char_limit),
            markers=markers,
        )

        planned_names = make_planned_filenames(
            txt_name,
            len(chunks),
        )

        if not chunks:
            status.update(label="保存失敗", state="error")
            st.error("中間テキストが空のため保存できませんでした。")
            st.stop()

        job_dir = save_word_edit_job(
            projects_root=PROJECTS_ROOT,
            user_sub=str(sub),
            source_filename=uploaded_file.name,
            output_mode=output_mode,
            base_chapter=int(base_chapter),
            use_same_left_placeholder=bool(use_same_left_placeholder),
            chunk_char_limit=int(chunk_char_limit),
            intermediate_text=intermediate_text,
            chunks=chunks,
            planned_names=planned_names,
        )

        status.update(label="保存完了", state="complete")

    st.success(
        f"Word解析を実行し，中間テキストを保存しました。"
        f"（job: {job_dir.name} / {len(chunks)}分割）"
    )
    st.rerun()

# ============================================================
# 現在保存されている job / ファイル一覧
# ============================================================
word_edit_root = get_word_edit_root(projects_root=PROJECTS_ROOT, user_sub=str(sub))
current_job_dir = resolve_current_job_dir(root_dir=word_edit_root)
saved_rows = list_saved_intermediate_files(job_dir=current_job_dir)

st.markdown("---")
st.subheader("② 保存済み中間テキストを選択")

if current_job_dir is not None:
    manifest = read_manifest(job_dir=current_job_dir)
    source_filename = str(manifest.get("source_filename") or "")
    created_at = str(manifest.get("created_at") or "")
    if source_filename or created_at:
        st.caption(
            f"現在の job: {current_job_dir.name}"
            f"{' / 元ファイル: ' + source_filename if source_filename else ''}"
            f"{' / 作成日時: ' + created_at if created_at else ''}"
        )

if not saved_rows:
    st.info("保存済みの中間テキストはありません。まず上で Word解析を実行してください。")
else:
    label_to_row = {row["label"]: row for row in saved_rows}
    radio_labels = list(label_to_row.keys())

    current_selected = str(st.session_state.get(K_SELECTED_LABEL) or "")
    if current_selected not in radio_labels:
        st.session_state[K_SELECTED_LABEL] = radio_labels[0]

    selected_label = st.radio(
        "校正対象の中間テキストを選択",
        options=radio_labels,
        key=K_SELECTED_LABEL,
    )

    selected_row = label_to_row.get(selected_label)
    if selected_row is None:
        st.warning("選択中の中間テキストを取得できませんでした。")
        st.stop()

    selected_text = read_saved_text(path=selected_row["path"])
    selected_name = str(selected_row["filename"])

    st.session_state[K_SELECTED_TEXT] = selected_text
    st.session_state[K_SELECTED_NAME] = selected_name

    st.caption(
        f"選択中: {selected_name} / {selected_row['chars']:,}文字 / "
        f"{selected_row['index']}/{selected_row['total']}"
    )

# ============================================================
# 選択済みプレビュー
# ============================================================
preview_text = str(st.session_state.get(K_SELECTED_TEXT) or "").strip()
preview_name = str(st.session_state.get(K_SELECTED_NAME) or "").strip()

if preview_text:
    preview_lines = to_numbered_lines(preview_text)

    st.subheader("👀 行番号付きプレビュー（選択中中間テキスト）")
    st.text_area(
        "原文（番号付きプレビュー）",
        value=_render_numbered_preview_no_paging(preview_lines),
        height=260,
        key=f"{PAGE_NAME}__preview_text_area",
    )

# ============================================================
# ② 校正解析ボタン
# ============================================================
col_run2, col_info2 = st.columns([1, 3])

with col_run2:
    do_analyze = st.button(
        "② 解析（校正）",
        type="primary",
        key=f"{PAGE_NAME}__btn_analyze",
        disabled=(not bool(preview_text)),
    )

with col_info2:
    st.caption("選択した中間テキストに対して，校正方針（ページ/行/理由）を抽出します。")

if do_analyze:
    st.session_state[K_DO_ANALYZE] = True

# ============================================================
# 解析実行
# ============================================================
plan_md: str = ""
numbered_preview: str = ""

want_analyze = bool(st.session_state.pop(K_DO_ANALYZE, False))

if want_analyze:
    src_text = str(st.session_state.get(K_SELECTED_TEXT) or "").strip()
    used_file_name = str(st.session_state.get(K_SELECTED_NAME) or "input.txt")

    if not src_text:
        st.warning("校正対象の中間テキストがありません。")
        st.stop()

    lines = to_numbered_lines(src_text)

    # ------------------------------------------------------------
    # model_key -> provider/model
    # ------------------------------------------------------------
    model_key = str(st.session_state.get(K_MODEL_KEY) or DEFAULT_MODEL_KEY)
    provider, chosen_model = _parse_model_key(model_key)
    if not provider or not chosen_model:
        st.error(f"モデル指定が不正です: {model_key}")
        st.stop()

    # ------------------------------------------------------------
    # 直近表示初期化
    # ------------------------------------------------------------
    st.session_state[K_LAST_MODEL] = chosen_model
    st.session_state[K_LAST_PROVIDER] = provider
    st.session_state[K_LAST_IN_TOK] = None
    st.session_state[K_LAST_OUT_TOK] = None
    st.session_state[K_LAST_COST_OBJ] = None
    st.session_state[K_LAST_NOTE] = ""
    st.session_state[K_LAST_RUN_ID] = ""
    st.session_state[K_LAST_RUN_ACTION] = ""

    # ------------------------------------------------------------
    # prompt 構築
    # ------------------------------------------------------------
    mode = str(st.session_state.get(K_PROOF_MODE) or WORD_EDIT_DEFAULT_MODE)

    system_prompt = build_system_prompt(
        mode=mode,
        extra=str(extra_prompt or ""),
    )

    numbered_preview = _render_numbered_preview_no_paging(lines)

    prompt = (
        "次の文章を解析し、校正方針（ページ/行/理由）を Markdown 表で出力してください。\n"
        "Markdown表以外は出力しないでください。\n\n"
        "【追加指示（任意）】\n"
        f"{(extra_prompt or '').strip()}\n\n"
        "【原文（行番号付き）】\n"
        f"{numbered_preview}\n"
    )

    # ------------------------------------------------------------
    # AI 実行
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
                "feature": "word_proofreading_policy",
                "action": "analyze_policy",
                "input_method": "word_edit_saved_text",
                "input_chars": len(src_text or ""),
                "lines": len(lines),
                "mode": mode,
                "dl_format": str(st.session_state.get(f"{PAGE_NAME}__dl_format_radio") or ""),
                "source_filename": used_file_name,
            },
        ) as br:
            st.session_state[K_LAST_RUN_ID] = br.run_id
            st.session_state[K_LAST_RUN_ACTION] = "analyze_policy"

            with st.spinner("解析中（校正方針を抽出）…"):
                res = call_text(
                    provider=provider,
                    model=chosen_model,
                    prompt=prompt,
                    system=system_prompt,
                    temperature=None,
                    max_output_tokens=None,
                    extra=None,
                )

            plan_md = (getattr(res, "text", "") or "").strip()

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
        st.error(f"実行に失敗しました: {e}")
        st.stop()

    st.success("解析が完了しました。行番号/理由つきで方針を表示します。")

    # ============================================================
    # 校正方針 表示
    # ============================================================
    st.subheader("📋 校正方針")
    html_table = md_table_to_html(plan_md)
    inject_proof_table_css()
    st.markdown(html_table, unsafe_allow_html=True)

    # ============================================================
    # 実行サマリ
    # ============================================================
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
    # ダウンロード
    # ============================================================
    st.markdown("### ⤵️ 解析レポートをダウンロード")

    file_base = (used_file_name or "word_intermediate").rsplit(".", 1)[0]
    mode_label = mode.replace(" ", "")
    file_stub = f"校正結果_{file_base}_[{mode_label}]" if mode_label else f"校正結果_{file_base}"

    in_t = st.session_state.get(K_LAST_IN_TOK)
    out_t = st.session_state.get(K_LAST_OUT_TOK)

    if isinstance(in_t, int) and isinstance(out_t, int):
        usage_summary = {
            "input_tokens": int(in_t),
            "output_tokens": int(out_t),
            "total_tokens": int(in_t + out_t),
        }
    else:
        usage_summary = {}

    fx = get_default_usd_jpy()
    usd_jpy = float(fx.usd_jpy)

    def _format_cost_lines_stub(*args: Any, **kwargs: Any) -> list[str]:
        return ["概算: —（このレポートでは推計しません）"]

    dl_choice_key = str(st.session_state.get(f"{PAGE_NAME}__dl_format_radio") or "pdf")

    if dl_choice_key == "pdf":
        pdf_bytes = build_policy_pdf_bytes_core(
            original_numbered_preview=numbered_preview,
            plan_md=plan_md,
            model=chosen_model,
            mode=mode,
            extra_prompt=extra_prompt,
            src_name=used_file_name or "word_intermediate.txt",
            usage_summary=usage_summary,
            usd_jpy=usd_jpy,
            format_cost_lines=_format_cost_lines_stub,
        )
        if pdf_bytes:
            st.download_button(
                "PDF（.pdf）として保存",
                data=pdf_bytes,
                file_name=f"{file_stub}.pdf",
                mime="application/pdf",
                key=f"{PAGE_NAME}__dl_pdf_{file_stub}",
            )
        else:
            st.warning(
                "PDF を生成できませんでした。`pip install reportlab` を実行し、"
                "CIDフォント（HeiseiMin/HeiseiKakuGo）が使えるか確認してください。"
            )
    else:
        data_docx, ext = build_policy_docx_bytes_core(
            original_numbered_preview=numbered_preview,
            plan_md=plan_md,
            model=chosen_model,
            mode=mode,
            extra_prompt=extra_prompt,
            src_name=used_file_name or "word_intermediate.txt",
            usage_summary=usage_summary,
            usd_jpy=usd_jpy,
            format_cost_lines=_format_cost_lines_stub,
        )
        st.download_button(
            "Word（.docx）として保存" if ext == ".docx" else "テキスト（.txt）として保存",
            data=data_docx,
            file_name=f"{file_stub}{ext}",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if ext == ".docx"
            else "text/plain",
            key=f"{PAGE_NAME}__dl_word_{file_stub}",
        )

# ============================================================
# 初期案内
# ============================================================
if (not preview_text) and (not want_analyze):
    st.info("上で Word解析を実行するか、既存の中間テキストを選択してください。")