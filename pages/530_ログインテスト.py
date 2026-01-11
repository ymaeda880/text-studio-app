# -*- coding: utf-8 -*-
# pages/530_ログインテスト.py
#
# ✅ ログイン表示だけの最小ページ
# - common_lib の require_login を使って「ログイン必須」にする
# - sub（ユーザーID）が取れたら画面に表示する
# - ついでに、参照している auth_helpers の実体パスも出す（別common_lib拾いの切り分け用）

from __future__ import annotations

from pathlib import Path
import sys
import streamlit as st

# ============================================================
# sys.path 調整（common_lib を import 可能に）
# - pages 配下のファイルを想定：parents[3] が .../projects になる構成
# ============================================================
_THIS = Path(__file__).resolve()
PROJECTS_ROOT = _THIS.parents[3]
if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))

# ============================================================
# common_lib: login
# ============================================================
from common_lib.auth.auth_helpers import require_login, get_current_user_from_session_or_cookie  # noqa: E402
import common_lib.auth.auth_helpers as _auth_helpers  # noqa: E402

st.set_page_config(page_title="🧪 ログインテスト", page_icon="🧪", layout="wide")

st.write("PROJECTS_ROOT =", str(PROJECTS_ROOT))
st.write("auth_helpers file =", str(Path(_auth_helpers.__file__).resolve()))
st.write("sys.path[0] =", sys.path[0] if sys.path else "(empty)")

import sys, jwt
st.code({
    "python": sys.executable,
    "jwt_file": jwt.__file__,
    "jwt_version": jwt.__version__,
})


# from common_lib.auth.jwt_utils import verify_jwt
# from common_lib.auth.config import JWT_ISS, JWT_AUD
# import inspect

# st.write("verify_jwt module:", verify_jwt.__module__)
# st.write("verify_jwt file:", inspect.getfile(verify_jwt))
# st.write("JWT_ISS / JWT_AUD:", JWT_ISS, JWT_AUD)


# from common_lib.auth.config import COOKIE_NAME
# from common_lib.auth.auth_helpers import CM_KEY, _get_cm

# cm = _get_cm(CM_KEY)
# st.write("COOKIE_NAME:", COOKIE_NAME)
# st.write("CM_KEY:", CM_KEY)
# st.write("cm.get(cookie) exists?:", bool(cm.get(COOKIE_NAME)))

# ============================================================
# Page
# ============================================================
#st.set_page_config(page_title="🧪 ログインテスト", page_icon="🧪", layout="wide")

left, right = st.columns([2, 1])
with left:
    st.title("🧪 ログインテスト")
with right:
    # require_login が内部でログインUIを出す実装なら、未ログイン時はそこで案内が出る
    sub = require_login(st)
    if not sub:
        st.stop()
    st.success(f"✅ ログイン中: **{sub}**")

st.markdown("---")
st.subheader("ログイン情報（確認用）")

user, payload = get_current_user_from_session_or_cookie(st)

c1, c2 = st.columns(2)
with c1:
    st.write("**sub（require_login の戻り）**")
    st.code(str(sub), language="text")
with c2:
    st.write("**user（get_current_user_from_session_or_cookie）**")
    st.code(str(user), language="text")

st.write("**payload（JWTペイロードの一部）**")
# payload が dict の想定。None の場合はそのまま表示
st.json(payload if isinstance(payload, dict) else {"payload": str(payload)})

st.markdown("---")
st.subheader("参照している common_lib（切り分け用）")

st.write("**PROJECTS_ROOT**")
st.code(str(PROJECTS_ROOT), language="text")

st.write("**auth_helpers 実体ファイル**")
st.code(str(Path(_auth_helpers.__file__).resolve()), language="text")

st.write("**common_lib ルート推定**")
try:
    st.code(str(Path(_auth_helpers.__file__).resolve().parents[2]), language="text")
except Exception:
    st.code("(unknown)", language="text")
