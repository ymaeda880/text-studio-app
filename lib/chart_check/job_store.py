# -*- coding: utf-8 -*-
# lib/chart_check/job_store.py
# ============================================================
# 図表チェック：内部保存 helper
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


# ============================================================
# constants
# ============================================================
CHART_CHECK_APP_DIRNAME = "chart_check_app"
JOB_PREFIX = "job_"
MANIFEST_NAME = "manifest.json"


# ============================================================
# helper：図表チェック用ルート
# ============================================================
def get_chart_check_root(
    *,
    projects_root: Path,
    user_sub: str,
) -> Path:
    return (
        projects_root
        / "Storages"
        / str(user_sub)
        / CHART_CHECK_APP_DIRNAME
    )


# ============================================================
# helper：job名生成
# ============================================================
def make_chart_check_job_name() -> str:
    return f"{JOB_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}"


# ============================================================
# helper：chart_check_app 配下を空にする
# ============================================================
def clear_chart_check_root(
    *,
    root_dir: Path,
) -> None:
    if root_dir.exists():
        shutil.rmtree(root_dir)

    root_dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# helper：manifest 保存
# ============================================================
def write_chart_check_manifest(
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
# helper：AI用サマリーJSONLを内部保存
# ============================================================
def save_ai_summary_jsonl_job(
    *,
    projects_root: Path,
    user_sub: str,
    source_filename: str,
    jsonl_filename: str,
    jsonl_bytes: bytes,
    page_count: int,
    caption_count: int,
    ref_count: int,
    prev_text_max_chars: int,
    next_text_max_chars: int,
) -> Path:
    root_dir = get_chart_check_root(
        projects_root=projects_root,
        user_sub=user_sub,
    )

    clear_chart_check_root(
        root_dir=root_dir,
    )

    job_name = make_chart_check_job_name()
    job_dir = root_dir / job_name
    job_dir.mkdir(parents=True, exist_ok=True)

    out_path = job_dir / jsonl_filename
    out_path.write_bytes(jsonl_bytes)

    manifest = {
        "job_name": job_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_filename": source_filename,
        "jsonl_filename": jsonl_filename,
        "jsonl_bytes": len(jsonl_bytes or b""),
        "page_count": int(page_count),
        "caption_count": int(caption_count),
        "ref_count": int(ref_count),
        "prev_text_max_chars": int(prev_text_max_chars),
        "next_text_max_chars": int(next_text_max_chars),
    }

    write_chart_check_manifest(
        job_dir=job_dir,
        payload=manifest,
    )

    return job_dir