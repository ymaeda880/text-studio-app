# app.py — Text Studio メインページ
from __future__ import annotations
import streamlit as st

st.set_page_config(page_title="Text Studio", page_icon="✍️", layout="wide")


st.title("✍️ Text Studio — 文章を磨くAIスタジオ")
st.caption("Check・Translate・Summarize・Refine — all in one workspace.")

st.markdown(
    """
    左サイドバーの **Pages** から機能ページへ移動してください。  
    まずは **校正** ページをお試しください。
    """
)
