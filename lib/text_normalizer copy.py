# -*- coding: utf-8 -*-
# lib/text_normalizer.py
"""
テキスト正規化ユーティリティ（目次チェック系・図表抽出系など共通）

機能:
  - 全角→半角変換（数字・括弧・ピリオド）
  - 各種ハイフン/長音→'-' に統一
  - リーダー（……・…‧）除去
  - 空白の整理（strict / loose モード）
"""

import re

# =========================
# 定数
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D\u30FC]"   # 各種ハイフン・長音
LEADER_CHARS_CLASS = r"[\.．・･…‧｡]"
LEADERS_SPACED = rf"(?:\s*{LEADER_CHARS_CLASS}\s*){{3,}}"


# =========================
# 正規化関数
# =========================
def z2h_numhy(s: str) -> str:
    """
    全角数字/括弧/ピリオド類 → 半角、
    各種ハイフン/長音 → '-'
    """
    s = (s or "").replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９（）［］｛｝．｡", "0123456789()[]{}.."))
    return re.sub(HY, "-", s)


def normalize_strict(s: str) -> str:
    """
    行単位の正規化：
      - 全角→半角
      - リーダー（……など）削除
      - 空白圧縮
    """
    s = z2h_numhy(s)
    s = re.sub(rf"\s*{LEADERS_SPACED}\s*$", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def normalize_loose(s: str) -> str:
    """
    ゆるめの正規化：
      - 全角→半角
      - 空白削除
      - 終端リーダー軽除去
    """
    s = z2h_numhy(s)
    s = re.sub(rf"{LEADERS_SPACED}$", "", s)
    return re.sub(r"\s+", "", s)
