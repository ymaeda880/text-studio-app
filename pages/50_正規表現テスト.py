# -*- coding: utf-8 -*-
# pages/50_正規表現テスト.py
# 任意のテキストから「図/表/図表 + 番号（例: 表 2.1-1）」だけを抽出して表示する簡易テスター

from __future__ import annotations
import re
import streamlit as st

st.set_page_config(page_title="🔎 正規表現テスト（図表番号抽出）", page_icon="🔎", layout="wide")
st.title("🔎 正規表現テスト：図/表/図表 + 番号 を抽出")

st.caption("例）入力：『表 2.1-1 選定した対象とする鳥類』 → 抽出：『表 2.1-1』")

# ===== 正規表現パーツ =====
DOT = r"[\.．・･]"  # 半角ドット・全角ドット・中黒など
HY  = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D\u30FC]"  # 各種ハイフン/長音
NUM_ZH = r"[0-9０-９]+"  # 半角/全角の数字

# 数字トークン（2.1-1 / ３．１０－２ / （3） などに対応）
NUM_TOKEN = rf"""
(
    {NUM_ZH}                              # 先頭の数字
    (?:\s*(?:{DOT}|{HY})\s*{NUM_ZH})*     # . や - で続く数字
    |                                     # または
    [（(]\s*{NUM_ZH}\s*[）)]              # 括弧つき数字
)
"""

# ★ 抽出用：テキスト中の「図/表/図表 + 番号」をそのまま取り出す
#    行途中でもOK（見出しか参照かは区別しないシンプル版）
EXTRACT_RE = re.compile(
    rf"(?P<kind>図表|図|表)\s*(?P<num>{NUM_TOKEN})",
    re.X
)

def canon_num(num: str) -> str:
    """番号表記の正規化（全角→半角、ドット/ハイフンの空白除去、括弧除去）"""
    s = num
    # 全角→半角（数字・括弧）
    s = s.translate(str.maketrans("０１２３４５６７８９（）", "0123456789()"))
    # ドット・ハイフン類を標準化
    s = re.sub(DOT, ".", s)
    s = re.sub(HY, "-", s)
    # 括弧の除去（（3）→3）
    s = re.sub(r"[()（）]", "", s)
    # 区切り前後の空白を詰める
    s = re.sub(r"\s*\.\s*", ".", s)
    s = re.sub(r"\s*-\s*", "-", s)
    # 残る空白も削除
    s = re.sub(r"\s+", "", s)
    return s

def canon_label(kind: str, num: str) -> str:
    return f"{kind}{canon_num(num)}"

# ===== UI =====
default_text = "表 2.1-1 選定した対象とする鳥類\n本文中の参照例：…を表 3.1-2 に示す。"
text = st.text_area("テキストを入力", value=default_text, height=180)

if st.button("抽出を実行", type="primary", use_container_width=True):
    matches = list(EXTRACT_RE.finditer(text))
    if not matches:
        st.warning("図/表/図表 + 番号 は見つかりませんでした。")
    else:
        st.success(f"抽出ヒット数: {len(matches)}")
        rows = []
        for m in matches:
            kind = m.group("kind")
            num  = m.group("num")
            raw  = m.group(0)  # そのままのヒット文字列（例: 「表 2.1-1」）
            rows.append({
                "抽出テキスト": raw.strip(),
                "種別": kind,
                "番号(生)": num.strip(),
                "図表番号(正規化表示)": f"{kind}{canon_num(num)}",
                "図表キー(内部一意化)": canon_label(kind, num),
                "start": m.start(),
                "end": m.end(),
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

st.markdown("---")
st.caption("注：このページは『見出しか参照か』の判定は行わず、テキスト内のヒットを素直に抽出する最小テスターです。見出し/参照の分離やコンテキスト抽出は 44_頁ラベル抽出_1頁1ラベル.py などで実装したロジックをご利用ください。")


# ===== タイトル/参照 判定の追加 =====
# ルール:
# (1) 図表番号が行頭に無ければ「参照」
# (2) 図表番号の直後に {に|を|は|へ|で|と|の|など|等|または|又は|および|及び|かつ} が続けば「参照」
# (3) 行内に句点「。」があれば「参照」
# (4) それ以外は「タイトル」

import pandas as pd
import regex as re2  # Pythonの're'でもOKですが、将来の拡張を見据えて'regex'を使用可

if 'rows' in locals() and rows:
    # 行スパン（開始/終了オフセット）を計算
    lines_keep = text.splitlines(keepends=True)  # 改行を保持
    line_spans = []  # [(lineno, start, end, content_without_newline)]
    pos = 0
    for i, seg in enumerate(lines_keep, 1):
        start = pos
        end   = pos + len(seg)
        line_spans.append((i, start, end, seg.rstrip("\r\n")))
        pos = end

    def locate_line(offset: int):
        """テキスト中のオフセットが属する行情報を返す"""
        for lineno, s, e, content in line_spans:
            if s <= offset < e:
                return lineno, s, e, content
        # 最終行終端に一致などの保険
        if line_spans:
            return line_spans[-1]
        return 1, 0, len(text), text

    # 直後の助詞/接続語にマッチ（空白は許容）
    PARTICLES_RE = re2.compile(r"(?:に|を|は|へ|で|と|の|など|等|または|又は|および|及び|かつ)")

    judged = []
    for m in EXTRACT_RE.finditer(text):
        kind = m.group("kind")
        num  = m.group("num")
        raw  = m.group(0)

        lineno, line_start, line_end, line_txt = locate_line(m.start())
        # 行頭にあるか（前方が空白のみなら行頭とみなす）
        is_line_head = (text[line_start:m.start()].strip() == "")

        # 行内の相対位置
        rel_start = m.start() - line_start
        rel_end   = rel_start + len(raw)
        after_on_line = line_txt[rel_end:] if rel_end <= len(line_txt) else ""

        # (2) 直後の助詞/接続語（空白をスキップして即マッチするか）
        particle_follow = bool(re2.match(rf"\s*{PARTICLES_RE.pattern}", after_on_line))

        # (3) 行内に句点「。」が含まれるか
        has_period = ("。" in line_txt)

        # 判定
        if (not is_line_head) or particle_follow or has_period:
            kind_judged = "参照"
        else:
            kind_judged = "タイトル"

        judged.append({
            "行番号": lineno,
             "判定": kind_judged,
            "行テキスト": line_txt,
            "抽出テキスト": raw.strip(),
            "種別": kind,
            "番号(生)": num.strip(),
            "図表番号(正規化表示)": f"{kind}{canon_num(num)}",
            "図表キー(内部一意化)": canon_label(kind, num),
            "rule(理由)": (
                "行頭でない→参照" if not is_line_head else
                ("直後が助詞/接続語→参照" if particle_follow else
                 ("行に句点あり→参照" if has_period else "その他→タイトル"))
            ),
            "start": m.start(),
            "end": m.end(),
        })

    st.markdown("### 🧭 タイトル/参照の判定結果")
    st.dataframe(pd.DataFrame(judged), use_container_width=True)


