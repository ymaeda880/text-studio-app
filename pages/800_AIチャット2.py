# -*- coding: utf-8 -*-
# /Users/macmini2025/projects/text_studio_project/
# text_studio_app/pages/800_AIチャット2.py
# ============================================================
# 800：AIチャット2の入口．画面と処理はlib/ai_chatへ委譲する．
# ============================================================
from pathlib import Path
import sys
import streamlit as st

_THIS = Path(__file__).resolve()
APP_DIR, PROJ_DIR, MONO_ROOT = _THIS.parents[1:4]
for path in (MONO_ROOT, PROJ_DIR, APP_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from lib.ai_chat.page_ui import render_ai_chat_page

st.set_page_config(
    page_title='Text Studio / AIチャット2', page_icon='💬', layout='wide',
)
render_ai_chat_page(
    projects_root=MONO_ROOT, app_dir=APP_DIR, page_name=_THIS.stem,
)
