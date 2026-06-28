# -*- coding: utf-8 -*-
# text_studio_app/pages/110_word画像埋込.py
# ============================================================
# 🖼 Word画像埋込
#
# Inbox内の画像ファイルを選択し，
# タイトル・説明付きのWord写真一覧表として出力する。
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================
from pathlib import Path
import sys
from datetime import timezone, timedelta
import traceback

# ============================================================
# imports（3rd party）
# ============================================================
import pandas as pd
import streamlit as st

# ============================================================
# ページ設定
# - st.set_page_config は最初に1回だけ実行する
# ============================================================
st.set_page_config(
    page_title="Text Studio / Word画像埋込",
    page_icon="🖼",
    layout="wide",
)

# ============================================================
# パス設定
# - common_lib / app lib を import できるようにする
# - 03_文章校正.py の構成に合わせる
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
JST = timezone(timedelta(hours=9))

# ============================================================
# common_lib（ページ共通UI）
# ============================================================
from common_lib.ui.page_header import render_standard_page_header

# ============================================================
# Inbox：パス・初期化
# - 30_インボックス操作.py と同じ系統を使う
# ============================================================
from common_lib.inbox.inbox_common.paths import (
    resolve_inbox_root,
    ensure_user_dirs,
    items_db_path,
    last_viewed_db_path,
)

from common_lib.inbox.inbox_db.items_db import ensure_items_db
from common_lib.inbox.inbox_db.last_viewed_db import ensure_last_viewed_db

# ============================================================
# Inbox：検索
# ============================================================
from common_lib.inbox.inbox_query.query_builder import (
    split_terms_and,
    build_where_and_params,
)

from common_lib.inbox.inbox_query.query_exec import query_items_page

# ============================================================
# app lib（画像Word埋込）
# ============================================================
from lib.image_embed.explanation import (
    render_image_embed_page_intro,
    render_image_embed_help_expander,
)

from lib.image_embed.inbox_images import load_inbox_image_items
from lib.image_embed.dataframe_builder import (
    build_image_selection_df,
    extract_selected_images,
)
from lib.image_embed.image_utils import (
    calc_docx_image_width_inches,
    normalize_hex_color,
)
from lib.image_embed.word_builder import build_photo_table_docx_bytes

from lib.image_embed.dataframe_builder import (
    build_image_selection_df,
    extract_selected_images,
)

from lib.image_embed.thumb_grid import render_image_thumb_grid

from lib.image_embed.word_preview import render_photo_table_preview

from common_lib.inbox.inbox_db.items_db import update_item_tag_single
from lib.image_embed.tag_metadata import build_tag_with_title_exp

# ============================================================
# 共通ヘッダー
# ============================================================
sub, theme, BANNER_KEY, settings = render_standard_page_header(
    st_module=st,
    projects_root=PROJECTS_ROOT,
    app_dir=APP_DIR,
    app_name=APP_NAME,
    page_name=PAGE_NAME,
    title="🖼 Word画像埋込",
    subtitle_text="Inbox画像からWord写真一覧表を作成",
    default_banner_key="navy_dark",
)

# ============================================================
# ページ説明
# ============================================================
render_image_embed_page_intro()
render_image_embed_help_expander(
    theme=theme,
    banner_key=BANNER_KEY,
)

# ============================================================
# Inbox 初期化
# ============================================================
INBOX_ROOT = resolve_inbox_root(PROJECTS_ROOT)

if not INBOX_ROOT.exists():
    st.error(f"InBoxStorages のルートが存在しません: {INBOX_ROOT}")
    st.stop()

paths = ensure_user_dirs(INBOX_ROOT, sub)

items_db = items_db_path(INBOX_ROOT, sub)
lv_db = last_viewed_db_path(INBOX_ROOT, sub)

ensure_items_db(items_db)
ensure_last_viewed_db(lv_db)

# ============================================================
# session_state
# ============================================================
K_RAW_IMAGE_ITEMS_DF = f"{PAGE_NAME}__raw_image_items_df"
K_IMAGE_DF = f"{PAGE_NAME}__image_df"
K_EDITED_DF = f"{PAGE_NAME}__edited_df"
K_DOCX_BYTES = f"{PAGE_NAME}__docx_bytes"
K_DOCX_NAME = f"{PAGE_NAME}__docx_name"

st.session_state.setdefault(K_RAW_IMAGE_ITEMS_DF, None)
st.session_state.setdefault(K_IMAGE_DF, None)
st.session_state.setdefault(K_EDITED_DF, None)
st.session_state.setdefault(K_DOCX_BYTES, None)
st.session_state.setdefault(K_DOCX_NAME, "")

