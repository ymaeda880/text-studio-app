# -*- coding: utf-8 -*-
# lib/graph/bar/sidebar.py
#
# 棒グラフページ共通の「サイドバー UI」部品
# - サンプルデータ選択（サンプル1〜4）
# - パラメータのリセット / プリセット適用
# - JSONC プリセットの保存・読み込み

from __future__ import annotations

from typing import Dict, Any, Optional

import streamlit as st

from .presets import (
    DEFAULTS,
    PRESETS,
    sample_hint,
    sample_hint2,
    sample_hint3,
    sample_hint4,
)
from .state import apply_preset, reset_params_keep_data, assert_preset_exists
from .jsonc_presets import (
    export_jsonc_from_session,
    load_preset_from_jsonc,
    apply_preset_to_session,
)


# =========================================================
# サンプルデータ用の設定
# =========================================================
SAMPLE_CONFIG: Dict[str, Dict[str, Optional[str]]] = {
    "なし":      {"hint": "",            "preset": None},
    "サンプル1": {"hint": sample_hint,   "preset": "サンプル1"},
    "サンプル2": {"hint": sample_hint2,  "preset": "サンプル2"},
    "サンプル3": {"hint": sample_hint3,  "preset": "サンプル3"},
    "サンプル4": {"hint": sample_hint4,  "preset": "サンプル4"},
}


# =========================================================
# 1) サンプル選択パネル
# =========================================================
# def render_sample_sidebar(
#     *,
#     key_choice: str = "sample_choice",
#     key_prev_choice: str = "__prev_sample_choice",
# ) -> str:
#     """
#     サイドバー内に「サンプルデータの種類」ラジオボタンを描画し，
#     現在選ばれているサンプルの「貼り付け欄に表示するヒント文字列」を返す。

#     - 初回呼び出し時は，現在の選択値を「前回選択値」として記録するだけで，
#       プリセットの適用は行わない。
#     - 2回目以降でサンプル選択が前回から変化した場合に限り，
#       SAMPLE_CONFIG に対応するプリセット名が設定されていれば
#       apply_preset() で session_state に反映し st.rerun() する。

#     使い方（ページ側）：
#     -------------------
#     with st.sidebar:
#         current_hint = render_sample_sidebar()
#     """
#     # --- サンプル選択 ---
#     sample_choice = st.radio(
#         "サンプルデータの種類（貼り付け欄が空のときに表示）",
#         tuple(SAMPLE_CONFIG.keys()),
#         horizontal=False,
#         key=key_choice,
#     )

#     # --- 初回：前回選択値を現在値で初期化して終了 ---
#     if key_prev_choice not in st.session_state:
#         st.session_state[key_prev_choice] = sample_choice
#         sample_conf = SAMPLE_CONFIG.get(sample_choice, SAMPLE_CONFIG["なし"])
#         return sample_conf["hint"] or ""

#     # --- 現在のサンプル設定 ---
#     sample_conf = SAMPLE_CONFIG.get(sample_choice, SAMPLE_CONFIG["なし"])
#     current_hint: str = sample_conf["hint"] or ""
#     # preset_for_sample = sample_conf.get("preset")  # ← もう自動適用しないなら不要

#     # --- サンプル選択変更時のみ raw_text を差し替える ---
#     if sample_choice != st.session_state[key_prev_choice]:
#         st.session_state[key_prev_choice] = sample_choice

#         # ここでテキストエリア用の raw_text を更新する
#         if sample_choice == "なし":
#             # なしを選んだときは空にする（お好みで）
#             st.session_state["raw_text"] = ""
#         else:
#             # サンプル名に対応した固定テキストを入れる
#             st.session_state["raw_text"] = current_hint

#         # ※ レイアウトのプリセットはサイドバーの「🎛 プリセット」で
#         #    ユーザーが手動で適用する運用にする

#     return current_hint

