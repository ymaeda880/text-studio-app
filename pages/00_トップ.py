# text_studio_app/pages/00_トップ.py
#
from __future__ import annotations

# ============================================================
# imports
# ============================================================
import sys
from pathlib import Path
import tomllib

import streamlit as st


# ============================================================
# パスの取得と common_lib 読み込み
# ============================================================
_THIS = Path(__file__).resolve()
APP_ROOT = _THIS.parents[1]
APP_NAME = APP_ROOT.name
PROJECTS_ROOT = _THIS.parents[3]

if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))


# ============================================================
# common_lib imports
# ============================================================
from common_lib.auth.auth_helpers import require_login
from common_lib.sessions import (
    SessionConfig,
    heartbeat_tick,
    init_session,
)
from common_lib.storage.storages_config import (
    resolve_storages_root,
)
from common_lib.ui.ui_basics import subtitle
from common_lib.ui.banner_lines import (
    render_banner_line_by_key,
)
from common_lib.ui.theme_colors import (
    get_theme_colors_from_banner_key,
)
from common_lib.ui.intro_panel import (
    render_intro_css,
    render_hero_panel,
    render_two_column_cards,
    render_info_card,
)

# ============================================================
# settings.toml
# ============================================================
SETTINGS_TOML = (
    APP_ROOT
    / ".streamlit"
    / "settings.toml"
)
with open(SETTINGS_TOML, "rb") as f:
    settings = tomllib.load(f)


# ============================================================
# theme / banner
# ============================================================
BANNER_KEY = settings.get(
    "BANNER_KEY",
    "purple_light",
)
render_banner_line_by_key(BANNER_KEY)
theme = get_theme_colors_from_banner_key(
    BANNER_KEY
)
render_intro_css(theme)

# ============================================================
# セッション設定
# ============================================================
STORAGES_ROOT = resolve_storages_root(
    PROJECTS_ROOT
)
SESSIONS_DB = (
    STORAGES_ROOT
    / "_admin"
    / "sessions"
    / "sessions.db"
)
CFG = SessionConfig()

# ============================================================
# ログイン必須
# ============================================================
sub = require_login(st)
if not sub:
    st.stop()
user = sub

# ============================================================
# ヘッダ
# ============================================================
left, right = st.columns([2, 1])
with left:
    st.title(
        "✍️ Text Studio"
    )
with right:
    st.success(
        f"✅ ログイン中: **{sub}**"
    )
subtitle("文章作成支援：文章を磨くAIスタジオ")

# ============================================================
# sessions
# ============================================================
init_session(
    db_path=SESSIONS_DB,
    cfg=CFG,
    user_sub=user,
    app_name=APP_NAME,
)

heartbeat_tick(
    db_path=SESSIONS_DB,
    cfg=CFG,
    user_sub=user,
    app_name=APP_NAME,
)


# ============================================================
# short description
# ============================================================
st.caption(
    "Check・Translate・Summarize・Refine — all in one workspace."
)

st.markdown(
    """
**左サイドバーのメニュー項目**をクリックして各機能ページへ移動してください。  
"""
)


# ============================================================
# hero
# ============================================================
render_hero_panel(
    kicker="TEXT STUDIO",
    title="文章を、もっと正確に。もっと伝わりやすく。",
    body_html="""
<span class="ts-highlight">Text Studio</span>
は、文章校正・翻訳・要約・表現改善をまとめて扱うための
AIワークスペースです。<br>

左サイドバーから目的に応じた機能を選び、お使いください．７
まずは
<span class="ts-highlight">文章校正</span>
ページをお試しください。
""",
    chips=[
        "Check",
        "Translate",
        "Summarize",
        "Refine",
    ],
)


# ============================================================
# info cards
# ============================================================
render_two_column_cards(
    left_title="🚧 現在も改良中です",
    left_body_html="""
本アプリケーションは、
業務効率を高めることを目的として
継続的に改良しています。<br>

気づいた点・改善要望・不具合がありましたら、
ぜひフィードバックをお寄せください。
""",
    right_title="📝 Word連携にも対応しました",
    right_body_html="""
Wordファイルを解析し、
中間解析ファイルを inBox に保存することで、
文章校正へ連携できる
統合型ツールを目指しています。<br>

皆様のご利用とご意見が、
より良いツールづくりにつながります。
""",
)


# ============================================================
# feature card
# ============================================================
render_info_card(
    title="📝 一括Word校正にも対応しました",
    body_html="""
Wordファイルを解析し、
中間解析ファイルをサーバー内部に保存することで、
文章校正へ直接連携できる
一括処理ツールを作成しました。<br>

Word → 解析 → AI校正 → 修正確認
までを一連の流れで扱えます。
""",
)