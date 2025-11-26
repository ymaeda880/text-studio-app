# -*- coding: utf-8 -*-
# pages/75_名詞リスト.py
#
# PDF または Word(.docx) をアップロードして
# ・名詞抽出（Janome / MeCab をラジオボタンで切替）
# ・連続名詞の複合語化（生物 + 多様性 → 生物多様性）
# ・数字だけの語を排除
# ・カタカナのみ語を複合化前に別抽出
# ・名詞 / カタカナ語 の頻度集計
# ・CSV ダウンロード（PDF / Word で prefix 区別）
# ・日本語対応の簡易グラフ表示

from __future__ import annotations

import io
import os
import re
from collections import Counter
from typing import List, Tuple

import pandas as pd
import streamlit as st

# ============== ページ設定 ==============
st.set_page_config(
    page_title="📄 PDF/Word 名詞リスト（形態素解析）",
    page_icon="📄",
    layout="wide",
)
st.title("📄 53_ PDF/Word 名詞リスト（形態素解析）")
st.caption("PDF または Word(.docx) をアップロードして、名詞を抽出・集計します。")

# ============== 形態素エンジンの読み込み ==============

# --- Janome ---
try:
    from janome.tokenizer import Tokenizer

    tokenizer = Tokenizer()
    HAS_JANOME = True
except Exception:
    HAS_JANOME = False

# --- MeCab ---
try:
    import MeCab  # pip install mecab-python3

    HAS_MECAB = True
except Exception:
    HAS_MECAB = False

if not HAS_JANOME and not HAS_MECAB:
    st.error("Janome / MeCab のどちらも利用できません。janome または mecab-python3 をインストールしてください。")
    st.stop()

# ============== PDF 読み込み ==============
try:
    import fitz  # PyMuPDF

    _HAS_FITZ = True
except Exception:
    _HAS_FITZ = False

try:
    import pdfplumber

    _HAS_PDFPLUMBER = True
except Exception:
    _HAS_PDFPLUMBER = False

# ============== Word 読み込み ==============
try:
    from docx import Document

    _HAS_DOCX = True
except Exception:
    _HAS_DOCX = False

# ============== サイドバー（設定） ==============
with st.sidebar:
    st.subheader("⚙️ オプション")

    # 利用可能なエンジンだけを候補にする
    analyzer_options = []
    if HAS_MECAB:
        analyzer_options.append("MeCab")
    if HAS_JANOME:
        analyzer_options.append("Janome")
  

    analyzer_choice = st.radio(
        "形態素解析エンジン",
        analyzer_options,
        index=0,
        help="Janome と MeCab のどちらで名詞抽出を行うか選択します。",
    )

    mecab_dic_path = ""
    if "MeCab" in analyzer_options:
        mecab_dic_path = st.text_input(
            "MeCab 辞書ディレクトリ（任意）",
            value="",
            help="NEologd などを使う場合は dic ディレクトリへのパスを指定（例: /opt/homebrew/lib/mecab/dic/mecab-ipadic-neologd）。空欄ならデフォルト辞書。",
        )

    min_len = st.number_input("最小文字数（名詞）", 1, 20, 2)
    use_base = st.checkbox("原形で集計（揺れを抑える）", True)
    show_pos_detail = st.checkbox("品詞細分類を表示", False)

    st.markdown("---")
    stopwords_raw = st.text_area(
        "ストップワード（改行区切り）",
        "こと\nもの\nそれ\nこれ\nため\nよう\nところ",
        height=120,
    )
    stopwords = {w.strip() for w in stopwords_raw.splitlines() if w.strip()}
    st.caption("PDF / Word に対応。名詞・カタカナ語を抽出します。")

# ============== ファイルアップロード ==============
uploaded = st.file_uploader(
    "📥 PDF または Word(.docx) をアップロードしてください",
    type=["pdf", "docx"],
)

run = st.button("🚀 解析する")

# ============== ユーティリティ ==============


