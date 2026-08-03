# -*- coding: utf-8 -*-
# text_studio_app/pages/310_slideTex.py
# ============================================================
# 📊 PowerPointスライド作成（SlideTex / 非AI）
#
# 機能：
# - .stexファイルをドラッグ＆ドロップで読み込む
# - SlideTex独自構文を解析する
# - スライド構成と構文エラーを表示する
# - 解析結果からPowerPointファイルを作成する
#
# UI方針：
# - use_container_widthは使わない
# - st.formは使わない
# - .stex読込時に構文解析を行う
# - PowerPoint生成はボタン押下時のみ実行する
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
import hashlib
import sys
from pathlib import Path

# ============================================================
# imports（3rd party）
# ============================================================
import streamlit as st

# ============================================================
# sys.path
# ============================================================
_THIS = Path(__file__).resolve()
APP_DIR = _THIS.parents[1]
PROJ_DIR = _THIS.parents[2]
MONO_ROOT = _THIS.parents[3]

for p in (MONO_ROOT, PROJ_DIR, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PROJECTS_ROOT = MONO_ROOT
APP_NAME = APP_DIR.name
PAGE_NAME = _THIS.stem


# ============================================================
# session_state keys
# ============================================================
SS_PPTX_DATA = f"{PAGE_NAME}__pptx_data"
SS_PPTX_FILENAME = f"{PAGE_NAME}__pptx_filename"
SS_STEX_HASH = f"{PAGE_NAME}__stex_hash"


# ============================================================
# common_lib
# ============================================================
from common_lib.inbox.inbox_common.paths import (
    resolve_inbox_root,
)
from common_lib.ui.page_header import (
    render_standard_page_header,
)

# ============================================================
# lib
# ============================================================
from lib.slide_creation.explanation import (
    render_slide_creation_logic_expander,
    render_slide_creation_page_intro,
)
from lib.slide_creation.powerpoint_builder import (
    PPTX_MIME_TYPE,
    create_powerpoint,
)
from lib.slide_creation.stex_parser import (
    StexParseResult,
    parse_stex_bytes,
)

from lib.slide_creation.themes import (
    FOOTER_STYLES,
    HEADER_STYLES,
    SLIDE_THEMES,
    get_slide_type_label,
    get_style_label,
)


# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="Text Studio",
    page_icon="📄",
    layout="wide",
)


# ============================================================
# 共通ヘッダー
# ============================================================
sub, theme, BANNER_KEY, settings = render_standard_page_header(
    st_module=st,
    projects_root=PROJECTS_ROOT,
    app_dir=APP_DIR,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
    title="📊 slideTex",
    subtitle_text="slideTexファイルからPowerPointを作成",
    default_banner_key="purple_light",
)

# ============================================================
# Inboxルート
# ============================================================
INBOX_ROOT = resolve_inbox_root(
    PROJECTS_ROOT
)

# ============================================================
# ページ説明
# ============================================================
render_slide_creation_page_intro()


# ============================================================
# 詳細説明
# ============================================================
render_slide_creation_logic_expander(
    theme=theme,
    banner_key=BANNER_KEY,
)


# ============================================================
# session_state初期化
# ============================================================
st.session_state.setdefault(SS_PPTX_DATA, None)
st.session_state.setdefault(
    SS_PPTX_FILENAME,
    "作成したスライド.pptx",
)
st.session_state.setdefault(SS_STEX_HASH, "")


# ============================================================
# ① SlideTexファイル
# ============================================================
st.divider()
st.subheader("① SlideTexファイル")

st.caption(
    "UTF-8で保存した.stexファイルを，"
    "下の領域へドラッグ＆ドロップしてください．"
)

uploaded_file = st.file_uploader(
    "SlideTexファイルをドロップ",
    type=["stex"],
    key=f"{PAGE_NAME}__stex_file",
)

# ============================================================
# 出力ファイル名を入力ファイル名へ同期
# ============================================================
if uploaded_file is not None:
    output_name = f"{Path(uploaded_file.name).stem}.pptx"

    if (
        st.session_state.get(f"{PAGE_NAME}__file_name")
        != output_name
    ):
        st.session_state[
            f"{PAGE_NAME}__file_name"
        ] = output_name

# ============================================================
# SlideTex読込・解析
# ============================================================
parse_result: StexParseResult | None = None
stex_text = ""

if uploaded_file is not None:
    stex_data = uploaded_file.getvalue()
    current_hash = hashlib.sha256(stex_data).hexdigest()

    if current_hash != st.session_state[SS_STEX_HASH]:
        st.session_state[SS_STEX_HASH] = current_hash
        st.session_state[SS_PPTX_DATA] = None

    parse_result = parse_stex_bytes(stex_data)

    try:
        stex_text = stex_data.decode("utf-8-sig")

    except UnicodeDecodeError:
        stex_text = ""


