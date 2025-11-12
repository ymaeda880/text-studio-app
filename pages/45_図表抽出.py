# -*- coding: utf-8 -*-
# pages/45_図表抽出.py
# 目的：
#   貼り付けテキストから「図/表/図表」の
#   ① 行単独の見出し（キャプション）
#   ② 本文中の参照（行途中の言及）
# を抽出し表示・CSV保存する。
# 判定ロジックは 24_図表チェック.py 簡略版と同じ（行頭/直後助詞/句点）。
# 追加の見やすさ改善：
#   ・行テキスト中でヒット箇所を ⟪…⟫ で強調
#   ・前後 ±N 文字の抜粋 excerpt を付与

from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
import io, re

import streamlit as st
import pandas as pd

# === 共通ライブラリ（lib/）からインポート ===
from lib.text_normalizer import (
    z2h_numhy,
    normalize_strict,
    HY,  # 各種ハイフン/長音 正規表現クラス
)

# =========================
# ページ設定 & メインUI
# =========================
st.set_page_config(page_title="📝 図表 抽出（テキスト貼り付け）", page_icon="📝", layout="wide")
st.title("📝 図表 抽出 — タイトル/参照（行頭・直後助詞・句点ルール）")

with st.sidebar:
    st.markdown("### オプション")
    ctx_chars  = st.slider("参照の前後コンテキスト文字数（excerpt 用）", 10, 300, 60, 5)
    show_debug = st.checkbox("内部情報（デバッグ）を表示", value=False)

st.markdown("貼り付け欄に本文テキストをそのまま入れてください。**抽出**を押すと、図表タイトルと本文中の参照をリスト化します。")

text_in = st.text_area("↓ ここに本文テキストを貼り付け", value="", height=280, placeholder="本文を貼り付けてください…")
run = st.button("▶ 抽出", type="primary", use_container_width=True)

if not text_in or not run:
    st.stop()

# =========================
# 抽出ロジック（テキスト版）
# =========================
DOT = r"[\.．・･]"         # 半角/全角ドット・中黒など
NUM_ZH = r"[0-9０-９]+"     # 半角/全角の数字
NUM_TOKEN = rf"""
(
    {NUM_ZH}                              # 先頭の数字
    (?:\s*(?:{DOT}|{HY})\s*{NUM_ZH})*     # . や - の連続
    |                                     # または
    [（(]\s*{NUM_ZH}\s*[）)]              # 括弧つき数字
)
"""
EXTRACT_RE = re.compile(
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})",
    re.X
)

