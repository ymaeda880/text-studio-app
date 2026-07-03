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

##### 2. 基本形

    \set{fig_caption=図}
    \set{fig_caption_sep=：}
    \set{fig_numbers=1}
    \set{fig_format={1}}

値は，必要に応じて引用符で囲むこともできます．

    \set{fig_caption="図"}
    \set{fig_format="{1}-{2}"}

---

##### 3. 図番号の設定

図番号に関する設定です．

    \set{fig_caption=図}

図番号の前に付く文字を指定します．

    図1

---

    \set{fig_caption_sep=：}

図番号とキャプションの間の区切り文字を指定します．

    図1：現場全景

---

    \set{fig_numbers=3,1}

次に出力する図番号を指定します．

    図3-1

---

    \set{fig_format={1}-{2}}

図番号の表示形式を指定します．

    図3-1

別の例です．

    \set{fig_format={1}({2})}

    図3(1)

---

##### 4. 図番号の増加

図を1つ出力した後に，どの階層の番号を増やすかを指定します．

    \set{fig_increment_level=1}

第1階層を増やします．

    図1
    図2
    図3

---

    \set{fig_increment_level=2}

第2階層を増やします．

    図3-1
    図3-2
    図3-3

---

##### 5. 下位番号のリセット

上位番号が進んだときに，下位番号をリセットするかを指定します．

    \set{fig_reset_lower=true}

通常は true のままで使います．

---

##### 6. 図キャプション位置

図キャプションを上に出すか，下に出すかを指定します．

    \set{fig_caption_position=bottom}

指定できる値は次の2つです．

- top
- bottom


---

##### 7. 表番号の設定

表番号も図番号と同様に設定できます．

---

    \set{table_caption=表}

表番号の前に付く文字を指定します．

    表1

---

    \set{table_caption_sep=：}

表番号とキャプションの間の区切り文字を指定します．

    表1：調査対象一覧

---

    \set{table_numbers=5}

次に出力する表番号を指定します．

    表5

---

    \set{table_format={1}}

表番号の表示形式を指定します．

例えば，

    \set{table_format=({1})}

とすると，

    表(1)

のように表示されます．

---

    \set{table_caption_position=bottom}

表キャプションを表の上または下に表示します．

指定できる値は次の2つです．

- top
- bottom

---

##### 8. 見出し書式

section，subsection，subsubsection の表示形式を指定できます．

    \set{section_title_format=第{num}章 {title}}
    \set{subsection_title_format={num} {title}}
    \set{subsubsection_title_format={num} {title}}

{num} が番号，{title} が見出し本文です．

---

##### 9. 設定の有効範囲

設定は，以降のブロックへ適用されます．

例えば，

    \set{fig_numbers=10}

と書くと，その次の図は図10になります．

文書途中で変更することもできます．

    図1

    図2

    \set{fig_numbers=20}

    図20

    図21

---
##### 10. フォント設定

文書全体のフォントセットと本文文字サイズを指定できます．

    \set{font="report",size=11}

font はフォントセット名です．

現在用意されているフォントセットは次のとおりです．

- report
- biz
- gothic
- mincho

例えば，

    \set{font="report",size=11}

とすると，

- 本文：游明朝 11pt
- 見出し：游ゴシック
- コードなど：Consolas

で出力されます．

size は本文の基本文字サイズ（pt）です．

設定は，以降に出力される本文・見出し・表などへ適用されます．

文書途中で変更することもできます．

    \set{font="report",size=11}

    この部分は11pt

    \set{size=14}

    この部分は14pt

---

##### 11. 未対応の設定

現在サポートされていない `\set{...}` を指定すると，警告が出力されます．

---

##### 12. 今後追加予定

将来的には次の設定も追加対象です．

- 数式番号
- 目次
- ページ番号
- 用紙サイズ
- 余白
- 行間
- 段落設定
- テーマ

"""