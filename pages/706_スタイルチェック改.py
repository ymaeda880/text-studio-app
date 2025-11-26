# -*- coding: utf-8 -*-
# pages/21_スタイルチェック改.py
#
# PDF（テキストPDF）をアップロードして、
# - 実際に使われているフォントの一覧（文字数ベース）
# - ベース明朝体・ベースゴシック体の推定
# - ベース以外のフォントを使用している行の抜き書き（<>でマーク）
# - 特定フォント（例: Arial）の使用例一覧
# を表示する Streamlit ページ
#
# ※ スキャンPDF（画像のみ）の場合はフォント情報が取得できません。

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from collections import Counter

import streamlit as st
import pandas as pd

try:
    import fitz  # PyMuPDF
except Exception as e:
    fitz = None

# ================================
# ヘルパー関数群
# ================================

def normalize_font_name(name: str) -> str:
    """
    PDF に埋め込まれたサブセットフォント名を正規化する。
    例: "ABCDEE+MS-Gothic" → "MS-Gothic"
    """
    if not name:
        return name
    if "+" in name:
        prefix, base = name.split("+", 1)
        # プレフィックスが 6 文字の大文字の場合、サブセット名とみなして削る
        if len(prefix) == 6 and prefix.isalpha() and prefix.isupper():
            return base
    return name


def collect_font_counts_pdf(doc: "fitz.Document") -> Tuple[Counter, bool]:
    """
    PDF 全体（全ページ）を走査して、
    フォント名（正規化後）ごとにテキストの文字数を集計する。

    戻り値:
        (font_counter, has_plain_text)
        font_counter: フォント別文字数
        has_plain_text: page.get_text("text") で何らかのテキストが取得できたかどうか
    """
    counter: Counter = Counter()
    has_plain_text = False

    for page in doc:
        # 素のテキストがあるかどうか（フォント情報とは別に見ておく）
        plain_text = page.get_text("text") or ""
        if plain_text.strip():
            has_plain_text = True

        info = page.get_text("rawdict")
        for block in info.get("blocks", []):
            # block["type"] == 0 がテキストブロック
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    font_raw = span.get("font")
                    text = span.get("text", "")
                    if not font_raw or not text:
                        continue
                    font_name = normalize_font_name(font_raw)
                    counter[font_name] += len(text)

    return counter, has_plain_text



def guess_base_fonts(counter: Counter) -> Tuple[Optional[str], Optional[str]]:
    """
    フォント名と文字数の Counter から、
    - 明朝系（"明朝", "Mincho" を含む）の中で最頻出のもの → ベース明朝
    - ゴシック系（"ゴシック", "Gothic", "ｺﾞｼｯｸ" を含む）の中で最頻出のもの → ベースゴシック
    を推定する。
    """
    base_mincho: Optional[str] = None
    base_gothic: Optional[str] = None

    for font, _cnt in counter.most_common():
        name = font or ""
        if base_mincho is None and ("明朝" in name or "Mincho" in name):
            base_mincho = font
        if base_gothic is None and ("ゴシック" in name or "Gothic" in name or "ｺﾞｼｯｸ" in name):
            base_gothic = font

    return base_mincho, base_gothic


@dataclass
class PdfLineExcerpt:
    page_num: int          # ページ番号（1始まり）
    location: str          # どこか（例: "1ページ ブロック2 行3"）
    marked_text: str       # <> でマーク済みのテキスト（1行分）
    fonts_in_line: list    # その行に現れたフォント一覧（重複除去前で OK）


