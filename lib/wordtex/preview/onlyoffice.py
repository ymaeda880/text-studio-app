# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/preview/onlyoffice.py
# ============================================================
# wordTex Preview
# OnlyOffice PDF Export
# ============================================================

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile


def find_onlyoffice_converter() -> str | None:
    candidates = [
        shutil.which("documentbuilder"),
        shutil.which("onlyoffice-documentbuilder"),
        "/Applications/ONLYOFFICE.app/Contents/MacOS/ONLYOFFICE",
        "/Applications/ONLYOFFICE Desktop Editors.app/Contents/MacOS/ONLYOFFICE",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)

    return None


def export_pdf_by_onlyoffice(
    *,
    docx_path: Path,
    pdf_path: Path,
) -> bool:
    """
    初版では DocumentBuilder が使える環境だけ対応する。

    OnlyOffice Desktop Editors のCLI変換は環境差が大きいため，
    未対応環境では False を返して auto 側で LibreOffice へ戻す。
    """
    docx_path = Path(docx_path)
    pdf_path = Path(pdf_path)

    if not docx_path.exists():
        return False

    converter = find_onlyoffice_converter()
    if not converter:
        return False

    pdf_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            script_path = tmp_dir / "convert.js"

            script_path.write_text(
                f'''
                var doc = Api.OpenDocument("{str(docx_path)}");
                doc.SaveAs("{str(pdf_path)}");
                doc.Close();
                ''',
                encoding="utf-8",
            )

            r = subprocess.run(
                [
                    converter,
                    str(script_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            return r.returncode == 0 and pdf_path.exists()

    except Exception:
        return False