# ============================================================
# ① Word設定
# ============================================================
st.divider()
st.subheader("① Word写真一覧表の設定")

c1, c2, c3 = st.columns([2.5, 1, 1])

with c1:
    document_title = st.text_input(
        "表全体のタイトル",
        value="現場写真一覧",
        key=f"{PAGE_NAME}__document_title",
    )

with c2:
    columns = st.number_input(
        "表の列数",
        min_value=1,
        max_value=4,
        value=2,
        step=1,
        key=f"{PAGE_NAME}__columns",
    )

with c3:
    image_size_mode = st.radio(
        "写真サイズ",
        options=["自動設定", "手動指定"],
        horizontal=True,
        key=f"{PAGE_NAME}__image_size_mode",
    )

c4, c5 = st.columns([1, 3])

with c4:
    manual_width_cm = st.number_input(
        "写真幅（cm）",
        min_value=2.0,
        max_value=18.0,
        value=7.0,
        step=0.5,
        disabled=(image_size_mode != "手動指定"),
        key=f"{PAGE_NAME}__manual_width_cm",
    )

with c5:
    bg_color_label = st.selectbox(
        "画像のバックグラウンドとなる表の色",
        options=[
            "薄いグレー",
            "白",
            "薄いベージュ",
            "薄い青",
            "薄い緑",
            "薄い黄色",
        ],
        index=0,
        key=f"{PAGE_NAME}__bg_color_label",
    )

    bg_color_map = {
        "薄いグレー": "#F2F2F2",
        "白": "#FFFFFF",
        "薄いベージュ": "#F7F0E6",
        "薄い青": "#EAF3FF",
        "薄い緑": "#EAF7EA",
        "薄い黄色": "#FFF8D8",
    }

    bg_color = bg_color_map.get(bg_color_label, "#F2F2F2")

image_width_inches = calc_docx_image_width_inches(
    mode=image_size_mode,
    manual_width_cm=float(manual_width_cm),
    columns=int(columns),
)

cell_background_hex = normalize_hex_color(bg_color)

# ============================================================
# ② Inbox画像検索
# ============================================================
st.divider()
st.subheader("② Inbox画像の検索")

s1, s2, s3 = st.columns([2, 2, 1])

with s1:
    tag_q = st.text_input(
        "タグ（AND検索：スペース/カンマ区切り）",
        value="",
        key=f"{PAGE_NAME}__tag_q",
        placeholder="例：プロジェクト 2025",
    )

with s2:
    name_q = st.text_input(
        "ファイル名（AND検索：スペース/カンマ区切り）",
        value="",
        key=f"{PAGE_NAME}__name_q",
        placeholder="例：現場 写真",
    )

with s3:
    limit = st.number_input(
        "最大取得数",
        min_value=10,
        max_value=1000,
        value=300,
        step=10,
        key=f"{PAGE_NAME}__limit",
    )

load_clicked = st.button(
    "Inbox画像を読み込む",
    type="primary",
    key=f"{PAGE_NAME}__load_images",
)

if load_clicked:
    image_items_df = load_inbox_image_items(
        inbox_root=INBOX_ROOT,
        sub=sub,
        items_db=items_db,
        lv_db=lv_db,
        query_items_page=query_items_page,
        build_where_and_params=build_where_and_params,
        split_terms_and=split_terms_and,
        tag_q=tag_q,
        name_q=name_q,
        limit=int(limit),
    )

    selection_df = build_image_selection_df(
        image_items_df=image_items_df,
    )

    st.session_state[K_RAW_IMAGE_ITEMS_DF] = image_items_df
    st.session_state[K_IMAGE_DF] = selection_df
    st.session_state[K_EDITED_DF] = None
    st.session_state[K_DOCX_BYTES] = None
    st.session_state[K_DOCX_NAME] = ""

# ============================================================
# ③ サムネ一覧
# - auth_portal_app/pages/30_インボックス操作.py と同じサムネ表示を使う
# - 選択前に画像内容を確認できるようにする
# ============================================================
st.divider()
st.subheader("③ サムネ一覧")

raw_image_items_df = st.session_state.get(K_RAW_IMAGE_ITEMS_DF)

if isinstance(raw_image_items_df, pd.DataFrame) and not raw_image_items_df.empty:
    render_image_thumb_grid(
        inbox_root=INBOX_ROOT,
        sub=sub,
        image_df=raw_image_items_df,
        max_items=20,
        per_row=4,
    )
else:
    st.info("サムネ表示する画像がありません。")


# ============================================================
# ④ 画像選択
# ============================================================
st.divider()
st.subheader("④ Wordに入れる画像を選択")

