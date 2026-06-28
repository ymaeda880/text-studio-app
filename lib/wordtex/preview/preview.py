# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/preview/preview.py
# ============================================================
# wordTex Preview
#
# Word / LibreOffice / OnlyOffice を切り替えて
# PDFプレビューする。
#
# - common_lib.preview.file_preview は使わない
# - UIは既存プレビューに近い構成にする
# - renderer="auto" は実際のレンダラ名へ解決してから使う
# ============================================================

from __future__ import annotations

from pathlib import Path

import streamlit as st

from lib.wordtex.preview.detect import (
    has_ms_word,
    has_libreoffice,
    has_onlyoffice,
)
from lib.wordtex.preview.exporter import (
    export_docx_to_pdf,
    renderer_display_name,
    resolve_renderer,
)
from lib.wordtex.preview.cache import (
    build_preview_pdf_path,
    write_preview_meta,
)
from lib.wordtex.preview.render_pdf import (
    get_pdf_page_count,
    clamp_page_no,
    render_pdf_preview,
)


def preview_page_key(key_prefix: str) -> str:
    return f"{key_prefix}__wordtex_preview_page"


def preview_page_input_key(key_prefix: str) -> str:
    return f"{key_prefix}__wordtex_preview_page_input"


def preview_width_key(key_prefix: str) -> str:
    return f"{key_prefix}__wordtex_preview_width"


def preview_renderer_key(key_prefix: str) -> str:
    return f"{key_prefix}__wordtex_preview_renderer"


def preview_regen_key(key_prefix: str, renderer: str) -> str:
    return f"{key_prefix}__wordtex_preview_regen__{renderer}"


def render_renderer_selector(
    *,
    key_prefix: str,
) -> str:
    renderer_items: list[tuple[str, str]] = [
        ("auto", "自動"),
        ("word", "Microsoft Word" + ("" if has_ms_word() else "（未インストール）")),
        ("libreoffice", "LibreOffice" + ("" if has_libreoffice() else "（未インストール）")),
        ("onlyoffice", "OnlyOffice" + ("" if has_onlyoffice() else "（未インストール）")),
    ]

    renderer_map = {label: value for value, label in renderer_items}

    label = st.radio(
        "レンダラ",
        options=list(renderer_map.keys()),
        horizontal=True,
        key=preview_renderer_key(key_prefix),
    )

    return renderer_map[label]


def ensure_wordtex_preview_pdf(
    *,
    docx_path: Path,
    preview_root: Path,
    renderer: str,
    key_prefix: str,
) -> Path | None:
    requested_renderer = str(renderer or "auto").lower()
    actual_renderer = resolve_renderer(requested_renderer)

    if actual_renderer == "none":
        st.error("利用可能なPDF変換レンダラがありません。")
        return None

    pdf_path = build_preview_pdf_path(
        preview_root=preview_root,
        docx_path=docx_path,
        renderer=actual_renderer,
    )

    st.caption(
        f"使用レンダラ: {renderer_display_name(actual_renderer)}"
    )

    regenerate = False

    if pdf_path.exists():
        regenerate = st.button(
            "🔄 PDFを再生成",
            key=preview_regen_key(
                key_prefix,
                actual_renderer,
            ),
        )

        if pdf_path.exists() and not regenerate:
            return pdf_path

    with st.spinner(
        f"{renderer_display_name(actual_renderer)}でPDFを生成しています..."
    ):
        pdf_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        ok = export_docx_to_pdf(
            docx_path=docx_path,
            pdf_path=pdf_path,
            renderer=actual_renderer,
        )

        if not ok:
            st.error("PDFの生成に失敗しました。")
            return None

        write_preview_meta(
            pdf_path=pdf_path,
            docx_path=docx_path,
            renderer=actual_renderer,
        )

    return pdf_path if pdf_path.exists() else None


def render_page_navigation(
    *,
    key_prefix: str,
    total_pages: int,
) -> int:
    page_key = preview_page_key(key_prefix)
    input_key = preview_page_input_key(key_prefix)

    preview_page = int(st.session_state.get(page_key, 1))
    preview_page = clamp_page_no(preview_page, total_pages)

    st.session_state[page_key] = preview_page

    if input_key not in st.session_state:
        st.session_state[input_key] = int(preview_page)
    else:
        try:
            st.session_state[input_key] = int(
                st.session_state[input_key]
            )
        except Exception:
            st.session_state[input_key] = int(preview_page)

    st.markdown(
        """
        <div style="height: 12px;"></div>
        <hr style="margin: 8px 0 16px 0; border: none; border-top: 1px solid #ddd;">
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])

    with c1:
        if st.button(
            "⬅ 前へ",
            key=f"{key_prefix}__preview_prev",
        ):
            if preview_page > 1:
                preview_page -= 1
                st.session_state[page_key] = preview_page
                st.session_state[input_key] = preview_page

    with c2:
        if st.button(
            "次へ ➡",
            key=f"{key_prefix}__preview_next",
        ):
            if preview_page < total_pages:
                preview_page += 1
                st.session_state[page_key] = preview_page
                st.session_state[input_key] = preview_page

    with c3:
        page_input = st.number_input(
            "ページ番号",
            min_value=1,
            max_value=max(1, int(total_pages)),
            step=1,
            key=input_key,
            label_visibility="collapsed",
        )

        if int(page_input) != int(preview_page):
            preview_page = int(page_input)
            st.session_state[page_key] = preview_page

    with c5:
        st.write(
            f"Page: {int(preview_page)} / {int(total_pages)}"
        )

    return int(preview_page)


def render_wordtex_preview(
    *,
    docx_path: Path,
    preview_root: Path,
    key_prefix: str,
) -> None:
    docx_path = Path(docx_path)

    if not docx_path.exists():
        st.info("Word文書がありません。")
        return

    renderer = render_renderer_selector(
        key_prefix=key_prefix,
    )

    width = st.slider(
        "表示倍率（%）",
        min_value=50,
        max_value=200,
        value=100,
        step=10,
        key=preview_width_key(key_prefix),
    )

    st.caption(f"現在倍率: {width}%")

    pdf_path = ensure_wordtex_preview_pdf(
        docx_path=docx_path,
        preview_root=preview_root,
        renderer=renderer,
        key_prefix=key_prefix,
    )

    if pdf_path is None or not pdf_path.exists():
        return

    total_pages = get_pdf_page_count(pdf_path)

    if total_pages is None or total_pages <= 0:
        st.info("PDFプレビューには PyMuPDF(fitz) が必要です。")
        return

    page_no = render_page_navigation(
        key_prefix=key_prefix,
        total_pages=int(total_pages),
    )

    max_width = int(600 * int(width) / 100)

    shown_total_pages = render_pdf_preview(
        pdf_path=pdf_path,
        display_name=docx_path.name,
        page_no=page_no,
        max_width=max_width,
    )

    if shown_total_pages is not None:
        current_page = clamp_page_no(
            page_no=page_no,
            total_pages=int(shown_total_pages),
        )
        st.caption(f"ページ {current_page} / {int(shown_total_pages)}")