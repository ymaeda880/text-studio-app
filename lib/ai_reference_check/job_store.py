# -*- coding: utf-8 -*-
# text_studio_app/lib/ai_reference_check/job_store.py
# ============================================================
# AI図表チェック：内部保存JSONL job管理
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import json
from pathlib import Path
from typing import Any, Dict, List

# ============================================================
# constants
# ============================================================
CHART_CHECK_APP_DIRNAME = "chart_check_app"
JOB_PREFIX = "job_"
MANIFEST_NAME = "manifest.json"


# ============================================================
# JSONL / JSON 判定
# ============================================================
def is_jsonl_like_file(filename: str) -> bool:
    suffix = Path(str(filename or "")).suffix.lower()
    return suffix in [".jsonl", ".json"]


# ============================================================
# 保存ルート
# ============================================================
def get_chart_check_root(*, projects_root: Path, user_sub: str) -> Path:
    return projects_root / "Storages" / str(user_sub) / CHART_CHECK_APP_DIRNAME


# ============================================================
# manifest 読み込み
# ============================================================
def read_manifest(*, job_dir: Path) -> Dict[str, Any]:
    manifest_path = job_dir / MANIFEST_NAME

    if not manifest_path.exists():
        return {}

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ============================================================
# current job 解決
# ============================================================
def resolve_current_job_dir(*, root_dir: Path) -> Path | None:
    if not root_dir.exists():
        return None

    job_dirs = [
        p for p in root_dir.iterdir()
        if p.is_dir() and p.name.startswith(JOB_PREFIX)
    ]

    if not job_dirs:
        return None

    job_dirs = sorted(job_dirs, key=lambda x: x.name)
    return job_dirs[-1]


# ============================================================
# 内部保存AIサマリーJSONL一覧
# ============================================================
def list_saved_ai_summary_jsonl_files(*, job_dir: Path | None) -> List[Dict[str, Any]]:
    if job_dir is None:
        return []

    manifest = read_manifest(job_dir=job_dir)

    rows: List[Dict[str, Any]] = []

    jsonl_filename = str(manifest.get("jsonl_filename") or "").strip()

    if jsonl_filename:
        path = job_dir / jsonl_filename

        if path.exists() and is_jsonl_like_file(path.name):
            rows.append(
                {
                    "label": f"{path.name} | {path.stat().st_size:,} bytes",
                    "filename": path.name,
                    "path": path,
                    "bytes": int(path.stat().st_size),
                }
            )

    if rows:
        return rows

    for path in sorted(list(job_dir.glob("*.jsonl")) + list(job_dir.glob("*.json"))):
        if not path.exists():
            continue

        rows.append(
            {
                "label": f"{path.name} | {path.stat().st_size:,} bytes",
                "filename": path.name,
                "path": path,
                "bytes": int(path.stat().st_size),
            }
        )

    return rows