# ============================================================
# ② 解析結果
# ============================================================
if parse_result is not None:
    st.divider()
    st.subheader("② 解析結果")

    if parse_result.errors:
        st.error(
            f"構文エラーが"
            f"{len(parse_result.errors)}件あります．"
        )

        for message in parse_result.errors:
            st.write(f"❌ {message}")

    else:
        st.success(
            f"SlideTexを正常に読み込みました．"
            f"スライド数：{len(parse_result.slides)}枚"
        )

    if parse_result.warnings:
        with st.expander(
            f"警告：{len(parse_result.warnings)}件",
            expanded=False,
        ):
            for message in parse_result.warnings:
                st.write(f"⚠️ {message}")

    settings_result = parse_result.settings
    theme_option = SLIDE_THEMES.get(settings_result.theme_key)
    header_option = HEADER_STYLES.get(settings_result.header_key)
    footer_option = FOOTER_STYLES.get(settings_result.footer_key)

    st.write(
        f"**資料名：** "
        f"{settings_result.presentation_title}"
    )
    st.write(
        f"**テーマ：** "
        f"{theme_option.label if theme_option else settings_result.theme_key}"
        f"（`{settings_result.theme_key}`）"
    )
    st.write(
        f"**ヘッダー：** "
        f"{header_option.label if header_option else settings_result.header_key}"
        f"（`{settings_result.header_key}`）"
    )
    st.write(
        f"**フッター：** "
        f"{footer_option.label if footer_option else settings_result.footer_key}"
        f"（`{settings_result.footer_key}`）"
    )

    if parse_result.slides:
        with st.expander(
            "スライド構成",
            expanded=True,
        ):
            for index, slide in enumerate(
                parse_result.slides,
                start=1,
            ):
                slide_type_label = get_slide_type_label(
                    slide.slide_type
                )
                style_label = get_style_label(
                    slide.slide_type,
                    slide.style_key,
                )

                st.write(
                    f"**{index}．"
                    f"{slide.title or 'タイトルなし'}**"
                )
                st.caption(
                    f"{slide_type_label} ／ "
                    f"{style_label} ／ "
                    f"type={slide.slide_type} ／ "
                    f"style={slide.style_key}"
                )

    with st.expander(
        "読み込んだSlideTex",
        expanded=False,
    ):
        st.code(
            stex_text,
            language="latex",
        )


# ============================================================
# ③ PowerPoint作成
# ============================================================
if parse_result is not None:
    st.divider()
    st.subheader("③ PowerPointを作成")

    default_file_name = (
        f"{Path(uploaded_file.name).stem}.pptx"
        if uploaded_file is not None
        else "作成したスライド.pptx"
    )

    file_name = st.text_input(
        "出力ファイル名",
        key=f"{PAGE_NAME}__file_name",
    )

    create_run = st.button(
        "PowerPointを作成",
        type="primary",
        disabled=not parse_result.is_valid,
        key=f"{PAGE_NAME}__create_powerpoint",
    )

    if create_run:
        cleaned_file_name = file_name.strip()

        if not cleaned_file_name:
            cleaned_file_name = default_file_name

        if not cleaned_file_name.lower().endswith(".pptx"):
            cleaned_file_name = f"{cleaned_file_name}.pptx"

        try:
            pptx_data = create_powerpoint(
                slides=parse_result.slides,
                settings=parse_result.settings,
                inbox_root=INBOX_ROOT,
                sub=sub,
            )

            st.session_state[SS_PPTX_DATA] = pptx_data
            st.session_state[SS_PPTX_FILENAME] = cleaned_file_name

            st.success(
                "PowerPointファイルを作成しました．"
                f"スライド数：{len(parse_result.slides)}枚"
            )

        except Exception as exc:
            st.session_state[SS_PPTX_DATA] = None
            st.error(
                "PowerPointの作成に失敗しました："
                f"{exc}"
            )


# ============================================================
# ④ ダウンロード
# ============================================================
pptx_data = st.session_state.get(SS_PPTX_DATA)

if pptx_data:
    st.divider()
    st.subheader("④ PowerPointをダウンロード")

    st.download_button(
        "📥 PowerPointをダウンロード",
        data=pptx_data,
        file_name=st.session_state[SS_PPTX_FILENAME],
        mime=PPTX_MIME_TYPE,
        key=f"{PAGE_NAME}__download_powerpoint",
    )