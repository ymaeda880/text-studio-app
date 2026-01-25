# -*- coding: utf-8 -*-
# pages/16_word解析.py
#
# Word(.docx) をアップロードして内部構造をざっくり解析し、
# - 本文 / 図 / 表 / 目次候補 / 見出し を分類
# - 「生成AIへの入力用」の中間テキストを 1 つ生成してダウンロード
#   * 見出し     : === HEADING[3-1-2] タイトル ===  のように章番号付きで出力
#   * 本文       : プレーンテキスト
#   * 表         : 表番号＋タイトルの下に JSON を埋め込む
#   * 図         : 図のキャプション＋画像ファイル名
# - 画像ファイルを ZIP で一括ダウンロード
#
# ※ base_chapter（この章が第何章か）はサイドバーから指定

from __future__ import annotations

from pathlib import Path
import sys

_THIS = Path(__file__).resolve()
PROJECTS_ROOT = _THIS.parents[3] ## appの時は[2]
if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))


from io import BytesIO
from typing import List, Tuple, Dict, Any
import json

import streamlit as st

# from pathlib import Path
# import sys

# =========================
# プロジェクトルートを sys.path に追加
# =========================
# PROJECTS_ROOT = Path(__file__).resolve().parents[3]
# if str(PROJECTS_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECTS_ROOT))

# _THIS = Path(__file__).resolve()
# PROJECTS_ROOT = _THIS.parents[3] ## appの時は[2]
# if str(PROJECTS_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECTS_ROOT))

# ==== python-docx 関連 ====
try:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False

# ==== 自作ライブラリ ====
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
    collect_images_as_zip,
)

# --- Inboxへ保存（common_lib.inbox.*）---
from common_lib.auth.auth_helpers import require_login
from common_lib.inbox.inbox_ops.ingest import ingest_to_inbox
from common_lib.inbox.inbox_common.types import (
    IngestRequest,
    InboxNotAvailable,
    QuotaExceeded,
    IngestFailed,
)

from lib.word_analysis.explanation import render_word_analysis_help_expander

from common_lib.ui.ui_basics import subtitle
from common_lib.ui.banner_lines import render_banner_line_by_key

