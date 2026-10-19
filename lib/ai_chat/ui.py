# -*- coding: utf-8 -*-
# /Users/macmini2025/projects/text_studio_project/
# text_studio_app/lib/ai_chat/ui.py
# ============================================================
# AIチャットの各画面：選択・設定・前提文書・会話・出力・費用．
# AI実行はai_ops，永続保存はjobs/state，共通検索はcommon_libへ委譲する．
# ============================================================
import hashlib
import json
import streamlit as st
from common_lib.ui.model_picker import render_text_model_picker
from common_lib.ai.models import TEXT_MODEL_CATALOG, DEFAULT_TEXT_MODEL_KEY
from common_lib.ai.web_search_chat import safe_url
from common_lib.ai.types import CostResult
from common_lib.ui import render_run_summary_compact
from common_lib.io import read_doc_context_from_bytes, read_doc_context_from_text
from config.config import has_gemini_api_key
from lib.ai_chat.jobs import new_job, list_jobs, load_job, import_history
from lib.ai_chat.exports import make_docx, make_pdf
from lib.ai_chat.state import persist
from lib.ai_chat.ai_ops import run_turn


# ============================================================
# 新規会話・保存済み会話を選択する
# ============================================================
def render_job_selection(root):
    S = st.session_state
    if S.pop('chat800_switch_new', False):
        S['chat800_mode'] = '新規会話から作成'
    st.subheader('① ジョブの設定')
    mode = st.radio('ジョブの指定方法', ['新規会話から作成', '保存済みジョブを選択'],
                    horizontal=True, key='chat800_mode')
    st.caption('最新の5ジョブを作成順で保存します．6件目の保存時に最も古いジョブを自動削除します．')
    if mode == '新規会話から作成':
        if st.button('新しい会話を始める', key='chat800_create'):
            S['chat800_new'] = new_job()
            S['chat800_draft_no'] += 1
            st.rerun()
        job = S['chat800_new']
    else:
        saved = list_jobs(root)
        if not saved:
            st.info('保存済みジョブがありません．新規会話から作成してください．')
            st.stop()
        by_id = {j['job_id']: j for j in saved}
        selected = st.radio('対象ジョブ', list(by_id),
            format_func=lambda key: f"{by_id[key]['title']}　｜ {by_id[key]['created_at'][:19].replace('T', ' ')}",
            key='chat800_job_radio')
        if S.get('chat800_loaded_id') != selected:
            S['chat800_saved'] = load_job(root, selected)
            S['chat800_loaded_id'] = selected
            S['chat800_draft_no'] += 1
        if st.button('保存内容を読み直す', key='chat800_reload'):
            S['chat800_saved'] = load_job(root, selected)
            S['chat800_draft_no'] += 1
            st.rerun()
        job = S['chat800_saved']
    if S.get('chat800_notice'):
        st.info(S.pop('chat800_notice'))
    st.markdown('**現在の会話：' + job['title'] + '**')
    return job


# ============================================================
# サイドバーにモデル・出力上限・JSON取り込みを表示する
# ============================================================
def render_settings(root):
    S = st.session_state
    with st.sidebar:
        st.header('AIの設定')
        model_key = render_text_model_picker(title='使用モデル', catalog=TEXT_MODEL_CATALOG,
            session_key='chat800_model_key', default_key=DEFAULT_TEXT_MODEL_KEY,
            page_name='chat800', gemini_available=bool(has_gemini_api_key()))
        provider, model = model_key.split(':', 1)
        maximum = st.number_input('最大出力トークン', min_value=256, max_value=128000,
                                  value=32000, step=256, key='chat800_maximum')
        st.caption('過去の会話全体を送信します．長い会話では入力トークンと費用が増えます．')
        st.divider()
        st.subheader('JSONの取り込み')
        upload = st.file_uploader('会話履歴JSON（18ページにも対応）', type=['json'], key='chat800_json')
        if st.button('新規ジョブとして取り込む', disabled=upload is None, key='chat800_import'):
            try:
                restored = import_history(upload.getvalue())
                if persist(root, restored):
                    S['chat800_new'] = restored
                    S['chat800_switch_new'] = True
                    S['chat800_draft_no'] += 1
                    st.rerun()
            except (ValueError, TypeError, KeyError) as exc:
                st.error(f'JSONを取り込めませんでした：{exc}')
    return provider, model, int(maximum)


