# -*- coding: utf-8 -*-
# /Users/macmini2025/projects/text_studio_project/
# text_studio_app/lib/ai_chat/state.py
# ============================================================
# 利用者別の画面状態と保存結果を管理する．
# ============================================================
import streamlit as st
from common_lib.storage.external_ssd_root import resolve_storage_subdir_root
from lib.ai_chat.jobs import new_job, user_dir, save_job


def initialize_state(projects_root, sub):
    # 利用者切替時は前の利用者の状態を破棄する．
    OWNER = 'chat800_owner'
    if st.session_state.get(OWNER) != str(sub):
        for key in list(st.session_state):
            if key.startswith('chat800_'):
                del st.session_state[key]
        st.session_state[OWNER] = str(sub)
    root = user_dir(resolve_storage_subdir_root(projects_root, subdir='Storages'), str(sub))
    S = st.session_state
    S.setdefault('chat800_new', new_job())
    S.setdefault('chat800_draft_no', 0)
    return root


def persist(root, job):
    S = st.session_state
    try:
        deleted = save_job(root, job)
        if deleted:
            S['chat800_notice'] = '最新5ジョブを保持するため，古いジョブを削除しました：' + '，'.join(deleted)
        return True
    except Exception as exc:
        S['chat800_notice'] = f'未保存です．JSONをダウンロードして保管してください：{exc}'
        st.error(f'保存できませんでした：{exc}')
        st.info('会話はこの画面に保持しています．JSONをダウンロードしてください．')
        return False
