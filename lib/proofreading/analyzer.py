# -*- coding: utf-8 -*-
# test_studio_app/lib/proofreading/ana;yzer.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .md_table_parser import parse_plan_md_tables

# ✅ 正本：common_lib.ai を使う（OpenAI/Gemini差は吸収）
from common_lib.ai import call_text


def _provider_from_model(model: str) -> str:
    return "gemini" if str(model).startswith("gemini") else "openai"


def _extract_usage_tokens_from_result(res: Any) -> tuple[int | None, int | None, int | None]:
    """
    common_lib.ai の result から tokens を安全に抽出。
    - res.usage が dict / object の両方に対応
    - input/output/total が無ければ prompt/completion を見る
    """
    usage = getattr(res, "usage", None)
    if usage is None:
        return (None, None, None)

    def _get(u: Any, key: str) -> int | None:
        if u is None:
            return None
        if isinstance(u, dict):
            v = u.get(key)
        else:
            v = getattr(u, key, None)
        if v is None:
            return None
        try:
            return int(v)
        except Exception:
            return None

    in_tok = _get(usage, "input_tokens")
    out_tok = _get(usage, "output_tokens")
    tot_tok = _get(usage, "total_tokens")

    if in_tok is None:
        in_tok = _get(usage, "prompt_tokens")
    if out_tok is None:
        out_tok = _get(usage, "completion_tokens")
    if tot_tok is None and (in_tok is not None or out_tok is not None):
        tot_tok = int((in_tok or 0) + (out_tok or 0))

    return (in_tok, out_tok, tot_tok)


def _finalize_plan_md(*, raw_md: str) -> str:
    """
    Markdown 表（複数表でも可）をパースして、
    1個の大きな表（ヘッダ1回）に正規化して返す。
    """
    items = parse_plan_md_tables(raw_md)

    def _is_header_like(row: Dict[str, str]) -> bool:
        def norm(s: str) -> str:
            return (s or "").strip().lower()

        return (
            norm(row.get("頁", "")) in {"頁", "page", "ページ"}
            and norm(row.get("行", "")) in {"行", "line"}
            and norm(row.get("重要度", "")) in {"重要度", "issue", "問題点"}
            and norm(row.get("原文", "")) in {"原文", "original"}
            and norm(row.get("修正案", "")) in {"修正案", "suggestion", "提案"}
            and norm(row.get("理由", "")) in {"理由", "reason", "根拠"}
        )

    items = [row for row in items if not _is_header_like(row)]

    def esc_cell(s: str) -> str:
        s = (s or "").replace("|", r"\|")
        s = s.replace("\n", "<br/>")
        return s

    header = "| 行 | 重要度 | 原文 | 修正案 | 理由 |"
    sep = "| --- | --- | --- | --- | --- |"
    rows = [header, sep]
    for it in items:
        rows.append(
            "| {line} | {imp} | {orig} | {sugg} | {reason} |".format(
                line=esc_cell(it.get("行", "")),
                imp=esc_cell(it.get("重要度", "")),
                orig=esc_cell(it.get("原文", "")),
                sugg=esc_cell(it.get("修正案", "")),
                reason=esc_cell(it.get("理由", "")),
            )
        )

    return "\n".join(rows)


