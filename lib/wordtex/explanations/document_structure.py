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



"""