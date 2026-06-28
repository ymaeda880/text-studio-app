# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/preview/exporter.py
# ============================================================
# wordTex Preview
# PDF Export Dispatcher
#
# Microsoft Word
# LibreOffice
# OnlyOffice
# の切替を行う。
# ============================================================

from __future__ import annotations

from pathlib import Path

from lib.wordtex.preview.detect import get_default_renderer
from lib.wordtex.preview.libreoffice import export_pdf_by_libreoffice
from lib.wordtex.preview.ms_word import export_pdf_by_ms_word
from lib.wordtex.preview.onlyoffice import export_pdf_by_onlyoffice


def resolve_renderer(renderer: str) -> str:
    """
    auto を実際のレンダラ名へ解決する。
    """
    renderer = str(renderer or "auto").lower()

    if renderer == "auto":
        return get_default_renderer()

    return renderer


def export_docx_to_pdf(
    *,
    docx_path: Path,
    pdf_path: Path,
    renderer: str = "auto",
) -> bool:
    """
    Word(.docx) を PDF へ変換する。
    """
    docx_path = Path(docx_path)
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    renderer = resolve_renderer(renderer)

    if renderer == "word":
        return export_pdf_by_ms_word(
            docx_path=docx_path,
            pdf_path=pdf_path,
        )

    if renderer == "libreoffice":
        return export_pdf_by_libreoffice(
            docx_path=docx_path,
            pdf_path=pdf_path,
        )

    if renderer == "onlyoffice":
        return export_pdf_by_onlyoffice(
            docx_path=docx_path,
            pdf_path=pdf_path,
        )

    return False


def renderer_display_name(renderer: str) -> str:
    renderer = str(renderer or "").lower()

    if renderer == "auto":
        return "自動"

    if renderer == "word":
        return "Microsoft Word"

    if renderer == "libreoffice":
        return "LibreOffice"

    if renderer == "onlyoffice":
        return "OnlyOffice"

    if renderer == "none":
        return "利用可能なレンダラなし"

    return renderer