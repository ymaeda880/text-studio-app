# -*- coding: utf-8 -*-
# /Users/macmini2025/projects/text_studio_project/
# text_studio_app/lib/ai_chat/page_ui.py
# ============================================================
# AIチャットの画面構成．各工程の関数を順番に呼び出す．
# ============================================================
import streamlit as st
from common_lib.ui.page_header import render_standard_page_header
from lib.ai_chat.explanation import (
    render_ai_chat_page_intro,
    render_ai_chat_help_expander,
)
from lib.ai_chat.state import initialize_state
from lib.ai_chat.ui import (
    render_job_selection, render_settings, render_document_context,
    render_conversation, render_downloads, render_usage,
)


# ============================================================
# 認証と各画面の呼び出しをまとめる
# ============================================================
def render_ai_chat_page(*, projects_root, app_dir, page_name):
    sub, theme, banner, settings = render_standard_page_header(
        st_module=st, projects_root=projects_root, app_dir=app_dir,
        app_name=app_dir.name, page_name=page_name, title='💬 AIチャット2',
        subtitle_text='会話を保存して再開できます．Web検索にも対応しています．',
        default_banner_key='purple_light')
    if not sub:
        st.error('ログインしていません．')
        st.stop()
    # ------------------------------------------------------------
    # タイトル・サブタイトルの下に，共通形式の説明を表示する
    # 詳細説明の色は，このページのバナー設定に合わせる
    # ------------------------------------------------------------
    render_ai_chat_page_intro()
    render_ai_chat_help_expander(
        theme=theme,
        banner_key=banner,
    )

    # ------------------------------------------------------------
    # 利用者の会話ジョブを読み込み，各工程を表示する
    # ------------------------------------------------------------
    root = initialize_state(projects_root, sub)
    job = render_job_selection(root)
    provider, model, maximum = render_settings(root)
    render_document_context(root, job)
    render_conversation(root, job, provider, model, maximum,
                        projects_root, sub, app_dir.name, page_name)
    render_downloads(root, job)
    render_usage(job, projects_root)