# =========================
# 中間テキストの構築
# =========================
def build_intermediate_text(
    doc: Document,
    base_chapter: int,
    #mode: str = "standard",  # "standard" or "simple"
    mode: str = "detailed",  # "simple" | "standard" | "detailed"

    
) -> Tuple[str, Dict[str, int]]:

    simple_mode = (mode == "simple")

    lines: List[str] = []
    stats = {"heading": 0, "paragraph": 0, "table": 0, "figure": 0}

    heading_counters = [0, 0, 0, 0]
    prev_block: Block | None = None
    pending_table_caption: Paragraph | None = None


    def _looks_like_heading_line(s: str) -> bool:
        """
        「見出しと思われるもの」の簡易判定（標準モード用）
        条件（あなたの要件）：
          - 句読点がない（。、「」，． など）
          - 1行のみ（= 改行なし）
          - 短すぎず長すぎない（安全側のガード）
        """
        if not s:
            return False

        t = s.strip()
        if not t:
            return False

        # 1行のみ（念のため）
        if "\n" in t or "\r" in t:
            return False

        # 句読点がない（必要なら増やしてOK）
        for ch in ["。", "、", "，", "．", ".", ",", "!", "?", "！", "？", ":", "：", ";", "；"]:
            if ch in t:
                return False

        # 長さガード（お好みで調整）
        if len(t) < 2:
            return False
        if len(t) > 80:
            return False

        return True


    def append_blank():
        """簡素モードで、HEADING/FIGURE/TABLE の代わりに入れる空行"""
        if simple_mode:
            lines.append("")

    for block_idx, block in enumerate(iter_block_items(doc), start=1):

        # --------------------
        # Paragraph
        # --------------------
        if isinstance(block, Paragraph):

            # ---- 見出し ----
            if is_heading_paragraph(block):
                level = detect_heading_level(block)
                heading_id = format_heading_id(base_chapter, heading_counters, level)
                text = (block.text or "").strip()

                if text:
                    # mode は simple / standard / detailed
                    if mode == "simple":
                        append_blank()
                        lines.append(text)

                    elif mode == "standard":
                        # ★重要：=== HEADING のスタイルでも本文を括っている場合がある
                        # → 「見出しと思われるもの」だけを見出しとして括る
                        if _looks_like_heading_line(text):
                            lines.append("<ここから見出し>")
                            lines.append(text)
                            lines.append("<ここまで見出し>")
                            lines.append("")
                            stats["heading"] += 1
                        else:
                            # 見出しっぽくなければ本文扱いとして素のテキストで出す
                            lines.append(text)
                            stats["paragraph"] += 1

                    else:  # mode == "detailed"
                        lines.append(f"=== HEADING[{heading_id}] {text} ===")
                        stats["heading"] += 1

                prev_block = block
                pending_table_caption = None
                continue






            # ---- 見出し以外の分類 ----
            cat = classify_paragraph(block)

            if cat == "toc":
                prev_block = block
                pending_table_caption = None
                continue

            if cat == "table_caption":
                pending_table_caption = block
                prev_block = block
                continue

            # ---- 図キャプション ----
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
                    # 標準：見出しほど厳密にしないが、分かりやすく
                    if caption:
                        lines.append("<ここから図>")
                        lines.append(caption)
                        lines.append("<ここまで図>")
                    else:
                        lines.append("<ここから図>")
                        lines.append("<ここまで図>")

                    # image_files 行は両モード共通の情報として残す（運用上便利）
                    if img_files:
                        lines.append(f"image_files: {', '.join(img_files)}")
                    else:
                        lines.append("image_files: (none)")

                else:  # detailed
                    lines.append(f"=== FIGURE[{fig_id}] {caption} ===")
                    if img_files:
                        lines.append(f"image_files: {', '.join(img_files)}")
                    else:
                        lines.append("image_files: (none)")


                lines.append("")
                prev_block = block
                pending_table_caption = None
                continue

            # ---- 本文 ----
            text = (block.text or "").strip()
            if text:
                lines.append(text)
                stats["paragraph"] += 1

            prev_block = block
            pending_table_caption = None

        # --------------------
        # Table
        # --------------------
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
                    # 簡素モード：
                    # - 「=== TABLE ... ===」「=== END_TABLE ===」の代わりに
                    #   <ここから表> ～ <ここまで表> を出す
                    # - table_number/title/cells: の見出し行は出さない
                    # - 各行は [a, b, c, ...] の 1 行表記
                    # - セル内改行はスペースに統合
                    append_blank()

                    cells = tbl_json.get("cells", [])

                    lines.append("<ここから表>")
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

                else:  # mode == "standard" or "detailed"（TABLEは同じ扱い）
                    # 標準 / 詳細モード（従来仕様そのまま）
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


def split_text_by_heading_markers(text: str, limit: int) -> List[str]:
    """
    <ここから見出し> の直前を「候補の切れ目」として、
    1チャンクが limit 文字を超えないように分割する。

    - <ここから見出し> が無い場合は、最後にフォールバックで単純分割。
    - 先頭に見出しマーカーが来ても空チャンクは作らない。
    """
    if not text:
        return []

    t = text.strip()
    if not t:
        return []

    marker = "<ここから見出し>"

    # 見出しマーカーが無いならフォールバック（固定長で割る）
    if marker not in t:
        chunks: List[str] = []
        i = 0
        while i < len(t):
            chunks.append(t[i : i + limit].strip() + "\n")
            i += limit
        return [c for c in chunks if c.strip()]

    # マーカー位置で分割候補を作る（marker を保持したまま）
    parts = t.split(marker)

    # parts[0] は marker より前（本文など）。parts[1:] は marker の後ろ断片
    # 後ろ断片を marker 付きに戻す
    segments: List[str] = []
    if parts[0].strip():
        segments.append(parts[0].strip())

    for p in parts[1:]:
        seg = (marker + p).strip()
        if seg:
            segments.append(seg)

    # segments を limit 以内になるように束ねる（基本は marker の直前で切れる）
    chunks: List[str] = []
    buf = ""

    def flush():
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip() + "\n")
        buf = ""

    for seg in segments:
        # seg 単体が limit を超える場合：ここは例外。seg を内部でさらに割る（でも marker は先頭維持）
        if len(seg) > limit:
            # まず buf を確定
            flush()
            # seg を無理やり割る
            j = 0
            while j < len(seg):
                chunks.append(seg[j : j + limit].strip() + "\n")
                j += limit
            continue

        # buf に足して limit を超えるなら、ここで切る（seg は新チャンクへ）
        if buf and (len(buf) + 1 + len(seg) > limit):
            flush()
            buf = seg
        else:
            buf = (buf + "\n" + seg) if buf else seg

    flush()
    return [c for c in chunks if c.strip()]



