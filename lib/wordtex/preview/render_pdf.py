# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/preview/render_pdf.py
# ============================================================
# wordTex Preview
# PDF Render
#
# - PDFをPyMuPDFでPNG化してStreamlit表示する
# - common_lib.preview.file_preview は使わない
# ============================================================

from __future__ import annotations

from pathlib import Path

import streamlit as st


def try_import_fitz():
    try:
        import fitz  # type: ignore
        return fitz
    except Exception:
        return None


def clamp_page_no(page_no: int, total_pages: int) -> int:
    try:
        p = int(page_no)
    except Exception:
        p = 1

    if total_pages <= 0:
        return 1

    if p < 1:
        return 1

    if p > total_pages:
        return total_pages

    return p


def get_pdf_page_count(pdf_path: Path) -> int | None:
    fitz = try_import_fitz()
    if fitz is None:
        return None

    try:
        doc = fitz.open(str(pdf_path))
        return int(doc.page_count)
    except Exception:
        return None


def pdf_page_png(
    pdf_path: Path,
    *,
    page_no: int,
    max_width: int,
) -> bytes | None:
    fitz = try_import_fitz()
    if fitz is None:
        return None

    try:
        doc = fitz.open(str(pdf_path))
        total_pages = int(doc.page_count)

        if total_pages <= 0:
            return None

        page_no = clamp_page_no(
            page_no=page_no,
            total_pages=total_pages,
        )

        page = doc.load_page(page_no - 1)
        pix0 = page.get_pixmap()

        if pix0.width <= 0:
            return None

        zoom = float(max_width) / float(pix0.width)
        if zoom <= 0:
            zoom = 1.0

        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        return pix.tobytes("png")

    except Exception:
        return None


def render_pdf_preview(
    *,
    pdf_path: Path,
    display_name: str,
    page_no: int,
    max_width: int,
) -> int | None:
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        st.warning("プレビューPDFが見つかりません。")
        return None

    total_pages = get_pdf_page_count(pdf_path)

    if total_pages is None or total_pages <= 0:
        st.info("PDFプレビューには PyMuPDF(fitz) が必要です。")
        return None

    current_page = clamp_page_no(
        page_no=page_no,
        total_pages=total_pages,
    )

    png = pdf_page_png(
        pdf_path,
        page_no=current_page,
        max_width=max_width,
    )

    if not png:
        st.info("PDFページの画像化に失敗しました。")
        return None

    st.image(
        png,
        caption=f"{display_name}（{current_page} / {total_pages} ページ）",
        width=max_width,
    )

    return total_pages