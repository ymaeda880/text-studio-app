# -*- coding: utf-8 -*-
# pages/510_word_styles解析.py
#
# Word(.docx) をアップロードして、
# - 中から styles.xml / numbering.xml を ZIP 経由で取り出す
# - styles.xml の内容を要約して DataFrame 化（スタイル一覧）
# - numbering.xml の内容を要約して DataFrame 化（番号定義一覧）
# - それらを 1 つの Excel (.xlsx) に複数シートで出力
# - 画面にもプレビュー表示
#
# まとめる内容の例：
#   styles.xml:
#     style_id, type, customStyle, name, basedOn, next, link,
#     qFormat, outlineLvl, numId, ilvl など
#
#   numbering.xml:
#     1) abstractNum_levels:
#        abstractNumId, ilvl, numFmt, lvlText, start, isLgl, tenths, ...
#     2) num_map:
#        numId, abstractNumId
#
# ついでに styles.xml / numbering.xml を「生の XML」としてもダウンロード可能にする。

from __future__ import annotations

from io import BytesIO
from typing import Dict, Any, List, Optional

import zipfile

import streamlit as st
import pandas as pd

try:
    from lxml import etree as ET  # python-docx でも使っている lxml をそのまま利用
    HAS_LXML = True
except Exception:
    HAS_LXML = False


# =========================
# 共通：.docx から XML パーツを取り出す
# =========================
def extract_xml_from_docx(docx_bytes: bytes, inner_path: str) -> Optional[bytes]:
    """
    .docx (ZIP) バイト列から、指定したパス（例: 'word/styles.xml'）の
    XML を取り出して bytes で返す。存在しなければ None。
    """
    with zipfile.ZipFile(BytesIO(docx_bytes), "r") as zf:
        namelist = zf.namelist()
        if inner_path not in namelist:
            return None
        with zf.open(inner_path) as f:
            return f.read()


# =========================
# styles.xml を DataFrame にまとめる
# =========================
def parse_styles_xml(xml_bytes: bytes) -> pd.DataFrame:
    """
    styles.xml の内容を要約して DataFrame にまとめる。

    1 行 = 1 <w:style> 要素

    列の例：
      style_id   : w:styleId
      type       : w:type
      customStyle: w:customStyle
      name       : w:name/@w:val
      basedOn    : w:basedOn/@w:val
      next       : w:next/@w:val
      link       : w:link/@w:val
      qFormat    : bool（<w:qFormat> があるか）
      outlineLvl : w:pPr/w:outlineLvl/@w:val
      numId      : w:pPr/w:numPr/w:numId/@w:val
      ilvl       : w:pPr/w:numPr/w:ilvl/@w:val
    """
    if not HAS_LXML:
        raise RuntimeError("lxml がインポートできませんでした。")

    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    rows: List[Dict[str, Any]] = []

    for style in root.findall("w:style", ns):
        # 属性
        style_id = style.get("{%s}styleId" % ns["w"], "")
        type_ = style.get("{%s}type" % ns["w"], "")
        custom_style = style.get("{%s}customStyle" % ns["w"], "")

        # 子要素
        def get_child_val(tag: str) -> str:
            el = style.find(tag, ns)
            if el is None:
                return ""
            return el.get("{%s}val" % ns["w"], "")

        name = get_child_val("w:name")
        based_on = get_child_val("w:basedOn")
        next_style = get_child_val("w:next")
        link_style = get_child_val("w:link")

        q_format = style.find("w:qFormat", ns) is not None

        # pPr 内の outlineLvl, numPr
        outline_lvl = ""
        num_id = ""
        ilvl = ""

        ppr = style.find("w:pPr", ns)
        if ppr is not None:
            outline_el = ppr.find("w:outlineLvl", ns)
            if outline_el is not None:
                outline_lvl = outline_el.get("{%s}val" % ns["w"], "")

            num_pr = ppr.find("w:numPr", ns)
            if num_pr is not None:
                num_id_el = num_pr.find("w:numId", ns)
                if num_id_el is not None:
                    num_id = num_id_el.get("{%s}val" % ns["w"], "")
                ilvl_el = num_pr.find("w:ilvl", ns)
                if ilvl_el is not None:
                    ilvl = ilvl_el.get("{%s}val" % ns["w"], "")

        rows.append(
            {
                "style_id": style_id,
                "type": type_,
                "customStyle": custom_style,
                "name": name,
                "basedOn": based_on,
                "next": next_style,
                "link": link_style,
                "qFormat": q_format,
                "outlineLvl": outline_lvl,
                "numId": num_id,
                "ilvl": ilvl,
            }
        )

    df = pd.DataFrame(rows)
    # 文字列系は str に揃えておく
    if not df.empty:
        for col in [
            "style_id",
            "type",
            "customStyle",
            "name",
            "basedOn",
            "next",
            "link",
            "outlineLvl",
            "numId",
            "ilvl",
        ]:
            df[col] = df[col].astype(str)

    return df


