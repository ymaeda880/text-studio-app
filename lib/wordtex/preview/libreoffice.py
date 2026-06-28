# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/preview/libreoffice.py
# ============================================================
# wordTex Preview
# LibreOffice PDF Export
# ============================================================

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile


def find_soffice() -> str | None:
    found = shutil.which("soffice")
    if found:
        return found

    candidates = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/opt/homebrew/bin/soffice",
        "/usr/local/bin/soffice",
        "/usr/bin/soffice",
    ]

    for path in candidates:
        if Path(path).exists():
            return path

    return None


def export_pdf_by_libreoffice(
    *,
    docx_path: Path,
    pdf_path: Path,
) -> bool:
    docx_path = Path(docx_path)
    pdf_path = Path(pdf_path)

    soffice = find_soffice()
    if not soffice:
        return False

    if not docx_path.exists():
        return False

    pdf_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)

            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    str(docx_path),
                    "--outdir",
                    str(tmp_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            cand = tmp_dir / f"{docx_path.stem}.pdf"
            if not cand.exists():
                return False

            cand.replace(pdf_path)

        return pdf_path.exists()

    except Exception:
        return False