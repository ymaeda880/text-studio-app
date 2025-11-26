# -*- coding: utf-8 -*-
# pages/74_形態素解析.py
from __future__ import annotations

import io
from collections import Counter
from typing import List, Tuple

import pandas as pd
import streamlit as st

# ============== ページ設定 ==============
st.set_page_config(page_title="🧩 形態素解析（名詞のみ抽出）", page_icon="🧩", layout="wide")
st.title("🧩 52_ 形態素解析（名詞のみ抽出）")
st.caption("textarea に入力した文章へ形態素解析をかけ、名詞のみを抽出します（Janome 使用）。")

# ============== Janome の読み込み ==============
try:
    from janome.tokenizer import Tokenizer  # pip install janome
    tokenizer = Tokenizer()
except Exception as e:
    st.error(
        "Janome が見つかりません。ターミナルで `pip install janome` を実行してください。\n\n"
        f"詳細: {e}"
    )
    st.stop()

# ============== サイドバー（オプション） ==============
with st.sidebar:
    st.subheader("⚙️ オプション")
    min_len = st.number_input("最小文字数（名詞）", min_value=1, max_value=20, value=2, step=1)
    uniq_only = st.checkbox("重複を除く（名詞の一覧）", value=False)
    use_base = st.checkbox("原形で集計（例：複合語の揺れを抑える）", value=True)
    show_pos_detail = st.checkbox("品詞細分類を表示", value=False)
    st.markdown("---")
    stopwords_raw = st.text_area(
        "ストップワード（改行区切り）", value="こと\nもの\nそれ\nこれ\nため\nよう\nところ",
        height=120
    )
    stopwords = {w.strip() for w in stopwords_raw.splitlines() if w.strip()}

# ============== 入力エリア ==============
sample = "生成AIの活用が進む中で、ガバナンス、著作権、個人情報保護、透明性の確保が重要となっている。企業はモデルの精度だけでなく、説明可能性や監査可能性にも配慮する必要がある。"
text = st.text_area("📥 解析するテキストを貼り付けてください", value=sample, height=180)

# ============== 解析ボタン ==============
run = st.button("🚀 解析する")

# ============== ユーティリティ ==============
def extract_nouns(s: str) -> List[Tuple[str, str, str, int]]:
    """
    文章から名詞のみを抽出。
    Returns: List of (surface, base, pos, start_index)
    """
    res: List[Tuple[str, str, str, int]] = []
    ofs = 0
    # ✅ stream=True は削除。通常のイテレーションでOK。
    for token in tokenizer.tokenize(s):
        surf = token.surface
        base = token.base_form if token.base_form != "*" else surf
        pos = token.part_of_speech  # 例: 名詞,一般,*,*
        start_idx = ofs
        ofs += len(surf)
        if pos.startswith("名詞"):
            res.append((surf, base, pos, start_idx))
    return res


def normalize_token(t: str) -> str:
    return t.replace("\u3000", " ").strip()

# ============== 実行 ==============
if run:
    s = (text or "").strip()
    if not s:
        st.warning("テキストを入力してください。")
        st.stop()

    tokens = extract_nouns(s)

    # 最小長・ストップワードでフィルタ
    filtered = []
    for surf, base, pos, idx in tokens:
        key = base if use_base else surf
        key = normalize_token(key)
        if len(key) < min_len:
            continue
        if key in stopwords:
            continue
        filtered.append((surf, base, pos, idx, key))

    # ===== 名詞一覧 =====
    st.subheader("📝 名詞一覧")
    if uniq_only:
        seen = set()
        uniq_rows = []
        for surf, base, pos, idx, key in filtered:
            if key in seen:
                continue
            seen.add(key)
            uniq_rows.append((surf, base, pos, idx))
        rows = uniq_rows
    else:
        rows = [(surf, base, pos, idx) for surf, base, pos, idx, _ in filtered]

    cols = ["表層形", "原形", "品詞", "開始位置"]
    if not show_pos_detail:
        # 品詞の最初のカテゴリだけ（"名詞"）に単純化
        rows_disp = [(a, b, (c.split(",")[0] if c else ""), d) for (a, b, c, d) in rows]
    else:
        rows_disp = rows

    df_tokens = pd.DataFrame(rows_disp, columns=cols)
    st.dataframe(df_tokens, use_container_width=True, height=320)

    # ダウンロード（名詞一覧）
    buf_tok = io.StringIO()
    df_tokens.to_csv(buf_tok, index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 名詞一覧をCSVで保存",
        data=buf_tok.getvalue().encode("utf-8-sig"),
        file_name="nouns_list.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # ===== 出現頻度 =====
    st.subheader("📊 出現頻度（上位）")
    counter = Counter([key for *_, key in filtered])
    freq_rows = counter.most_common()
    df_freq = pd.DataFrame(freq_rows, columns=["名詞（キー）", "頻度"])
    st.dataframe(df_freq, use_container_width=True, height=320)

    # ダウンロード（頻度表）
    buf_freq = io.StringIO()
    df_freq.to_csv(buf_freq, index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 頻度表をCSVで保存",
        data=buf_freq.getvalue().encode("utf-8-sig"),
        file_name="nouns_freq.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # ===== ちょい可視化（上位20件の棒グラフ） =====
    try:
        import matplotlib.pyplot as plt

        topn = min(20, len(df_freq))
        if topn > 0:
            st.subheader("📈 頻度（上位20）")
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.barh(df_freq["名詞（キー）"].iloc[:topn][::-1], df_freq["頻度"].iloc[:topn][::-1])
            ax.set_xlabel("頻度")
            ax.set_ylabel("名詞（キー）")
            ax.set_title("名詞の出現頻度（上位20）")
            st.pyplot(fig)
    except Exception as e:
        st.info(f"簡易グラフの表示に失敗しました（matplotlib 未インストールなど）。詳細: {e}")

else:
    st.info("左上のテキストエリアに文章を入力し、[🚀 解析する] を押してください。")
