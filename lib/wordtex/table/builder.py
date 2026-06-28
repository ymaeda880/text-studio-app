# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/table/builder.py
# ============================================================
# wordTex table builder
# ============================================================

from __future__ import annotations

from lib.table.helpers import (
    _compute_col_widths_cm as compute_col_widths_cm,
    _compute_spans_markers as compute_spans_markers,
    _merge_docx_by_spans as merge_docx_by_spans,
    _apply_docx_col_widths as apply_docx_col_widths,
    _apply_table_borders_robust as apply_table_borders_robust,
    _apply_font_run as apply_font_run,
)

from lib.wordtex.table.style import resolve_table_preset


TOTAL_CM = 16.0


def add_table_block(
    doc,
    block,
    settings: dict,
) -> None:
    """
    TableBlock を Word 文書へ追加する。
    """
    rows = getattr(block, "rows", [])

    if not rows:
        return

    preset = resolve_table_preset(getattr(block, "style", "simple"))

    header_rows = max(0, min(int(getattr(block, "header_rows", 1)), len(rows)))
    header_cols = max(0, min(int(getattr(block, "header_cols", 0)), len(rows[0])))

    font_name = preset.get("font_name", "Meiryo")
    header_bg = preset.get("header_bg") or "#EEEEEE"
    header_fg = preset.get("header_fg") or "#000000"
    body_bg = preset.get("body_bg")
    body_fg = preset.get("body_fg") or "#000000"

    inner_h = bool(preset.get("inner_h", True))
    inner_v = bool(preset.get("inner_v", True))
    outer = bool(preset.get("outer", True))
    zebra = bool(preset.get("zebra", False))
    outer_mode = preset.get("outer_mode", "box")

    body_size = int(getattr(settings, "table_body_size", 10))
    header_size = int(getattr(settings, "table_header_size", body_size + 1))

    caption_position = str(
        getattr(settings, "table_caption_position", "top")
    ).strip().lower()

    caption_text = build_table_caption_text(
        block=block,
        settings=settings,
    )

    if caption_position == "top" and caption_text:
        p = doc.add_paragraph()
        run = p.add_run(caption_text)
        apply_font_run(run, font_name, body_size, "#000000", bold=False)

    table = doc.add_table(rows=len(rows), cols=len(rows[0]))

    widths_cm = compute_col_widths_cm(rows, total_cm=TOTAL_CM)
    apply_docx_col_widths(table, widths_cm)

    spans = compute_spans_markers(
        rows,
        use_up=True,
        use_left=True,
        header_rows=header_rows,
        strict_rect=True,
    )

    merge_docx_by_spans(
        table,
        rows,
        spans,
        font_name=font_name,
        base_size=body_size,
        header_size=header_size,
        header_fg=header_fg,
        body_fg=body_fg,
        header_bg=header_bg,
        body_bg=body_bg,
        zebra=zebra,
        header_same=False,
        body_bg_on=body_bg is not None,
        header_rows=header_rows,
        header_cols=header_cols,
    )

    apply_table_borders_robust(
        table,
        spans,
        inner_h=inner_h,
        inner_v=inner_v,
        outer=outer,
        outer_mode=outer_mode,
        sz_inner=6,
        sz_outer=12,
        color="000000",
    )

    if caption_position == "bottom" and caption_text:
        p = doc.add_paragraph()
        run = p.add_run(caption_text)
        apply_font_run(run, font_name, body_size, "#000000", bold=False)

    note = str(getattr(block, "note", "") or "").strip()

    if note:
        p = doc.add_paragraph()
        run = p.add_run(note)
        apply_font_run(run, font_name, body_size, "#444444", bold=False)


def build_table_caption_text(
    *,
    block,
    settings,
) -> str:
    """
    table_caption / table_caption_sep / table_numbers / table_format に従って
    表キャプションを作る。
    """
    caption = str(
        getattr(block, "caption", "") or getattr(block, "title", "") or ""
    ).strip()

    if not caption:
        return ""

    table_caption = str(getattr(settings, "table_caption", "表"))
    table_caption_sep = str(getattr(settings, "table_caption_sep", "："))
    table_numbers = int(getattr(settings, "table_numbers", 1))
    table_format = str(getattr(settings, "table_format", "{1}"))

    if table_numbers:
        number = int(getattr(settings, "_table_counter", 0)) + 1
        setattr(settings, "_table_counter", number)

        number_text = table_format.replace("{1}", str(number))
        return f"{table_caption}{number_text}{table_caption_sep}{caption}"

    return caption