# ============================================================
# 会話の参考資料を読み込み・保存する
# ============================================================
def render_document_context(root, job):
    S = st.session_state
    with st.expander('前提文書（任意）'):
        source = st.file_uploader('参考資料（Word／PDF／テキスト）',
            type=['docx', 'pdf', 'txt', 'md', 'json'], key='chat800_context_file_' + job['job_id'])
        pasted = st.text_area('前提文書の貼り付け', key='chat800_context_text_' + job['job_id'])
        if st.button('前提文書を保存', key='chat800_context_set'):
            try:
                with st.spinner('前提文書を読み込み中…'):
                    if source is not None:
                        ctx = read_doc_context_from_bytes(file_name=source.name, data=source.getvalue(), max_chars=15000)
                    elif pasted.strip():
                        ctx = read_doc_context_from_text(raw_text=pasted, kind='貼り付けテキスト', max_chars=15000)
                    else:
                        raise ValueError('資料を選択するか，本文を入力してください．')
                    job['doc_context'] = ctx.to_dict()
                    persist(root, job)
            except Exception as exc:
                st.error(f'前提文書を保存できませんでした：{exc}')
        if job.get('doc_context'):
            st.caption('保存中の前提文書：' + job['doc_context'].get('kind', '文書'))
            st.text(job['doc_context']['text'][:1000])
            if (job['doc_context'].get('meta') or {}).get('truncated'):
                st.caption('前提文書は先頭15,000文字までです．')
            if st.button('前提文書を解除', key='chat800_context_clear'):
                job['doc_context'] = None
                persist(root, job)
                st.rerun()


# ============================================================
# 会話の直上に検索設定を置き，履歴表示と送信を行う
# ============================================================
def render_conversation(root, job, provider, model, maximum, projects_root, user_sub, app_name, page_name):
    S = st.session_state
    st.subheader('② AIとの会話')

    # ------------------------------------------------------------
    # 検索設定：会話の直上で通常検索・詳細検索を選ぶ
    # モデルの選択はサイドバーに残す
    # ------------------------------------------------------------
    search_available = provider in ('openai', 'gemini')
    search_column, detail_column = st.columns(2)

    with search_column:
        web = st.checkbox(
            'ネット検索をする',
            key='chat800_web',
            disabled=not search_available,
        )

    web = bool(web and search_available)

    with detail_column:
        detailed = st.checkbox(
            '詳細にネット検索する',
            key='chat800_search_detailed',
            disabled=not web,
            help='通常は参考URL一覧を最大10件，詳細は件数制限なしにします．',
        )

    detailed = bool(detailed and web)

    if not search_available:
        st.caption('Web検索はOpenAIまたはGeminiで利用できます．')
    elif web:
        st.caption(
            '詳細検索：複数の情報源を調べます．参考URL一覧の件数は制限しません．'
            if detailed
            else '通常検索：関連する情報を調べます．参考URL一覧は最大10件です．'
        )

    # ------------------------------------------------------------
    # 保存した会話と出典を表示する
    # ------------------------------------------------------------
    for msg in job['messages']:
        with st.chat_message(msg['role']):

            # ------------------------------------------------------------
            # AI回答の先頭タイトル：通常サイズの太字で表示する
            # 保存済みの本文や，本文中の見出しは変更しない
            # ------------------------------------------------------------
            content = msg['content']

            if msg['role'] == 'assistant':
                first_line, separator, body = content.partition('\n')

                if first_line.startswith('# '):
                    title = first_line[2:].strip()
                    content = f"**{title}**"

                    if separator:
                        content += '\n\n' + body

            st.markdown(content)
            info = msg.get('search') or {}
            sources = info.get('sources') or []
            if sources and not info.get('sources_in_text'):
                st.markdown("**参考にしたネット情報**")
                for number, source in enumerate(sources, 1):
                    url = source.get('url', '')
                    if safe_url(url):
                        title = source.get('title') or url
                        st.link_button(f"{number}．{title}", url)
                        st.caption(url)
            if info.get('requested'):
                st.caption('検索実行確認済み' if info.get('performed') else '検索実行を確認できませんでした')
                if info.get('note'):
                    st.warning(info['note'])

                # Googleが返した検索候補HTMLは加工せず，独立したiframeで表示する．
                if info.get('search_suggestions'):
                    import streamlit.components.v1 as components
                    components.html(info['search_suggestions'], height=200, scrolling=True)

    question = st.text_area('追加の質問・指示' if job['messages'] else '質問・指示',
                           key=f"chat800_draft_{job['job_id']}_{S['chat800_draft_no']}", height=120)
    if st.button('送信', type='primary', key='chat800_send'):
        if not question.strip():
            st.warning('質問・指示を入力してください．')
        else:
            progress = st.progress(0, text='会話履歴を準備中…')
            try:
                progress.progress(15, text='Web検索・回答生成中…' if web else '回答生成中…')
                with st.spinner('Web検索・回答を作成しています…' if web else '回答を作成しています…'):
                    run_turn(root=root, job=job, question=question.strip(),
                             provider=provider, model=model, maximum=maximum, web=web,
                             detailed=detailed,
                             projects_root=projects_root, user_sub=user_sub,
                             app_name=app_name, page_name=page_name)
                progress.progress(85, text='会話を保存中…')
                ok = persist(root, job)
                progress.progress(100, text='保存しました．' if ok else '回答生成済み・保存は未完了です．')
                S['chat800_draft_no'] += 1
                st.rerun()
            except Exception as exc:
                progress.empty()
                st.error(f'処理を完了できませんでした：{exc}')


