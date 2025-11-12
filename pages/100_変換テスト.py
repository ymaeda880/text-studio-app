# -*- coding: utf-8 -*-
# pages/62_福島カテゴリ変換テスト.py
# 目的：福島県カテゴリー表記を記号（CR/VU/NT/DD/EX）へ変換する最小テスト

from __future__ import annotations
from typing import Optional
import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="福島カテゴリ変換テスト", page_icon="🧪", layout="wide")
st.title("🧪 福島県カテゴリー → 記号 変換テスト（最小）")
st.caption("例：『絶滅危惧ⅠＡ類』→ CR，『絶滅危惧Ⅱ類』→ VU を確認。")

# ---- 正規化（最小限：空白除去/全角→半角/ローマ数字→英字/IとA混在補正/小文字化）----
def _norm_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    t = str(s)

    # 空白類を削除
    for ch in ("\u3000", "\u00A0", "\u200B", "\uFEFF", "\n", "\t"):
        t = t.replace(ch, " ")
    t = t.strip().replace(" ", "")

    # 全角英数 → 半角
    z = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９"
    h = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    t = t.translate(str.maketrans(z, h))

    # ローマ数字 → ラテン（Ⅰ/Ⅱ/Ⅲ…）
    roman_map = {
        "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V",
        "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX", "Ⅹ": "X",
        "Ⅺ": "XI", "Ⅻ": "XII",
    }
    for k, v in roman_map.items():
        t = t.replace(k, v)

    # I と A の全角/半角混在補正（例：ⅠＡ → IA, IＡ → IA, ⅠA → IA）
    t = re.sub(r"([IVX]+)[ＡA]", lambda m: m.group(1) + "A", t, flags=re.IGNORECASE)

    return t.lower()

# ---- 福島県カテゴリー → 記号（完全一致・正規化後）----
def to_fukushima_code(s: Optional[str]) -> Optional[str]:
    """
    正規化後の完全一致で変換：
      絶滅危惧ia類 → CR
      絶滅危惧ii類 → VU
      準絶滅危惧   → NT
      情報不足     → DD
      絶滅         → EX
    該当なしは「変換規則不明」。
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None

    raw = str(s).strip()
    # 明示リクエスト：この原文が来たら必ず CR
    if raw == "絶滅危惧ⅠＡ類":
        return "CR"

    key = _norm_text(raw)
    mapping = {
        "絶滅危惧ia類": "CR",
        "絶滅危惧ii類": "VU",
        "準絶滅危惧":   "NT",
        "情報不足":     "DD",
        "絶滅":         "EX",
    }
    return mapping.get(key, "変換規則不明")

# ---- UI ----
col1, col2 = st.columns([2, 1])
with col1:
    s = st.text_input("福島県カテゴリーを入力（例：絶滅危惧ⅠＡ類 / 絶滅危惧Ⅱ類 / 準絶滅危惧 など）", value="絶滅危惧ⅠＡ類")
with col2:
    if st.button("変換する", use_container_width=True):
        st.success(f"変換結果：{to_fukushima_code(s)}")

st.markdown("### サンプル（一括確認）")
samples = ["絶滅危惧ⅠＡ類", "絶滅危惧IA類", "絶滅危惧Ⅱ類", "準絶滅危惧", "情報不足", "絶滅", "不明カテゴリ"]
df = pd.DataFrame({
    "入力": samples,
    "正規化後": [ _norm_text(x) for x in samples ],
    "記号": [ to_fukushima_code(x) for x in samples ],
})
st.dataframe(df, use_container_width=True)
