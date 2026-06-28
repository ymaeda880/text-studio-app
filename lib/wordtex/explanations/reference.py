# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/reference.py
# ============================================================
# wordTex 詳細説明：参照
# ============================================================

from __future__ import annotations


REFERENCE_TEXT = r"""

##### 1. label

sectionやfigureTableには
label属性を指定できます．

例

    \section{はじめに,label="sec:intro"}

    \begin{figureTable,
    label="fig:site"}

---

##### 2. ref

本文では

    \ref{sec:intro}

や

    \ref{fig:site}

を書けます．

---

##### 3. section参照

例えば

    第\ref{sec:intro}章

↓

    第1章

になります．

---

##### 4. 図参照

例えば

    図\ref{fig:site}

↓

    図3

になります．

---

##### 5. TeX互換

参照はTeXと同様に

    \label
    \ref

を採用しています．

figure専用の

    \figref

は採用しません．

---

##### 6. 前方参照

本文で先に参照を書き，
後ろでlabelを書くこともできます．

wordTexでは1パス目でlabelだけ登録するため，
前方参照にも対応しています．

"""