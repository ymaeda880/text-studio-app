# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/section_number.py
# ============================================================
# wordTex 詳細説明：section番号
# ============================================================

from __future__ import annotations


SECTION_NUMBER_TEXT = r"""

##### 1. section番号

section番号は自動管理されます．

    \section{}

を記述すると，

1

2

3

...

と自動採番されます．

---

##### 2. subsection

subsectionは親番号を引き継ぎます．

例

    2
      ↓
    2.1
    2.2
    2.3

---

##### 3. subsubsection

さらに階層を追加できます．

例

    2.3
       ↓
    2.3.1
    2.3.2

---

##### 4. 見出し表示形式

表示形式は自由に変更できます．

例

    第{num}章 {title}

↓

    第3章 現場写真

また，

    {num}. {title}

↓

    3. 現場写真

なども指定できます．

---

##### 5. label

sectionでは

    \section{現場写真,label="sec:site"}

のようにlabelを指定できます．

本文では

    第\ref{sec:site}章

と書くと，

    第2章

へ自動変換されます．

"""