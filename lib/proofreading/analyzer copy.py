# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Tuple

from .md_table_parser import parse_plan_md_tables


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
    """
    md_tables: List[str] = []
    total_pages = (len(lines) + lines_per_page - 1) // lines_per_page

    total_in_tokens = 0
    total_out_tokens = 0
    total_tokens = 0

    sys_inst_template = build_system_prompt(mode=mode, extra=extra)
    use_gemini = model.startswith("gemini")

    if use_gemini:
        if not gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY が未設定のため Gemini は利用できません。")
        try:
            from google import genai
        except Exception as e:
            raise RuntimeError("Gemini を使うには `pip install google-genai` が必要です。") from e
        gem_client = genai.Client(api_key=gemini_api_key)
    else:
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)

    for pg in range(total_pages):
        start = pg * lines_per_page
        end = min((pg + 1) * lines_per_page, len(lines))
        page_chunk = [f"[{(i + 1):04d}] {lines[i]}" for i in range(start, end)]
        page_text = "\n".join(page_chunk)

        if use_gemini:
            prompt = (
                f"{sys_inst_template}\n\n"
                f"次のテキスト（このページのみ）を解析してください：\n---\n{page_text}\n\n"
                "出力は必ず Markdown の表（| 行 | 重要度 | 原文 | 修正案 | 理由 |）で返してください。"
            )
            resp = gem_client.models.generate_content(model=model, contents=prompt)
            out_text = (getattr(resp, "text", "") or "").strip()
            md_tables.append(out_text)

            u = getattr(resp, "usage_metadata", None)
            if u is not None:
                in_t = int(getattr(u, "prompt_token_count", 0) or 0)
                out_t = int(getattr(u, "candidates_token_count", 0) or 0)
                tot_t = int(getattr(u, "total_token_count", 0) or (in_t + out_t))
            else:
                in_t = estimate_tokens_from_text(prompt)
                out_t = estimate_tokens_from_text(out_text)
                tot_t = in_t + out_t

        else:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys_inst_template},
                    {"role": "user", "content": f"次のテキスト（このページのみ）を解析してください：\n---\n{page_text}"},
                ],
            )
            out_text = resp.choices[0].message.content.strip()
            md_tables.append(out_text)

            usage = getattr(resp, "usage", None)
            if usage is not None:
                in_t = int(getattr(usage, "prompt_tokens", 0) or 0)
                out_t = int(getattr(usage, "completion_tokens", 0) or 0)
                tot_t = int(getattr(usage, "total_tokens", 0) or (in_t + out_t))
            else:
                in_t = estimate_tokens_from_text(sys_inst_template + "\n" + page_text)
                out_t = estimate_tokens_from_text(out_text)
                tot_t = in_t + out_t

        total_in_tokens += in_t
        total_out_tokens += out_t
        total_tokens += tot_t

    raw_md = "\n\n".join(md_tables)
    items = parse_plan_md_tables(raw_md)

    def _is_header_like(row: Dict[str, str]) -> bool:
        def norm(s: str) -> str:
            return (s or "").strip().lower()
        return (
            norm(row.get("頁", "")) in {"頁", "page", "ページ"} and
            norm(row.get("行", "")) in {"行", "line"} and
            norm(row.get("重要度", "")) in {"重要度", "issue", "問題点"} and
            norm(row.get("原文", "")) in {"原文", "original"} and
            norm(row.get("修正案", "")) in {"修正案", "suggestion", "提案"} and
            norm(row.get("理由", "")) in {"理由", "reason", "根拠"}
        )
    items = [row for row in items if not _is_header_like(row)]

    def esc_cell(s: str) -> str:
        s = (s or "").replace("|", r"\|")
        s = s.replace("\n", "<br/>")
        return s

    header = "| 行 | 重要度 | 原文 | 修正案 | 理由 |"
    sep    = "| --- | --- | --- | --- | --- |"
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

    final_md = "\n".join(rows)
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
    """
    sys_inst_template = build_system_prompt(mode=mode, extra=extra)
    use_gemini = model.startswith("gemini")

    # 全文を「全体通しの行番号」で付番してまとめる
    page_chunk = [f"[{(i + 1):04d}] {lines[i]}" for i in range(len(lines))]
    page_text = "\n".join(page_chunk)

    total_in_tokens = 0
    total_out_tokens = 0
    total_tokens = 0

    if use_gemini:
        if not gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY が未設定のため Gemini は利用できません。")
        try:
            from google import genai
        except Exception as e:
            raise RuntimeError("Gemini を使うには `pip install google-genai` が必要です。") from e
        gem_client = genai.Client(api_key=gemini_api_key)

        prompt = (
            f"{sys_inst_template}\n\n"
            f"次のテキスト（全文）を解析してください：\n---\n{page_text}\n\n"
            "出力は必ず Markdown の表（| 行 | 重要度 | 原文 | 修正案 | 理由 |）で返してください。"
        )
        resp = gem_client.models.generate_content(model=model, contents=prompt)
        out_text = (getattr(resp, "text", "") or "").strip()

        u = getattr(resp, "usage_metadata", None)
        if u is not None:
            in_t = int(getattr(u, "prompt_token_count", 0) or 0)
            out_t = int(getattr(u, "candidates_token_count", 0) or 0)
            tot_t = int(getattr(u, "total_token_count", 0) or (in_t + out_t))
        else:
            in_t = estimate_tokens_from_text(prompt)
            out_t = estimate_tokens_from_text(out_text)
            tot_t = in_t + out_t

    else:
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_inst_template},
                {
                    "role": "user",
                    "content": f"次のテキスト（全文）を解析してください：\n---\n{page_text}",
                },
            ],
        )
        out_text = (resp.choices[0].message.content or "").strip()

        usage = getattr(resp, "usage", None)
        if usage is not None:
            in_t = int(getattr(usage, "prompt_tokens", 0) or 0)
            out_t = int(getattr(usage, "completion_tokens", 0) or 0)
            tot_t = int(getattr(usage, "total_tokens", 0) or (in_t + out_t))
        else:
            in_t = estimate_tokens_from_text(sys_inst_template + "\n" + page_text)
            out_t = estimate_tokens_from_text(out_text)
            tot_t = in_t + out_t

    total_in_tokens += in_t
    total_out_tokens += out_t
    total_tokens += tot_t

    # ---- 以降は既存 analyze_issues() と同じ「表のパース＆正規化」ロジック ----
    raw_md = out_text
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

    final_md = "\n".join(rows)
    usage_summary = {
        "input_tokens": int(total_in_tokens),
        "output_tokens": int(total_out_tokens),
        "total_tokens": int(total_tokens),
        "pages": 1,
    }
    return final_md, usage_summary