# =========================
# Streamlit UI
# =========================
st.set_page_config(
    page_title="📄 Word 解析 → 生成AI用中間テキスト",
    page_icon="📄",
    layout="wide",
)

# ============================================================
# バナー / ログイン（テンプレ準拠）
# ============================================================
render_banner_line_by_key("purple_light")

# ============================================================
# session_state keys（解析結果を rerun でも保持する）
# ============================================================
SS_TEXT = "word15_intermediate_text"
SS_STATS = "word15_stats"
SS_TXT_NAME = "word15_txt_name"
SS_SOURCE = "word15_source_filename"



#st.title("📄 Word 解析 → 生成AI入力用テキスト生成")

# --- Inbox保存のためログイン必須 ---
sub = require_login(st)
if not sub:
    st.stop()
left, right = st.columns([2, 1])
with left:
    st.title("📄 Word 解析")
with right:
    st.success(f"✅ ログイン中: **{sub}**")


subtitle("生成AI入力用テキスト生成")

st.caption("Word書類の文章校正を行う前処理として，Word書類をAIが読めるようにした中間テキストファイルを作成します．"
           "inboxに対応していますので，作成された中間ファイルをinboxに保存して，文章校正に進むことができます．"
           "Word書類の字数が多い時は，中間ファイルは30,000字程度に区切った複数のファイルが作成されます．")

st.caption("オプションは原則デフォルトで問題ありません．")

render_word_analysis_help_expander()


if not HAS_DOCX:
    st.error("python-docx がインポートできませんでした。`python-docx` をインストールしてください。")
    st.stop()

# --- サイドバー設定 ---
with st.sidebar:
    st.header("🔧 オプション")
    st.caption("「出力スタイル」は，続けて「文章校正」を行う時は「標準」で使用してくだい．")

    # 出力スタイル選択（簡素 / 標準 / 詳細）
    output_mode_label = st.radio(
        "出力スタイル",
        options=["簡素", "標準", "詳細"],
        index=1,  # デフォルト: 簡素
        horizontal=True,
        help=(
            "簡素：プレーン寄り\n"
            "標準：見出し/表などを読みやすく整形（見出し候補を <ここから見出し> で括る）\n"
            "詳細：従来の === HEADING[...] === 等のマーカー付き"
        ),
    )

    if output_mode_label == "簡素":
        output_mode = "simple"
    elif output_mode_label == "標準":
        output_mode = "standard"
    else:
        output_mode = "detailed"

    st.caption(
            "「この章の章番号」は，1のまま使用してください"
        )
    base_chapter = st.number_input(
        "この章の章番号 (base_chapter)",
        min_value=1,
        max_value=50,
        value=1,
        step=1,
        help="見出しIDの先頭に付ける章番号です（例: 3 → HEADING[3-1-2]）。",
    )

    st.caption(
        "「結合セルの扱い」は，続けて「文章校正」を行う時は「横結合セルを<同左>にする」で使用してくだい．"
    )

    # --- 表の結合セル処理の選択 ---
    merge_label = st.radio(
        "結合セルの扱い",
        options=["そのまま", "横結合セルを <同左> にする"],
        index=1,
        help="横方向に結合されているセルを <同左> で埋めることができます。",
    )
    use_same_left_placeholder = (merge_label == "横結合セルを <同左> にする")

     # --- Inboxへ送る時の分割上限（文字数）---
    st.caption(
        "「Inboxへ送る時の分割上限」は，続けて「文章校正」を行う時は30,000で使用してくだい．"
    )
    chunk_char_limit = st.slider(
        "📏 Inbox送信用 分割上限（文字数）",
        min_value=10000,
        max_value=50000,
        value=30000,     # デフォルト 30000
        step=5000,
        help="「<ここから見出し>」の直前で切って、1ファイルがこの文字数を超えないように分割します。",
    )
   


