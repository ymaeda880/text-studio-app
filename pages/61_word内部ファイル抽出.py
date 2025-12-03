# -*- coding: utf-8 -*-
# pages/61_word内部ファイル抽出.py
#
# Word(.docx) をアップロードして、
# - .docx を ZIP として開きエントリ一覧を表示
# - word/document.xml（本文）、word/_rels/document.xml.rels（関連）、styles.xml、numbering.xml など
#   代表的な XML を「XML のまま」表示
# - 必要に応じて各 XML をダウンロードできるようにする
#
# OpenXML（WordprocessingML）の中身を直接確認したいとき用のページ。

from __future__ import annotations

from io import BytesIO
from typing import List, Optional
import zipfile
import xml.dom.minidom as minidom

import streamlit as st


# =========================
# ヘルパー関数
# =========================
def pretty_xml(xml_bytes: bytes, max_chars: int | None = 50000) -> str:
    """
    XML バイト列を UTF-8 とみなして文字列化し、minidom で整形して返す。
    - max_chars を超える場合は途中で切って「...(truncated)」を付ける。
    """
    try:
        text = xml_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # 念のため / 他のエンコーディングの場合は適当にデコード
        text = xml_bytes.decode("utf-8", errors="ignore")

    # サイズ制限（大きすぎる XML を全部表示すると重いので）
    truncated = False
    if max_chars is not None and len(text) > max_chars:
        text = text[:max_chars]
        truncated = True

    try:
        dom = minidom.parseString(text.encode("utf-8"))
        pretty = dom.toprettyxml(indent="  ")
    except Exception:
        # パースに失敗したらそのまま返す
        pretty = text

    if truncated:
        pretty += "\n\n... (truncated: original XML is longer than max_chars)"
    return pretty


def read_entry(zf: zipfile.ZipFile, name: str) -> Optional[bytes]:
    """
    ZIP から指定エントリを読み込んで bytes を返す。
    見つからなければ None。
    """
    try:
        with zf.open(name) as f:
            return f.read()
    except KeyError:
        return None


def list_entries(zf: zipfile.ZipFile) -> List[str]:
    """
    ZIP 内のファイル一覧を返す。
    """
    return zf.namelist()


# =========================
# Streamlit UI
# =========================
st.set_page_config(
    page_title="🧩 Word 内部XML解析",
    page_icon="🧩",
    layout="wide",
)

st.title("🧩 Word 内部XML解析（OpenXML Viewer）")

st.markdown(
    """
アップロードした Word(.docx) を **ZIP として開き**、内部の XML をそのまま表示します。

- `.docx` は ZIP の中に `word/document.xml` などの XML が入っています  
- `document.xml` … 本文（段落 `<w:p>`、表 `<w:tbl>`、図 `<w:drawing>` など）  
- `document.xml.rels` … 画像ファイル (`/word/media/image1.png` など) との関連  
- `styles.xml` … 段落スタイル・文字スタイル定義  
- `numbering.xml` … 箇条書き・段落番号の定義  

ここでは、それらを **XML のまま** 確認できるようにします。
"""
)

uploaded_file = st.file_uploader("Word ファイル（.docx）をアップロードしてください", type=["docx"])

col_btn1, _ = st.columns([1, 3])
with col_btn1:
    run = st.button("🔍 内部XMLを解析", type="primary", use_container_width=True)

if uploaded_file is None:
    st.info(".docx ファイルを選択してください。")
    st.stop()

if not run:
    st.stop()

# =========================
# .docx を ZIP としてオープン
# =========================
data = uploaded_file.getvalue()
buf = BytesIO(data)

try:
    zf = zipfile.ZipFile(buf, "r")
except Exception as e:
    st.error(f".docx を ZIP として開くのに失敗しました: {e}")
    st.stop()

entries = list_entries(zf)

st.subheader("📁 ZIP エントリ一覧（.docx 内部）")
st.caption("※ Word の中身はこのようなファイルの集合になっています。")

st.code("\n".join(entries), language="text")

st.markdown("---")

# =========================
# 代表的な XML の表示パネル
# =========================

# --- document.xml (本文) ---
st.subheader("📝 word/document.xml（本文）")

doc_xml_bytes = read_entry(zf, "word/document.xml")
if doc_xml_bytes is None:
    st.warning("word/document.xml が見つかりませんでした。")
