# -*- coding: utf-8 -*-
# text_studio_app/app.py
# ============================================================
# Text Studio
#
# 機能：
# - Text Studio のページナビゲーションを構成する
# - ページ単位・グループ単位で管理者表示を制御する
#
# 方針：
# - 一般ユーザーには通常利用ページだけを表示する
# - 管理者専用ページには admin=True を指定する
# - 管理者専用グループには nav_group(..., admin=True) を指定する
# - 空になったグループは navigation から除外する
# - navigation非表示と実際のアクセス制御は分ける
# - 管理者専用ページ側でも管理者チェックを継続する
# ============================================================

from __future__ import annotations

# ============================================================
# imports（stdlib）
# ============================================================

from pathlib import Path
import sys

# ============================================================
# imports（3rd party）
# ============================================================

import streamlit as st


# ============================================================
# パス設定（app.py 用）
# ============================================================

_THIS = Path(__file__).resolve()

APP_DIR = _THIS.parent
PROJ_DIR = _THIS.parents[1]
MONO_ROOT = _THIS.parents[2]

for p in (
    MONO_ROOT,
    PROJ_DIR,
    APP_DIR,
):
    if str(p) not in sys.path:
        sys.path.insert(
            0,
            str(p),
        )


# ============================================================
# app
# ============================================================

PROJECTS_ROOT = MONO_ROOT
APP_NAME = APP_DIR.name
PAGE_NAME = _THIS.stem


# ============================================================
# navigation icons
# ============================================================

from common_lib.ui.nav_icons import (
    NAV_HOME_ICON,
    NAV_PORTAL_RETURN_ICON,
    NAV_PROCESS_ICON,
    NAV_CONSTRUCTION_ICON,
    PAGE_HOME_ICON,
    PAGE_PORTAL_RETURN_ICON,
    NAV_STOP_ICON,
)


# ============================================================
# navigation access
# ============================================================

from common_lib.ui.navigation_access import (
    clean_navigation_groups,
    nav_group,
    nav_page,
    set_navigation_debug_general_user,
)


# ============================================================
# page config
# ============================================================

st.set_page_config(
    page_title="Text Studio",
    page_icon="✍️",
    layout="wide",
)


# ============================================================
# DEBUG：navigation表示切替
# ============================================================

# ------------------------------------------------------------
# True:
#   管理者でログインしていても一般ユーザー用navigationを表示
#
# False:
#   実際のログインユーザーの権限に従う
# ------------------------------------------------------------

#DEBUG_FORCE_GENERAL_USER = True
DEBUG_FORCE_GENERAL_USER = False

set_navigation_debug_general_user(
    DEBUG_FORCE_GENERAL_USER
)


# ============================================================
# navigation
# ============================================================

