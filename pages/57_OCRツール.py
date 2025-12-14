# -*- coding: utf-8 -*-
# pages/72_OCRツール.py — PDF→OCR→テキスト抽出＆保存（プレビューなし）
from __future__ import annotations
from pathlib import Path
import sys
import streamlit as st

# ===== 共有ライブラリ（common_lib / lib）をパスに追加 =====
PROJECTS_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))

# ---- 自作ライブラリ（事前に作成済みのモジュールを想定） ----
from lib.text_loaders import extract_pdf_text
from lib.pdf_ocr import run_ocrmypdf

# ------------------------------------------------------------
# ページ設定
# ------------------------------------------------------------
st.set_page_config(page_title="Text Studio / OCRツール", page_icon="🪄", layout="wide")
st.title("🪄 OCRツール — PDF → OCR → テキスト抽出")
st.caption("画像PDFやスキャンPDFからOCRでテキストを抽出します（PDFプレビューは非表示）。")

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
col_u, col_opts = st.columns([2, 1])
with col_u:
    up = st.file_uploader("📁 PDFをアップロード（.pdf）", type=["pdf"])

with col_opts:
    st.markdown("**OCRオプション**")
    lang = st.text_input("言語（-l）", value="jpn+eng", help="日本語主体なら jpn+eng が無難です。")
    force_ocr_toggle = st.checkbox("テキスト層があっても強制OCR", value=False)
    optimize = st.select_slider("最適化レベル（--optimize）", options=[0, 1, 3], value=1, help="0=無圧縮, 1=軽圧縮, 3=強圧縮")

st.divider()

# 抽出テキストエリアキー
text_area_key = "ocr_output_text"

# ------------------------------------------------------------
# メインロジック
# ------------------------------------------------------------
if up:
    data = up.read()

    # テキスト層チェック
    try:
        stats = extract_pdf_text(data)
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    visible = int(stats["visible"])
    has_text_layer = visible >= 20  # 簡易判定

    st.subheader("テキスト層の検出結果")
    st.write(f"検出テキスト数（visible）: {visible}")
    if has_text_layer:
        st.success("✅ テキスト層が検出されました。")
    else:
        st.warning("⚠️ テキスト層がほとんどありません。画像PDFの可能性があります。")

    # 現在の抽出テキストを表示
    with st.expander("抽出テキスト（PDF内テキスト層）", expanded=False):
        st.text_area("抽出テキスト（PDF内テキスト層）", value=stats["text"], height=250, key=text_area_key)

        # ✅ 抽出テキストを直接ダウンロード
        st.download_button(
            "📄 抽出テキストを保存 (.txt)",
            data=(stats["text"] or "").encode("utf-8"),
            file_name=f"{up.name.rsplit('.',1)[0]}_extracted.txt",
            mime="text/plain",
            use_container_width=True
        )

    # OCR実行ボタン
    run_ocr = st.button(
        "🪄 OCRを実行",
        type="primary",
        use_container_width=True,
        disabled=(has_text_layer and not force_ocr_toggle)
    )

    # OCR 実行処理
    if run_ocr:
        with st.spinner("OCRを実行中…"):
            try:
                ocr_pdf = run_ocrmypdf(data, lang=lang, optimize=optimize, force=True)
                st.success("OCRが完了しました。抽出テキストを表示します。")

                # OCR後テキスト抽出
                stats_after = extract_pdf_text(ocr_pdf)
                out_text = stats_after["text"] or ""

                st.subheader("📝 OCR結果テキスト")
                st.text_area("OCR結果", value=out_text, height=400, key=f"{text_area_key}_after")

                # ✅ ダウンロードボタン（OCR結果）
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button(
                        "📥 OCR済みPDFを保存",
                        data=ocr_pdf,
                        file_name=f"{up.name.rsplit('.',1)[0]}_ocr.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                with col_dl2:
                    st.download_button(
                        "📄 OCR結果テキストを保存 (.txt)",
                        data=(out_text or "").encode("utf-8"),
                        file_name=f"{up.name.rsplit('.',1)[0]}_ocr.txt",
                        mime="text/plain",
                        use_container_width=True
                    )

            except RuntimeError as e:
                st.error(f"OCR実行中にエラーが発生しました: {e}")
                st.stop()
else:
    st.info("PDFをアップロードするとテキスト層の有無を確認します。画像PDFの場合は『OCR実行』をクリックしてください。")
