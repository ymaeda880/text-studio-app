# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/preview/cache.py
# ============================================================
# wordTex Preview
# Cache
#
# - wordTex専用プレビューキャッシュ
# - rendererごとにPDFを分離する
# ============================================================

from __future__ import annotations

from pathlib import Path
import hashlib
import json


def safe_name(text: str) -> str:
    src = str(text or "").strip()

    if not src:
        return "default"

    out: list[str] = []

    for ch in src:
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("_")

    return "".join(out)


def file_hash(
    path: Path,
    *,
    size: int = 12,
) -> str:
    path = Path(path)

    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()[:size]


def build_preview_cache_dir(
    *,
    preview_root: Path,
    docx_path: Path,
    renderer: str,
) -> Path:
    preview_root = Path(preview_root)
    docx_path = Path(docx_path)

    stem = safe_name(docx_path.stem)
    renderer_key = safe_name(renderer)

    # ------------------------------------------------------------
    # Microsoft Word
    # - macOSのアクセス許可ダイアログを避けるため，
    #   Word用だけ固定フォルダにする。
    # ------------------------------------------------------------
    if renderer_key == "word":
        return preview_root / stem / "word"

    digest = file_hash(docx_path)

    return preview_root / stem / renderer_key / digest


def build_preview_pdf_path(
    *,
    preview_root: Path,
    docx_path: Path,
    renderer: str,
) -> Path:
    cache_dir = build_preview_cache_dir(
        preview_root=preview_root,
        docx_path=docx_path,
        renderer=renderer,
    )

    return cache_dir / "preview.pdf"


def write_preview_meta(
    *,
    pdf_path: Path,
    docx_path: Path,
    renderer: str,
) -> None:
    pdf_path = Path(pdf_path)
    docx_path = Path(docx_path)

    try:
        stat = docx_path.stat()
        meta = {
            "docx_path": str(docx_path.resolve()),
            "docx_size": int(stat.st_size),
            "docx_mtime_ns": int(stat.st_mtime_ns),
            "renderer": str(renderer),
        }

        meta_path = pdf_path.parent / "preview_meta.json"
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        return