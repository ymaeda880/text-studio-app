# -*- coding: utf-8 -*-
# pages/512_word見出解析.py
#
# Word(.docx) をアップロードして、
# - styles.xml（= python-docx の doc.styles）を読み込む
# - numbering.xml を読み込んで numId / ilvl ごとの番号書式を取得
# - 段落ごとに「見出し / 本文」を XML 構造から判定
#   * 見出しレベル: スタイル名（Heading 1 / 見出し 1 等）、または outlineLvl
# - base_chapter を付けて見出しID（例: 3-1-1）を振る
# - 見出しとその間に挟まる本文を 1 行ずつ並べた表を作る
# - 表を Excel(.xlsx) でダウンロード
#   * heading_id は文字列形式で保存（3-1 → 3月1日 にならないように）
#   * 見出し用の表示列 heading_display を追加
#   * 各段落の num_id / num_ilvl / num_fmt / lvl_text / num_start も出力
#   * style_type（w:type 相当: paragraph / character など）も出力

from __future__ import annotations

from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple
import re

import streamlit as st
import pandas as pd

try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.enum.style import WD_STYLE_TYPE
    from docx.text.paragraph import Paragraph
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False


# =========================
# numbering.xml 解析
# =========================
def load_numbering_info(doc: Document) -> Dict[Tuple[str, str], Dict[str, Optional[str]]]:
    """
    numbering.xml を読み込み、
    (numId, ilvl) -> {numFmt, lvlText, start} の辞書を返す。

    例:
      key: ("1", "0")
      value: {"numFmt": "decimal", "lvlText": "%1", "start": "1"}
    """
    try:
        pkg = doc.part.package
        numbering_part = pkg.part_related_by(RT.NUMBERING)
    except Exception:
        return {}

    root = numbering_part.element  # BaseOxmlElement（名前空間付き）

    # 1) abstractNumId ごとにレベル定義を集める
    abs_map: Dict[str, Dict[str, Dict[str, Optional[str]]]] = {}

    for abs_num in root.xpath("./w:abstractNum"):
        abs_id = abs_num.get(qn("w:abstractNumId"))
        if not abs_id:
            continue

        lvl_map: Dict[str, Dict[str, Optional[str]]] = {}
        for lvl in abs_num.xpath("./w:lvl"):
            ilvl = lvl.get(qn("w:ilvl"))
            if ilvl is None:
                continue

            numFmt_el = lvl.xpath("./w:numFmt")
            lvlText_el = lvl.xpath("./w:lvlText")
            start_el = lvl.xpath("./w:start")

            numFmt = numFmt_el[0].get(qn("w:val")) if numFmt_el else None
            lvlText = lvlText_el[0].get(qn("w:val")) if lvlText_el else None
            start = start_el[0].get(qn("w:val")) if start_el else None

            lvl_map[ilvl] = {
                "numFmt": numFmt,
                "lvlText": lvlText,
                "start": start,
            }

        abs_map[abs_id] = lvl_map

    # 2) numId → abstractNumId を解決して (numId, ilvl) 辞書に展開
    result: Dict[Tuple[str, str], Dict[str, Optional[str]]] = {}

    for num in root.xpath("./w:num"):
        num_id = num.get(qn("w:numId"))
        if not num_id:
            continue

        abs_el = num.xpath("./w:abstractNumId")
        if not abs_el:
            continue

        abs_id = abs_el[0].get(qn("w:val"))
        if not abs_id:
            continue

        lvl_map = abs_map.get(abs_id)
        if not lvl_map:
            continue

        for ilvl, info in lvl_map.items():
            result[(num_id, ilvl)] = info

    return result


