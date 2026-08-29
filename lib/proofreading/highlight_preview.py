# -*- coding: utf-8 -*-
# text_studio_app/lib/proofreading/highlight_preview.py
# ============================================================
# 校正方針 原文ハイライト表示
#
# 機能：
# - AIが返したMarkdown表から「行」「原文」を取得する
# - 行番号付き原文と照合する
# - 校正対象の原文部分だけをハイライト表示する
# - 句読点・空白・Unicode差を吸収して照合する
# - 「〜」「～」「…」「...」「・・・」を省略表現として扱う
#
# 方針：
# - 400_文章校正2.py / 410_一括word校正2.py で共通利用する
# - AIへの再問い合わせは行わない
# - 既存の 03_文章校正.py / 12_一括word校正.py は変更しない
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import html
import re
import unicodedata

import streamlit as st


def _split_markdown_table_row(row: str) -> list[str]:
    # ------------------------------------------------------------
    # Markdown表の1行をセルへ分割する
    # ------------------------------------------------------------
    s = str(row or "").strip()

    if s.startswith("|"):
        s = s[1:]

    if s.endswith("|"):
        s = s[:-1]

    return [cell.strip() for cell in s.split("|")]


def _is_markdown_separator_row(cells: list[str]) -> bool:
    # ------------------------------------------------------------
    # Markdown表の区切り行か確認する
    # ------------------------------------------------------------
    if not cells:
        return False

    for cell in cells:
        s = str(cell or "").strip().replace(" ", "")

        if not re.fullmatch(r":?-{3,}:?", s):
            return False

    return True


def _normalize_policy_header(value: str) -> str:
    # ------------------------------------------------------------
    # Markdown表ヘッダーの比較用文字列を作る
    # ------------------------------------------------------------
    s = str(value or "").strip()
    s = s.replace(" ", "")
    s = s.replace("　", "")
    s = s.replace("<br>", "")
    s = s.replace("<br/>", "")
    s = s.replace("<br />", "")
    return s


def _find_policy_column_index(
    headers: list[str],
    candidates: tuple[str, ...],
) -> int | None:
    # ------------------------------------------------------------
    # 候補名から対象列を探す
    # ------------------------------------------------------------
    normalized_candidates = {
        _normalize_policy_header(candidate)
        for candidate in candidates
    }

    for index, header in enumerate(headers):
        normalized = _normalize_policy_header(header)

        if normalized in normalized_candidates:
            return index

    return None


def _extract_line_numbers(value: str) -> list[int]:
    # ------------------------------------------------------------
    # 行番号欄から対象行番号を抽出する
    # 例：
    # - 12
    # - [0012]
    # - 12-14
    # - 12～14
    # - 12, 14
    # ------------------------------------------------------------
    s = str(value or "").strip()

    if not s:
        return []

    s = s.replace("−", "-")
    s = s.replace("–", "-")
    s = s.replace("—", "-")
    s = s.replace("〜", "～")
    s = s.replace("~", "～")

    numbers: list[int] = []

    # 範囲を先に処理
    range_pattern = re.compile(
        r"(?<!\d)(\d{1,6})\s*(?:-|～)\s*(\d{1,6})(?!\d)"
    )

    for match in range_pattern.finditer(s):
        start = int(match.group(1))
        end = int(match.group(2))

        if start <= end and (end - start) <= 5000:
            numbers.extend(range(start, end + 1))
        elif end < start and (start - end) <= 5000:
            numbers.extend(range(end, start + 1))

    # 範囲部分を消してから単独番号を取得
    s_without_ranges = range_pattern.sub(" ", s)

    for match in re.finditer(r"(?<!\d)(\d{1,6})(?!\d)", s_without_ranges):
        numbers.append(int(match.group(1)))

    # 順序を維持して重複除去
    result: list[int] = []
    seen: set[int] = set()

    for number in numbers:
        if number <= 0:
            continue

        if number in seen:
            continue

        seen.add(number)
        result.append(number)

    return result