# ============================================================
# JSON保存とWord・PDFダウンロードを表示する
# ============================================================
def render_downloads(root, job):
    S = st.session_state
    st.divider()
    st.subheader('③ 保存・ダウンロード')
    if st.button('現在の会話を保存', key='chat800_save'):
        if persist(root, job):
            st.success('保存しました．')
    payload = json.dumps(job, ensure_ascii=False, indent=2).encode('utf-8')
    st.download_button('JSONをダウンロード', payload, file_name='AIチャット_' + job['job_id'] + '.json',
                       mime='application/json', key='chat800_download_json')
    fingerprint = hashlib.sha256(payload).hexdigest()
    if st.button('Word・PDFを作成', disabled=not job['messages'], key='chat800_export'):
        S.pop('chat800_export_bytes', None)
        with st.spinner('Word・PDFを作成しています…'):
            files = {}
            for ext, exporter in [('docx', make_docx), ('pdf', make_pdf)]:
                try:
                    files[ext] = exporter(job)
                except Exception as exc:
                    st.error(f'{ext}を作成できませんでした：{exc}')
            S['chat800_export_bytes'] = (fingerprint, files)
    exported = S.get('chat800_export_bytes')
    if exported and exported[0] == fingerprint:
        for ext, data in exported[1].items():
            st.download_button(('Word' if ext == 'docx' else 'PDF') + 'をダウンロード', data,
                file_name='AIチャット.' + ext,
                mime='application/pdf' if ext == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                key='chat800_dl_' + ext)


# ============================================================
# 直近1回分のAI利用状況を表示する
# ============================================================
def render_usage(job, projects_root):
    S = st.session_state
    st.divider()

    # ------------------------------------------------------------
    # AI利用状況：直近1回分だけ表示する
    # 保存済みの実行ログはすべて保持する
    # ------------------------------------------------------------
    st.subheader('AI利用状況（直近1回分）')

    for run in job.get('runs', [])[-1:]:
        info = run.get('search') or {}
        render_run_summary_compact(projects_root=projects_root, run_id=run['run_id'], model=run['model'],
            in_tokens=run.get('in_tokens'), out_tokens=run.get('out_tokens'),
            cost=CostResult(**run['cost']) if run.get('cost') else None,
            note=run.get('note', ''), show_divider=False)
        if info.get('requested'):
            text_fee = info.get('text_usd')
            search_fee = info.get('estimated_search_usd')
            total_fee = info.get('total_usd')
            fmt = lambda value: f'${value:.6f}' if value is not None else '不明'
            st.caption(f"本文 {fmt(text_fee)} ／ 検索 {fmt(search_fee)} ／ 合計 {fmt(total_fee)}"
                       f" ／ 検索実行数 {info.get('calls') if info.get('calls') is not None else '不明'}")
            st.caption(info.get('cost_kind', '') + '・単価確認日 ' + info.get('pricing_date', ''))


