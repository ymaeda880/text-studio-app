# -*- coding: utf-8 -*-
from __future__ import annotations
from matplotlib import font_manager, rcParams
import os, tempfile
import streamlit as st

def setup_japanese_font() -> str:
    """
    PNG出力時の日本語文字化け対策。
    1) サイドバーでアップロードした .ttf/.otf を最優先
    2) システム既存フォント候補から探索
    """
    uploaded = st.session_state.get("__jp_font_path")
    if uploaded is None:
        with st.sidebar.expander("🈺 日本語フォント（PNG用・任意）", expanded=False):
            st.caption("化ける場合は .ttf/.otf をアップロードしてください（例: IPAexGothic, Noto Sans CJK JP）")
            f = st.file_uploader("日本語フォントファイル", type=["ttf", "otf"], accept_multiple_files=False)
            if f:
                save_path = os.path.join(tempfile.gettempdir(), f.name)
                with open(save_path, "wb") as w:
                    w.write(f.read())
                font_manager.fontManager.addfont(save_path)
                st.session_state["__jp_font_path"] = save_path
                uploaded = save_path
                st.success("フォントを登録しました。")

    if uploaded:
        prop = font_manager.FontProperties(fname=uploaded)
        name = prop.get_name()
        rcParams["font.family"] = "sans-serif"
        rcParams["font.sans-serif"] = [name]
        rcParams["axes.unicode_minus"] = False
        return name

    candidates = [
        "IPAexGothic", "IPAGothic",
        "Noto Sans CJK JP", "Noto Sans JP",
        "Hiragino Sans", "Hiragino Kaku Gothic ProN",
        "Yu Gothic", "MS Gothic",
    ]
    for nm in candidates:
        try:
            path = font_manager.findfont(nm, fallback_to_default=False)
            if os.path.exists(path):
                rcParams["font.family"] = "sans-serif"
                rcParams["font.sans-serif"] = [nm]
                rcParams["axes.unicode_minus"] = False
                return nm
        except Exception:
            pass

    st.sidebar.info("PNG の日本語が化ける場合は、.ttf/.otf をアップロードしてください。")
    rcParams["axes.unicode_minus"] = False
    return "(system default)"