def _clean_policy_original_text(value: str) -> str:
    # ------------------------------------------------------------
    # 「原文」セルを照合しやすい形へ整える
    # ------------------------------------------------------------
    s = str(value or "").strip()

    if not s:
        return ""

    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = s.replace("&nbsp;", " ")

    # Markdownのコード記号・引用符を軽く除去
    s = s.strip("`")
    s = s.strip()

    quote_pairs = (
        ("「", "」"),
        ("『", "』"),
        ('"', '"'),
        ("“", "”"),
        ("‘", "’"),
    )

    for left, right in quote_pairs:
        if s.startswith(left) and s.endswith(right) and len(s) >= 2:
            s = s[len(left):]
            s = s[:-len(right)]
            s = s.strip()
            break

    return s


def _parse_policy_highlight_targets(
    plan_md: str,
) -> dict[int, list[str]]:
    # ------------------------------------------------------------
    # 校正方針Markdown表から
    # 行番号 -> 原文文字列一覧
    # を作る
    # ------------------------------------------------------------
    rows = [
        line
        for line in str(plan_md or "").splitlines()
        if "|" in line
    ]

    if len(rows) < 2:
        return {}

    header_cells = _split_markdown_table_row(rows[0])

    line_col = _find_policy_column_index(
        header_cells,
        (
            "行",
            "行番号",
            "該当行",
            "対象行",
            "ページ/行",
            "ページ／行",
            "頁/行",
            "頁／行",
        ),
    )

    original_col = _find_policy_column_index(
        header_cells,
        (
            "原文",
            "該当原文",
            "対象原文",
            "修正前",
            "校正前",
        ),
    )

    if line_col is None or original_col is None:
        return {}

    targets: dict[int, list[str]] = {}

    for row in rows[1:]:
        cells = _split_markdown_table_row(row)

        if _is_markdown_separator_row(cells):
            continue

        if line_col >= len(cells) or original_col >= len(cells):
            continue

        line_numbers = _extract_line_numbers(cells[line_col])
        original_text = _clean_policy_original_text(cells[original_col])

        if not line_numbers or not original_text:
            continue

        # セル内に改行相当がある場合は候補を分ける
        original_candidates = [
            part.strip()
            for part in original_text.splitlines()
            if part.strip()
        ]

        if not original_candidates:
            original_candidates = [original_text]

        for line_number in line_numbers:
            bucket = targets.setdefault(line_number, [])

            for candidate in original_candidates:
                if candidate not in bucket:
                    bucket.append(candidate)

    return targets


def _normalize_for_highlight(
    value: str,
) -> tuple[str, list[int]]:
    # ------------------------------------------------------------
    # ハイライト照合用に文字列を正規化する
    #
    # 吸収する差：
    # - Unicode全角／半角
    # - 「，」「、」→ ","
    # - 「．」「。」→ "."
    # - 各種空白
    # - Markdown装飾記号
    #
    # 戻り値：
    # - 正規化文字列
    # - 正規化後の各文字が元文字列の何文字目かを示すmap
    # ------------------------------------------------------------
    src = str(value or "")

    normalized_chars: list[str] = []
    index_map: list[int] = []

    punctuation_map = {
        "，": ",",
        "、": ",",
        "．": ".",
        "。": ".",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "［": "[",
        "］": "]",
        "｛": "{",
        "｝": "}",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }

    ignored_chars = {
        "*",
        "`",
        "\u200b",   # zero width space
        "\u200c",
        "\u200d",
        "\ufeff",
    }

    for original_index, char in enumerate(src):
        if char in ignored_chars:
            continue

        # 空白差は照合上無視
        if char.isspace():
            continue

        piece = unicodedata.normalize("NFKC", char)

        for normalized_char in piece:
            if normalized_char.isspace():
                continue

            normalized_char = punctuation_map.get(
                normalized_char,
                normalized_char,
            )

            normalized_chars.append(normalized_char)
            index_map.append(original_index)

    return "".join(normalized_chars), index_map


def _normalize_target_piece(
    value: str,
) -> str:
    # ------------------------------------------------------------
    # ターゲット側だけ正規化する簡易ラッパー
    # ------------------------------------------------------------
    normalized, _ = _normalize_for_highlight(value)
    return normalized


