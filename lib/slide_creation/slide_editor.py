# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/slide_editor.py
# ============================================================
# スライド構成編集UI
#
# 機能：
# - スライド枚数を指定する
# - 各スライドのページ種別を選択する
# - ページ種別ごとのスタイルを選択する
# - 各スライドの入力内容をSlideDefinitionへ変換する
#
# 方針：
# - st.formは使用しない
# - ページ種別とスタイルはラジオボタンで選択する
# - PowerPoint生成処理には依存しない
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
import streamlit as st

from lib.slide_creation.models import SlideDefinition
from lib.slide_creation.themes import (
    DEFAULT_SLIDE_TYPES,
    SLIDE_STYLE_MAP,
    SLIDE_TYPES,
    get_default_style_key,
    get_slide_type_label,
    get_slide_type_options,
    get_style_label,
    get_style_options,
)


# ============================================================
# 初期値
# ============================================================
def _get_default_slide_type(index: int) -> str:
    if index < len(DEFAULT_SLIDE_TYPES):
        return DEFAULT_SLIDE_TYPES[index]

    return "content"


def _default_title(
    *,
    slide_type: str,
    index: int,
) -> str:
    if slide_type == "title":
        return "PAISの概要"

    if slide_type == "section":
        return "PAISとは"

    if slide_type == "subsection":
        return "文書検索機能"

    if slide_type == "ending":
        return "ご清聴ありがとうございました"

    return f"本文スライド {index + 1}"


# ============================================================
# 共通UI
# ============================================================
def _render_slide_type_radio(
    *,
    index: int,
    page_name: str,
) -> str:
    key = f"{page_name}__slide_{index}__type"
    options = get_slide_type_options()
    default_type = _get_default_slide_type(index)

    if key not in st.session_state:
        st.session_state[key] = default_type

    return st.radio(
        "ページ種別",
        options=options,
        format_func=get_slide_type_label,
        horizontal=True,
        key=key,
    )


def _render_style_radio(
    *,
    index: int,
    page_name: str,
    slide_type: str,
) -> str:
    state_key = f"{page_name}__slide_{index}__style"
    type_state_key = f"{page_name}__slide_{index}__style_type"

    style_options = get_style_options(slide_type)
    default_style = get_default_style_key(slide_type)

    if st.session_state.get(type_state_key) != slide_type:
        st.session_state[state_key] = default_style
        st.session_state[type_state_key] = slide_type

    if st.session_state.get(state_key) not in style_options:
        st.session_state[state_key] = default_style

    return st.radio(
        "ページスタイル",
        options=style_options,
        format_func=lambda value: get_style_label(slide_type, value),
        horizontal=True,
        key=state_key,
    )


# ============================================================
# タイトルページ
# ============================================================
def _render_title_fields(
    *,
    index: int,
    page_name: str,
    style_key: str,
) -> SlideDefinition:
    prefix = f"{page_name}__slide_{index}"

    title = st.text_input(
        "資料タイトル",
        value=_default_title(slide_type="title", index=index),
        key=f"{prefix}__title",
    )

    subtitle = st.text_input(
        "サブタイトル",
        value="PowerPoint自動生成サンプル",
        key=f"{prefix}__subtitle",
    )

    presenter_name = st.text_input(
        "発表者名",
        value="",
        key=f"{prefix}__presenter_name",
    )

    return SlideDefinition(
        slide_type="title",
        style_key=style_key,
        title=title,
        subtitle=subtitle,
        presenter_name=presenter_name,
    )


# ============================================================
# 見出しページ
# ============================================================
def _render_section_fields(
    *,
    index: int,
    page_name: str,
    style_key: str,
) -> SlideDefinition:
    prefix = f"{page_name}__slide_{index}"

    section_number = st.text_input(
        "章番号",
        value=f"{index:02d}",
        key=f"{prefix}__section_number",
    )

    title = st.text_input(
        "章タイトル",
        value=_default_title(slide_type="section", index=index),
        key=f"{prefix}__title",
    )

    subtitle = st.text_area(
        "章の説明",
        value="この章で説明する内容を入力します．",
        height=100,
        key=f"{prefix}__subtitle",
    )

    return SlideDefinition(
        slide_type="section",
        style_key=style_key,
        title=title,
        subtitle=subtitle,
        section_number=section_number,
    )


# ============================================================
# 小見出しページ
# ============================================================
def _render_subsection_fields(
    *,
    index: int,
    page_name: str,
    style_key: str,
) -> SlideDefinition:
    prefix = f"{page_name}__slide_{index}"

    title = st.text_input(
        "小見出し",
        value=_default_title(slide_type="subsection", index=index),
        key=f"{prefix}__title",
    )

    subtitle = st.text_area(
        "補足説明",
        value="次に説明する内容の概要を入力します．",
        height=100,
        key=f"{prefix}__subtitle",
    )

    return SlideDefinition(
        slide_type="subsection",
        style_key=style_key,
        title=title,
        subtitle=subtitle,
    )


