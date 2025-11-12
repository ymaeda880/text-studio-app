# pages/40_翻訳（PDF・画像）.py
# ============================================================
# 📥 PDF/画像 をドロップ → 解析（PDF抽出 or OCR）→ 翻訳 → プレビュー/ダウンロード
# - PDF: PyMuPDFで抽出。空ならページ画像化→OCR
# - 画像: pytesseract でOCR
# - 翻訳: OpenAI（自動言語判定→指定言語へ）
# ============================================================

from __future__ import annotations
from pathlib import Path
import io, os, math, textwrap
import streamlit as st
from PIL import Image

from openai import OpenAI

# --- PDF ---
import fitz  # PyMuPDF
# --- OCR ---
import pytesseract
# --- LLM (OpenAI) ---
from openai import OpenAI

st.set_page_config(page_title="翻訳（PDF・画像）", page_icon="🌐", layout="wide")
st.title("🌐 翻訳（PDF・画像をドロップ）")

# ---------------- UI: 説明 ----------------
with st.expander("ℹ️ このページで行うこと（処理フロー）", expanded=False):
    st.markdown(
        """
        1. **ファイルをドロップ**（PDF / PNG / JPG / JPEG / TIFF）
        2. **テキスト抽出**  
           - PDFはテキスト抽出、空ならページ画像化→OCR  
           - 画像はOCR（pytesseract）
        3. **翻訳**（OpenAIにより自動言語判定→指定言語へ）
        4. **結果表示 & ダウンロード**（.txt / .md）
        """
    )

# ---------------- UI: 設定 ----------------
colA, colB, colC = st.columns([1, 1, 1])
with colA:
    target_lang = st.selectbox(
        "出力言語（target language）",
        ["日本語", "英語", "中国語", "韓国語", "フランス語", "ドイツ語", "スペイン語"],
        index=0,
    )
with colB:
    chunk_chars = st.slider("翻訳チャンクサイズ（文字数）", 800, 8000, 3000, 200)
with colC:
    preserve_formatting = st.checkbox("段落・改行をできる限り保持", value=True)

st.caption("※ 大きなPDFは分割翻訳します。スキャンPDFはOCRのため時間がかかる場合があります。")

# ---------------- ファイル入力 ----------------
uploaded_files = st.file_uploader(
    "📎 PDF/画像をドロップ（複数可）", type=["pdf", "png", "jpg", "jpeg", "tif", "tiff"], accept_multiple_files=True
)

# ============================================================
# 抽出ユーティリティ
# ============================================================
def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, int]:
    """テキスト抽出。戻り値: (text, num_pages)"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts = []
    for page in doc:
        t = page.get_text("text") or ""
        texts.append(t.strip())
    full = "\n\n".join(texts).strip()
    return full, len(doc)

def ocr_pdf_by_raster(pdf_bytes: bytes, dpi: int = 220, lang_hint: str | None = None) -> tuple[str, int]:
    """PDFを画像化してOCR。戻り値: (text, num_pages)"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out_lines = []
    total = len(doc)
    prog = st.progress(0.0, text="OCR（PDF）実行中…")
    for i, page in enumerate(doc):
        # DPI→拡大行列
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)  # RGB
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        txt = pytesseract.image_to_string(img, lang=lang_hint) if lang_hint else pytesseract.image_to_string(img)
        out_lines.append(txt.strip())
        prog.progress((i + 1) / total, text=f"OCR（PDF）{i+1}/{total} ページ")
    prog.empty()
    return "\n\n".join(out_lines).strip(), total

def ocr_image_file(file) -> str:
    """画像ファイル（BytesIO）をOCR"""
    img = Image.open(file).convert("RGB")
    return pytesseract.image_to_string(img).strip()