def canon_num(num: str) -> str:
    """図表番号の正規化：全角→半角、（1）→1、全角ドット→.、空白/余分な記号調整。"""
    s = num.translate(str.maketrans("０１２３４５６７８９（）", "0123456789()"))
    s = re.sub(DOT, ".", s)
    s = re.sub(HY, "-", s)
    s = re.sub(r"[()（）]", "", s)
    s = re.sub(r"\s*\.\s*", ".", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", "", s)
    return s

def canon_label(kind: str, num: str) -> str:
    return f"{kind}{canon_num(num)}"

# 後方参照などを使える場合は regex を優先
try:
    import regex as re2  # pip install regex
except Exception:
    re2 = re

PARTICLES_RE = re2.compile(r"(?:に|を|は|へ|で|と|の|など|等|または|又は|および|及び|かつ)")

def extract_line_covering_match(full: str, start: int, end: int) -> Tuple[int, str, int, int]:
    """
    マッチ区間 [start, end) を必ず含む '行' を返す。
    行の定義：直前の改行（または先頭）～ 直後の改行（または末尾）
    戻り値: (行番号(概算), 行テキスト, 行開始オフセット, 行終了オフセット)
    """
    # 行開始は直前の \n の次
    line_start = full.rfind("\n", 0, start)
    line_start = 0 if line_start == -1 else line_start + 1
    # 行終了はマッチ終了以降で最初の \n
    line_end = full.find("\n", end)
    if line_end == -1:
        line_end = len(full)
    line_txt = full[line_start:line_end].rstrip("\r\n")

    # 概算の行番号（先頭から line_start までの \n の数 + 1）
    approx_lineno = full.count("\n", 0, line_start) + 1
    return approx_lineno, line_txt, line_start, line_end

def judge_hits_in_text(full_text: str, ctx: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    貼り付けテキスト全体から “図/表/図表 + 番号” の全ヒットを列挙し、
    以下のルールでタイトル/参照を分離：
      (1) 図表番号が行頭に無ければ「参照」
      (2) 図表番号直後に 助詞/接続語（上記）なら「参照」
      (3) 行内に句点「。」があれば「参照」
      (4) その他は「タイトル」→ 行末残部を見出しタイトルとして採取
    参照は前後 ctx 文字の文脈を付与（excerpt）。
    """
    captions: List[Dict[str, Any]] = []
    refs: List[Dict[str, Any]] = []

    full = full_text.replace("\r\n", "\n").replace("\r", "\n")

    for m in EXTRACT_RE.finditer(full):
        kind = m.group("kind")
        num  = m.group("num")
        raw  = m.group(0)

        # マッチを必ず含む“行”を取得（改行跨ぎでも行全体が拾える）
        lineno, line_txt, line_start, line_end = extract_line_covering_match(full, m.start(), m.end())

        # 行頭判定（行頭側が空白のみなら行頭扱い）
        is_line_head = (full[line_start:m.start()].strip() == "")

        # 行内の相対終端 & 直後テキスト
        rel_end = (m.start() - line_start) + len(raw)
        after_on_line = line_txt[rel_end:] if rel_end <= len(line_txt) else ""

        # 直後助詞チェック（空白スキップ許容）
        particle_follow = bool(re2.match(rf"\s*{PARTICLES_RE.pattern}", after_on_line))
        # 句点の有無
        has_period = ("。" in line_txt)

        is_reference = (not is_line_head) or particle_follow or has_period

        # 追加の見やすさ改善：
        #  ・行テキスト内でヒット箇所を ⟪…⟫ で強調（最初の1回だけ）
        #  ・前後 ±ctx の抜粋 excerpt を付与
        highlighted = line_txt.replace(raw, f"⟪{raw}⟫", 1)
        left  = max(0, m.start() - ctx)
        right = min(len(full), m.end() + ctx)
        excerpt = full[left:m.start()] + f"⟪{raw}⟫" + full[m.end():right]

        if is_reference:
            refs.append({
                "行番号": lineno,
                "参照テキスト": raw.strip(),
                "図表種類": kind,
                "図表番号": f"{kind}{z2h_numhy(num)}",
                "図表キー": canon_label(kind, num),
                "excerpt": excerpt,
                "hit": raw,
                "start": m.start(),
                "end": m.end(),
                "判定": "参照",
                "rule(理由)": (
                    "行頭でない→参照" if not is_line_head else
                    ("直後が助詞/接続語→参照" if particle_follow else "行に句点あり→参照")
                ),
                "行テキスト": line_txt,
                "行テキスト(強調)": highlighted,
            })
        else:
            # タイトル：ヒット直後の行の残りをタイトルとして採取
            title = re.sub(r"^[\s:：.\-．、・]+", "", after_on_line).strip()
            captions.append({
                "行番号": lineno,
                "図表種類": kind,
                "図表番号": f"{kind}{z2h_numhy(num)}",
                "図表キー": canon_label(kind, num),
                "見出しタイトル": title,
                "matched_line": line_txt,
                "matched_line(強調)": highlighted,
                "excerpt": excerpt,
                "start": m.start(),
                "end": m.end(),
                "判定": "タイトル",
                "rule(理由)": "その他→タイトル",
            })

    return captions, refs

# =========================
# 実行：タイトル/参照の抽出
# =========================
captions, refs = judge_hits_in_text(text_in, ctx=ctx_chars)

df_captions = pd.DataFrame(captions)
df_refs     = pd.DataFrame(refs)

# =========================
# 表示
# =========================
st.subheader("🖼️ 行単独の 図/表/図表 見出し（キャプション）")
st.dataframe(df_captions if not df_captions.empty else pd.DataFrame(), use_container_width=True)

st.subheader("🔗 本文中の 図/表/図表 参照（文脈つき）")
st.dataframe(df_refs if not df_refs.empty else pd.DataFrame(), use_container_width=True)

# =========================
# ダウンロード
# =========================
st.markdown("### ダウンロード")
for df, name in [
    (df_captions, "figure_table_captions_from_text.csv"),
    (df_refs,     "figure_table_references_from_text.csv"),
]:
    if not df.empty:
        buf = io.StringIO(); df.to_csv(buf, index=False)
        st.download_button(f"📥 {name}",
                           data=buf.getvalue().encode("utf-8-sig"),
                           file_name=name,
                           mime="text/csv",
                           use_container_width=True)

# =========================
# デバッグ
# =========================
if show_debug:
    st.divider()
    st.markdown("### 🧪 Debug")
    st.code(f"EXTRACT_RE = {EXTRACT_RE.pattern}")
    st.caption("判定ルール: 行頭でない/直後に助詞/行内『。』→参照、その他→タイトル。行抽出は“マッチを含む1行”を厳密取得。強調表示とexcerptを付与。")