# =========================
# スタイル解析（styles.xml 相当）
# =========================
def build_style_info(doc: Document) -> Dict[str, Dict[str, Any]]:
    """
    doc.styles から「段落スタイル」の情報を集めて、
    style_id -> {
        style_name,
        style_type,      # w:type 相当 (paragraph / character / table ...)
        heading_level,
        is_heading,
        style_num_id,
        style_num_ilvl,
    } の dict を返す。
    """
    style_info: Dict[str, Dict[str, Any]] = {}

    for style in doc.styles:
        # 段落スタイルだけを見る（他のタイプも欲しければ条件を緩める）
        if style.type != WD_STYLE_TYPE.PARAGRAPH:
            continue

        style_id = style.style_id or ""
        style_name = style.name or ""

        # w:type 相当
        style_type = ""
        try:
            # WD_STYLE_TYPE.PARAGRAPH 等 → "paragraph"
            style_type = style.type.name.lower()
        except Exception:
            style_type = ""

        heading_level: Optional[int] = None

        # 1) スタイル名から推定（Heading 1 / 見出し 1 / HEADING 1 など）
        m = re.search(r"(Heading|見出し)\s*([1-9])", style_name, re.IGNORECASE)
        if m:
            try:
                heading_level = int(m.group(2))
            except Exception:
                heading_level = None

        # 2) outlineLvl から推定（0 ベースなので +1）
        if heading_level is None:
            try:
                elems = style._element.xpath("./w:pPr/w:outlineLvl")
                if elems:
                    val = elems[0].get(qn("w:val"))
                    if val is not None:
                        heading_level = int(val) + 1
            except Exception:
                pass

        # --- スタイルに紐づく numPr（番号設定）を読む ---
        style_num_id: Optional[str] = None
        style_num_ilvl: Optional[str] = None
        try:
            num_elems = style._element.xpath("./w:pPr/w:numPr")
            if num_elems:
                num_pr = num_elems[0]
                num_id_el = num_pr.xpath("./w:numId")
                if num_id_el:
                    style_num_id = num_id_el[0].get(qn("w:val"))
                ilvl_el = num_pr.xpath("./w:ilvl")
                if ilvl_el:
                    style_num_ilvl = ilvl_el[0].get(qn("w:val"))
        except Exception:
            pass

        is_heading = heading_level is not None

        style_info[style_id] = {
            "style_name": style_name,
            "style_type": style_type,
            "heading_level": heading_level,
            "is_heading": is_heading,
            "style_num_id": style_num_id,
            "style_num_ilvl": style_num_ilvl,
        }

    return style_info


# =========================
# 見出しID生成（3-1-2 など）
# =========================
def update_heading_counters(
    base_chapter: int, counters: List[int], heading_level: int
) -> str:
    """
    base_chapter と 見出しレベル（1〜4程度）から
    「3-1」「3-1-2」「3-1-2-1」等の ID を作る。
    """
    # level を 1〜4 にクリップし、0〜3 の index に変換
    idx = max(1, min(heading_level, 4)) - 1

    for i in range(len(counters)):
        if i < idx:
            continue        # 上位はそのまま
        elif i == idx:
            counters[i] += 1
        else:
            counters[i] = 0  # 下位はリセット

    parts = [str(base_chapter)]
    for c in counters:
        if c > 0:
            parts.append(str(c))
        else:
            break

    return "-".join(parts)


# =========================
# 段落 → num_id / num_ilvl を取得
# =========================
def get_paragraph_num_info(
    p: Paragraph,
    style_meta: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str]]:
    """
    段落 p から num_id / num_ilvl を取得する。

    優先順位:
      1) 段落自身の pPr/numPr/numId, ilvl
      2) スタイルに設定されている style_num_id, style_num_ilvl
      3) どちらも無ければ (None, None)
    """
    num_id: Optional[str] = None
    num_ilvl: Optional[str] = None

    # 1) 段落側
    try:
        num_pr_elems = p._element.xpath("./w:pPr/w:numPr")
        if num_pr_elems:
            num_pr = num_pr_elems[0]
            num_id_el = num_pr.xpath("./w:numId")
            if num_id_el:
                num_id = num_id_el[0].get(qn("w:val"))
            ilvl_el = num_pr.xpath("./w:ilvl")
            if ilvl_el:
                num_ilvl = ilvl_el[0].get(qn("w:val"))
    except Exception:
        pass

    # 2) スタイル側（段落に無かったときだけ）
    if num_id is None:
        num_id = style_meta.get("style_num_id")
    if num_ilvl is None:
        num_ilvl = style_meta.get("style_num_ilvl")

    return num_id, num_ilvl