# =========================================================
# 1) サンプル選択パネル
# =========================================================
def render_sample_sidebar(
    *,
    key_choice: str = "sample_choice",
    key_prev_choice: str = "__prev_sample_choice",
) -> str:
    """
    サイドバー内に「サンプルデータの種類」ラジオボタンを描画し，
    現在選ばれているサンプルの「貼り付け欄に表示するヒント文字列」を返す。

    - ラジオボタンは「どのサンプルを使うかの選択」だけを担当し，
      実際に貼り付け欄（raw_text）の中身を書き換えるのは
      下の「サンプルを適用」ボタンを押したときだけ。
    - レイアウトのプリセット適用は，サイドバー下部の
      「🎛 プリセット」のところでユーザーが手動で行う。

    使い方（ページ側）：
    -------------------
    with st.sidebar:
        current_hint = render_sample_sidebar()
    """
    state = st.session_state

    # --- 前回選択値の初期化 ---
    if key_prev_choice not in state:
        state[key_prev_choice] = "なし"

    # --- サンプル選択（ラジオ） ---
    sample_choice = st.radio(
        "サンプルデータの種類（貼り付け欄が空のときに表示）",
        tuple(SAMPLE_CONFIG.keys()),
        horizontal=False,
        key=key_choice,
    )

    # --- 現在のサンプル設定 ---
    sample_conf = SAMPLE_CONFIG.get(sample_choice, SAMPLE_CONFIG["なし"])
    current_hint: str = sample_conf["hint"] or ""

    # ユーザー向け案内
    st.caption("※ サンプルを貼り付け欄に反映するには、下の『サンプルを適用』ボタンを押してください。")

    # --- 「サンプルを適用」ボタン ---
    if st.button("サンプルを適用", key="sample_apply_button", use_container_width=True):
        # 選択中サンプルのテキストを貼り付け欄(raw_text)に入れる
        if sample_choice == "なし":
            state["raw_text"] = ""
        else:
            state["raw_text"] = current_hint

        # ついでに「前回選択値」も更新しておく
        state[key_prev_choice] = sample_choice

    # ラジオの最新選択値を記録（今後別用途で使う場合に備えて）
    state[key_prev_choice] = sample_choice

    # ページ側では current_hint を「ヒント文字列」として使える
    return current_hint


# =========================================================
# 2) 「リセット & プリセット」パネル
# =========================================================
def render_reset_and_preset_sidebar() -> None:
    """
    サイドバー内に「パラメータのリセット」＋「プリセット」＋「JSONC入出力」GUIを描画する。

    ページ側では：

        with st.sidebar:
            render_reset_and_preset_sidebar()

    のように呼び出す想定。
    """
    # -----------------------------
    # 🧼 パラメータのリセット
    # -----------------------------
    st.markdown("### 🧼 パラメータのリセット")

    if st.button("🔄 すべて初期値に戻す（安全）", use_container_width=True):
        reset_params_keep_data()
        st.rerun()

    # -----------------------------
    # 🎛 プリセット
    # -----------------------------
    st.markdown("### 🎛 プリセット")

    # PRESETS のキー一覧（dict は順序を保つのでそのままリスト化）
    preset_options = list(PRESETS.keys())
    if not preset_options:
        st.info("利用可能なレイアウトプリセットが定義されていません。")
        return

    preset_name = st.selectbox(
        "レイアウトプリセットを選択",
        preset_options,
        index=0,
    )

    if st.button("適用", use_container_width=True):
        apply_preset(PRESETS[preset_name])
        st.success(f"プリセット「{preset_name}」を適用しました。")
        st.rerun()

    # -----------------------------
    # JSONC ダウンロード（常に最新 state を反映）
    # -----------------------------
    jsonc_text = export_jsonc_from_session(st.session_state)
    st.download_button(
        "⬇️ JSONCで現在の設定を保存",
        data=jsonc_text.encode("utf-8"),
        file_name="current_preset.jsonc",
        mime="application/json",
        use_container_width=True,
    )

    # -----------------------------
    # JSONC プリセットのアップロード＆適用
    # -----------------------------
    st.markdown("### 📥 JSONCプリセットの読み込み")
    st.caption(
        "※ プリセットを読み込んだ後は、メイン画面の『🔁 再描画を実行』ボタンを押してグラフを更新してください。"
    )

    uploaded = st.file_uploader(
        "JSONC形式のプリセットファイル（.json / .jsonc）を選択",
        type=["json", "jsonc"],
        key="preset_upload",
    )

    if st.button("⬆️ アップロードしたプリセットを適用", use_container_width=True):
        if uploaded is None:
            st.warning("先にJSONCファイルを選択してください。")
        else:
            try:
                raw = uploaded.getvalue().decode("utf-8")
                preset_dict: Dict[str, Any] = load_preset_from_jsonc(raw)
                # JSONC から読み込んだプリセットは，
                # jsonc_presets 側の apply_preset_to_session を利用
                apply_preset_to_session(preset_dict, st.session_state)
                st.success("JSONC プリセットを適用しました。")
            except Exception as e:
                st.warning(f"プリセットの読み込みに失敗しました: {e}")
