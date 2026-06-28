# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/preview/detect.py
# ============================================================
# wordTex Preview
# renderer detection
#
# Microsoft Word
# LibreOffice
# OnlyOffice
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import shutil
import subprocess
import platform
from pathlib import Path

from lib.wordtex.settings import (
    DEV_FORCE_NO_MS_WORD,
    DEV_FORCE_NO_ONLYOFFICE,
    DEV_FORCE_NO_LIBREOFFICE,
)


# ============================================================
# OS
# ============================================================
def get_platform() -> str:
    """
    実行OSを返す。

    Returns
    -------
    windows
    mac
    linux
    unknown
    """
    name = platform.system().lower()

    if name == "windows":
        return "windows"

    if name == "darwin":
        return "mac"

    if name == "linux":
        return "linux"

    return "unknown"


# ============================================================
# Microsoft Word
# ============================================================
def has_ms_word() -> bool:
    """
    Microsoft Word がインストールされているか判定する。
    """
    if DEV_FORCE_NO_MS_WORD:
        return False

    os_name = get_platform()

    # ------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------
    if os_name == "windows":

        candidates = [
            Path(
                r"C:\Program Files\Microsoft Office"
            ),
            Path(
                r"C:\Program Files (x86)\Microsoft Office"
            ),
        ]

        for root in candidates:
            if root.exists():
                return True

        return False

    # ------------------------------------------------------------
    # macOS
    # ------------------------------------------------------------
    if os_name == "mac":

        app = Path("/Applications/Microsoft Word.app")

        if app.exists():
            return True

        try:
            r = subprocess.run(
                [
                    "mdfind",
                    "kMDItemCFBundleIdentifier == 'com.microsoft.Word'",
                ],
                capture_output=True,
                text=True,
            )

            if r.stdout.strip():
                return True

        except Exception:
            pass

        return False

    return False


# ============================================================
# LibreOffice
# ============================================================
def has_libreoffice() -> bool:
    """
    LibreOffice が利用可能か判定する。
    """
    if DEV_FORCE_NO_LIBREOFFICE:
        return False

    if shutil.which("soffice"):
        return True

    candidates = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        "/opt/homebrew/bin/soffice",
    ]

    for path in candidates:
        if Path(path).exists():
            return True

    return False


# ============================================================
# OnlyOffice
# ============================================================
def has_onlyoffice() -> bool:
    """
    OnlyOffice Desktop Editors が利用可能か判定する。
    """
    if DEV_FORCE_NO_ONLYOFFICE:
        return False

    candidates = [
        "/Applications/ONLYOFFICE.app",
        "/Applications/ONLYOFFICE Desktop Editors.app",
    ]

    for path in candidates:
        if Path(path).exists():
            return True

    return False


# ============================================================
# 利用可能レンダラ一覧
# ============================================================
def list_available_renderers() -> list[str]:
    """
    利用可能なレンダラ一覧を返す。

    自動は常に表示する。
    """

    renderers = ["auto"]

    if has_ms_word():
        renderers.append("word")

    if has_libreoffice():
        renderers.append("libreoffice")

    if has_onlyoffice():
        renderers.append("onlyoffice")

    return renderers


# ============================================================
# 推奨レンダラ
# ============================================================
def get_default_renderer() -> str:
    """
    自動選択時のレンダラ。
    """

    if has_ms_word():
        return "word"

    if has_onlyoffice():
        return "onlyoffice"

    if has_libreoffice():
        return "libreoffice"

    return "none"