# -*- coding: utf-8 -*-
# pages/62_word段落リスト.py
#
# Word(.docx) をアップロードすると，
# 1) document.xml のブロック（段落・表・図）を順番どおりに走査して DF 化（blocks）
# 2) styles.xml に相当するスタイル一覧を DF 化（styles）
# 3) numbering.xml に相当する番号定義を DF 化（numbering）
# し，3つを 1 つの Excel (.xlsx) に
# - blocks シート
# - styles シート
# - numbering シート
# として書き出すツール。
#
# blocks シート（document.xml）の主な列：
# - index        : 文書中のブロック順（1〜）
# - type         : "paragraph" / "table" / "figure"
# - text         : ブロックのテキスト（段落本文 / 表タイトル / 図キャプション）
# - text_trim    : text の strip()
# - style        : 段落スタイル名（paragraph / figure のみ）
# - is_heading   : 見出し判定（paragraph のみ）
# - heading_level: 見出しレベル（detect_heading_level）（paragraph のみ）
# - outlineLvl   : w:outlineLvl（paragraph のみ）
# - numbering    : 段落番号(numPr)の有無（paragraph のみ）
# - numId / ilvl : numbering の詳細（paragraph のみ）
# - bookmark     : bookmarkStart の name（;区切り）（paragraph / figure）
# - rows / cols  : 表の行数・列数（table のみ）
# - image_files  : 図キャプションに紐づく画像ファイル名（figure のみ）
# - json         : 表の JSON（table のみ）
#
# styles シート（styles.xml 相当）の主な列：
# - style_id         : スタイルID（document.xml 側の w:pStyle w:val に対応）
# - name             : スタイル名（UI 表示名：見出し 1 / Normal など）
# - type             : paragraph / character / table / … の種別
# - based_on         : 継承元スタイルID（あれば）
# - next             : 次のスタイルID（段落終了後に適用されるスタイル）
# - is_builtin       : 組み込みスタイルかどうか
# - is_quick_style   : クイックスタイルかどうか
# - outlineLvl       : w:outlineLvl（段落スタイルの見出しレベル）
# - numId / ilvl     : 段落番号(numPr)の設定（あれば）
# - xml              : スタイル要素の生 XML（styles.xml の該当部分）
#
# numbering シート（numbering.xml 相当）の主な列：
# - abstractNumId : 抽象番号スタイルID
# - numIds       : この abstractNum を使う numId の一覧（カンマ区切り）
# - ilvl         : レベル番号（0,1,2,...）
# - numFmt       : 番号形式（decimal / upperLetter / lowerRoman など）
# - lvlText      : 表示形式（例：「第%1章」「%1.%2」）
# - start        : 開始番号
# - lvlJc        : 揃え（left / center / right）

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
from typing import Dict, Any, List
import re  # ★ 追加

import pandas as pd
import streamlit as st

# ===== プロジェクトルート =====
PROJECTS_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))

# ===== python-docx =====
try:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    from docx.oxml.ns import qn
    from docx.enum.style import WD_STYLE_TYPE
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False

# ===== 自作ライブラリ =====
from lib.word_analysis.blocks import iter_block_items, classify_paragraph
from lib.word_analysis.headings import is_heading_paragraph, detect_heading_level
from lib.word_analysis.tables import table_to_json
from lib.word_analysis.images import get_image_filenames_from_paragraph


# -------------------------------------------------------------------
# document.xml 側：XML 情報抽出補助
# -------------------------------------------------------------------
def get_outline_level(p: Paragraph):
    """w:outlineLvl からアウトラインレベルを取得（なければ None）"""
    try:
        elems = p._element.xpath("./w:pPr/w:outlineLvl")
        if elems:
            val = elems[0].get(qn("w:val"))
            return int(val)
    except Exception:
        pass
    return None


def get_numbering_info(p: Paragraph):
    """
    段落に numbering (w:numPr) が付いているかどうかと，
    numId, ilvl を返す。
    """
    has_num = False
    num_id = None
    ilvl = None
    try:
        num_pr = p._element.xpath("./w:pPr/w:numPr")
        if num_pr:
            has_num = True
            num_id_e = p._element.xpath("./w:pPr/w:numPr/w:numId")
            if num_id_e:
                num_id = num_id_e[0].get(qn("w:val"))
            ilvl_e = p._element.xpath("./w:pPr/w:numPr/w:ilvl")
            if ilvl_e:
                v = ilvl_e[0].get(qn("w:val"))
                if v is not None:
                    ilvl = int(v)
    except Exception:
        pass
    return has_num, num_id, ilvl


