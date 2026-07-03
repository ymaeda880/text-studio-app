# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/figuretable.py
# ============================================================
# wordTex 詳細説明：figureTable
# ============================================================

from __future__ import annotations


FIGURE_TABLE_TEXT = r"""

##### 1. figureTable

wordTexでは，InBoxに保存した複数画像を，
Wordの表セルに配置するために figureTable を使用します．

figure が画像1枚用であるのに対して，
figureTable は複数画像を一覧表のように並べるためのブロックです．

---

##### 2. 基本形

    \begin{figureTable,
    title="現場写真",
    caption="工事現場全景",
    label="fig:site",
    row=2,
    width="100%",
    col_ratio="1,1",
    bc="lightgreen",
    numbering=true}

        \item{
        file="north.png",
        title="北側",
        desp="北側から撮影"
        }

        \item{
        file="south.png",
        title="南側",
        desc="南側から撮影"
        }

    \end{figureTable}

---

##### 3. 画像の取得元

figureTable の画像は，`fig_table_path` で読み込み先を指定できます．

通常のフォルダから画像を読む場合は，次のように指定します．

    \set{fig_table_path="/Users/macmini2025/Documents/myDocument/wordTex/2019003/fig"}

この場合，item の file で指定した画像名を，
fig_table_path の下にある画像ファイルとして読み込みます．

    file="north.png"

上の例では，次の画像を読み込みます．

    /Users/macmini2025/Documents/myDocument/wordTex/2019003/fig/north.png

Inbox に保存されている画像を使う場合は，次のように指定します．

    \set{fig_table_path="inbox"}

また，fig_table_path を指定しない場合も，従来どおり Inbox から画像を探します．

---

##### 3-1. 注意：引用符

fig_table_path の指定では，引用符は半角の `"` を使ってください．

正しい例：

    \set{fig_table_path="/Users/macmini2025/Documents/myDocument/wordTex/2019003/fig"}

誤った例：

    \set{fig_table_path=”/Users/macmini2025/Documents/myDocument/wordTex/2019003/fig”}

全角の `”` を使うと，パスとして正しく認識されない場合があります．

---

##### 4. title

図表ブロック全体のタイトルです．

    title="現場写真"

---

##### 5. caption

図番号と結合されるキャプションです．

    caption="工事現場全景"

出力例

    図1：工事現場全景

---

##### 6. label

本文中から参照するためのラベルです．

    label="fig:site"

本文では次のように参照できます．

    図\ref{fig:site}

---

##### 7. row

1行に配置する画像数を指定します．

    row=2

指定できる範囲は 1 から 4 です．  
指定しない場合は，既定値として 2 が使われます．

---

##### 8. width

figureTable 全体の横幅を指定します．

    width="100%"

指定しない場合は，既定値として 100% が使われます．

---

##### 9. col_ratio

列幅の比率を指定します．

    col_ratio="1,1"

---

##### 10. bc / background

タイトルセルなどの背景色を指定します．

    bc="lightgreen"

または

    background="lightgreen"

を使用できます．

使用できる背景色

- white
- lightgray / lightgrey
- gray / grey
- beige
- lightblue
- lightgreen
- lightyellow

指定しない場合は，lightgray が使われます．

---

##### 11. numbering

図番号を付けるかどうかを指定します．

    numbering=true

既定値は true です．

図番号を付けない場合は，

    numbering=false

と指定します．

---

##### 12. item

画像1枚を表します．

    \item{
    file="north.png",
    title="北側",
    desp="北側から撮影"
    }

指定できる項目は次のとおりです．

- file
- title
- desp
- desc

file は必須です．  
file には，読み込み先にある画像名を指定します．
読み込み先は fig_table_path で指定します．
fig_table_path が未指定または "inbox" の場合は，Inbox から画像を探します．

---

##### 13. desp / desc

画像の説明文です．

    desp="説明"

または

    desc="説明"

のどちらも使用できます．

---

##### 14. 注意

figureTable 内に有効な item が1つもない場合は警告になります．

また，\end{figureTable} がない場合も警告になります．

"""