# ============================================================
# 本文ページ
# ============================================================
def _render_content_fields(
    *,
    index: int,
    page_name: str,
    style_key: str,
) -> SlideDefinition:
    prefix = f"{page_name}__slide_{index}"

    title = st.text_input(
        "スライドタイトル",
        value=_default_title(slide_type="content", index=index),
        key=f"{prefix}__title",
    )

    body = st.text_area(
        "本文",
        value=(
            "社内文書を検索できます．\n"
            "RAGを利用した質問応答ができます．\n"
            "議事録や説明資料を作成できます．"
        ),
        height=180,
        help="1行を1項目としてPowerPointへ配置します．",
        key=f"{prefix}__body",
    )

    left_heading = ""
    right_heading = ""

    if style_key == "comparison":
        left_heading = st.text_input(
            "左側の見出し",
            value="項目A",
            key=f"{prefix}__left_heading",
        )

        right_heading = st.text_input(
            "右側の見出し",
            value="項目B",
            key=f"{prefix}__right_heading",
        )

    return SlideDefinition(
        slide_type="content",
        style_key=style_key,
        title=title,
        body=body,
        left_heading=left_heading,
        right_heading=right_heading,
    )


# ============================================================
# 最終ページ
# ============================================================
def _render_ending_fields(
    *,
    index: int,
    page_name: str,
    style_key: str,
) -> SlideDefinition:
    prefix = f"{page_name}__slide_{index}"

    title = st.text_input(
        "終了ページのタイトル",
        value=_default_title(slide_type="ending", index=index),
        key=f"{prefix}__title",
    )

    subtitle = st.text_input(
        "補足メッセージ",
        value="",
        key=f"{prefix}__subtitle",
    )

    body = ""
    presenter_name = ""
    contact_text = ""

    if style_key == "summary":
        body = st.text_area(
            "まとめ",
            value=(
                "PAISの主な機能を紹介しました．\n"
                "社内文書を安全に活用できます．\n"
                "今後も機能を拡張します．"
            ),
            height=150,
            key=f"{prefix}__body",
        )

    if style_key == "contact":
        presenter_name = st.text_input(
            "担当者名",
            value="",
            key=f"{prefix}__presenter_name",
        )

        contact_text = st.text_area(
            "問い合わせ先",
            value="メールアドレスやURLを入力してください．",
            height=100,
            key=f"{prefix}__contact_text",
        )

    return SlideDefinition(
        slide_type="ending",
        style_key=style_key,
        title=title,
        subtitle=subtitle,
        body=body,
        presenter_name=presenter_name,
        contact_text=contact_text,
    )


# ============================================================
# 1スライド編集
# ============================================================
def _render_one_slide(
    *,
    index: int,
    page_name: str,
) -> SlideDefinition:
    slide_type = _render_slide_type_radio(
        index=index,
        page_name=page_name,
    )

    st.caption(SLIDE_TYPES[slide_type].description)

    style_key = _render_style_radio(
        index=index,
        page_name=page_name,
        slide_type=slide_type,
    )

    st.caption(
        SLIDE_STYLE_MAP[slide_type][style_key].description
    )

    if slide_type == "title":
        return _render_title_fields(
            index=index,
            page_name=page_name,
            style_key=style_key,
        )

    if slide_type == "section":
        return _render_section_fields(
            index=index,
            page_name=page_name,
            style_key=style_key,
        )

    if slide_type == "subsection":
        return _render_subsection_fields(
            index=index,
            page_name=page_name,
            style_key=style_key,
        )

    if slide_type == "ending":
        return _render_ending_fields(
            index=index,
            page_name=page_name,
            style_key=style_key,
        )

    return _render_content_fields(
        index=index,
        page_name=page_name,
        style_key=style_key,
    )


# ============================================================
# public API
# ============================================================
def render_slide_editor(
    *,
    page_name: str,
) -> list[SlideDefinition]:
    slide_count = st.number_input(
        "スライド枚数",
        min_value=1,
        max_value=30,
        value=5,
        step=1,
        key=f"{page_name}__slide_count",
    )

    slides: list[SlideDefinition] = []

    for index in range(int(slide_count)):
        current_type = st.session_state.get(
            f"{page_name}__slide_{index}__type",
            _get_default_slide_type(index),
        )

        label = get_slide_type_label(current_type)

        with st.expander(
            f"スライド {index + 1}：{label}",
            expanded=index == 0,
        ):
            slides.append(
                _render_one_slide(
                    index=index,
                    page_name=page_name,
                )
            )

    return slides