def get_bookmarks(p: Paragraph):
    """段落内の bookmarkStart の name を ';' 区切りで取得"""
    names = []
    try:
        elems = p._element.xpath("./w:bookmarkStart")
        for e in elems:
            nm = e.get(qn("w:name"))
            if nm:
                names.append(nm)
    except Exception:
        pass
    return ";".join(names)

# 段落の XML から SEQ/STYLEREF を見る補助関数
def _instr_text(p: Paragraph) -> str:
    """段落内の w:instrText を全部つなげた文字列を返す（SEQ / STYLEREF 判定用）"""
    try:
        elems = p._element.xpath(".//w:instrText")
        return " ".join(e.text or "" for e in elems)
    except Exception:
        return ""
    
#「caption かどうか」を document.xml ベースで判定する関数
def detect_caption_kind(p: Paragraph) -> str | None:
    """
    document.xml の情報から caption 種別を推定する。

    戻り値:
        "figure_caption" / "table_caption" / None
    """
    text = (p.text or "").strip()
    style_name = (p.style.name if p.style is not None else "") or ""
    instr = _instr_text(p)

    # --- SEQ フィールド優先（Word 自動番号） ---
    # 例: SEQ 図, SEQ Figure, SEQ 表, SEQ Table
    if re.search(r"\bSEQ\s*(図|Figure|Fig|Table)", instr):
        # 図か表かは text/スタイルから切り分け
        if text.startswith("表") or "表" in style_name or "Table" in style_name:
            return "table_caption"
        else:
            return "figure_caption"

    # --- テキスト先頭のラベルで判定（手打ち対応） ---
    if re.match(r"^(図|Figure|Fig\.?)\s*\d", text):
        return "figure_caption"
    if re.match(r"^表\s*\d", text) or re.match(r"^Table\s*\d", text, re.IGNORECASE):
        return "table_caption"

    # --- スタイル名による判定 ---
    if any(k in style_name for k in ["図", "Figure", "キャプション", "Caption"]):
        return "figure_caption"
    if any(k in style_name for k in ["表", "Table"]):
        return "table_caption"

    return None
 
# -------------------------------------------------------------------
# 1) document.xml 側：Paragraph + Table + Figure を DF 化
# -------------------------------------------------------------------
def get_table_style(tbl):
    """table に style がある場合のみ取得し、無ければ空白を返す"""
    tblPr = tbl._element.tblPr
    if tblPr is None:
        return ""
    style_el = tblPr.find(qn("w:tblStyle"))
    if style_el is not None:
        return style_el.get(qn("w:val")) or ""
    return ""