# =========================
# numbering.xml を DataFrame にまとめる
# =========================
def parse_numbering_xml(xml_bytes: bytes) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    numbering.xml の内容を要約して DataFrame を 2 つ返す。

    戻り値:
      (df_abs_levels, df_num_map)

    df_abs_levels: 抽象番号定義ごとのレベル情報
      abstractNumId, ilvl, numFmt, lvlText, start, isLgl, ...

    df_num_map: numId -> abstractNumId の対応表
      numId, abstractNumId
    """
    if not HAS_LXML:
        raise RuntimeError("lxml がインポートできませんでした。")

    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    abs_rows: List[Dict[str, Any]] = []
    map_rows: List[Dict[str, Any]] = []

    # --- abstractNum 部分 ---
    for abs_num in root.findall("w:abstractNum", ns):
        abs_id = abs_num.get("{%s}abstractNumId" % ns["w"], "")

        for lvl in abs_num.findall("w:lvl", ns):
            ilvl = lvl.get("{%s}ilvl" % ns["w"], "")

            numFmt_el = lvl.find("w:numFmt", ns)
            lvlText_el = lvl.find("w:lvlText", ns)
            start_el = lvl.find("w:start", ns)
            isLgl_el = lvl.find("w:isLgl", ns)

            numFmt = numFmt_el.get("{%s}val" % ns["w"], "") if numFmt_el is not None else ""
            lvlText = lvlText_el.get("{%s}val" % ns["w"], "") if lvlText_el is not None else ""
            start = start_el.get("{%s}val" % ns["w"], "") if start_el is not None else ""
            isLgl = bool(isLgl_el is not None)

            abs_rows.append(
                {
                    "abstractNumId": abs_id,
                    "ilvl": ilvl,
                    "numFmt": numFmt,
                    "lvlText": lvlText,
                    "start": start,
                    "isLgl": isLgl,
                }
            )

    # --- num (numId -> abstractNumId) 部分 ---
    for num in root.findall("w:num", ns):
        num_id = num.get("{%s}numId" % ns["w"], "")
        abs_ref_el = num.find("w:abstractNumId", ns)
        abs_ref = abs_ref_el.get("{%s}val" % ns["w"], "") if abs_ref_el is not None else ""
        map_rows.append(
            {
                "numId": num_id,
                "abstractNumId": abs_ref,
            }
        )

    df_abs = pd.DataFrame(abs_rows)
    if not df_abs.empty:
        for col in ["abstractNumId", "ilvl", "numFmt", "lvlText", "start"]:
            df_abs[col] = df_abs[col].astype(str)

    df_map = pd.DataFrame(map_rows)
    if not df_map.empty:
        for col in ["numId", "abstractNumId"]:
            df_map[col] = df_map[col].astype(str)

    return df_abs, df_map


# =========================
# Excel(.xlsx) を作成
# =========================
def make_excel(
    df_styles: Optional[pd.DataFrame],
    df_abs: Optional[pd.DataFrame],
    df_map: Optional[pd.DataFrame],
) -> bytes:
    """
    styles / numbering の DataFrame から 1 つの xlsx を生成して bytes を返す。

    シート構成:
      - "styles"            : スタイル一覧
      - "abstractNumLevels" : abstractNumId ごとのレベル定義
      - "numMap"            : numId -> abstractNumId 対応
    """
    buf = BytesIO()

    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        workbook = writer.book

        if df_styles is not None and not df_styles.empty:
            sheet_name = "styles"
            df_styles.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]
            text_fmt = workbook.add_format({"num_format": "@"})

            # 文字列扱いにしたい列をまとめて指定
            col_indices = {name: i for i, name in enumerate(df_styles.columns)}
            for col_name in ["style_id", "type", "customStyle", "name", "basedOn", "next", "link"]:
                if col_name in col_indices:
                    c = col_indices[col_name]
                    ws.set_column(c, c, 25, text_fmt)

        if df_abs is not None and not df_abs.empty:
            sheet_name = "abstractNumLevels"
            df_abs.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]
            text_fmt = workbook.add_format({"num_format": "@"})
            col_indices = {name: i for i, name in enumerate(df_abs.columns)}
            for col_name in ["abstractNumId", "ilvl", "numFmt", "lvlText", "start"]:
                if col_name in col_indices:
                    c = col_indices[col_name]
                    ws.set_column(c, c, 20, text_fmt)

        if df_map is not None and not df_map.empty:
            sheet_name = "numMap"
            df_map.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]
            text_fmt = workbook.add_format({"num_format": "@"})
            col_indices = {name: i for i, name in enumerate(df_map.columns)}
            for col_name in ["numId", "abstractNumId"]:
                if col_name in col_indices:
                    c = col_indices[col_name]
                    ws.set_column(c, c, 20, text_fmt)

    buf.seek(0)
    return buf.read()


# =========================
# Streamlit UI
# =========================
st.set_page_config(
    page_title="📑 Word styles.xml / numbering.xml 解析",
    page_icon="📑",
    layout="wide",
)

st.title("📑 Word styles.xml / numbering.xml 解析 → Excel 出力")

st.markdown(
    """
