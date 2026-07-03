# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/reference.py
# ============================================================
# wordTex 詳細説明：参照
# ============================================================

from __future__ import annotations


REFERENCE_TEXT = r"""

##### 1. 参照

wordTexでは，見出し，図，表などに label を付け，
本文から \ref を使って参照できます．

参照方法は TeX と同じ考え方です．

---

##### 2. label

参照したい対象に label を指定します．

section の例

    \section{はじめに,label="sec:intro"}

figure の例

    \begin{figure,
    label="fig:site"}

figureTable の例

    \begin{figureTable,
    label="fig:photo"}

table の例

    \begin{table,
    label="tbl:survey"}

---

##### 3. ref

本文中では，\ref を使って参照します．

section

    \ref{sec:intro}

figure

    図\ref{fig:site}

figureTable

    図\ref{fig:photo}

table

    表\ref{tbl:survey}

---

##### 4. 見出しの参照

例えば，

    第\ref{sec:intro}章

と書くと，

    第1章

のように置き換えられます．

---

##### 5. 図の参照

例えば，

    図\ref{fig:site}

と書くと，

    図3

のように置き換えられます．

figure と figureTable は，
どちらも図番号として参照できます．

---

##### 6. 表の参照

例えば，

    表\ref{tbl:survey}

と書くと，

    表2

のように置き換えられます．

---

##### 7. TeX互換

参照方法は TeX と同様に，

    \label
    \ref

を採用しています．

figure 専用の

    \figref

や

table 専用の

    \tabref

は採用していません．

---

##### 8. 前方参照

本文で先に参照を書き，
後ろで label を書くこともできます．

例えば，

    図\ref{fig:site}

を本文で書き，
後から

    \begin{figure,
    label="fig:site"}

を記述しても参照できます．

wordTex では，最初に label を収集してから
本文を処理するため，前方参照にも対応しています．

"""