def build_block_dataframe(doc: Document) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    pending_table_caption: Paragraph | None = None

    for idx, block in enumerate(iter_block_items(doc), start=1):

        if isinstance(block, Paragraph):
            text = block.text or ""
            text_trim = text.strip()
            style_name = ""
            try:
                if block.style is not None and block.style.name:
                    style_name = block.style.name
            except Exception:
                style_name = ""

            # ★ まず画像を持っているかどうかを見る
            img_files = get_image_filenames_from_paragraph(block)
            has_image = bool(img_files)

            # ★ 既存のカテゴリ判定（toc / figure_caption / table_caption / body など）
            cat = classify_paragraph(block)

            # 1) 図キャプション（「図3.1.1-1 …」みたいな行）
            if cat == "figure_caption":
                rows.append(
                    {
                        "index": idx,
                        "type": "figure",
                        "type_detail": "figure_caption",
                        "text": text,
                        "text_trim": text_trim,
                        "style": style_name,
                        "is_heading": None,
                        "heading_level": None,
                        "outlineLvl": None,
                        "numbering": None,
                        "numId": None,
                        "ilvl": None,
                        "bookmark": get_bookmarks(block),
                        "rows": None,
                        "cols": None,
                        "image_files": ", ".join(img_files) if img_files else "",
                        "json": None,
                    }
                )
                pending_table_caption = None
                continue

            # 2) 表キャプション（「表3.1.1-1 …」）
            if cat == "table_caption":
                pending_table_caption = block  # 後続の Table と結びつける用
                # blocks シートにも 1 行出したいなら、ここで rows.append してよい
                rows.append(
                    {
                        "index": idx,
                        "type": "paragraph",
                        "type_detail": "table_caption",
                        "text": text,
                        "text_trim": text_trim,
                        "style": style_name,
                        "is_heading": False,
                        "heading_level": None,
                        "outlineLvl": None,
                        "numbering": None,
                        "numId": None,
                        "ilvl": None,
                        "bookmark": get_bookmarks(block),
                        "rows": None,
                        "cols": None,
                        "image_files": "",
                        "json": None,
                    }
                )
                continue

            # 3) 図本体（画像を含んでいるがキャプションではない段落）
            if has_image:
                rows.append(
                    {
                        "index": idx,
                        "type": "figure",
                        "type_detail": "figure_body",  # ★ 図本体
                        "text": text,
                        "text_trim": text_trim,
                        "style": style_name,
                        "is_heading": False,
                        "heading_level": None,
                        "outlineLvl": None,
                        "numbering": None,
                        "numId": None,
                        "ilvl": None,
                        "bookmark": get_bookmarks(block),
                        "rows": None,
                        "cols": None,
                        "image_files": ", ".join(img_files),
                        "json": None,
                    }
                )
                pending_table_caption = None
                continue

            # 4) それ以外（普通の段落・見出しなど）
            is_hd = is_heading_paragraph(block)
            heading_level = detect_heading_level(block) if is_hd else None
            outline_lvl = get_outline_level(block)
            has_num, num_id, ilvl = get_numbering_info(block)
            bookmarks = get_bookmarks(block)

            # --- type_detail を決める（今回の修正ポイントはここだけ） ---
            if not text_trim:
                type_detail = "empty"
            elif is_hd:
                type_detail = "heading"
            else:
                type_detail = cat

            rows.append(
                {
                    "index": idx,
                    "type": "paragraph",
                    "type_detail": type_detail,
                    "text": text,
                    "text_trim": text_trim,
                    "style": style_name,
                    "is_heading": is_hd,
                    "heading_level": heading_level,
                    "outlineLvl": outline_lvl,
                    "numbering": has_num,
                    "numId": num_id,
                    "ilvl": ilvl,
                    "bookmark": bookmarks,
                    "rows": None,
                    "cols": None,
                    "image_files": "",
                    "json": None,
                }
            )

        elif isinstance(block, Table):
            # （今の Table の処理はそのままでOK）
            tbl_json = table_to_json(block, pending_table_caption)
            cells = tbl_json.get("cells", [])
            n_rows = len(cells)
            n_cols = len(cells[0]) if cells else 0
            title = tbl_json.get("title", "")

            rows.append(
                {
                    "index": idx,
                    "type": "table",
                    "type_detail": "table",
                    "text": "",
                    "text_trim": "",
                    "style": get_table_style(block),
                    "is_heading": None,
                    "heading_level": None,
                    "outlineLvl": None,
                    "numbering": None,
                    "numId": None,
                    "ilvl": None,
                    "bookmark": None,
                    "rows": n_rows,
                    "cols": n_cols,
                    "image_files": None,
                    "json": tbl_json,
                }
            )
            pending_table_caption = None

    return pd.DataFrame(rows)