def extract_text_from_pdf(file) -> str:
    """PDF からテキスト抽出（PyMuPDF → pdfplumber の順で試す）"""
    data = file.read()

    if _HAS_FITZ:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            return "\n".join(page.get_text("text") for page in doc)
        except Exception:
            pass

    if _HAS_PDFPLUMBER:
        try:
            import io as _io

            with pdfplumber.open(_io.BytesIO(data)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception:
            pass

    return ""


def extract_text_from_docx(file) -> str:
    """Word(.docx) の段落テキスト抽出"""
    if not _HAS_DOCX:
        st.error("python-docx が必要です。`pip install python-docx` を実行してください。")
        return ""

    data = file.read()
    import io as _io

    doc = Document(_io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_nouns_janome(s: str) -> List[Tuple[str, str, str, int]]:
    """Janome で名詞と開始位置を取得"""
    res: List[Tuple[str, str, str, int]] = []
    ofs = 0
    for t in tokenizer.tokenize(s):
        surf = t.surface
        base = t.base_form if t.base_form != "*" else surf
        pos = t.part_of_speech
        start = ofs
        ofs += len(surf)
        if pos.startswith("名詞"):
            res.append((surf, base, pos, start))
    return res


def extract_nouns_mecab(s: str, tagger: "MeCab.Tagger") -> List[Tuple[str, str, str, int]]:
    """MeCab で名詞と開始位置を取得"""
    res: List[Tuple[str, str, str, int]] = []
    node = tagger.parseToNode(s)
    ofs = 0
    while node:
        surf = node.surface
        feat = node.feature.split(",") if node.feature else []
        pos = feat[0] if feat else ""
        base = feat[6] if len(feat) > 6 and feat[6] != "*" else surf

        if surf:
            start = ofs
            ofs += len(surf)
            if pos == "名詞":
                res.append((surf, base, pos, start))

        node = node.next
    return res


def merge_contiguous(tokens: List[Tuple[str, str, str, int]]) -> List[Tuple[str, str, str, int]]:
    """連続名詞を結合（例: 生物 + 多様性 → 生物多様性）"""
    if not tokens:
        return []

    merged: List[Tuple[str, str, str, int]] = []
    cur_surf, cur_base, cur_pos, cur_idx = tokens[0]
    prev_end = cur_idx + len(cur_surf)

    for surf, base, pos, idx in tokens[1:]:
        if idx == prev_end:
            cur_surf += surf
            cur_base += base
            prev_end = idx + len(surf)
        else:
            merged.append((cur_surf, cur_base, cur_pos, cur_idx))
            cur_surf, cur_base, cur_pos, cur_idx = surf, base, pos, idx
            prev_end = idx + len(surf)

    merged.append((cur_surf, cur_base, cur_pos, cur_idx))
    return merged


def normalize(s: str) -> str:
    return s.replace("\u3000", " ").strip()


def is_katakana_only(s: str) -> bool:
    """カタカナのみ（長音符含む）かどうか"""
    return bool(re.fullmatch(r"[ァ-ヶー]+", s))


# ============== メイン処理 ==============
if run:
    if uploaded is None:
        st.warning("ファイルをアップロードしてください。")
        st.stop()

    name = uploaded.name.lower()
    base_name = os.path.splitext(uploaded.name)[0]

    # PDF / Word で prefix を切り替え
    if name.endswith(".pdf"):
        prefix = "pdf"
    elif name.endswith(".docx"):
        prefix = "docx"
    else:
        prefix = "unknown"

    # テキスト抽出
    if prefix == "pdf":
        with st.spinner("PDF を読み込み中…"):
            text = extract_text_from_pdf(uploaded)
    else:
        with st.spinner("Word を読み込み中…"):
            text = extract_text_from_docx(uploaded)

    if not text.strip():
        st.error("テキストを抽出できませんでした（画像PDF などの可能性）。")
        st.stop()

    # -------- 形態素解析エンジンの選択 --------
    if analyzer_choice == "MeCab":
        if not HAS_MECAB:
            st.error("MeCab が利用できません。mecab-python3 をインストールしてください。")
            st.stop()

        # --- MeCab（NEologd 強制使用） ---
        NEOLOGD_PATH = "/opt/homebrew/lib/mecab/dic/mecab-ipadic-neologd"

        try:
            if not os.path.exists(NEOLOGD_PATH):
                st.error(f"NEologd 辞書が見つかりません: {NEOLOGD_PATH}\nインストールされていることを確認してください。")
                st.stop()

            mecab_args = f'-d {NEOLOGD_PATH}'
            tagger = MeCab.Tagger(mecab_args)

        except Exception as e:
            st.error(f"MeCab(NEologd) の初期化に失敗しました: {e}")
            st.stop()

        # try:
        #     mecab_args = ""
        #     if mecab_dic_path.strip():
        #         mecab_args = f'-d {mecab_dic_path.strip()}'
        #     tagger = MeCab.Tagger(mecab_args)
        # except Exception as e:
        #     st.error(f"MeCab の初期化に失敗しました: {e}")
        #     st.stop()

        tokens_raw = extract_nouns_mecab(text, tagger)
    else:  # Janome
        if not HAS_JANOME:
            st.error("Janome が利用できません。janome をインストールしてください。")
            st.stop()
        tokens_raw = extract_nouns_janome(text)

    # --- カタカナ語（複合前に抽出） ---
    kata_raw: list[Tuple[str, str, str, int, str]] = []
    for surf, base, pos, idx in tokens_raw:
        key = base if use_base else surf
        key = normalize(key)
        if len(key) < min_len:
            continue
        if key in stopwords:
            continue
        if key.isdigit():
            continue
        if is_katakana_only(key):
            kata_raw.append((surf, base, pos, idx, key))

    # --- 名詞の複合名詞化 ---
    tokens = merge_contiguous(tokens_raw)

    # --- 名詞フィルタ（複合名詞込み） ---
    filtered: list[Tuple[str, str, str, int, str]] = []
    for surf, base, pos, idx in tokens:
        key = base if use_base else surf
        key = normalize(key)
        if len(key) < min_len:
            continue
        if key in stopwords:
            continue
        if key.isdigit():
            continue
        filtered.append((surf, base, pos, idx, key))

    # =============================
    # 名詞一覧（複合名詞込み）
    # =============================
    st.subheader("📝 名詞一覧（複合名詞込み）")

    rows_tokens = []
    for surf, base, pos, idx, key in filtered:
        pos_disp = pos if show_pos_detail else (pos.split(",")[0] if pos else "")
        rows_tokens.append((surf, base, pos_disp, idx))

    df_tokens = pd.DataFrame(rows_tokens, columns=["表層形", "原形", "品詞", "開始位置"])
    st.dataframe(df_tokens, use_container_width=True, height=280)

    buf = io.StringIO()
    df_tokens.to_csv(buf, index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 名詞一覧 CSV",
        buf.getvalue().encode("utf-8-sig"),
        file_name=f"{prefix}_{base_name}__名詞一覧.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # =============================
    # カタカナ語（複合前）
    # =============================
    st.subheader("🔤 カタカナ語一覧（複合化前）")

    if kata_raw:
        rows_k = []
        for surf, base, pos, idx, key in kata_raw:
            pos_disp = pos if show_pos_detail else (pos.split(",")[0] if pos else "")
            rows_k.append((surf, base, pos_disp, idx))

        df_k = pd.DataFrame(rows_k, columns=["表層形", "原形", "品詞", "開始位置"])
        st.dataframe(df_k, use_container_width=True, height=240)

        buf_k = io.StringIO()
        df_k.to_csv(buf_k, index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 カタカナ語一覧 CSV",
            buf_k.getvalue().encode("utf-8-sig"),
            file_name=f"{prefix}_{base_name}__カタカナ一覧.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # カタカナ頻度
        counter_k = Counter(key for *_, key in kata_raw)
        df_kfreq = pd.DataFrame(counter_k.most_common(), columns=["カタカナ語", "頻度"])
        st.dataframe(df_kfreq, use_container_width=True, height=240)

        buf_kf = io.StringIO()
        df_kfreq.to_csv(buf_kf, index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 カタカナ頻度 CSV",
            buf_kf.getvalue().encode("utf-8-sig"),
            file_name=f"{prefix}_{base_name}__カタカナ頻度.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("カタカナ語は見つかりませんでした。")

    # =============================
    # 名詞頻度
    # =============================
    st.subheader("📊 名詞頻度（複合名詞込み）")

    counter = Counter(key for *_, key in filtered)
    df_freq = pd.DataFrame(counter.most_common(), columns=["名詞", "頻度"])
    st.dataframe(df_freq, use_container_width=True, height=300)

    buf_f = io.StringIO()
    df_freq.to_csv(buf_f, index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 名詞頻度 CSV",
        buf_f.getvalue().encode("utf-8-sig"),
        file_name=f"{prefix}_{base_name}__名詞頻度.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # =============================
    # グラフ（上位20）
    # =============================
    try:
        import matplotlib.pyplot as plt

        plt.rcParams["font.family"] = "Hiragino Sans"  # macOS の場合
        plt.rcParams["axes.unicode_minus"] = False

        if len(df_freq) > 0:
            st.subheader("📈 名詞頻度（上位20）")

            topn = min(20, len(df_freq))
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.barh(
                df_freq["名詞"].iloc[:topn][::-1],
                df_freq["頻度"].iloc[:topn][::-1],
            )
            ax.set_xlabel("頻度")
            ax.set_ylabel("名詞")
            ax.set_title("名詞出現頻度（上位20）")
            st.pyplot(fig)
    except Exception as e:
        st.info(f"グラフ描画に失敗: {e}")

else:
    st.info("PDF または Word をアップロードして「🚀 解析する」を押してください。")