def analyze_issues(
    *,
    model: str,
    lines: List[str],
    lines_per_page: int,
    mode: str,
    extra: str,
    build_system_prompt,
    estimate_tokens_from_text,
    openai_api_key: str,
    gemini_api_key: str | None,
) -> Tuple[str, Dict[str, int]]:
    """
    ページ単位でモデルから Markdown 表を取得し、
    まとめて 1 個の大きな表（ヘッダー 1 回だけ）に組み直して返す。
    さらに token usage（input/output/total）も返す。

    ✅ 変更点：
    - OpenAI/Gemini の SDK 直叩きを廃止
    - common_lib.ai.call_text を正本として使用（provider差を吸収）
    - openai_api_key / gemini_api_key は互換のため受け取る（この関数では未使用）
    """
    md_tables: List[str] = []
    total_pages = (len(lines) + lines_per_page - 1) // lines_per_page

    total_in_tokens = 0
    total_out_tokens = 0
    total_tokens = 0

    sys_inst_template = build_system_prompt(mode=mode, extra=extra)
    provider = _provider_from_model(model)

    for pg in range(total_pages):
        start = pg * lines_per_page
        end = min((pg + 1) * lines_per_page, len(lines))
        page_chunk = [f"[{(i + 1):04d}] {lines[i]}" for i in range(start, end)]
        page_text = "\n".join(page_chunk)

        prompt = (
            "次のテキスト（このページのみ）を解析してください：\n---\n"
            f"{page_text}\n\n"
            "出力は必ず Markdown の表（| 行 | 重要度 | 原文 | 修正案 | 理由 |）で返してください。"
        )

        res = call_text(
            provider=provider,
            model=model,
            prompt=prompt,
            system=sys_inst_template,
        )

        out_text = (getattr(res, "text", "") or "").strip()
        md_tables.append(out_text)

        in_t, out_t, tot_t = _extract_usage_tokens_from_result(res)
        if in_t is None or out_t is None or tot_t is None:
            # usage が取れない場合は推計
            in_t2 = estimate_tokens_from_text(sys_inst_template + "\n" + prompt)
            out_t2 = estimate_tokens_from_text(out_text)
            tot_t2 = in_t2 + out_t2
            in_t, out_t, tot_t = in_t2, out_t2, tot_t2

        total_in_tokens += int(in_t)
        total_out_tokens += int(out_t)
        total_tokens += int(tot_t)

    raw_md = "\n\n".join(md_tables)
    final_md = _finalize_plan_md(raw_md=raw_md)

    usage_summary = {
        "input_tokens": int(total_in_tokens),
        "output_tokens": int(total_out_tokens),
        "total_tokens": int(total_tokens),
        "pages": int(total_pages),
    }
    return final_md, usage_summary


def analyze_issues_singlecall(
    *,
    model: str,
    lines: List[str],
    lines_per_page: int,  # 互換性のため受け取る（この関数では未使用）
    mode: str,
    extra: str,
    build_system_prompt,
    estimate_tokens_from_text,
    openai_api_key: str,
    gemini_api_key: str | None,
) -> Tuple[str, Dict[str, int]]:
    """
    ループ無し（=全文を1回で解析）版。
    - lines 全体を 1 回の API 呼び出しで Markdown 表として返させる
    - 返ってきた表（複数表でも可）をパースして、最終的に 1 個の大きな表に整形して返す
    - token usage（input/output/total）も返す

    ✅ 変更点：
    - OpenAI/Gemini の SDK 直叩きを廃止
    - common_lib.ai.call_text を正本として使用（provider差を吸収）
    - openai_api_key / gemini_api_key は互換のため受け取る（この関数では未使用）
    """
    sys_inst_template = build_system_prompt(mode=mode, extra=extra)
    provider = _provider_from_model(model)

    # 全文を「全体通しの行番号」で付番してまとめる
    page_chunk = [f"[{(i + 1):04d}] {lines[i]}" for i in range(len(lines))]
    page_text = "\n".join(page_chunk)

    prompt = (
        "次のテキスト（全文）を解析してください：\n---\n"
        f"{page_text}\n\n"
        "出力は必ず Markdown の表（| 行 | 重要度 | 原文 | 修正案 | 理由 |）で返してください。"
    )

    res = call_text(
        provider=provider,
        model=model,
        prompt=prompt,
        system=sys_inst_template,
    )

    out_text = (getattr(res, "text", "") or "").strip()

    in_t, out_t, tot_t = _extract_usage_tokens_from_result(res)
    if in_t is None or out_t is None or tot_t is None:
        in_t2 = estimate_tokens_from_text(sys_inst_template + "\n" + prompt)
        out_t2 = estimate_tokens_from_text(out_text)
        tot_t2 = in_t2 + out_t2
        in_t, out_t, tot_t = in_t2, out_t2, tot_t2

    final_md = _finalize_plan_md(raw_md=out_text)

    usage_summary = {
        "input_tokens": int(in_t),
        "output_tokens": int(out_t),
        "total_tokens": int(tot_t),
        "pages": 1,
    }
    return final_md, usage_summary
