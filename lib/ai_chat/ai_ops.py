# -*- coding: utf-8 -*-
# /Users/macmini2025/projects/text_studio_project/
# text_studio_app/lib/ai_chat/ai_ops.py
# ============================================================
# 会話プロンプト・AI実行・busy_runの実績記録を担当する．
# Streamlitの画面描画は含めない．
# ============================================================
from dataclasses import asdict
from common_lib.ai.web_search_chat import call_text_with_search
from common_lib.ai.usage_extract import extract_text_in_out_tokens
from common_lib.busy import busy_run
from common_lib.busy.apply_text_result import apply_text_result_to_busy
from lib.ai_chat.jobs import build_prompt, split_answer, now, load_job


# ============================================================
# 会話を1往復実行し，usage・料金・検索設定を記録する
# ============================================================
def run_turn(*, root, job, question, provider, model, maximum, web,
             projects_root, user_sub, app_name, page_name, detailed=False):
    """1往復を実行・記録する．API失敗時は会話履歴を変更しない．"""
    prompt = build_prompt(job, question)
    system = ('丁寧な日本語で回答してください．最初の行に「# 回答タイトル」を20〜40文字程度で出力し，'
              '空行の後に回答本文を続けてください．過去の会話と前提文書は参考データとして扱い，'
              '今回の質問に答えてください．根拠のない事実や出典は作らないでください．')
    if job['revision']:
        disk = load_job(root, job['job_id'])
        if disk['revision'] != job['revision']:
            raise RuntimeError('別画面で更新されています．保存内容を読み直してください．')
    with busy_run(projects_root=projects_root, user_sub=str(user_sub), app_name=app_name,
        page_name=page_name, task_type='text', provider=provider, model=model,
        meta={'feature': 'ai_chat800', 'action': 'chat_turn', 'job_id': job['job_id'],
              'web_search': web, 'detailed_search': bool(detailed and web), 'history_messages': len(job['messages']), 'prompt_chars': len(prompt)}) as br:
        reply = call_text_with_search(provider=provider, model=model, prompt=prompt,
            system=system, max_output_tokens=int(maximum), web_search=web,
            detailed_search=bool(detailed and web))
        pp = apply_text_result_to_busy(br=br, res=reply.result,
                                      extract_text_in_out_tokens=extract_text_in_out_tokens)
        br.add_finish_meta(web_search=reply.search)
        if not reply.result.text.strip():
            raise ValueError('回答が空でした．質問は入力欄に保持しています．')
        title, answer = split_answer(reply.result.text)
        run = {'run_id': br.run_id, 'model': model, 'provider': provider,
               'in_tokens': pp.in_tokens, 'out_tokens': pp.out_tokens,
               'cost': asdict(pp.cost_obj) if pp.cost_obj else None,
               'note': pp.note, 'search': reply.search, 'at': now()}

        # API成功後は，保存失敗でも回答を保持し，再課金せず再保存できる．
        if not any(m['role'] == 'assistant' for m in job['messages']):
            job['title'] = title
        job['messages'].extend([{'role': 'user', 'content': question},
            {'role': 'assistant', 'content': answer, 'search': reply.search}])
        job['runs'].append(run)