image_df = st.session_state.get(K_IMAGE_DF)

if image_df is None:
    st.info("まず「Inbox画像を読み込む」を押してください。")
    st.stop()

if isinstance(image_df, pd.DataFrame) and image_df.empty:
    st.warning("条件に一致する画像がありません。")
    st.stop()

st.caption(
    "「選択」にチェックを付けた画像だけをWordに出力します。"
    " タイトルと説明はここで編集できます。タグ自体の変更は今回は行いません。"
)

edited_df = st.data_editor(
    image_df,
    hide_index=True,
    key=f"{PAGE_NAME}__image_editor",
    column_config={
        "選択": st.column_config.CheckboxColumn(
            "選択",
            help="Wordに出力する画像にチェック",
            default=False,
        ),
        "タグ": st.column_config.TextColumn(
            "タグ",
            disabled=True,
        ),
        "タイトル": st.column_config.TextColumn(
            "タイトル",
            help="Word表の上段セルに表示するタイトル",
        ),
        "説明": st.column_config.TextColumn(
            "説明",
            help="タイトルの下に表示する説明文",
        ),
        "ファイル名": st.column_config.TextColumn(
            "ファイル名",
            disabled=True,
        ),
        "item_id": st.column_config.TextColumn(
            "item_id",
            disabled=True,
        ),
        "path": st.column_config.TextColumn(
            "path",
            disabled=True,
        ),
    },
    disabled=["タグ", "ファイル名", "item_id", "path"],
)

st.session_state[K_EDITED_DF] = edited_df

selected_df = extract_selected_images(
    edited_df=edited_df,
)

st.caption(f"選択中: {len(selected_df)} 件")

# ============================================================
# タグ保存
# - data_editorで編集したタイトル・説明をタグ内メタ情報として保存する
# ============================================================
save_tags_clicked = st.button(
    "タグを保存",
    type="secondary",
    key=f"{PAGE_NAME}__save_title_exp_to_tags",
)

if save_tags_clicked:
    saved_count = 0
    skipped_count = 0

    for _, row in edited_df.iterrows():
        item_id = str(row.get("item_id") or "").strip()
        base_tag = str(row.get("タグ") or "").strip()
        title = str(row.get("タイトル") or "").strip()
        exp = str(row.get("説明") or "").strip()

        if not item_id:
            skipped_count += 1
            continue

        if not title and not exp:
            skipped_count += 1
            continue

        new_tag = build_tag_with_title_exp(
            base_tag=base_tag,
            title=title,
            exp=exp,
        )

        update_item_tag_single(
            items_db,
            item_id,
            new_tag,
        )

        saved_count += 1

    st.success(f"タグを保存しました: {saved_count} 件")
    if skipped_count:
        st.caption(f"スキップ: {skipped_count} 件")

    st.success(f"タグを保存しました: {saved_count} 件")

    #st.rerun()

# ============================================================
# ⑤ Word写真一覧表プレビュー
# ============================================================
st.divider()
st.subheader("⑤ Word写真一覧表プレビュー")

if selected_df.empty:
    st.info("Wordを作成するには，画像を1件以上選択してください。")
    st.stop()

render_photo_table_preview(
    inbox_root=INBOX_ROOT,
    sub=sub,
    selected_df=selected_df,
    document_title=document_title,
    columns=int(columns),
    cell_background_color=bg_color,
)

# ============================================================
# ⑥ Word作成
# ============================================================
st.divider()
st.subheader("⑥ Word写真一覧表を作成")

create_clicked = st.button(
    "Wordを作成",
    type="primary",
    key=f"{PAGE_NAME}__create_word",
)

if create_clicked:
    try:
        docx_bytes = build_photo_table_docx_bytes(
            inbox_root=INBOX_ROOT,
            sub=sub,
            selected_df=selected_df,
            document_title=document_title,
            columns=int(columns),
            image_width_inches=float(image_width_inches),
            cell_background_hex=cell_background_hex,
        )

        st.session_state[K_DOCX_BYTES] = docx_bytes
        st.session_state[K_DOCX_NAME] = "写真一覧表.docx"

        st.success("Word写真一覧表を作成しました。")

    except Exception as e:
        st.exception(e)
        st.code(traceback.format_exc())

if st.session_state.get(K_DOCX_BYTES):
    st.download_button(
        "Wordとして保存",
        data=st.session_state[K_DOCX_BYTES],
        file_name=st.session_state[K_DOCX_NAME] or "写真一覧表.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key=f"{PAGE_NAME}__download_word",
        on_click="ignore",
    )