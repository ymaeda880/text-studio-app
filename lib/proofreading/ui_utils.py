# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
from html import escape
from typing import List

import streamlit as st


def display_pdf_bytes(data: bytes, height: int = 600) -> None:
    """Streamlit PDF表示（streamlit[pdf] があれば st.pdf）。なければ iframe 埋め込み。"""
    try:
        st.pdf(data, height=height)  # Streamlit 1.31+ / streamlit[pdf]
    except Exception:
        b64 = base64.b64encode(data).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}px"></iframe>',
            unsafe_allow_html=True,
        )


def to_numbered_lines(raw: str) -> List[str]:
    return raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def render_preview_with_numbers(lines: List[str], lines_per_page: int) -> str:
    _ = lines_per_page  # 互換のため引数は残す
    return "\n".join(f"[{i+1:04d}] {t}" for i, t in enumerate(lines))


def md_table_to_html(md: str) -> str:
    """
    Markdown表（|...|...|）を簡易HTML tableに変換。
    期待：ヘッダ行 + セパレータ行 + ボディ行...
    """
    lines_ = [ln.strip() for ln in (md or "").splitlines() if ln.strip()]
    rows: List[List[str]] = []
    for ln in lines_:
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return "<p>（データなし）</p>"

    header = rows[0]
    body = rows[2:] if len(rows) > 2 else []

    col_html = """
        <colgroup>
            <col style="width:10%">
            <col style="width:10%">
            <col style="width:20%">
            <col style="width:20%">
            <col style="width:40%">
        </colgroup>
    """

    html = "<table class='proof-table'>"
    html += col_html

    html += "<thead><tr>"
    for h in header:
        html += f"<th>{escape(h)}</th>"
    html += "</tr></thead>"

    html += "<tbody>"
    for r in body:
        html += "<tr>"
        for c in r:
            html += f"<td>{c}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


def inject_proof_table_css() -> None:
    st.markdown(
        """
<style>
.proof-table { width: 100%; border-collapse: collapse; }
.proof-table th, .proof-table td { border: 1px solid #ccc; padding: 6px; vertical-align: top; }
.proof-table th { background: #e8edf7; text-align: center; }
</style>
        """,
        unsafe_allow_html=True,
    )