def chunk_text(s: str, max_chars: int) -> list[str]:
    s = s.replace("\r\n", "\n")
    if len(s) <= max_chars:
        return [s]
    parts = []
    start = 0
    while start < len(s):
        end = min(len(s), start + max_chars)
        # なるべく段落で切る
        cut = s.rfind("\n\n", start, end)
        if cut == -1 or cut <= start + int(max_chars * 0.5):
            cut = end
        parts.append(s[start:cut])
        start = cut
    return parts

# ============================================================
# 翻訳（OpenAI）
# ============================================================
def get_client() -> OpenAI:
    """`.streamlit/secrets.toml` の OPENAI_API_KEY を使用"""
    api_key = st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        st.error("❌ OPENAI_API_KEY が設定されていません。.streamlit/secrets.toml を確認してください。")
        st.stop()
    try:
        return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"OpenAI クライアント初期化に失敗: {e}")
        st.stop()
        

def translate_text(text: str, target_lang: str, preserve_formatting: bool = True) -> str:
    """
    OpenAI で翻訳。モデルは 'gpt-5-mini' を既定（必要に応じて調整）
    """
    client = get_client()
    system = (
        "You are a professional translator. Detect the source language automatically and translate "
        f"faithfully into {target_lang}. Use formal, accurate wording."
    )
    if preserve_formatting:
        system += " Preserve paragraph breaks, lists, inline math and basic formatting as much as possible."

    try:
        resp = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            temperature=1,  # 一部のモデルは温度固定
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        st.error(f"翻訳API呼び出しに失敗: {e}")
        return ""

def translate_large_text(s: str, target_lang: str, max_chars: int, preserve_formatting: bool) -> str:
    parts = chunk_text(s, max_chars)
    out = []
    pbar = st.progress(0.0, text="翻訳中…")
    total = len(parts)
    for i, p in enumerate(parts):
        t = translate_text(p, target_lang, preserve_formatting)
        out.append(t)
        pbar.progress((i + 1) / total, text=f"翻訳中… {i+1}/{total}")
    pbar.empty()
    return "\n\n".join(out).strip()

# ============================================================
# 実行
# ============================================================
if uploaded_files:
    results = []
    for up in uploaded_files:
        suffix = (Path(up.name).suffix or "").lower()
        st.write(f"### 📄 処理対象: `{up.name}`")
        raw_text = ""
        n_pages = None

        if suffix == ".pdf":
            pdf_bytes = up.read()
            raw_text, n_pages = extract_text_from_pdf(pdf_bytes)
            if not raw_text.strip():
                st.info("このPDFはテキストが抽出できませんでした。スキャンPDFと推定→OCRに切替えます。")
                raw_text, n_pages = ocr_pdf_by_raster(pdf_bytes, dpi=220)

        elif suffix in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]:
            raw_text = ocr_image_file(up)
            n_pages = 1
        else:
            st.warning("未対応の拡張子です。PDF/PNG/JPG/TIFF を使用してください。")
            continue

        if not raw_text.strip():
            st.warning("テキストが抽出できませんでした。ファイル内容をご確認ください。")
            continue

        with st.expander("抽出テキスト（原文）", expanded=False):
            st.text_area("原文", raw_text, height=220)

        translated = translate_large_text(raw_text, target_lang=target_lang, max_chars=chunk_chars, preserve_formatting=preserve_formatting)

        st.subheader("📝 翻訳結果")
        st.text_area("Translated", translated, height=320)

        # ダウンロード
        base = Path(up.name).stem
        txt_bytes = translated.encode("utf-8")
        md_bytes = f"# {base} — Translation ({target_lang})\n\n{translated}\n".encode("utf-8")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("⬇️ ダウンロード (.txt)", data=txt_bytes, file_name=f"{base}_translated.txt", mime="text/plain")
        with c2:
            st.download_button("⬇️ ダウンロード (.md)", data=md_bytes, file_name=f"{base}_translated.md", mime="text/markdown")

        results.append((up.name, n_pages, len(raw_text)))

    # まとめ
    if results:
        st.success("✅ 完了")
