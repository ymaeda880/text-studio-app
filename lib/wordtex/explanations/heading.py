# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/heading.py
# ============================================================
# wordTex 詳細説明：見出し
# ============================================================

from __future__ import annotations


HEADING_TEXT = r"""

##### 1. 見出し

wordTexでは，section，subsection，subsubsection，paragraph を使って
Word文書の見出しを作成します．

---

##### 2. section

章レベルの見出しです．

    \section{はじめに}

label を付けることもできます．

    \section{はじめに,label="sec:intro"}

---

##### 3. subsection

節レベルの見出しです．

    \subsection{調査方法}

---

##### 4. subsubsection

小節レベルの見出しです．

    \subsubsection{調査対象}

---

##### 5. paragraph

段落見出しです．

    \paragraph{補足事項}

---

##### 6. 番号

section番号は自動で進みます．

例

    \section{第1章}
    \subsection{第1節}
    \subsection{第2節}
    \section{第2章}

出力例

    1 第1章
    1.1 第1節
    1.2 第2節
    2 第2章

---

##### 7. 見出し書式

set設定で，見出しの表示形式を変更できます．

    \set{section_title_format={num}　{title}}
    \set{subsection_title_format={num}　{title}}
    \set{subsubsection_title_format={num}　{title}}

{num} が番号，{title} が見出し本文です．

"""