uploaded_file = st.file_uploader("Word ファイル（.docx）をアップロードしてください", type=["docx"])

col_btn1, _ = st.columns([1, 3])
with col_btn1:
    run = st.button("🔍 解析して中間テキストを生成", type="primary")


if uploaded_file is None:
    st.info("まず .docx ファイルをアップロードしてください。")
    st.stop()

# 解析結果が既に session_state にあれば、run=False でも表示できるようにする
has_cached = bool(st.session_state.get(SS_TEXT)) and (st.session_state.get(SS_SOURCE) == uploaded_file.name)

if (not run) and (not has_cached):
    st.stop()

# =========================
# 解析本体
# =========================
try:
    src_doc = Document(uploaded_file)
except Exception as e:
    st.error(f"Word ファイルの読み込みに失敗しました: {e}")
    st.stop()

# 解析済みキャッシュがあるならそれを使い、無ければ run で解析する
has_cached = bool(st.session_state.get(SS_TEXT)) and (st.session_state.get(SS_SOURCE) == uploaded_file.name)

if run or (not has_cached):
    with st.status("解析中です…", expanded=False) as status:
        intermediate_text, stats = build_intermediate_text(
            src_doc,
            base_chapter=int(base_chapter),
            mode=output_mode,
        )
        status.update(label="解析完了", state="complete")

    # session_state に保持（rerun でも消えない）
    st.session_state[SS_TEXT] = intermediate_text
    st.session_state[SS_STATS] = stats
    st.session_state[SS_SOURCE] = uploaded_file.name

    base_name = uploaded_file.name.rsplit(".", 1)[0]

    if output_mode == "simple":
        mode_jp = "簡素"
    elif output_mode == "standard":
        mode_jp = "標準"
    else:
        mode_jp = "詳細"

    st.session_state[SS_TXT_NAME] = f"{base_name}_intermediate_{mode_jp}.txt"

else:
    intermediate_text = st.session_state[SS_TEXT]
    stats = st.session_state[SS_STATS]


# =========================
# 結果表示
# =========================
st.subheader("📊 分類結果（ブロック数）")

c1, c2, c3, c4 = st.columns(4)
c1.metric("見出し数", stats.get("heading", 0))
c2.metric("本文段落数", stats.get("paragraph", 0))
c3.metric("表ブロック数", stats.get("table", 0))
c4.metric("図ブロック数", stats.get("figure", 0))

st.markdown("---")

st.subheader("📝 生成された中間テキスト（先頭部分プレビュー）")
# ============================================================
# 中間テキストのファイル名（以降で共通利用）
# ============================================================
txt_name = st.session_state.get(SS_TXT_NAME) or "intermediate.txt"


st.code(intermediate_text[:3000], language="text")  # 長くなりすぎないように頭だけ

st.markdown("---")

# ============================================================
# 分割後の「生成ファイル名（予定）」一覧（ダウンロード前に表示）
# ============================================================
chunks_preview = split_text_by_heading_markers(intermediate_text, int(chunk_char_limit))

def _split_filename(name: str) -> tuple[str, str]:
    if "." in name:
        base, ext = name.rsplit(".", 1)
        return base, "." + ext
    return name, ""

# 解析時に決めた txt_name をベースに「予定ファイル名」を作る
base_fn_preview, ext_fn_preview = _split_filename(txt_name)