# -------------------------------------------------------------------
# 2) styles.xml 相当：スタイル一覧を DF 化
# -------------------------------------------------------------------
def build_styles_dataframe(doc: Document) -> pd.DataFrame:
    """
    doc.styles からスタイル情報を抜き出して DataFrame にする。
    実質的に styles.xml の内容を表形式で見られるようにする。
    """
    rows: List[Dict[str, Any]] = []

    for style in doc.styles:
        try:
            style_id = style.style_id
        except Exception:
            style_id = None

        try:
            name = style.name
        except Exception:
            name = None

        try:
            style_type = getattr(style.type, "name", str(style.type))
        except Exception:
            style_type = None

        try:
            based_on = style.based_on.style_id if style.based_on is not None else None
        except Exception:
            based_on = None

        try:
            next_style = style.next.style_id if style.next is not None else None
        except Exception:
            next_style = None

        try:
            is_builtin = style.builtin
        except Exception:
            is_builtin = None

        try:
            is_quick_style = style.quick_style
        except Exception:
            is_quick_style = None

        outline_lvl = None
        num_id = None
        ilvl = None
        try:
            if style.type == WD_STYLE_TYPE.PARAGRAPH:
                el = style.element
                elems = el.xpath(".//w:pPr/w:outlineLvl")
                if elems:
                    v = elems[0].get(qn("w:val"))
                    if v is not None:
                        outline_lvl = int(v)

                num_pr = el.xpath(".//w:pPr/w:numPr")
                if num_pr:
                    num_id_e = el.xpath(".//w:pPr/w:numPr/w:numId")
                    if num_id_e:
                        num_id = num_id_e[0].get(qn("w:val"))
                    ilvl_e = el.xpath(".//w:pPr/w:numPr/w:ilvl")
                    if ilvl_e:
                        v2 = ilvl_e[0].get(qn("w:val"))
                        if v2 is not None:
                            ilvl = int(v2)
        except Exception:
            pass

        try:
            xml_str = style.element.xml
        except Exception:
            xml_str = None

        rows.append(
            {
                "style_id": style_id,
                "name": name,
                "type": style_type,
                "based_on": based_on,
                "next": next_style,
                "is_builtin": is_builtin,
                "is_quick_style": is_quick_style,
                "outlineLvl": outline_lvl,
                "numId": num_id,
                "ilvl": ilvl,
                "xml": xml_str,
            }
        )

    return pd.DataFrame(rows)


# -------------------------------------------------------------------
# 3) numbering.xml 相当：番号定義を DF 化
# -------------------------------------------------------------------
def build_numbering_dataframe(doc: Document) -> pd.DataFrame:
    """
    numbering.xml の内容を DataFrame にする。
    行は「abstractNumId × ilvl（レベル）」単位。
    blocks シートの numId / ilvl と突き合わせて使う想定。
    """
    rows: List[Dict[str, Any]] = []

    # numbering_part が無い文書もあるので防御的に
    try:
        numbering_root = doc.part.numbering_part.element
    except Exception:
        return pd.DataFrame()

    # ---- numId -> abstractNumId の対応表を作る ----
    numid_to_abs: Dict[str, str | None] = {}

    # <w:num> 要素（名前空間プレフィックスは使わず local-name() で取得）
    for num in numbering_root.xpath("./*[local-name()='num']"):
        # 属性は qn("w:numId") で Clark 記法の名前を指定
        num_id = num.get(qn("w:numId"))
        abs_id = None

        # <w:abstractNumId>
        abs_elems = num.xpath("./*[local-name()='abstractNumId']")
        if abs_elems:
            abs_id = abs_elems[0].get(qn("w:val"))

        if num_id is not None:
            numid_to_abs[num_id] = abs_id

    # abstractNumId -> numId リスト
    abs_to_numids: Dict[str, List[str]] = {}
    for num_id, abs_id in numid_to_abs.items():
        if abs_id is None:
            continue
        abs_to_numids.setdefault(abs_id, []).append(num_id)

    # ---- <w:abstractNum> ごとに <w:lvl> を展開 ----
    for absnum in numbering_root.xpath("./*[local-name()='abstractNum']"):
        abs_id = absnum.get(qn("w:abstractNumId"))
        num_ids = ",".join(abs_to_numids.get(abs_id, []))

        # 各レベル <w:lvl>
        for lvl in absnum.xpath("./*[local-name()='lvl']"):
            ilvl_raw = lvl.get(qn("w:ilvl"))
            try:
                ilvl = int(ilvl_raw) if ilvl_raw is not None else None
            except Exception:
                ilvl = None

            def _child_val(local_name: str):
                # 例: local_name="numFmt" なら <w:numFmt> の w:val
                elems = lvl.xpath(f"./*[local-name()='{local_name}']")
                if elems:
                    v = elems[0].get(qn("w:val"))
                    return v
                return None

            num_fmt = _child_val("numFmt")
            lvl_text = _child_val("lvlText")
            start = _child_val("start")
            lvl_jc = _child_val("lvlJc")

            rows.append(
                {
                    "abstractNumId": abs_id,
                    "numIds": num_ids,   # この abstractNum を使う numId 達（カンマ区切り）
                    "ilvl": ilvl,
                    "numFmt": num_fmt,
                    "lvlText": lvl_text,
                    "start": start,
                    "lvlJc": lvl_jc,
                }
            )

    return pd.DataFrame(rows)


