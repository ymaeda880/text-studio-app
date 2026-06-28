# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/set_settings.py
# ============================================================
# wordTex 詳細説明：set設定
# ============================================================

from __future__ import annotations


SET_LOGIC_TEXT = r"""

##### 1. \set{...} の役割

wordTexでは，全体設定を

    \set{キー=値}

で指定します．

設定は，その位置以降に現れるブロックへ適用されます．

---

##### 2. 現在実装済みの設定

図番号

    \set{fig_caption="図"}
    \set{fig_caption_sep="："}
    \set{fig_numbers=1}
    \set{fig_format="{1}"}
    \set{fig_increment_level=1}

section表示

    \set{section_title_format="第{num}章 {title}"}

subsection表示

    \set{subsection_title_format="{num}節 {title}"}

subsubsection表示

    \set{subsubsection_title_format="{num} {title}"}

---

##### 3. 設定の有効範囲

設定は以降のブロックへ適用されます．

例えば，

    \set{fig_numbers=10}

とすると，

その次の図は図10になります．

---

##### 4. 途中変更

文書途中でも自由に変更できます．

    図1

    図2

    \set{fig_numbers=20}

    図20

    図21

このような使い方を想定しています．

---

##### 5. 今後追加予定

将来的には次の設定も追加予定です．

- 表番号
- 数式番号
- 目次
- ページ番号
- 用紙サイズ
- 余白
- フォント
- 行間
- 段落設定
- キャプション位置
- テーマ

"""