# -*- coding: utf-8 -*-
# /Users/macmini2025/projects/text_studio_project/
# text_studio_app/lib/ai_chat/jobs.py
# ============================================================
# AIチャットのジョブ：利用者ごとに最新5件（作成順）を保持する．
# JSONは原子的に保存し，同時更新はrevisionで検出する．
# ============================================================
import copy
import fcntl
import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo


def now():
    return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='microseconds')


def user_dir(storage_root: Path, user: str) -> Path:
    username = re.sub(r'[^0-9A-Za-z_-]+', '_', user.strip()).strip('_') or 'anonymous'
    return storage_root / username / 'text_studio_app' / 'ai_chat800'


def new_job():
    stamp = now()
    return {'schema': 'chat_history_v2', 'job_id': 'job_' + uuid4().hex,
            'title': '新しい会話', 'created_at': stamp, 'updated_at': stamp,
            'messages': [], 'doc_context': None, 'runs': [], 'revision': 0}


@contextmanager
def _lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.jobs.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _path(root, job_id):
    if not re.fullmatch(r'job_[0-9a-f]{32}', job_id):
        raise ValueError('ジョブIDが不正です．')
    path = root / job_id
    if path.is_symlink():
        raise ValueError('リンク先のジョブは読み書きしません．')
    return path / 'job.json'


def list_jobs(root):
    result = []
    for path in root.glob('job_*/job.json'):
        if path.parent.is_symlink() or path.is_symlink():
            continue
        try:
            job = json.loads(path.read_text(encoding='utf-8'))
            if _path(root, job['job_id']) == path and job.get('schema') == 'chat_history_v2':
                result.append(job)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(result, key=lambda j: j['created_at'], reverse=True)


def load_job(root, job_id):
    path = _path(root, job_id)
    if path.is_symlink():
        raise ValueError('リンク先のファイルは読みません．')
    return json.loads(path.read_text(encoding='utf-8'))


def save_job(root, job):
    with _lock(root):
        path = _path(root, job['job_id'])
        if path.is_symlink():
            raise ValueError('リンク先のファイルには保存しません．')
        if path.exists():
            disk = json.loads(path.read_text(encoding='utf-8'))
            if disk.get('revision') != job.get('revision'):
                raise RuntimeError('別画面で会話が更新されています．JSONをダウンロードしてから，保存済みジョブを選び直してください．')
        elif job.get('revision', 0) > 0:
            raise RuntimeError('このジョブは保持件数の対象外になりました．JSONをダウンロードし，新規ジョブとして取り込んでください．')
        saved = copy.deepcopy(job)
        saved['revision'] = job.get('revision', 0) + 1
        saved['updated_at'] = now()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                json.dump(saved, out, ensure_ascii=False, indent=2)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        job.update(saved)
        deleted = []
        for old in list_jobs(root)[5:]:
            old_path = _path(root, old['job_id']).parent
            shutil.rmtree(old_path)
            deleted.append(old['title'])
        return deleted


def import_history(raw):
    obj = json.loads(raw.decode('utf-8-sig'))
    msgs = obj.get('messages') if isinstance(obj, dict) else obj
    if not isinstance(msgs, list) or any(
        not isinstance(m, dict) or m.get('role') not in ('user', 'assistant', 'system')
        or not isinstance(m.get('content'), str) for m in msgs
    ):
        raise ValueError('messagesの形式が不正です．18ページのJSONも取り込めます．')
    job = new_job()
    # 取り込み元のjob_id/revision/実行ログは信頼せず，新しいジョブを作る．
    job['messages'] = []
    for msg in msgs:
        clean = {'role': msg['role'], 'content': msg['content']}
        search = msg.get('search')
        if isinstance(search, dict):
            # アップロードJSON由来のHTML・料金・検索済み表示は再利用しない．
            sources = search.get('sources') or []
            clean['search'] = {'sources': [s for s in sources if isinstance(s, dict)
                and isinstance(s.get('title'), str) and isinstance(s.get('url'), str)]}
        job['messages'].append(clean)
    if isinstance(obj, dict):
        ctx = obj.get('doc_context')
        if ctx is not None and (not isinstance(ctx, dict) or not isinstance(ctx.get('text'), str)
                                or not isinstance(ctx.get('kind'), str)):
            raise ValueError('前提文書の形式が不正です．')
        job['doc_context'] = ctx
        job['title'] = str(obj.get('title') or '取り込んだ会話')[:80]
    return job


def split_answer(text):
    lines = text.strip().splitlines()
    if not lines:
        raise ValueError('回答が空でした．')
    head = lines[0].lstrip('# ').strip()
    # タイトルを生成させるが，形式が守られなくても回答を捨てない．
    title = re.sub(r'^(タイトル|題名)\s*[:：]\s*', '', head).strip()[:80]
    return title or 'AIとの会話', text.strip()


def build_prompt(job, question):
    return json.dumps({'前提文書': job.get('doc_context'),
                       'これまでの会話': [{'role': m['role'], 'content': m['content']}
                                  for m in job['messages']],
                       '今回の質問': question}, ensure_ascii=False)