navigation_pages = {

    # ========================================================
    # Home
    # ========================================================

    f"{NAV_HOME_ICON}": nav_group(
        [
            nav_page(
                "pages/00_トップ.py",
                title="Home",
                icon=PAGE_HOME_ICON,
                default=True,
                url_path="top",
            ),
        ],
    ),


    # ========================================================
    # 文章校閲
    # ========================================================

    f"{NAV_PROCESS_ICON} 文章校閲": nav_group(
        [
            nav_page(
                "pages/03_文章校正.py",
                title="文章校正",
                icon="📝",
                url_path="03_文章校正",
            ),
            # nav_page(
            #     "pages/04_word解析.py",
            #     title="Word解析",
            #     icon="📄",
            #     url_path="04_word解析",
            # ),
            nav_page(
                "pages/12_一括word校正.py",
                title="Word校正",
                icon="📚",
                url_path="12_一括word校正",
            ),
            nav_page(
                "pages/08_目次チェック.py",
                title="目次チェック",
                icon="📑",
                url_path="08_目次チェック",
            ),
            nav_page(
                "pages/09_図表チェック.py",
                title="図表チェック",
                icon="📊",
                url_path="09_図表チェック",
            ),
            nav_page(
                "pages/14_AI図表チェック.py",
                title="AI図表チェック",
                icon="🤖",
                url_path="14_AI図表チェック",
            ),
        ],
    ),


    # ========================================================
    # 文章校閲 v2
    # ========================================================

    f"{NAV_PROCESS_ICON} 文章校閲 ハイライト": nav_group(
        [
            nav_page(
                "pages/400_文章校正2.py",
                title="文章校正 v2",
                icon="📝",
                url_path="400_文章校正2",
            ),
            nav_page(
                "pages/410_一括word校正2.py",
                title="Word校正 v2",
                icon="📚",
                url_path="410_一括word校正2",
            ),
        ],
    ),


    # ========================================================
    # ポータルへ戻る
    # ========================================================

    f"{NAV_PORTAL_RETURN_ICON}": nav_group(
        [
            nav_page(
                "pages/38_ポータルへ戻る.py",
                title="ポータルへ戻る",
                icon=PAGE_PORTAL_RETURN_ICON,
                url_path="38_ポータルへ戻る",
            ),
        ],
    ),


    # ========================================================
    # AI・チャット
    # ========================================================

    f"{NAV_CONSTRUCTION_ICON} （開発中）AI・チャット": nav_group(
        [
            nav_page(
                "pages/18_AIチャット.py",
                title="AIチャット",
                icon="💬",
                url_path="18_AIチャット",
            ),
            nav_page(
                "pages/19_AIチャット（要約機能）.py",
                title="AIチャット要約",
                icon="🧾",
                url_path="19_AIチャット要約",
                developer_only=True,
            ),
            nav_page(
                "pages/800_AIチャット2.py",
                title="AIチャット2",
                icon="💬",
                url_path="800_AIチャット2",
            ),
        ],
    ),


    # ========================================================
    # AI文章作成
    # ========================================================

    f"{NAV_CONSTRUCTION_ICON} （開発中）AI文章作成": nav_group(
        [
            nav_page(
                "pages/24_AI文章作成.py",
                title="AI文章作成",
                icon="✍️",
                url_path="24_AI文章作成",
            ),
            nav_page(
                "pages/21_AI翻訳.py",
                title="AI翻訳",
                icon="🌐",
            ),
        ],
    ),


    # ========================================================
    # 図表・チャート
    # ========================================================

    f"{NAV_CONSTRUCTION_ICON} （開発中）図表・チャート": nav_group(
        [
            nav_page(
                "pages/26_表作成.py",
                title="表作成",
                icon="📋",
                url_path="26_表作成",
            ),
            nav_page(
                "pages/27_棒グラフ作成.py",
                title="棒グラフ作成",
                icon="📊",
                url_path="27_棒グラフ作成",
            ),
            nav_page(
                "pages/32_ガントチャート.py",
                title="ガントチャート",
                icon="📅",
                url_path="32_ガントチャート",
            ),
            nav_page(
                "pages/33_フローチャート.py",
                title="フローチャート",
                icon="🔀",
                url_path="33_フローチャート",
            ),
            nav_page(
                "pages/310_slideTex.py",
                title="slideTex",
                icon="📊",
                url_path="310_slideTex",
            ),
        ],
    ),


    # ========================================================
    # Word書類作成支援
    #
    # 管理者専用グループ
    # ========================================================

    f"{NAV_CONSTRUCTION_ICON} （開発中）Word書類作成支援": nav_group(
        [
            nav_page(
                "pages/110_word画像埋込.py",
                title="Word画像埋込",
                icon="🖼",
                url_path="110_word画像埋込",
            ),
            nav_page(
                "pages/200_wordtex.py",
                title="wordTex",
                icon="📄",
            ),
        ],
        developer_only=True,
    ),


    # ========================================================
    # 開発・管理
    #
    # 管理者専用グループ
    # ========================================================

    f"{NAV_STOP_ICON} 開発・管理": nav_group(
        [
            nav_page(
                "pages/999_開発用管理者ログイン.py",
                title="開発用 管理者ログイン",
                icon="🔐",
                url_path="999_開発用管理者ログイン",
            ),
        ],
        login=False,
    ),


    # ========================================================
    # PDF Tools
    #
    # 管理者専用グループ
    # ========================================================

    "📕 PDF Tools": nav_group(
        [
            nav_page(
                "pages/42_図表見出し抽出.py",
                title="図表見出し抽出",
                icon="📕",
                url_path="42_図表見出し抽出",
            ),
            nav_page(
                "pages/43_頁抽出チェック.py",
                title="頁抽出チェック",
                icon="🔍",
                url_path="43_頁抽出チェック",
            ),
            nav_page(
                "pages/44_頁テキスト抽出.py",
                title="頁テキスト抽出",
                icon="📄",
                url_path="44_頁テキスト抽出",
            ),
            nav_page(
                "pages/56_pdf頁テキスト抽出.py",
                title="PDF頁テキスト抽出",
                icon="📄",
                url_path="56_pdf頁テキスト抽出",
            ),
            nav_page(
                "pages/57_OCRツール.py",
                title="OCRツール",
                icon="👁️",
                url_path="57_OCRツール",
            ),
        ],
        developer_only=True,
    ),


    # ========================================================
    # 以下は現在未使用
    # ========================================================

    # "🌿 Redlist": nav_group(
    #     [
    #         nav_page(
    #             "pages/35_レッドリスト検索.py",
    #             title="レッドリスト検索",
    #             icon="🌿",
    #             url_path="35_レッドリスト検索",
    #         ),
    #     ],
    # ),

    # "📄 Word Tools": nav_group(
    #     [
    #         nav_page(
    #             "pages/61_word内部ファイル抽出.py",
    #             title="Word内部ファイル抽出",
    #             icon="📦",
    #             url_path="61_word内部ファイル抽出",
    #         ),
    #         nav_page(
    #             "pages/62_word段落リスト.py",
    #             title="Word段落リスト",
    #             icon="📄",
    #             url_path="62_word段落リスト",
    #         ),
    #     ],
    # ),

    # "🧰 Tools": nav_group(
    #     [
    #         nav_page(
    #             "pages/73_正規表現テスト.py",
    #             title="正規表現テスト",
    #             icon="🔤",
    #             url_path="73_正規表現テスト",
    #         ),
    #         nav_page(
    #             "pages/74_形態素解析.py",
    #             title="形態素解析",
    #             icon="🔠",
    #             url_path="74_形態素解析",
    #         ),
    #         nav_page(
    #             "pages/75_名詞リスト.py",
    #             title="名詞リスト",
    #             icon="📋",
    #             url_path="75_名詞リスト",
    #         ),
    #     ],
    # ),
}


# ============================================================
# 空グループ除去
# ============================================================

navigation_pages = clean_navigation_groups(
    navigation_pages
)


# ============================================================
# navigation 作成
# ============================================================

pg = st.navigation(
    navigation_pages
)


# ============================================================
# run
# ============================================================

pg.run()