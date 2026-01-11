# app.py — Text Studio メインページ
from __future__ import annotations
import streamlit as st

# ============================================================
# パスの取得とcommon_lib読み込み（app.pyにおけるコード）
# ============================================================
from pathlib import Path
import sys

_THIS = Path(__file__).resolve()
APP_ROOT = _THIS.parent
APP_NAME = APP_ROOT.name                  # ← app_name を自動取得
PROJECTS_ROOT = _THIS.parents[2]

if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))

from common_lib.sessions import SessionConfig, init_session, heartbeat_tick
from common_lib.auth.auth_helpers import require_login


st.set_page_config(page_title="Text Studio", page_icon="✍️", layout="wide")
# ============================================================
# Session heartbeat（全ページ共通・app.py）
# ============================================================
SESSIONS_DB = (
    PROJECTS_ROOT / "Storages" / "_admin" / "sessions" / "sessions.db"
)
CFG = SessionConfig()  # heartbeat=30s, TTL=120s（既定）

# ───────────────── ログイン必須 ─────────────────

sub = require_login(st)
if not sub:
    st.stop()

# ───────────────── ヘッダ ─────────────────
left, right = st.columns([2, 1])
with left:
    st.title("✍️ Text Studio — 文章を磨くAIスタジオ")
with right:
    st.success(f"✅ ログイン中: **{sub}**")

user = sub

# ───────────────── sessions（初期化 + heartbeat） ─────────────────
init_session(db_path=SESSIONS_DB, cfg=CFG, user_sub=user, app_name=APP_NAME)
heartbeat_tick(db_path=SESSIONS_DB, cfg=CFG, user_sub=user, app_name=APP_NAME)


st.caption("Check・Translate・Summarize・Refine — all in one workspace.")

st.markdown(
    """
    **左サイドバーの項目**をクリックして各機能ページへ移動してください。  
    まずは **校正** ページをお試しください。
    """
)

st.markdown("""
## 🚧 このアプリケーションは現在 **開発中** です

本アプリケーションシステム **Text Studio** は、皆様の業務効率を高めることを目的として継続的に改良を進めています。  
実際にご利用いただき、**気づいた点・改善してほしい点・不具合** などについてフィードバックをお寄せください。

いただいたご意見をもとにプログラムの改善を行い、  
より使いやすく、業務に役立つツールへと仕上げてまいります。

ご協力のほど、どうぞよろしくお願いいたします。
""")

st.markdown("""
## 📝 校正アプリケーションについて

**校正** アプリケーションは現在、**テキストを貼り付けて校正する方式**で動作していますが、  
最終的には、**Wordファイル（.docx）をドロップするだけで**、

- GPT が解釈可能な中間コードへ自動変換  
- 適切な単位への自動分割  
- 校正結果の一括生成  
- PDF／Word への出力  

までを **一度の操作で完了** できる統合型ツールを目指しています。

まだ開発途中であり、ご不便をおかけする点も多いかと思いますが、  
皆様からの **積極的なご利用とフィードバック** が改善の大きな力になります。

より良い校正アプリケーションを共に育てていくため、  
何卒ご協力のほどよろしくお願いいたします。
""")
