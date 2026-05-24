# -*- coding: utf-8 -*-
# lib/bulk_word_proofreading/job_store.py
# ============================================================
# 一括Word解析＋文章校正：中間テキスト保存 job 管理
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


# ============================================================
# constants
# ============================================================
WORD_EDIT_APP_DIRNAME = "word_edit_app"
JOB_PREFIX = "job_"
MANIFEST_NAME = "manifest.json"


# ============================================================
# helper：Word編集用ルート
# ============================================================
def get_word_edit_root(
    *,
    projects_root: Path,
    user_sub: str,
) -> Path:
    return (
        projects_root
        / "Storages"
        / str(user_sub)
        / WORD_EDIT_APP_DIRNAME
    )


# ============================================================
# helper：job名生成
# ============================================================
def make_job_name() -> str:
    return f"{JOB_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}"


# ============================================================
# helper：word_edit_app 配下を空にする
# ============================================================
def clear_word_edit_root(
    *,
    root_dir: Path,
) -> None:
    if root_dir.exists():
        shutil.rmtree(root_dir)

    root_dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# helper：manifest 保存
# ============================================================
def write_manifest(
    *,
    job_dir: Path,
    payload: Dict[str, Any],
) -> None:
    manifest_path = job_dir / MANIFEST_NAME

    manifest_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# helper：manifest 読込
# ============================================================
def read_manifest(
    *,
    job_dir: Path,
) -> Dict[str, Any]:
    manifest_path = job_dir / MANIFEST_NAME

    if not manifest_path.exists():
        return {}

    try:
        return json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except Exception:
        return {}


# ============================================================
# helper：現在 job を取得
# ============================================================
def resolve_current_job_dir(
    *,
    root_dir: Path,
) -> Path | None:
    if not root_dir.exists():
        return None

    job_dirs = [
        p
        for p in root_dir.iterdir()
        if p.is_dir() and p.name.startswith(JOB_PREFIX)
    ]

    if not job_dirs:
        return None

    job_dirs = sorted(
        job_dirs,
        key=lambda x: x.name,
    )

    return job_dirs[-1]


# ============================================================
# helper：保存済み txt 一覧
# ============================================================
def list_saved_intermediate_files(
    *,
    job_dir: Path | None,
) -> List[Dict[str, Any]]:
    if job_dir is None:
        return []

    manifest = read_manifest(job_dir=job_dir)
    files = manifest.get("files") or []

    rows: List[Dict[str, Any]] = []

    for row in files:
        filename = str(row.get("filename") or "").strip()

        if not filename:
            continue

        path = job_dir / filename

        if not path.exists():
            continue

        chars = int(row.get("chars") or 0)
        index = int(row.get("index") or 0)
        total = int(row.get("total") or 0)

        label = (
            f"{index}/{total} | "
            f"{filename} | "
            f"{chars:,}文字"
        )

        rows.append(
            {
                "label": label,
                "filename": filename,
                "path": path,
                "chars": chars,
                "index": index,
                "total": total,
            }
        )

    # ------------------------------------------------------------
    # fallback
    # ------------------------------------------------------------
    if rows:
        return rows

    txt_files = sorted(job_dir.glob("*.txt"))

    fallback_rows: List[Dict[str, Any]] = []

    for idx, path in enumerate(txt_files, start=1):

        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            text = ""

        chars = len(text)

        fallback_rows.append(
            {
                "label": (
                    f"{idx}/{len(txt_files)} | "
                    f"{path.name} | "
                    f"{chars:,}文字"
                ),
                "filename": path.name,
                "path": path,
                "chars": chars,
                "index": idx,
                "total": len(txt_files),
            }
        )

    return fallback_rows


# ============================================================
# helper：選択ファイル読込
# ============================================================
def read_saved_text(
    *,
    path: Path,
) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


# ============================================================
# helper：job 保存
# ============================================================
def save_word_edit_job(
    *,
    projects_root: Path,
    user_sub: str,
    source_filename: str,
    output_mode: str,
    base_chapter: int,
    use_same_left_placeholder: bool,
    chunk_char_limit: int,
    intermediate_text: str,
    chunks: List[str],
    planned_names: List[str],
) -> Path:

    # ------------------------------------------------------------
    # root
    # ------------------------------------------------------------
    root_dir = get_word_edit_root(
        projects_root=projects_root,
        user_sub=user_sub,
    )

    # ------------------------------------------------------------
    # 前回結果を削除
    # ------------------------------------------------------------
    clear_word_edit_root(
        root_dir=root_dir,
    )

    # ------------------------------------------------------------
    # job directory
    # ------------------------------------------------------------
    job_name = make_job_name()

    job_dir = root_dir / job_name

    job_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------
    # txt 保存
    # ------------------------------------------------------------
    file_rows: List[Dict[str, Any]] = []

    for idx, (chunk, filename) in enumerate(
        zip(chunks, planned_names),
        start=1,
    ):

        out_path = job_dir / filename

        out_path.write_text(
            chunk,
            encoding="utf-8",
        )

        file_rows.append(
            {
                "filename": filename,
                "chars": len(chunk),
                "index": idx,
                "total": len(chunks),
            }
        )

    # ------------------------------------------------------------
    # manifest
    # ------------------------------------------------------------
    manifest = {
        "job_name": job_name,
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "source_filename": source_filename,
        "output_mode": output_mode,
        "base_chapter": int(base_chapter),
        "use_same_left_placeholder": bool(
            use_same_left_placeholder
        ),
        "chunk_char_limit": int(chunk_char_limit),
        "total_chars": len(intermediate_text or ""),
        "file_count": len(file_rows),
        "files": file_rows,
    }

    write_manifest(
        job_dir=job_dir,
        payload=manifest,
    )

    return job_dir