def extract_lines_with_non_base_fonts(
    doc: "fitz.Document",
    base_mincho: Optional[str],
    base_gothic: Optional[str],
) -> List[PdfLineExcerpt]:
    """
    PDF から、ベース明朝・ベースゴシック以外のフォントを使っている行だけを抜き出す。

    ルール:
    - span のフォントが base_mincho / base_gothic / None のいずれにも該当しない場合、
      その span の text を <> で囲んでマーク。
    - 1行（line）にひとつでもベース外フォントがあれば、その行を抜き書きする。
    """
    results: List[PdfLineExcerpt] = []
    base_set = {f for f in (base_mincho, base_gothic, None)}

    for page_idx, page in enumerate(doc):
        info = page.get_text("rawdict")
        for block_idx, block in enumerate(info.get("blocks", [])):
            if block.get("type", 0) != 0:
                continue
            for line_idx, line in enumerate(block.get("lines", [])):
                fragments: List[str] = []
                fonts_in_line: List[str] = []
                has_other = False

                for span in line.get("spans", []):
                    font_raw = span.get("font")
                    text = span.get("text", "")
                    if not text:
                        continue
                    font_name = normalize_font_name(font_raw) if font_raw else None

                    if font_name and font_name not in fonts_in_line:
                        fonts_in_line.append(font_name)

                    if font_name not in base_set:
                        fragments.append(f"<{text}>")
                        has_other = True
                    else:
                        fragments.append(text)

                if has_other:
                    loc = f"{page_idx + 1}ページ ブロック{block_idx + 1} 行{line_idx + 1}"
                    results.append(
                        PdfLineExcerpt(
                            page_num=page_idx + 1,
                            location=loc,
                            marked_text="".join(fragments),
                            fonts_in_line=fonts_in_line,
                        )
                    )

    return results


@dataclass
class FontUsage:
    page_num: int
    location: str
    font_name: str
    text: str


def list_font_usage_for_font_pdf(doc: "fitz.Document", target_font: str) -> List[FontUsage]:
    """
    特定フォント名（正規化後で完全一致）を使っている span を列挙する。
    """
    usages: List[FontUsage] = []

    for page_idx, page in enumerate(doc):
        info = page.get_text("rawdict")
        for block_idx, block in enumerate(info.get("blocks", [])):
            if block.get("type", 0) != 0:
                continue
            for line_idx, line in enumerate(block.get("lines", [])):
                for span_idx, span in enumerate(line.get("spans", [])):
                    font_raw = span.get("font")
                    text = span.get("text", "")
                    if not font_raw or not text or not text.strip():
                        continue
                    font_name = normalize_font_name(font_raw)
                    if font_name == target_font:
                        loc = (
                            f"{page_idx + 1}ページ ブロック{block_idx + 1} "
                            f"行{line_idx + 1} / span{span_idx + 1}"
                        )
                        usages.append(
                            FontUsage(
                                page_num=page_idx + 1,
                                location=loc,
                                font_name=font_name,
                                text=text,
                            )
                        )

    return usages


# ================================
# Streamlit UI
# ================================

st.set_page_config(
    page_title="スタイルチェック改（PDFフォント解析）",
    page_icon="📄",
    layout="wide",
)

st.title("📄 スタイルチェック改（PDFフォント解析）")

if fitz is None:
    st.error("PyMuPDF (fitz) がインポートできませんでした。`pip install pymupdf` でインストールしてください。")
    st.stop()

st.markdown(
    """
PDF ファイル（テキストPDF）をアップロードして，実際に使用されているフォントを解析します。

- 使用フォントの一覧（文字数ベース）
- ベース明朝体・ベースゴシック体の推定
- ベース以外のフォントを用いた行の抜き書き（<> でマーク）
- 特定フォント（例: Arial）の使用例一覧

※ スキャンPDF（画像のみ）の場合はフォント情報が取得できません。
"""
)

uploaded_file = st.file_uploader("解析する PDF ファイルをアップロードしてください", type=["pdf"])

if uploaded_file is None:
    st.info("ファイルをアップロードすると解析結果が表示されます。")
    st.stop()

# PDF 読み込み（アップロードされたファイルは一度 bytes にしてから開く）
try:
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
except Exception as e:
    st.error(f"PDF ファイルの読み込みに失敗しました: {e}")
    st.stop()

st.success(f"ファイル読み込み完了: **{uploaded_file.name}**")

# ================================
# 1) 使用フォント一覧
# ================================
st.subheader("1) 実際に使用されているフォント一覧")