# =========================
# 本体：見出し＋本文一覧の構築
# =========================
def analyze_headings_and_body(doc: Document, base_chapter: int) -> pd.DataFrame:
    """
    Document 全体を段落単位で走査し、
    - 見出し（styles.xml + outlineLvl から判定）
    - 本文（見出し以外の段落）
    を 1 行ずつ並べた DataFrame を返す。

    列の例:
      para_index      : 段落番号（0ベース）
      kind            : "見出し" / "本文"
      heading_level   : 見出しレベル（1〜、本文は None）
      heading_id      : "3-1-1" など（本文は直前の見出しIDを引き継ぐ／なければ空）
      style_id        : w:pStyle/@w:val
      style_name      : styles.xml 上のスタイル名（Heading 1 等）
      style_type      : w:type 相当 (paragraph / character ...)
      num_id          : 番号定義 ID（styles.xml または段落の numPr）
      num_ilvl        : 番号レベル (0,1,2 ...)
      num_fmt         : numbering.xml の numFmt
      lvl_text        : numbering.xml の lvlText
      num_start       : numbering.xml の start
      text            : 段落テキスト
      heading_display : 見出し行のみ、レベルに応じた表示用文字列
                        （本文行は ""）
    """
    style_info = build_style_info(doc)
    numbering_info = load_numbering_info(doc)

    rows: List[Dict[str, Any]] = []
    heading_counters = [0, 0, 0, 0]
    current_heading_id = ""  # 本文行に「どの見出しの配下か」を付けるため

    for idx, p in enumerate(doc.paragraphs):
        text = (p.text or "").strip()
        if not text:
            # 空行はスキップ
            continue

        style_id = ""
        style_name = ""
        style_type = ""
        heading_level: Optional[int] = None
        is_heading = False
        style_meta: Dict[str, Any] = {}

        if p.style is not None:
            style_id = p.style.style_id or ""
            style_name = p.style.name or ""
            style_meta = style_info.get(style_id, {})

            heading_level = style_meta.get("heading_level")
            is_heading = style_meta.get("is_heading", False)
            style_type = style_meta.get("style_type", "")

        # スタイルから heading_level が取れなければ、段落自身の outlineLvl を見る
        if not is_heading:
            try:
                elems = p._element.xpath("./w:pPr/w:outlineLvl")
                if elems:
                    val = elems[0].get(qn("w:val"))
                    if val is not None:
                        heading_level = int(val) + 1
                        is_heading = True
            except Exception:
                pass

        # num_id / num_ilvl を取得
        num_id, num_ilvl = get_paragraph_num_info(p, style_meta)

        # numbering.xml から numFmt / lvlText / start を引く
        num_fmt = None
        lvl_text = None
        num_start = None
        if num_id is not None and num_ilvl is not None:
            num_meta = numbering_info.get((str(num_id), str(num_ilvl)), {})
            num_fmt = num_meta.get("numFmt")
            lvl_text = num_meta.get("lvlText")
            num_start = num_meta.get("start")

        if is_heading and heading_level is not None:
            # 見出し
            heading_id = update_heading_counters(
                base_chapter=base_chapter,
                counters=heading_counters,
                heading_level=heading_level,
            )
            current_heading_id = heading_id

            # heading_display（Excel/確認用の「スタイル付き見出し」）
            lvl = heading_level
            indent_level = max(0, min(lvl - 1, 3))  # 0〜3
            indent = "　" * indent_level  # 全角スペース
            label = f"H{lvl}"
            heading_display = f"{indent}【{label}】 [{heading_id}] {text}"

            rows.append(
                {
                    "para_index": idx,
                    "kind": "見出し",
                    "heading_level": heading_level,
                    "heading_id": heading_id,
                    "style_id": style_id,
                    "style_name": style_name,
                    "style_type": style_type,
                    "num_id": num_id,
                    "num_ilvl": num_ilvl,
                    "num_fmt": num_fmt,
                    "lvl_text": lvl_text,
                    "num_start": num_start,
                    "text": text,
                    "heading_display": heading_display,
                }
            )
        else:
            # 本文
            rows.append(
                {
                    "para_index": idx,
                    "kind": "本文",
                    "heading_level": None,
                    "heading_id": current_heading_id,
                    "style_id": style_id,
                    "style_name": style_name,
                    "style_type": style_type,
                    "num_id": num_id,
                    "num_ilvl": num_ilvl,
                    "num_fmt": num_fmt,
                    "lvl_text": lvl_text,
                    "num_start": num_start,
                    "text": text,
                    "heading_display": "",
                }
            )

    df = pd.DataFrame(rows)

    # 文字列として扱いたい列を str 化
    if not df.empty:
        for col in [
            "heading_id",
            "style_id",
            "style_name",
            "style_type",
            "heading_display",
            "num_id",
            "num_ilvl",
            "num_fmt",
            "lvl_text",
            "num_start",
        ]:
            df[col] = df[col].astype(str)

    return df


# =========================
# Excel(.xlsx) 作成
# =========================
def dataframe_to_excel_bytes(df: pd.DataFrame) -> BytesIO:
    """
    DataFrame を xlsx に変換して BytesIO を返す。
    heading_id / heading_display / num 系列は文字列書式 (@) を指定して、
    Excel による日付変換などを防ぐ。
    """
    buf = BytesIO()

    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        sheet_name = "headings"
        df.to_excel(writer, index=False, sheet_name=sheet_name)

        workbook = writer.book
        worksheet = writer.sheets[sheet_name]

        text_format = workbook.add_format({"num_format": "@"})

        col_indices = {name: i for i, name in enumerate(df.columns)}

        for col_name, width in [
            ("heading_id", 20),
            ("heading_display", 60),
            ("num_id", 12),
            ("num_ilvl", 8),
            ("num_fmt", 12),
            ("lvl_text", 20),
            ("num_start", 10),
        ]:
            if col_name in col_indices:
                c = col_indices[col_name]
                worksheet.set_column(c, c, width, text_format)

    buf.seek(0)
    return buf