def _find_normalized_exact_ranges(
    *,
    line_text: str,
    target: str,
) -> list[tuple[int, int]]:
    # ------------------------------------------------------------
    # 見た目が同じだが内部表現が違う文字列を照合する
    # ------------------------------------------------------------
    normalized_line, index_map = _normalize_for_highlight(
        line_text
    )
    normalized_target = _normalize_target_piece(
        target
    )

    if not normalized_line or not normalized_target:
        return []

    ranges: list[tuple[int, int]] = []
    start = 0

    while True:
        index = normalized_line.find(
            normalized_target,
            start,
        )

        if index < 0:
            break

        normalized_end = index + len(normalized_target) - 1

        if (
            index < len(index_map)
            and normalized_end < len(index_map)
        ):
            original_start = index_map[index]
            original_end = index_map[normalized_end] + 1

            ranges.append(
                (
                    original_start,
                    original_end,
                )
            )

        start = index + max(
            len(normalized_target),
            1,
        )

    return ranges


def _split_ellipsis_target(
    target: str,
) -> list[str]:
    # ------------------------------------------------------------
    # AIが省略表現として使う記号で分割する
    # ------------------------------------------------------------
    return [
        part
        for part in re.split(
            r"(?:〜|～|…+|\.{3,}|・{3,})",
            str(target or ""),
        )
        if str(part or "").strip()
    ]


def _find_ellipsis_range(
    *,
    line_text: str,
    target: str,
) -> tuple[int, int] | None:
    # ------------------------------------------------------------
    # 「〜」等を，同一行内の任意文字列として照合する
    #
    # 例：
    #   一部の学生では提出物の〜誤りが見られたため，
    #
    # 元文：
    #   一部の学生では提出物のおくれや記載内容の誤りが見られたため，
    #
    # → 前半と後半を順に見つけ，間も含めてハイライト
    # ------------------------------------------------------------
    parts = _split_ellipsis_target(target)

    if len(parts) < 2:
        return None

    normalized_line, index_map = _normalize_for_highlight(
        line_text
    )

    if not normalized_line or not index_map:
        return None

    normalized_parts = [
        _normalize_target_piece(part)
        for part in parts
    ]
    normalized_parts = [
        part
        for part in normalized_parts
        if part
    ]

    if len(normalized_parts) < 2:
        return None

    search_pos = 0
    first_index: int | None = None
    last_end: int | None = None

    for part in normalized_parts:
        index = normalized_line.find(
            part,
            search_pos,
        )

        if index < 0:
            return None

        if first_index is None:
            first_index = index

        last_end = index + len(part)
        search_pos = last_end

    if first_index is None or last_end is None:
        return None

    normalized_last_index = last_end - 1

    if (
        first_index >= len(index_map)
        or normalized_last_index >= len(index_map)
    ):
        return None

    return (
        index_map[first_index],
        index_map[normalized_last_index] + 1,
    )


def _extract_target_variants(
    target: str,
) -> list[str]:
    # ------------------------------------------------------------
    # AIが「原文」欄に引用・抜粋説明を付けた場合にも対応する
    #
    # 元セルそのものを最優先し，
    # 「...」「『...』」内の文字列も候補に加える
    # ------------------------------------------------------------
    s = str(target or "").strip()

    if not s:
        return []

    variants: list[str] = [s]

    quote_patterns = (
        r"「([^」]+)」",
        r"『([^』]+)』",
        r'"([^"]+)"',
        r"“([^”]+)”",
    )

    for pattern in quote_patterns:
        for match in re.finditer(pattern, s):
            candidate = str(match.group(1) or "").strip()

            if candidate and candidate not in variants:
                variants.append(candidate)

    return variants