# PDF → フォントカウンタと has_plain_text を受け取る
font_counter, has_plain_text = collect_font_counts_pdf(doc)

# フォントデータが空だったときの分岐
if not font_counter:
    if not has_plain_text:
        st.warning("テキストがありません（スキャンPDFの可能性）")
    else:
        st.warning("テキストはありますが、フォント情報（span.font）が取得できないPDFです。")
else:
    total_chars = sum(font_counter.values())   # ← OK
    data = []
    for font, cnt in font_counter.most_common():
        data.append({"フォント名": font, "文字数": cnt})
    st.dataframe(pd.DataFrame(data))


    df_fonts = pd.DataFrame(data)
    st.dataframe(df_fonts, use_container_width=True)

# ================================
# 2) ベース明朝・ベースゴシックの推定
# ================================
st.subheader("2) ベース明朝体・ベースゴシック体の推定")

base_mincho, base_gothic = guess_base_fonts(font_counter)

col1, col2 = st.columns(2)
with col1:
    st.markdown("**推定ベース明朝体**")
    st.write(base_mincho if base_mincho else "（明朝系フォントが見つかりませんでした）")

with col2:
    st.markdown("**推定ベースゴシック体**")
    st.write(base_gothic if base_gothic else "（ゴシック系フォントが見つかりませんでした）")

st.caption("※ フォント名に『明朝 / Mincho』『ゴシック / Gothic / ｺﾞｼｯｸ』が含まれるもののうち、文字数が多いものをベースとみなしています。")

# ================================
# 3) ベース以外のフォントを使用している行
# ================================
st.subheader("3) ベース明朝・ゴシック以外のフォントを使用している行")

excerpts = extract_lines_with_non_base_fonts(doc, base_mincho, base_gothic)

if not excerpts:
    st.info("ベース明朝・ベースゴシック以外のフォントを使用している行は見つかりませんでした。")
else:
    st.write(f"検出された行数: **{len(excerpts)}**")
    st.caption("<> で囲まれている部分が、ベースフォント以外のフォントで書かれているテキストです。（1行単位）")

    for i, ex in enumerate(excerpts, 1):
        with st.expander(f"[{i}] {ex.location}", expanded=False):
            if ex.fonts_in_line:
                uniq_fonts = sorted(set(ex.fonts_in_line))
                st.markdown("**この行に現れるフォント**")
                st.write(", ".join(uniq_fonts))
            st.markdown("**テキスト（<> がベース外フォント）**")
            st.code(ex.marked_text, language="text")

# ================================
# 4) 特定フォントの使用例（例: Arial）
# ================================
st.subheader("4) 特定フォントの使用例")

if not font_counter:
    st.info("フォント情報がないため，特定フォントの使用例を表示できません。")
else:
    available_fonts = [f for f, _c in font_counter.most_common()]
    default_font = "Arial" if "Arial" in available_fonts else available_fonts[0]

    target_font = st.selectbox(
        "使用例を確認するフォントを選択してください（正規化後フォント名）",
        options=available_fonts,
        index=available_fonts.index(default_font),
    )

    usages = list_font_usage_for_font_pdf(doc, target_font)

    if not usages:
        st.info(f"フォント **{target_font}** はテキスト中では使用されていないようです。")
    else:
        st.write(f"フォント **{target_font}** の使用例: **{len(usages)} 箇所**（最大 50 件を表示）")

        rows = []
        for u in usages[:50]:
            text_short = u.text.replace("\n", " ")
            if len(text_short) > 60:
                text_short = text_short[:57] + "..."
            rows.append(
                {
                    "ページ": u.page_num,
                    "場所": u.location,
                    "フォント名": u.font_name,
                    "テキスト": text_short,
                }
            )
        df_usage = pd.DataFrame(rows)
        st.dataframe(df_usage, use_container_width=True)

st.caption("※ PDF のフォント名はサブセットやビューアのフォールバックの影響を受けるため、画面表示と完全には一致しない場合があります。")
