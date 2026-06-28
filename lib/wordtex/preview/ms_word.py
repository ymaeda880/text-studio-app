# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/preview/ms_word.py
# ============================================================
# wordTex Preview
# Microsoft Word PDF Export
# ============================================================

from __future__ import annotations

from pathlib import Path
import platform
import subprocess


def export_pdf_by_ms_word(
    *,
    docx_path: Path,
    pdf_path: Path,
) -> bool:
    os_name = platform.system().lower()

    if os_name == "windows":
        return export_pdf_by_ms_word_windows(
            docx_path=docx_path,
            pdf_path=pdf_path,
        )

    if os_name == "darwin":
        return export_pdf_by_ms_word_mac(
            docx_path=docx_path,
            pdf_path=pdf_path,
        )

    return False


def export_pdf_by_ms_word_windows(
    *,
    docx_path: Path,
    pdf_path: Path,
) -> bool:
    try:
        import win32com.client  # type: ignore
    except Exception:
        return False

    docx_path = Path(docx_path)
    pdf_path = Path(pdf_path)

    if not docx_path.exists():
        return False

    pdf_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    word = None
    doc = None

    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False

        doc = word.Documents.Open(str(docx_path))
        doc.ExportAsFixedFormat(
            str(pdf_path),
            ExportFormat=17,
        )

        return pdf_path.exists()

    except Exception:
        return False

    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass

        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass


def export_pdf_by_ms_word_mac(
    *,
    docx_path: Path,
    pdf_path: Path,
) -> bool:
    docx_path = Path(docx_path).resolve()
    pdf_path = Path(pdf_path).resolve()

    if not docx_path.exists():
        return False

    pdf_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    script = f'''
    set inputPath to POSIX file "{str(docx_path)}"
    set outputPath to POSIX file "{str(pdf_path)}"

    tell application "Microsoft Word"
        activate
        open inputPath
        set theDoc to active document
        save as theDoc file name outputPath file format format PDF
        close theDoc saving no
    end tell
    '''

    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )

        return r.returncode == 0 and pdf_path.exists()

    except Exception:
        return False