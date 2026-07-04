# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/document_structure.py
# ============================================================
# wordTex 詳細説明：文書構成
# ============================================================

from __future__ import annotations


DOCUMENT_STRUCTURE_TEXT = r"""

##### 1. 文書構成

wordTexでは，Word文書全体の構成を指定するために，
タイトル，著者，日付，目次，改ページを使用します．

---

##### 2. タイトル

文書タイトルは次のように指定します．

    \title{調査報告書}

複数行にも対応しています．

    \title{
    令和8年度
    調査報告書
    }

---

##### 3. 著者

作成者名や会社名は次のように指定します．

    \author{株式会社〇〇}

---

##### 4. 日付

日付は次のように指定します．

    \date{2026年6月29日}

---

##### 5. 目次

目次を入れる位置に次の命令を書きます．

    \tableofcontents

目次は，section，subsection，subsubsection などの
見出し情報をもとに作成します．

---

##### 6. 改ページ

任意の位置で改ページする場合は，次の命令を使います．

    \newpage

例

    \title{調査報告書}
    \author{株式会社〇〇}
    \date{2026年6月29日}

    \newpage
    \tableofcontents
    \newpage

    \section{はじめに}


    ---

##### 7. 縦方向の空き（vskip）

本文中で任意の高さの空きを入れるには，

    \vskip{...}

を使用します．

例

    \vskip{1line}

1行分の空きを入れます．

    \vskip{0.5line}

半行分の空きを入れます．

    \vskip{2line}

2行分の空きを入れます．

長さを直接指定することもできます．

    \vskip{12pt}
    \vskip{5mm}
    \vskip{1cm}

利用できる単位は，

    line
    pt
    mm
    cm
    in

です．

---

##### 8. 字下げを行わない（noindent）

通常の本文は，段落の先頭を字下げして表示します．

字下げを行いたくない段落の直前に，

    \noindent

を指定します．

例

    \noindent
    各事業のデータの最終更新日時は以下のとおりである。

\vskip と組み合わせることもできます．

例

    \vskip{1line}
    \noindent
    各事業のデータの最終更新日時は以下のとおりである。

\noindent は直後の段落だけに適用されます．

"""