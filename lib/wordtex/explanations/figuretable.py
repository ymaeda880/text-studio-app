# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/figuretable.py
# ============================================================
# wordTex 詳細説明：figureTable
# ============================================================

from __future__ import annotations


FIGURE_TABLE_TEXT = r"""

##### 1. figureTable

wordTexでは，複数画像をWord表として配置するために
figureTableを使用します．

基本形は次のとおりです．

    \begin{figureTable,
    title="現場写真",
    caption="工事現場全景",
    label="fig:site",
    row=2,
    bc="lightgreen"}

        \item{
        file="xxx.png",
        title="北側",
        desp="説明"
        }

    \end{figureTable}

---

##### 2. title

表全体のタイトルです．

現在はWord本文には出力していませんが，
将来的には目次や一覧へ利用します．

---

##### 3. caption

図番号と結合されるキャプションです．

例

    図3：工事現場全景

---

##### 4. label

図参照用のラベルです．

本文では

    図\ref{fig:site}

と書くと，

    図3

になります．

---

##### 5. row

画像を何列並べるか指定します．

    row=2

なら

□ □

になります．

    row=3

なら

□ □ □

になります．

---

##### 6. bc

タイトルセルの背景色です．

例

    bc="lightgreen"

将来的にはテーマ管理へ移行します．

---

##### 7. item

画像1枚を表します．

指定できる項目

- file
- title
- desp

画像はInBoxから取得します．

"""