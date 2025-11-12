# lib/pdf_ocr.py
# ------------------------------------------------------------
# 🪄 OCRユーティリティ
#  - ocrmypdf を用いて PDF にテキスト層を付与
#  - 外部コマンド依存（tesseract / ghostscript 等）。環境に合わせて導入が必要
# ------------------------------------------------------------
from __future__ import annotations
import tempfile
import subprocess

def run_ocrmypdf(data: bytes, *, lang: str = "jpn+eng", optimize: int = 1, force: bool = True) -> bytes:
    """
    ocrmypdf でOCRを実行し、OCR済みPDFのバイト列を返す。
    - lang: ocrmypdf の -l オプション（例: "jpn", "eng", "jpn+eng"）
    - optimize: 0(無圧縮) / 1(軽圧縮) / 3(強圧縮)
    - force: True で --force-ocr を付け、既存テキスト層があってもOCRを強制
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_in, \
         tempfile.NamedTemporaryFile(suffix="_ocr.pdf", delete=False) as f_out:
        f_in.write(data); f_in.flush()
        in_path, out_path = f_in.name, f_out.name

    cmd = ["ocrmypdf"]
    if force:
        cmd += ["--force-ocr"]
    if optimize is not None:
        cmd += ["--optimize", str(optimize)]
    cmd += ["-l", lang, in_path, out_path]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError as e:
        raise RuntimeError("ocrmypdf が見つかりません。macOSなら `brew install ocrmypdf` で導入できます。") from e
    except subprocess.CalledProcessError as e:
        err = (e.stderr.decode(errors="ignore") if e.stderr else str(e))[:1000]
        raise RuntimeError(f"OCR実行に失敗しました: {err}") from e

    with open(out_path, "rb") as rf:
        return rf.read()