# -------------------------------------------------------------------
# ★ NEW: blocks + styles + numbering を統合したビュー
# -------------------------------------------------------------------

def build_unified_view(
    df_blocks: pd.DataFrame,
    df_styles: pd.DataFrame,
    df_numbering: pd.DataFrame,
) -> pd.DataFrame:
    """
    blocks（document.xml）に対し，
    - style 名 → styles の情報
    - numId / ilvl → numbering の情報
    を突き合わせた統合ビューを返す。
    """
    if df_blocks.empty:
        return df_blocks.copy()

    df = df_blocks.copy()

    # ---- styles と結合（style 名 = name）----
    if not df_styles.empty:
        styles_sub = df_styles[
            ["style_id", "name", "type", "based_on", "next", "outlineLvl", "numId", "ilvl"]
        ].rename(
            columns={
                "type": "style_type",
                "based_on": "style_based_on",
                "next": "style_next",
                "outlineLvl": "style_outlineLvl",
                "numId": "style_numId",
                "ilvl": "style_ilvl",
            }
        )

        df = df.merge(
            styles_sub,
            how="left",
            left_on="style",   # blocks.style（表示名）
            right_on="name",   # styles.name（表示名）
        )

    # ---- numbering と結合（numId / ilvl）----
    if not df_numbering.empty:
        num = df_numbering.copy()

        # numIds: "1,7,8" のようなカンマ区切り → 1 行ずつに展開
        num["numId"] = num["numIds"].fillna("").astype(str).str.split(",")
        num = num.explode("numId")
        num["numId"] = num["numId"].str.strip()
        num = num[num["numId"] != ""]  # 空は除外

        num_sub = num[
            ["abstractNumId", "numId", "ilvl", "numFmt", "lvlText", "start", "lvlJc"]
        ].rename(
            columns={
                "ilvl": "num_ilvl",
                "numFmt": "num_numFmt",
                "lvlText": "num_lvlText",
                "start": "num_start",
                "lvlJc": "num_lvlJc",
            }
        )

        # ★ 型をそろえる（ここがポイント）
        # blocks 側
        df["numId"] = df["numId"].astype(str)
        df["ilvl"] = pd.to_numeric(df["ilvl"], errors="coerce").astype("Int64")

        # numbering 側
        num_sub["numId"] = num_sub["numId"].astype(str)
        num_sub["num_ilvl"] = pd.to_numeric(num_sub["num_ilvl"], errors="coerce").astype("Int64")

        df = df.merge(
            num_sub,
            how="left",
            left_on=["numId", "ilvl"],
            right_on=["numId", "num_ilvl"],
        )

    # numbering など結合処理が終わった後
    df = df.drop(columns=["bookmark"], errors="ignore")

    return df






# -------------------------------------------------------------------
# Streamlit UI
# -------------------------------------------------------------------
st.set_page_config(
    page_title="📑 Word ブロック & スタイル & 番号一覧",
    page_icon="📑",
    layout="wide",
)

st.title("📑 Word ブロック & スタイル & 番号一覧（document.xml / styles.xml / numbering.xml → Excel）")

st.markdown(
    """
Word ファイル（.docx）をアップロードすると，  

1. **document.xml のブロック（段落・表・図）** を登場順のまま一覧化した DataFrame（blocks）  
2. **styles.xml のスタイル定義** を一覧化した DataFrame（styles）  
3. **numbering.xml の番号定義** を一覧化した DataFrame（numbering）  

を作成し，**1つの Excel（.xlsx）に 3 シート（blocks / styles / numbering）** として出力します。

- blocks シート … 文書構造（どこにどの見出し・表・図があるか）
- styles シート … 各スタイル（Heading 1 など）の outlineLvl / numId 等
- numbering シート … numId / abstractNumId / ilvl ごとの「第%1章」「%1.%2」等の定義
"""
)

if not HAS_DOCX:
    st.error("python-docx が読み込めませんでした。`python-docx` をインストールしてください。")
    st.stop()

uploaded_file = st.file_uploader("Word ファイル（.docx）をアップロードしてください", type=["docx"])

col_btn, _ = st.columns([1, 3])
with col_btn:
    run = st.button("🔍 解析して一覧を作成", type="primary", use_container_width=True)

if uploaded_file is None:
    st.info(".docx ファイルを選択してください。")
    st.stop()

