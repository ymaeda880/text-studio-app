# -*- coding: utf-8 -*-
# pages/102_フォント表示.py
#
# システムで利用可能なフォント一覧＋サンプル表示
# 追加: Matplotlib で実際に描画したプレビュー（PNG）と、フォントファイルの場所も表示

from __future__ import annotations
import io, base64, os
import streamlit as st
from matplotlib import font_manager, rcParams
import matplotlib.pyplot as plt
from streamlit.components.v1 import html as st_html

st.set_page_config(page_title="🔤 フォント一覧とサンプル", page_icon="🔤", layout="wide")
st.title("🔤 システムで利用可能なフォント一覧（サンプル付き）")

st.caption("matplotlib.font_manager で検出されたフォントを一覧表示し、各フォントのサンプルを確認できます。")

# ─────────────────────────────────────────────────────────────
# 1) 全フォント（Matplotlibが認識しているフォント）を取得
# ─────────────────────────────────────────────────────────────
ttf_list = font_manager.fontManager.ttflist  # FontEntry のリスト
fonts_all = sorted({f.name for f in ttf_list})
n_fonts = len(fonts_all)
st.info(f"Matplotlib が検出したフォント数: **{n_fonts}**")

# ─────────────────────────────────────────────────────────────
# 2) 検索ボックス
# ─────────────────────────────────────────────────────────────
query = st.text_input("🔍 フォント名で検索（部分一致）", value="", placeholder="例: Meiryo, Noto, Hiragino など")
if query.strip():
    fonts_filtered = [f for f in fonts_all if query.lower() in f.lower()]
    st.write(f"検索結果: {len(fonts_filtered)} / {n_fonts} 件")
else:
    fonts_filtered = fonts_all

# ─────────────────────────────────────────────────────────────
# 3) サンプル文字設定（HTMLプレビュー用）
# ─────────────────────────────────────────────────────────────
st.markdown("#### ✏️ サンプル文字列（HTML/CSSプレビュー用）")
sample_text = st.text_input("サンプル文字（任意）", value="あいうえお ABC 123", placeholder="例：こんにちは World 123")

# ─────────────────────────────────────────────────────────────
# 4) HTML構築（ブラウザ側レンダリング）
# ─────────────────────────────────────────────────────────────
html_rows = []
for fname in fonts_filtered:
    html_rows.append(
        f"""
        <tr>
            <td style="padding:6px 10px; vertical-align:middle; white-space:nowrap;">{fname}</td>
            <td style="font-family:'{fname}'; font-size:18px; padding:6px 10px; color:#222;">{sample_text}</td>
        </tr>
        """
    )

html_table = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<style>
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Meiryo", "Noto Sans CJK JP", "IPAexGothic", sans-serif;
  font-size: 15px;
  color: #333;
}}
table {{
  border-collapse: collapse;
  width: 100%;
}}
th, td {{
  border-bottom: 1px solid #ddd;
}}
th {{
  background: #f0f0f0;
  text-align: left;
}}
</style>
</head>
<body>
<table>
<thead>
<tr><th>フォント名</th><th>（ブラウザ）サンプル</th></tr>
</thead>
<tbody>
{''.join(html_rows)}
</tbody>
</table>
</body>
</html>
"""
st_html(html_table, height=520, scrolling=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────
# 5) Matplotlib で実際に描画するプレビュー（PNG）
#    → 「Matplotlibから本当に使えるか」を確認
# ─────────────────────────────────────────────────────────────
st.subheader("🧪 Matplotlib プレビュー（実際に描画）")

colL, colR = st.columns([1, 2])
with colL:
    mp_text = st.text_input("Matplotlib用サンプル文字", value="日本語プレビュー：あいうえお ABC 123")
    # 候補（検索結果の先頭を既定に）
    default_idx = 0 if not fonts_filtered else 0
    sel_font = st.selectbox("フォントを選択（Matplotlib名）", options=fonts_filtered or ["(なし)"], index=default_idx)
    size = st.slider("フォントサイズ", 8, 48, 18, 1)
    show_paths = st.checkbox("フォントファイルの場所も表示", value=True)
    if st.button("描画する", type="primary", use_container_width=True):
        st.session_state.__do_draw = True

with colR:
    if st.session_state.get("__do_draw"):
        # rcParams を設定（強制）
        rcParams["font.family"] = "sans-serif"
        rcParams["font.sans-serif"] = [sel_font]
        rcParams["axes.unicode_minus"] = False

        # 実際に描画
        buf = io.BytesIO()
        try:
            plt.close("all")
            fig = plt.figure(figsize=(7, 2.2), dpi=150)
            ax = fig.add_subplot(111)
            ax.axis("off")
            ax.text(0.02, 0.5, mp_text, fontsize=size, fontname=sel_font, va="center")
            fig.tight_layout(pad=0.6)
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            st.image(buf.getvalue(), caption=f"Matplotlib 描画プレビュー（{sel_font}）", use_column_width=True)
        except Exception as e:
            st.error(f"描画に失敗しました: {e}")

# ─────────────────────────────────────────────────────────────
# 6) フォントファイルの場所（Matplotlib が参照している実体）
# ─────────────────────────────────────────────────────────────
st.markdown("### 📁 Matplotlib が持つフォント情報（ファイルパス）")
if show_paths:
    # name -> [paths] の辞書
    name_to_paths = {}
    for fe in ttf_list:
        name_to_paths.setdefault(fe.name, []).append(fe.fname)

    # 検索結果に合わせて表示
    for nm in fonts_filtered[:300]:  # 表示し過ぎ防止で最大300件
        paths = name_to_paths.get(nm, [])
        disp = "<br/>".join(f"<code>{p}</code>" for p in paths) if paths else "<i>（パス未取得）</i>"
        st.markdown(f"- **{nm}**  → {disp}", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────
# 7) 代表的フォント存在チェック
# ─────────────────────────────────────────────────────────────
st.subheader("✅ 代表的フォントの存在確認（Matplotlib認識ベース）")
check_fonts = ["Meiryo", "Meiryo UI", "Hiragino Sans", "Yu Gothic", "Noto Sans CJK JP", "IPAexGothic", "MS Gothic"]
for name in check_fonts:
    found = any(name.lower() == f.lower() for f in fonts_all)
    st.write(f"**{name}**: {'🟢 あり' if found else '⚪️ なし'}")

# ─────────────────────────────────────────────────────────────
# 8) 使い方メモ
# ─────────────────────────────────────────────────────────────
st.markdown(
    """
---
💡 **使い方メモ**
- ここに出る一覧は *Matplotlib が実際にスキャンしたフォント* です（`font_manager.fontManager.ttflist`）。
- **Meiryo** は標準の macOS には入っていないため、表示されないのが正常です。使う場合は `.ttf/.ttc` を導入してください。
- プロジェクト内だけで使う場合は `font_manager.addfont(PATH)` で追加 → `rcParams["font.sans-serif"]=[その名前]` が簡単です。
"""
)