# =========================
# Streamlit UI
# =========================
st.set_page_config(
    page_title="🔎 Word 見出し解析 (styles.xml / numbering.xml 利用)",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 Word 見出し解析（styles.xml + numbering.xml + XML 構造ベース）")

st.markdown(
    """
アップロードした Word(.docx) から **styles.xml / numbering.xml と段落 XML を解析**し、

- 段落ごとに「見出し / 本文」を判定  
- 見出しには `base_chapter` から始まる ID（例: `3-1-1`）を付与  
- 各段落について番号設定（`num_id` / `num_ilvl`）と  
  numbering.xml の書式情報（`num_fmt` / `lvl_text` / `num_start`）も取得  
- 見出しと、その間にある本文を 1 行ずつ並べた表を作成  
- 結果を **Excel (.xlsx)** でダウンロード  

します。
"""
)

if not HAS_DOCX:
    st.error("python-docx がインポートできませんでした。`python-docx` をインストールしてください。")
    st.stop()

# ---- サイドバーオプション ----
with st.sidebar:
    st.header("🔧 オプション")
    base_chapter = st.number_input(
        "この章の章番号 (base_chapter)",
        min_value=1,
        max_value=50,
        value=3,
        step=1,
        help="例: 第3章なら 3 を指定 → 見出しID が 3-1, 3-1-1 などになります。",
    )
    st.caption(
        "※ 見出し判定は styles.xml のスタイル情報と outlineLvl、"
        "番号情報は numbering.xml の numId / ilvl 定義を用いています。"
    )

uploaded = st.file_uploader("Word ファイル（.docx）をアップロードしてください", type=["docx"])

col_btn, _ = st.columns([1, 3])
with col_btn:
    run = st.button("🔍 見出し解析を実行", type="primary", use_container_width=True)

if uploaded is None:
    st.info("まず .docx ファイルをアップロードしてください。")
    st.stop()

if not run:
    st.stop()

# =========================
# 解析本体
# =========================
try:
    doc = Document(uploaded)
except Exception as e:
    st.error(f"Word ファイルの読み込みに失敗しました: {e}")
    st.stop()

with st.status("解析中です…", expanded=False) as status:
    df = analyze_headings_and_body(doc, base_chapter=int(base_chapter))
    status.update(label="解析完了", state="complete")

if df.empty:
    st.warning("見出し／本文として出力できる段落が見つかりませんでした。")
    st.stop()

# =========================
# 結果表示
# =========================
st.subheader("📋 解析結果（表形式）")
st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("---")

# 見出しだけを抜き出して「スタイルに応じたプレビュー」を表示
st.subheader("📝 見出しプレビュー（Streamlit 見た目見出し）")

heading_df = df[df["kind"] == "見出し"].copy()

if heading_df.empty:
    st.info("見出しとして判定された段落がありません。")
else:
    for _, row in heading_df.iterrows():
        lvl = row.get("heading_level", None)
        hid = row.get("heading_id", "")
        text = row.get("text", "")

        if lvl == 1:
            prefix = "##"
        elif lvl == 2:
            prefix = "###"
        elif lvl == 3:
            prefix = "####"
        elif lvl == 4:
            prefix = "#####"
        else:
            prefix = "######"

        st.markdown(f"{prefix} [{hid}] {text}")

st.markdown("---")

# =========================
# Excel ダウンロード
# =========================
st.subheader("💾 Excel (.xlsx) ダウンロード")

base_name = uploaded.name.rsplit(".", 1)[0]
excel_bytes = dataframe_to_excel_bytes(df)
excel_name = f"{base_name}_heading_analysis.xlsx"

st.download_button(
    label="⬇️ 見出し＋本文＋番号情報 (Excel) をダウンロード",
    data=excel_bytes,
    file_name=excel_name,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

st.caption(
    "Excel では `heading_id` / `heading_display` / `num_id` / `num_ilvl` / "
    "`num_fmt` / `lvl_text` / `num_start` を文字列書式にしているので、"
    "3-1 が自動的に「3月1日」などの日付に変換されることを防げます。"
)