else:
    pretty = pretty_xml(doc_xml_bytes)

    st.caption(
        "本文・段落・表・図などの本体が入っている XML です。\n"
        "- 段落: `<w:p>`\n"
        "- 表: `<w:tbl>` / `<w:tr>` / `<w:tc>`\n"
        "- 画像: `<w:drawing>`（中に `<pic:pic>` など）"
    )

    with st.expander("📄 document.xml を表示（長い場合は途中まで）", expanded=True):
        st.code(pretty, language="xml")

    # ダウンロードボタン
    st.download_button(
        label="⬇️ document.xml をダウンロード",
        data=doc_xml_bytes,
        file_name="document.xml",
        mime="application/xml",
        use_container_width=True,
    )

st.markdown("---")

# --- document.xml.rels (本文からの関連付け) ---
st.subheader("🔗 word/_rels/document.xml.rels（関連情報）")

rels_bytes = read_entry(zf, "word/_rels/document.xml.rels")
if rels_bytes is None:
    st.info("word/_rels/document.xml.rels が見つかりませんでした。画像などを使っていない可能性があります。")
else:
    pretty_rels = pretty_xml(rels_bytes)

    st.caption(
        "画像ファイル（`word/media/image1.png` など）や他のパーツへの関連付け情報です。\n"
        "画像を埋め込むと、`document.xml` からここにある `Relationship Id` (`rIdX`) を参照する形になります。"
    )

    with st.expander("📎 document.xml.rels を表示", expanded=False):
        st.code(pretty_rels, language="xml")

    st.download_button(
        label="⬇️ document.xml.rels をダウンロード",
        data=rels_bytes,
        file_name="document.xml.rels",
        mime="application/xml",
        use_container_width=True,
    )

st.markdown("---")

# --- styles.xml (スタイル定義) ---
st.subheader("🎨 word/styles.xml（スタイル定義）")

styles_bytes = read_entry(zf, "word/styles.xml")
if styles_bytes is None:
    st.info("word/styles.xml が見つかりませんでした。")
else:
    pretty_styles = pretty_xml(styles_bytes)

    st.caption(
        "段落スタイル・文字スタイルなどが定義されている XML です。\n"
        "たとえば、`Caption` スタイルや `見出し 1` などの定義がここにあります。"
    )

    with st.expander("🎨 styles.xml を表示", expanded=False):
        st.code(pretty_styles, language="xml")

    st.download_button(
        label="⬇️ styles.xml をダウンロード",
        data=styles_bytes,
        file_name="styles.xml",
        mime="application/xml",
        use_container_width=True,
    )

st.markdown("---")

# --- numbering.xml (箇条書き・番号) ---
st.subheader("🔢 word/numbering.xml（箇条書き・段落番号）")

numbering_bytes = read_entry(zf, "word/numbering.xml")
if numbering_bytes is None:
    st.info("word/numbering.xml が見つかりませんでした。箇条書きや段落番号が使われていないと生成されない場合もあります。")
else:
    pretty_numbering = pretty_xml(numbering_bytes)

    st.caption(
        "箇条書き・段落番号のスタイルが定義されている XML です。\n"
        "「第1章」「1.1」などの番号付き見出しの定義もここに関係します。"
    )

    with st.expander("🔢 numbering.xml を表示", expanded=False):
        st.code(pretty_numbering, language="xml")

    st.download_button(
        label="⬇️ numbering.xml をダウンロード",
        data=numbering_bytes,
        file_name="numbering.xml",
        mime="application/xml",
        use_container_width=True,
    )

st.markdown("---")

# --- media フォルダの一覧（画像ファイルなど） ---
st.subheader("🖼️ word/media/（画像など）")

media_entries = [name for name in entries if name.startswith("word/media/")]
if not media_entries:
    st.info("word/media/ 以下にファイルが見つかりませんでした。画像が含まれていない可能性があります。")
else:
    st.caption("埋め込まれている画像ファイルなどの一覧です。")
    st.code("\n".join(media_entries), language="text")

    # 代表的な画像を1つダウンロードできるようにしておく（必要であれば）
    first_media = media_entries[0]
    media_bytes = read_entry(zf, first_media)
    if media_bytes is not None:
        st.download_button(
            label=f"⬇️ 最初のメディアファイルをダウンロード ({first_media.split('/')[-1]})",
            data=media_bytes,
            file_name=first_media.split("/")[-1],
            mime="application/octet-stream",
            use_container_width=True,
        )

st.caption(
    "※ XML のタグ `<w:p>`（段落）、`<w:tbl>`（表）、`<w:drawing>`（図）などを直接確認すると、"
    "WordprocessingML の挙動を細かく追いやすくなります。"
)