アップロードした Word (.docx) から

- `styles.xml`（スタイル定義）  
- `numbering.xml`（箇条書き・番号書式定義）  

を取り出して要約し、**Excel (.xlsx)** にまとめてダウンロードできるページです。

- styles.xml → スタイル一覧  
  - `style_id`, `type (w:type)`, `name`, `basedOn`, `outlineLvl`, `numId` など  
- numbering.xml →  
  - `abstractNumId` ごとのレベル設定（`ilvl`, `numFmt`, `lvlText`, `start`, …）  
  - `numId` → `abstractNumId` の対応表  

さらに、元の `styles.xml` / `numbering.xml` もそのまま XML としてダウンロードできます。
"""
)

if not HAS_LXML:
    st.error("lxml がインポートできませんでした。このページを使うには lxml が必要です。")
    st.stop()

uploaded = st.file_uploader("Word ファイル (.docx) をアップロードしてください", type=["docx"])

col_btn, _ = st.columns([1, 3])
with col_btn:
    run = st.button("🔍 解析を実行", type="primary", use_container_width=True)

if uploaded is None:
    st.info(".docx を選択してください。")
    st.stop()

if not run:
    st.stop()

# .docx を bytes で取得
docx_bytes = uploaded.read()

# =========================
# XML 抽出
# =========================
with st.status("styles.xml / numbering.xml を抽出中…", expanded=False) as status:
    styles_xml = extract_xml_from_docx(docx_bytes, "word/styles.xml")
    numbering_xml = extract_xml_from_docx(docx_bytes, "word/numbering.xml")
    status.update(label="XML 抽出完了", state="complete")

if styles_xml is None and numbering_xml is None:
    st.error("word/styles.xml も word/numbering.xml も見つかりませんでした。Word ファイルを確認してください。")
    st.stop()

# =========================
# styles.xml 解析
# =========================
df_styles: Optional[pd.DataFrame] = None
if styles_xml is not None:
    try:
        df_styles = parse_styles_xml(styles_xml)
    except Exception as e:
        st.error(f"styles.xml の解析に失敗しました: {e}")
else:
    st.warning("word/styles.xml が見つかりませんでした。styles シートは作成されません。")

# =========================
# numbering.xml 解析
# =========================
df_abs: Optional[pd.DataFrame] = None
df_map: Optional[pd.DataFrame] = None
if numbering_xml is not None:
    try:
        df_abs, df_map = parse_numbering_xml(numbering_xml)
    except Exception as e:
        st.error(f"numbering.xml の解析に失敗しました: {e}")
else:
    st.warning("word/numbering.xml が見つかりませんでした。numbering シートは作成されません。")

# =========================
# 結果表示
# =========================
st.markdown("---")
st.subheader("📋 styles.xml 要約（styles シート相当）")

if df_styles is not None and not df_styles.empty:
    st.dataframe(df_styles, use_container_width=True, hide_index=True)
else:
    st.info("styles.xml から有効なスタイルが取得できませんでした。")

st.markdown("---")
st.subheader("📋 numbering.xml 要約（abstractNumLevels / numMap シート相当）")

col_abs, col_map = st.columns(2)

with col_abs:
    st.markdown("**abstractNumLevels（抽象番号定義）**")
    if df_abs is not None and not df_abs.empty:
        st.dataframe(df_abs, use_container_width=True, hide_index=True)
    else:
        st.info("abstractNum (番号定義) が見つかりませんでした。")

with col_map:
    st.markdown("**numMap（numId → abstractNumId 対応）**")
    if df_map is not None and not df_map.empty:
        st.dataframe(df_map, use_container_width=True, hide_index=True)
    else:
        st.info("numId → abstractNumId の対応が見つかりませんでした。")

# =========================
# ダウンロード（Excel + 元 XML）
# =========================
st.markdown("---")
st.subheader("💾 ダウンロード")

base_name = uploaded.name.rsplit(".", 1)[0]

# Excel
excel_bytes = make_excel(df_styles, df_abs, df_map)
excel_name = f"{base_name}_styles_numbering_summary.xlsx"

st.download_button(
    label="⬇️ styles / numbering 要約 (Excel) をダウンロード",
    data=excel_bytes,
    file_name=excel_name,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

# raw styles.xml
if styles_xml is not None:
    st.download_button(
        label="⬇️ 元の styles.xml をダウンロード",
        data=styles_xml,
        file_name=f"{base_name}_styles.xml",
        mime="application/xml",
        use_container_width=True,
    )

# raw numbering.xml
if numbering_xml is not None:
    st.download_button(
        label="⬇️ 元の numbering.xml をダウンロード",
        data=numbering_xml,
        file_name=f"{base_name}_numbering.xml",
        mime="application/xml",
        use_container_width=True,
    )

st.caption(
    "この Excel から `style_id` / `type (w:type)` / `numId` / `ilvl` / `abstractNumId` などを確認すると、"
    "見出しスタイルと番号スタイルの対応関係をかなり安全に追えるようになります。"
)