planned_names: List[str] = []
if chunks_preview:
    total_preview = len(chunks_preview)
    for idx in range(1, total_preview + 1):
        if total_preview == 1:
            fn = txt_name
        else:
            fn = f"{base_fn_preview}_part{idx:03d}{ext_fn_preview or '.txt'}"
        planned_names.append(fn)

    st.subheader("📄 生成された中間テキスト（分割後ファイル一覧）")
    st.caption("※ 文字数上限と <ここから見出し> の直前を基準に分割した場合の、保存・運用上のファイル名一覧です。")
    st.code("\n".join(planned_names), language="text")
else:
    st.subheader("📄 生成された中間テキスト（分割後ファイル一覧）")
    st.caption("※ テキストが空のため、分割ファイルは生成されません。")

st.markdown("---")

# =========================
# ダウンロード
# =========================
st.subheader("💾 ダウンロード")

# --- 中間テキスト (.txt) ---
buf_txt = intermediate_text.encode("utf-8")

st.download_button(
    label="⬇️ 中間テキスト（.txt）をダウンロード",
    data=buf_txt,
    file_name=txt_name,
    mime="text/plain; charset=utf-8",
)

# --- 画像 ZIP ---
img_zip_buf = collect_images_as_zip(src_doc)

# uploaded_file 由来の base 名を session_state から復元
_src = st.session_state.get(SS_SOURCE)
if _src:
    _base = _src.rsplit(".", 1)[0]
else:
    _base = "word_images"

zip_name = f"{_base}_images.zip"

st.download_button(
    label="⬇️ 画像ファイルを ZIP でダウンロード",
    data=img_zip_buf,
    file_name=zip_name,
    mime="application/zip",
)

# ★ rerunでも必ず定義されるようにここで再計算
if output_mode == "simple":
    mode_jp = "簡素"
elif output_mode == "standard":
    mode_jp = "標準"
else:
    mode_jp = "詳細"


# tags / origin（運用で検索・追跡しやすくする）
tags_json = '["word_analysis/intermediate"]'
origin = {
    "app": "text_studio_app",          # 必要なら実際のAPP名に置換
    "page": "15_word解析",
    "action": "word_intermediate_text",
    "source_filename": (uploaded_file.name if uploaded_file is not None else ""),
    "mode": mode_jp,
    "base_chapter": int(base_chapter),
}

if st.button("📥 中間テキストを Inbox に保存", type="primary"):
    try:
        # ★ 分割（<ここから見出し> の直前で切る）
        chunks = chunks_preview

        if not chunks:
            st.error("❌ 保存対象テキストが空です。")
            st.stop()

        base_fn, ext_fn = _split_filename(txt_name)

        total = len(chunks)
        saved_names: List[str] = []

        for idx, chunk in enumerate(chunks, start=1):
            if total == 1:
                fn = inbox_txt_name
            else:
                fn = f"{base_fn}_part{idx:03d}{ext_fn or '.txt'}"

            # origin に分割情報を入れる（追跡用）
            origin2 = dict(origin)
            origin2.update(
                {
                    "chunk_char_limit": int(chunk_char_limit),
                    "chunk_index": idx,
                    "chunk_total": total,
                }
            )

            ingest_to_inbox(
                projects_root=PROJECTS_ROOT,
                req=IngestRequest(
                    user_sub=sub,
                    filename=fn,
                    data=chunk.encode("utf-8"),
                    tags_json=tags_json,
                    origin=origin2,
                ),
            )
            saved_names.append(fn)

        if total == 1:
            st.success("Inbox に保存しました。")
        else:
            st.success(f"Inbox に保存しました（{total}分割）。")
            st.caption("保存ファイル名：")
            st.code("\n".join(saved_names), language="text")

    except InboxNotAvailable:
        st.error("❌ Inbox が存在しません。ストレージ接続を確認してください。")

    except QuotaExceeded as e:
        st.error(
            f"❌ 容量オーバーです。"
            f" 現在={e.current} / 追加={e.incoming} / 上限={e.quota}"
        )

    except IngestFailed as e:
        st.error(f"❌ Inbox への保存に失敗しました: {e}")


st.caption(
    "この中間テキストをそのまま GPT API に投げることで、"
    "見出し構造・表（JSON）・図情報を含んだ形で追加解析に使えます。"
)
