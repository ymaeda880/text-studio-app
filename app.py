# text_studio_app/app.py
from __future__ import annotations

# ============================================================
# imports
# ============================================================
import streamlit as st

# ============================================================
# パス設定（app.py 用）
# ============================================================
from pathlib import Path
import sys

_THIS = Path(__file__).resolve()

APP_DIR = _THIS.parent
PROJ_DIR = _THIS.parents[1]
MONO_ROOT = _THIS.parents[2]

for p in (MONO_ROOT, PROJ_DIR, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

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
# page config
# ============================================================
st.set_page_config(
    page_title="Text Studio",
    page_icon="✍️",
    layout="wide",
)


# ============================================================
# navigation
# ============================================================
pg = st.navigation(
    {
        f"{NAV_HOME_ICON}": [
            st.Page(
                "pages/00_トップ.py",
                title="Home",
                icon=PAGE_HOME_ICON,
                default=True,
                url_path="top",
            ),
        ],

        f"{NAV_PROCESS_ICON} 文章校閲": [
            st.Page("pages/03_文章校正.py", title="文章校正", icon="📝", url_path="03_文章校正"),
            st.Page("pages/04_word解析.py", title="Word解析", icon="📄", url_path="04_word解析"),
            st.Page("pages/08_目次チェック.py", title="目次チェック", icon="📑", url_path="08_目次チェック"),
            st.Page("pages/09_図表チェック.py", title="図表チェック", icon="📊", url_path="09_図表チェック"),
            st.Page("pages/12_一括word校正.py", title="一括Word校正", icon="📚", url_path="12_一括word校正"),
            st.Page("pages/14_AI図表チェック.py", title="AI図表チェック", icon="🤖", url_path="14_AI図表チェック"),
        ],


        f"{NAV_PORTAL_RETURN_ICON}": [
            st.Page("pages/38_ポータルへ戻る.py", title="ポータルへ戻る", icon=PAGE_PORTAL_RETURN_ICON, url_path="38_ポータルへ戻る"),
        ],


        f"{NAV_CONSTRUCTION_ICON} （サンプル）AI・チャット": [
            st.Page("pages/18_AIチャット.py", title="AIチャット", icon="💬", url_path="18_AIチャット"),
            st.Page("pages/19_AIチャット（要約機能）.py", title="AIチャット要約", icon="🧾", url_path="19_AIチャット要約"),
        ],

        f"{NAV_CONSTRUCTION_ICON} （サンプル）AI文章作成": [
            st.Page("pages/24_AI文章作成.py", title="AI文章作成", icon="✍️", url_path="24_AI文章作成"),
            st.Page(
                "pages/21_AI翻訳.py",
                title="AI翻訳",
                icon="🌐",
            ),
        ],

        f"{NAV_CONSTRUCTION_ICON} （サンプル）図表・チャート": [
            st.Page("pages/26_表作成.py", title="表作成", icon="📋", url_path="26_表作成"),
            st.Page("pages/27_棒グラフ作成.py", title="棒グラフ作成", icon="📊", url_path="27_棒グラフ作成"),
            st.Page("pages/32_ガントチャート.py", title="ガントチャート", icon="📅", url_path="32_ガントチャート"),
            st.Page("pages/33_フローチャート.py", title="フローチャート", icon="🔀", url_path="33_フローチャート"),
            st.Page(
                "pages/310_スライド作成.py",
                title="スライド作成",
                icon="📊",
                url_path="310_スライド作成",
            ),
        ],

        f"{NAV_CONSTRUCTION_ICON} （開発中）Word書類作成支援": [
            st.Page(
                "pages/110_word画像埋込.py",
                title="Word画像埋込",
                icon="🖼",
                url_path="110_word画像埋込",
            ),
            st.Page(
                "pages/200_wordtex.py",
                title="wordTex",
                icon="📄",
            ),
        ],

        f"{NAV_STOP_ICON} 開発・管理": [
            st.Page(
                "pages/999_開発用管理者ログイン.py",
                title="開発用 管理者ログイン",
                icon="🔐",
                url_path="999_開発用管理者ログイン",
            ),
        ],       

        # "🌿 Redlist": [
        #     st.Page("pages/35_レッドリスト検索.py", title="レッドリスト検索", icon="🌿", url_path="35_レッドリスト検索"),
        # ],

        "📕 PDF Tools": [
            st.Page("pages/42_図表見出し抽出.py", title="図表見出し抽出", icon="📕", url_path="42_図表見出し抽出"),
            st.Page("pages/43_頁抽出チェック.py", title="頁抽出チェック", icon="🔍", url_path="43_頁抽出チェック"),
            st.Page("pages/44_頁テキスト抽出.py", title="頁テキスト抽出", icon="📄", url_path="44_頁テキスト抽出"),
            st.Page("pages/56_pdf頁テキスト抽出.py", title="PDF頁テキスト抽出", icon="📄", url_path="56_pdf頁テキスト抽出"),
            st.Page("pages/57_OCRツール.py", title="OCRツール", icon="👁️", url_path="57_OCRツール"),
        ],

        # "📄 Word Tools": [
        #     st.Page("pages/61_word内部ファイル抽出.py", title="Word内部ファイル抽出", icon="📦", url_path="61_word内部ファイル抽出"),
        #     st.Page("pages/62_word段落リスト.py", title="Word段落リスト", icon="📄", url_path="62_word段落リスト"),
        # ],

        # "🧰 Tools": [
        #     st.Page("pages/73_正規表現テスト.py", title="正規表現テスト", icon="🔤", url_path="73_正規表現テスト"),
        #     st.Page("pages/74_形態素解析.py", title="形態素解析", icon="🔠", url_path="74_形態素解析"),
        #     st.Page("pages/75_名詞リスト.py", title="名詞リスト", icon="📋", url_path="75_名詞リスト"),
        # ],

        # "🌿 Redlist App": [
        #     st.Page("pages/80_レッドリスト_チェック.py", title="レッドリストチェック", icon="🌿", url_path="80_レッドリストチェック"),
        #     st.Page("pages/90_レッドリスト_福島チェック.py", title="レッドリスト福島チェック", icon="🌿", url_path="90_レッドリスト福島チェック"),
        # ],

        # "🔐 管理・その他": [
        #     st.Page("pages/92_バックアップ.py", title="バックアップ", icon="💾", url_path="92_バックアップ"),
        #     st.Page("pages/102_フォント表示.py", title="フォント表示", icon="🔤", url_path="102_フォント表示"),
        # ],

        # "📄 Word解析・管理": [
        #     st.Page("pages/510_word_styles解析.py", title="Word styles解析", icon="🔎", url_path="510_word_styles解析"),
        #     st.Page("pages/512_word見出解析.py", title="Word見出解析", icon="📑", url_path="512_word見出解析"),
        #     st.Page("pages/520_ログインonly.py", title="ログインonly", icon="🔐", url_path="520_ログインonly"),
        #     st.Page("pages/530_ログインテスト.py", title="ログインテスト", icon="🔐", url_path="530_ログインテスト"),
        # ],

        # "🧪 実験ページ": [
        #     st.Page("pages/650_文章校正テスト.py", title="文章校正テスト", icon="📝", url_path="650_文章校正テスト"),
        #     st.Page("pages/700_ChatGPT風_QA.py", title="ChatGPT風QA", icon="💬", url_path="700_ChatGPT風_QA"),
        #     st.Page("pages/701_AIチャット(Gemini).py", title="AIチャット Gemini", icon="✨", url_path="701_AIチャット_Gemini"),
        #     st.Page("pages/900_JPEG_to_PDF.py", title="JPEG to PDF", icon="🖼️", url_path="900_JPEG_to_PDF"),
        #     st.Page("pages/902_ChatGPT風_QA copy.py", title="ChatGPT風QA copy", icon="💬", url_path="902_ChatGPT_QA_copy"),
        #     st.Page("pages/903_論文PNG化.py", title="論文PNG化", icon="🖼️", url_path="903_論文PNG化"),
        #     st.Page("pages/904_翻訳（PDF・画像）.py", title="翻訳 PDF・画像", icon="🌐", url_path="904_翻訳_PDF画像"),
        #     st.Page("pages/905_数式TeX出力.py", title="数式TeX出力", icon="🧮", url_path="905_数式TeX出力"),
        #     st.Page("pages/906_図表チェックv2.py", title="図表チェックv2", icon="📊", url_path="906_図表チェックv2"),
        #     st.Page("pages/907_AI図表チェックv2.py", title="AI図表チェック新版", icon="🤖", url_path="907_AI図表チェックv2"),
        # ],
    }
)


# ============================================================
# run
# ============================================================
pg.run()