# -*- coding: utf-8 -*-
# lib/graph/bar/state.py
#
# 棒グラフページ共通の「セッション状態まわり」のユーティリティ
# - DEFAULTS による初期化
# - プリセット適用（DEFAULTS をベースに上書き）
# - 「データだけ保持して他のパラメータを初期値に戻す」処理

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, MutableMapping

import streamlit as st

from .presets import DEFAULTS, PRESETS


SessionStateLike = MutableMapping[str, Any]


def _get_state(session_state: Optional[SessionStateLike] = None) -> SessionStateLike:
    """
    session_state 引数があればそれを使い，
    なければ st.session_state を返すヘルパ。
    """
    return session_state if session_state is not None else st.session_state


# =========================================================
# 1) 初期化
# =========================================================
def init_session_state_from_defaults(
    defaults: Optional[Dict[str, Any]] = None,
    session_state: Optional[SessionStateLike] = None,
) -> None:
    """
    DEFAULTS に定義されているキーについて，
    session_state にまだ存在しないものだけ初期化する。

    ページ冒頭で 1 回だけ呼び出す想定。

    Parameters
    ----------
    defaults : dict, optional
        デフォルト値の dict。省略時は presets.DEFAULTS を使用。
    session_state : Mapping, optional
        省略時は st.session_state を使用。
    """
    defaults = defaults or DEFAULTS
    state = _get_state(session_state)

    for k, v in defaults.items():
        if k not in state:
            state[k] = v


# =========================================================
# 2) プリセット適用
# =========================================================
def apply_preset(
    overrides: Dict[str, Any],
    *,
    defaults: Optional[Dict[str, Any]] = None,
    session_state: Optional[SessionStateLike] = None,
) -> None:
    """
    プリセットを session_state に適用する。

    - DEFAULTS に存在する全キーについて：
        プリセットに値があればその値，
        なければデフォルト値を設定する。
    - DEFAULTS に存在しない追加キーが overrides 側にある場合も，
      それをそのまま session_state に反映する。

    ページ内で以前ローカル定義していた apply_preset と同じ挙動。

    Parameters
    ----------
    overrides : dict
        プリセット定義（PRESETS[...] の 1 要素想定）。
    defaults : dict, optional
        デフォルト値 dict。省略時は presets.DEFAULTS を使用。
    session_state : Mapping, optional
        省略時は st.session_state を使用。
    """
    defaults = defaults or DEFAULTS
    state = _get_state(session_state)

    # 1) DEFAULTS に存在するキーは必ず「プリセット or デフォルト」で上書き
    for k, default_val in defaults.items():
        if k in overrides:
            state[k] = overrides[k]
        else:
            state[k] = default_val

    # 2) DEFAULTS にはないがプリセット側にだけ存在するキーも反映
    for k, v in overrides.items():
        if k not in defaults:
            state[k] = v


# =========================================================
# 3) 「データだけ保持して全パラメータを初期値に戻す」
# =========================================================
def reset_params_keep_data2(
    *,
    data_keys: Optional[Iterable[str]] = None,
    defaults: Optional[Dict[str, Any]] = None,
    session_state: Optional[SessionStateLike] = None,
) -> None:
    """
    「🔄 すべて初期値に戻す（安全）」ボタン用の処理。

    - data_keys に指定されたキーだけは値を保持し，
    - それ以外の session_state は一度 clear() してから DEFAULTS で再初期化，
    - 最後に保持しておいたデータを戻す。

    Parameters
    ----------
    data_keys : Iterable[str], optional
        データとして保持したいキー。
        省略時は ("data_df", "data_title", "data_diag", "raw_text") を使用。
    defaults : dict, optional
        デフォルト値 dict。省略時は presets.DEFAULTS を使用。
    session_state : Mapping, optional
        省略時は st.session_state を使用。
    """
    #defaults = defaults or DEFAULTS
    state = _get_state(session_state)

    if data_keys is None:
        data_keys = ("data_df", "data_title", "data_diag", "raw_text")

    # 1) データ系を一時退避
    kept: Dict[str, Any] = {k: state.get(k) for k in data_keys}

    # 2) state をクリアしてから DEFAULTS で再初期化
    state.clear()
    # for k, v in defaults.items():
    #     state[k] = v

    # 3) データ系を戻す
    for k, v in kept.items():
        if v is not None:
            state[k] = v


# =========================================================
# 3) 「データだけ保持して全パラメータを初期値に戻す」
# =========================================================
def reset_params_keep_data(
    *,
    data_keys: Optional[Iterable[str]] = None,
    defaults: Optional[Dict[str, Any]] = None,
    session_state: Optional[SessionStateLike] = None,
) -> None:
    """
    「🔄 すべて初期値に戻す（安全）」ボタン用の処理。

    - data_keys に指定されたキーだけは値を保持し，
    - それ以外の session_state は一度 clear() してから DEFAULTS で再初期化，
    - 最後に保持しておいたデータを戻す。

    Parameters
    ----------
    data_keys : Iterable[str], optional
        データとして保持したいキー。
        省略時は ("data_df", "data_title", "data_diag", "raw_text") を使用。
    defaults : dict, optional
        デフォルト値 dict。省略時は presets.DEFAULTS を使用。
    session_state : Mapping, optional
        省略時は st.session_state を使用。
    """
    defaults = defaults or DEFAULTS
    state = _get_state(session_state)

    if data_keys is None:
        data_keys = ("data_df", "data_title", "data_diag", "raw_text")

    # 1) データ系を一時退避
    kept: Dict[str, Any] = {k: state.get(k) for k in data_keys}

    # ★ サンプル選択など「保持したい UI 状態」も一緒に退避（必要なら）
    for extra_key in ("sample_choice", "__prev_sample_choice"):
        if extra_key in state:
            kept[extra_key] = state.get(extra_key)

    # 2) state をクリアしてから DEFAULTS で再初期化
    state.clear()
    for k, v in defaults.items():
        state[k] = v

    # 3) データ系 + サンプル選択を戻す
    for k, v in kept.items():
        if v is not None:
            state[k] = v

    # 4) スタイル用トグル／タブの状態は「存在しない状態」に戻す
    #    → 次回描画時に get(..., デフォルト) で安全に再初期化される
    for k in ("exp_style_all_open", "m_k_style_tab_choice"):
        if k in state:
            del state[k]


# =========================================================
# 4) PRESETS の存在チェック（おまけ）
# =========================================================
def assert_preset_exists(name: str) -> None:
    """
    PRESETS に name が存在しない場合は warning を出すヘルパ。
    """
    if name not in PRESETS:
        st.warning(f"プリセット '{name}' が PRESETS に見つかりませんでした。")