if not run:
    st.stop()

# -------------------------------------------------------------------
# 解析本体
# -------------------------------------------------------------------
try:
    src_doc = Document(uploaded_file)
except Exception as e:
    st.error(f"Word ファイルの読み込みに失敗しました: {e}")
    st.stop()

with st.status("document.xml（ブロック）を解析中…", expanded=False) as status:
    df_blocks = build_block_dataframe(src_doc)
    status.update(label="document.xml の解析完了", state="complete")

# 🔽 ここから追記：appendix 判定（blocks の type_detail を上書き）
if "type_detail" in df_blocks.columns:
    mask_appendix = (
        df_blocks["style"].astype(str).str.contains("資料|参考資料|付録", regex=True)
    )
    df_blocks.loc[mask_appendix, "type_detail"] = "appendix"
# 🔼 ここまで追記


with st.status("styles.xml 相当（スタイル）を解析中…", expanded=False) as status2:
    df_styles = build_styles_dataframe(src_doc)
    status2.update(label="styles の解析完了", state="complete")

with st.status("numbering.xml 相当（番号定義）を解析中…", expanded=False) as status3:
    df_numbering = build_numbering_dataframe(src_doc)
    status3.update(label="numbering の解析完了", state="complete")

# ★ NEW: 統合ビューを作成
with st.status("blocks / styles / numbering を統合中…", expanded=False) as status4:
    df_unified = build_unified_view(df_blocks, df_styles, df_numbering)
    status4.update(label="統合ビューの作成完了", state="complete")

st.subheader("📊 blocks シート用プレビュー（段落・表・図）")
st.caption(f"ブロック数: {len(df_blocks)}（段落・表・図の合計）")
st.dataframe(df_blocks, use_container_width=True, height=350)

st.subheader("🎨 styles シート用プレビュー（スタイル定義）")
st.caption(f"スタイル数: {len(df_styles)}")
st.dataframe(
    df_styles[["style_id", "name", "type", "based_on", "next", "outlineLvl", "numId", "ilvl"]],
    use_container_width=True,
    height=350,
)

st.subheader("🔢 numbering シート用プレビュー（番号定義）")
st.caption(f"numbering 定義数: {len(df_numbering)}")
if not df_numbering.empty:
    st.dataframe(df_numbering, use_container_width=True, height=250)
else:
    st.info("この文書には numbering.xml（自動番号）の定義が見つかりませんでした。")

# ★ NEW: 統合ビューのプレビュー
st.subheader("🧩 blocks × styles × numbering 統合ビュー（unified）")
st.caption("段落ごとにスタイル情報・番号定義を突き合わせた一覧です。")
if not df_unified.empty:
    # よく見る列を先頭に寄せて表示（必要に応じて調整）
    cols_pref = [
        "index", "type", "text_trim",
        "style", "is_heading", "heading_level", "outlineLvl",
        "numId", "ilvl",
        "style_id", "style_type", "style_outlineLvl",
        "abstractNumId", "num_numFmt", "num_lvlText",
    ]
    cols_show = [c for c in cols_pref if c in df_unified.columns] + [
        c for c in df_unified.columns if c not in cols_pref
    ]
    st.dataframe(df_unified[cols_show], use_container_width=True, height=400)
else:
    st.info("統合ビューに表示する行がありません。")

st.markdown("---")

# -------------------------------------------------------------------
# ダウンロード (Excel)
# -------------------------------------------------------------------
st.subheader("💾 Excel (.xlsx) でダウンロード")

base_name = uploaded_file.name.rsplit(".", 1)[0]
xlsx_name = f"{base_name}_blocks_styles_numbering.xlsx"

buf = BytesIO()
with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
    df_blocks.to_excel(writer, sheet_name="blocks", index=False)
    df_styles.to_excel(writer, sheet_name="styles", index=False)
    df_numbering.to_excel(writer, sheet_name="numbering", index=False)
    # ★ NEW: 統合ビューを追加
    df_unified.to_excel(writer, sheet_name="unified", index=False)
buf.seek(0)

st.download_button(
    label="⬇️ blocks / styles / numbering / unified（.xlsx）をダウンロード",
    data=buf,
    file_name=xlsx_name,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

st.caption("Excel 上で 3 シートと unified シートを突き合わせると，段落→スタイル→番号定義の流れが一望できます。")
