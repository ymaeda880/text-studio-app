# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/table.py
# ============================================================
# wordTex 詳細説明：表
# ============================================================

from __future__ import annotations


TABLE_TEXT = r"""

##### 1. 表

wordTexでは，文字情報を整理して表示するために table を使用します．

figureTable は画像を並べるための表ですが，
table は文字データを扱うための表です．

table では，通常の文字表だけでなく，
セル内に画像を入れることもできます．

---

##### 2. 基本形

    \begin{table,
    title="調査概要",
    caption="調査対象一覧",
    label="tbl:survey",
    style="simple",
    header_rows=1,
    header_cols=0,
    width="100%",
    compact="none",
    fontsize="normal",
    col_ratio=[1,2]}

    項目&内容\\
    場所&横浜市\\
    対象&現場写真

    \note{
    表に関する補足説明
    }

    \end{table}

---

##### 3. title

表全体のタイトルです．

    title="調査概要"

---

##### 4. caption

表番号と結合されるキャプションです．

    caption="調査対象一覧"

出力例：

    表1：調査対象一覧

caption を指定しない場合は，表キャプションを出力しません．

    \begin{table,
    label="tbl:survey",
    style="simple"}

この場合，表番号は進まず，label も登録されません．

そのため，本文中で

    表\ref{tbl:survey}

としても参照できません．

表番号と参照を使いたい場合は，必ず caption を指定してください．

---

##### 5. label

本文中から表を参照するためのラベルです．

    label="tbl:survey"

本文では次のように参照できます．

    表\ref{tbl:survey}

---

##### 6. style

表の表示スタイルを指定します．

現在使用できるスタイルは次のとおりです．

    style="simple"
    style="zebra"
    style="horizontal"
    style="box"
    style="dark"

指定しない場合は，

    style="simple"

が使用されます．

---

##### 7. header_rows

先頭から何行をヘッダー行として扱うかを指定します．

    header_rows=1

指定しない場合は，既定値として 1 が使われます．

ヘッダーがない表では，

    header_rows=0

と指定します．

---

##### 8. header_cols

左から何列をヘッダー列として扱うかを指定します．

    header_cols=0

左端の列を行見出しとして扱う場合は，

    header_cols=1

と指定します．

---

##### 9. width

表全体の横幅を指定します．

    width="100%"
    width="120%"
    width="18cm"

指定しない場合は，

    width="100%"

が使用されます．

---

##### 10. compact

表全体の行間を調整し，コンパクトに表示します．

指定できる値は次の4種類です．

    compact="none"
    compact="normal"
    compact="tight"
    compact="verytight"

指定しない場合は，

    compact="none"

として扱われます．

---

##### 11. fontsize

表の中の文字サイズを指定します．
本文の文字サイズには影響しません．

指定できる値は次の3種類です．

    fontsize="normal"
    fontsize="small"
    fontsize="verysmall"

指定しない場合は，

    fontsize="normal"

として扱われます．

---

##### 12. col_ratio

列幅の比率を指定します．

    col_ratio=[1,2,1]

この場合，列幅は

    1 : 2 : 1

の比率になります．

---

##### 13. col_widths

各列の幅を cm 単位で直接指定します．

    col_widths=[3,8,5]

この場合，

- 1列目：3cm
- 2列目：8cm
- 3列目：5cm

になります．

col_widths を指定した場合は，col_ratio より優先されます．

---

##### 14. 表データの書き方

列区切りには `&` を使えます．

    項目&内容

行区切りには LaTeX風の `\\` を使えます．

    項目&内容\\
    場所&横浜市\\
    対象&現場写真

Excelからコピーした Tab 区切り・改行区切りの表も利用できます．

---

##### 15. <同上>・<同左>・<改行>

表データでは，入力を簡単にするために，次の特殊記号を利用できます．

---

###### <同上>

上のセルと同じ内容として扱います．

    品目&分類&数量\\
    りんご&青果&12\\
    <同上>&<同上>&8

---

###### <同左>

左のセルと同じ内容として扱います．

    地域&担当1&担当2\\
    横浜&前田&<同左>

---

###### <改行>

1つのセル内で改行します．

    項目&内容\\
    所在地&横浜市<改行>港北区

Word上では，1つのセルの中で次のように表示されます．

    横浜市
    港北区

    
---

##### 16. セル罫線の制御

表全体の罫線は，table の `border` で指定できます．

既定値は，

    border=true

です．

罫線を表示しない表にする場合は，

    \begin{table,border=false}

のように指定します．

この場合，表全体の罫線は描かれません．

---

セルごとに罫線を制御する場合は，セルの先頭に
`<border:...>` を指定します．

指定できる位置は次の4種類です．

    top
    bottom
    left
    right

指定できる値は次のとおりです．

    none
    true

`none` は罫線を消します．

    <border:top=none>値

`true` は罫線を描きます．

    <border:top=true>値

複数指定する場合は，カンマで区切ります．

    <border:top=none,bottom=true>値

---

`border=false` の表でも，セル側の指定が優先されます．

例：

    \begin{table,border=false}
    項目&値\\
    <border:top=true>上線あり&100\\
    <border:bottom=true>下線あり&200
    \end{table}

この場合，表全体の罫線は描かれませんが，
指定したセルの罫線だけが描かれます．

---

画像セルにも指定できます．

    <border:top=true><図1.png>

    <border:left=none><図2.png,width=3cm>

例：

    項目&写真\\
    地点A&<border:top=true><図1.png>\\
    地点B&<border:left=none>調査中

罫線は隣接セルと共有されるため，

    top

を指定すると対象セルの上罫線だけでなく，
直上セルの下罫線にも同じ指定を反映します．

同様に，

    bottom → 直下セルの top に反映
    left   → 左隣セルの right に反映
    right  → 右隣セルの left に反映

として処理されます．

---

##### 17. 表セル内の画像

table では，セルの中に画像を入れることができます．

セル内に画像を入れる場合は，画像ファイル名を `<...>` で囲みます．

    <図1.png>

例えば，次のように書きます．

    項目&写真\\
    現場全景&<図1.png>

この場合，2列目のセルに `図1.png` が配置されます．

---

##### 18. 表セル画像の指定形式

表セル画像は，次の形式で指定できます．

    <図1.png>

画像の横幅を指定する場合は，`width` を使います．

    <図1.png,width=2.5cm>

画像の配置を指定する場合は，`align` を使います．

    <図1.png,align=center>

横幅と配置を同時に指定することもできます．

    <図1.png,width=2.5cm,align=center>

---

##### 19. 表セル画像で使用できる拡張子

表セル画像として使用できる拡張子は次のとおりです．

    .jpg
    .jpeg
    .png
    .gif
    .bmp
    .tif
    .tiff
    .webp

次の形式は，表セル画像としては認識されません．

    .svg
    .pdf
    .eps

---

##### 20. table_fig_path

表セル内の画像は，figure 用の `fig_path` ではなく，
table 専用の `table_fig_path` から読み込みます．

通常のフォルダから画像を読む場合は，次のように指定します．

    \set{table_fig_path="/Users/macmini2025/Documents/myDocument/wordTex/2019003/fig"}

その後，表セルではファイル名だけを書きます．

    項目&写真\\
    現場全景&<図1.png>

この場合，次の画像を読み込みます．

    /Users/macmini2025/Documents/myDocument/wordTex/2019003/fig/図1.png

---

##### 21. Inbox から表セル画像を読み込む

Inbox に保存されている画像を使う場合は，
`table_fig_path` に `"inbox"` を指定します．

    \set{table_fig_path="inbox"}

    \begin{table,caption="現場写真",label="tab:photo"}
    項目&写真\\
    現場全景&<図1.png>
    \end{table}

この場合，Inbox 内から `図1.png` を検索して，
該当セルに画像を配置します．

---

##### 22. 表セル画像の width

表セル画像の横幅は，`width` で指定できます．

    <図1.png,width=2.5cm>

単位は cm です．

`width` を省略した場合は，列幅に合わせて自動的に配置されます．

---

##### 23. 表セル画像の align

表セル画像の配置は，`align` で指定できます．

使用できる値は次の3種類です．

    align=left
    align=center
    align=right

省略した場合は，

    align=center

として扱われます．

---

##### 24. 表セル画像の実践例

写真台帳のような表は，次のように書けます．

    \set{table_fig_path="/Users/macmini2025/Documents/myDocument/wordTex/2019003/fig"}

    \begin{table,
    caption="現場写真一覧",
    label="tab:photos",
    style="simple",
    header_rows=1,
    col_widths=[4,8],
    compact="tight"}

    項目&写真\\
    現場全景&<図1.png,width=7cm,align=center>\\
    北側状況&<図2.jpg,width=7cm,align=center>\\
    南側状況&<図3.webp,width=7cm,align=center>

    \end{table}

---

##### 25. 表セル画像が表示されない場合

画像が表示されない場合は，次を確認してください．

- `table_fig_path` を指定しているか
- `table_fig_path` のフォルダが正しいか
- `table_fig_path="inbox"` の場合，Inbox に画像があるか
- ファイル名が一致しているか
- 拡張子を書いているか
- 使用できる拡張子か
- `<図1.png>` のようにセル全体が画像指定だけになっているか

次のように拡張子がない場合は画像として認識されません．

    <図1>

正しくは次のように書きます．

    <図1.png>

---

##### 26. GIF画像について

`.gif` は表セル画像として指定できます．

ただし，Word には通常の画像として貼り付けられるため，
アニメーションとして動くことは想定していません．

---

##### 27. note

表全体の補足説明です．

    \note{
    表に関する補足説明
    }

note は Word に出力されます．

---

##### 28. <memo>

`<memo>` は，その行以降を無視するための印です．

`<memo>` より下に書いた内容は，wordTex の本文として処理されません．
そのため，Word には出力されません．

例：

    <memo>
    この下は作業メモ。
    この表は後で差し替える。
    この文章は Word に出さない。

注意点として，`<memo>` を書くと，その下はすべて無視されます．

Word に出したい内容は，必ず `<memo>` より上に書いてください．

---

##### 29. note と memo の違い

`note` は，読者に見せる補足説明です．
Word に出力されます．

    \note{
    表中の数値は概数である。
    }

`memo` は，作業者用のメモです．
`<memo>` 以下は無視され，Word には出力されません．

    <memo>
    この表は後で差し替える。

---

##### 30. Excelファイルから表を読み込む

table では，Excelファイルを指定して表を読み込むことができます．

まず，Excelファイルを置いているフォルダを設定します．

    \set{table_path="/Users/macmini2025/Documents/myDocument/wordTex/2019003"}

その後，table の src に

    src=["Excelファイル名","シート名"]

を指定します．

    \begin{table,
    caption="調査地域の土地利用状況",
    label="tab:landuse",
    style="simple",
    col_ratio=[2,1,1,1,1,1],
    compact="verytight",
    fontsize="verysmall",
    width="12cm",
    src=["2019003.xlsx","Sheet2"]}
    \end{table}

---

##### 31. Inbox内のExcelファイルを読み込む

Inbox に保存されている Excel ファイルを使う場合は，
table_path に `"inbox"` を指定します．

    \set{table_path="inbox"}

    \begin{table,
    caption="調査地域の土地利用状況",
    src=["2019003.xlsx","Sheet2"]}
    \end{table}

この場合，Inbox 内から 2019003.xlsx を探し，
指定したシートを読み込みます．

---

##### 32. Excel内の <note>

Excelシートの A列に

    <note>

と書いた行がある場合，その行より下は表本体ではなく，
table の note として扱われます．

Excel側の例：

    場所    総面積(ha)    森林(ha)
    茨城県常総市    12,364    602
    茨城県坂東市    12,303    1,174
    <note>
    参考：農林水産省HPより

この場合，

- <note> より上：表本体
- <note> 行そのもの：出力しない
- <note> より下：note として出力

になります．

---

##### 33. Excel内の <memo>

Excelシート内で `<memo>` を使う場合も，
`<memo>` 以下は無視対象です．

Excel側の例：

    場所    総面積(ha)    森林(ha)
    茨城県常総市    12,364    602
    茨城県坂東市    12,303    1,174
    <memo>
    この下は確認用メモ。
    この行は表にも note にも出さない。

この場合，

- <memo> より上：処理対象
- <memo> 行そのもの：出力しない
- <memo> より下：無視する

になります．

`<note>` と `<memo>` の違いは次のとおりです．

    <note> 以下 → note として Word に出す
    <memo> 以下 → 無視して Word に出さない

---

##### 34. 注意

表データが空の場合は警告になります．

また，\end{table} がない場合も警告になります．

col_ratio，col_widths を指定する場合は，表の列数と数を合わせてください．

`<border:...>` を使用する場合は，セルの先頭に記述してください．
セル内の途中に書いた場合は，罫線指定として認識されません．

`<memo>` は，その下をすべて無視します．
Word に出したい内容は，必ず `<memo>` より上に書いてください．

"""