def _highlight_line_html(
    line_text: str,
    targets: list[str],
) -> tuple[str, int]:
    # ------------------------------------------------------------
    # 1行の原文中で校正対象文字列だけをハイライトする
    #
    # 照合順：
    # 1. 完全一致
    # 2. Unicode・空白・句読点を吸収した正規化一致
    # 3. 「〜」「～」「…」「...」「・・・」を省略として照合
    # 4. 引用符内の文字列も候補として照合
    # ------------------------------------------------------------
    line = str(line_text or "")

    if not targets:
        return html.escape(line), 0

    ranges: list[tuple[int, int]] = []

    for raw_target in sorted(
        {str(x) for x in targets if str(x)},
        key=len,
        reverse=True,
    ):
        variants = _extract_target_variants(
            raw_target
        )

        target_matched = False

        for target in variants:
            # ----------------------------------------------------
            # 1. 完全一致
            # ----------------------------------------------------
            exact_start = 0
            exact_ranges: list[tuple[int, int]] = []

            while True:
                index = line.find(
                    target,
                    exact_start,
                )

                if index < 0:
                    break

                exact_ranges.append(
                    (
                        index,
                        index + len(target),
                    )
                )

                exact_start = index + max(
                    len(target),
                    1,
                )

            if exact_ranges:
                ranges.extend(exact_ranges)
                target_matched = True
                break

            # ----------------------------------------------------
            # 2. 正規化一致
            # ----------------------------------------------------
            normalized_ranges = _find_normalized_exact_ranges(
                line_text=line,
                target=target,
            )

            if normalized_ranges:
                ranges.extend(normalized_ranges)
                target_matched = True
                break

            # ----------------------------------------------------
            # 3. 省略記号つき一致
            # ----------------------------------------------------
            ellipsis_range = _find_ellipsis_range(
                line_text=line,
                target=target,
            )

            if ellipsis_range is not None:
                ranges.append(ellipsis_range)
                target_matched = True
                break

        if target_matched:
            continue

    if not ranges:
        return html.escape(line), 0

    # ------------------------------------------------------------
    # 重複・隣接範囲を統合
    # ------------------------------------------------------------
    ranges.sort()

    merged: list[list[int]] = []

    for range_start, range_end in ranges:
        if (
            not merged
            or range_start > merged[-1][1]
        ):
            merged.append(
                [
                    range_start,
                    range_end,
                ]
            )
        else:
            merged[-1][1] = max(
                merged[-1][1],
                range_end,
            )

    # ------------------------------------------------------------
    # HTML生成
    # ------------------------------------------------------------
    parts: list[str] = []
    cursor = 0

    for range_start, range_end in merged:
        parts.append(
            html.escape(
                line[cursor:range_start]
            )
        )

        parts.append(
            '<mark class="proof-highlight">'
            + html.escape(
                line[range_start:range_end]
            )
            + "</mark>"
        )

        cursor = range_end

    parts.append(
        html.escape(
            line[cursor:]
        )
    )

    return "".join(parts), len(merged)


def render_policy_highlight_preview(
    *,
    numbered_preview: str,
    plan_md: str,
) -> None:
    # ------------------------------------------------------------
    # 校正方針に載っている「原文」を
    # 行番号付き原文の中でハイライト表示する
    # ------------------------------------------------------------
    targets_by_line = _parse_policy_highlight_targets(
        plan_md
    )

    source_lines = str(
        numbered_preview or ""
    ).splitlines()

    rendered_lines: list[str] = []
    highlighted_count = 0
    target_line_count = len(targets_by_line)

    numbered_pattern = re.compile(
        r"^\[(\d+)\]\s?(.*)$"
    )

    for source_line in source_lines:
        match = numbered_pattern.match(source_line)

        if match is None:
            rendered_lines.append(
                html.escape(source_line)
            )
            continue

        line_number = int(match.group(1))
        line_text = match.group(2)

        highlighted_text, count = _highlight_line_html(
            line_text,
            targets_by_line.get(
                line_number,
                [],
            ),
        )

        highlighted_count += count

        rendered_lines.append(
            '<span class="proof-line-number">'
            f"[{line_number:04d}]"
            "</span> "
            + highlighted_text
        )

    st.markdown(
        """
<style>
.proof-highlight-preview {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 6px;
    padding: 12px 14px;
    max-height: 420px;
    overflow-y: auto;
    background: rgba(128, 128, 128, 0.04);
    font-family:
        SFMono-Regular,
        Consolas,
        "Liberation Mono",
        Menlo,
        monospace;
    font-size: 0.90rem;
    line-height: 1.55;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
.proof-line-number {
    color: #777;
    user-select: none;
}
.proof-highlight {
    background: #fff59d;
    color: inherit;
    padding: 0 1px;
    border-radius: 2px;
}
</style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="proof-highlight-preview">'
        + "<br>".join(rendered_lines)
        + "</div>",
        unsafe_allow_html=True,
    )

    if not targets_by_line:
        st.warning(
            "校正方針から「行番号」と「原文」を取得できなかったため，"
            "ハイライトできませんでした。"
        )
    elif highlighted_count == 0:
        st.warning(
            "校正方針の対象行は取得できましたが，"
            "「原文」と元テキストが完全一致する箇所を見つけられませんでした。"
        )
    else:
        st.caption(
            f"校正方針の対象 {target_line_count} 行を確認し，"
            f"原文の一致箇所 {highlighted_count} 箇所をハイライトしています。"
        )
