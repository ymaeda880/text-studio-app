# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/itemize.py
# ============================================================
# wordTex 詳細説明：箇条書き
# ============================================================

from __future__ import annotations


ITEMIZE_TEXT = r"""

##### 1. 箇条書き

wordTexでは，箇条書きを作成するために itemize を使用します．

---

##### 2. 基本形

    \begin{itemize}
    \item アイテム1
    \item アイテム2
    \item アイテム3
    \end{itemize}

---

##### 3. ラベル付き item

item には任意のラベルを付けられます．

    \begin{itemize}
    \item[※] 注意事項
    \item[補足] 補足説明
    \end{itemize}

---

##### 4. 複数行 item

item の本文は複数行にできます．

    \begin{itemize}
    \item これは1つ目の項目です。
    続きの説明をここに書けます。
    \item これは2つ目の項目です。
    \end{itemize}

---

##### 5. 入れ子

itemize は入れ子にできます．

    \begin{itemize}
    \item 親項目
        \begin{itemize}
        \item 子項目1
        \item 子項目2
        \end{itemize}
    \end{itemize}

---

##### 6. style

開始タグに style を指定できます．

    \begin{itemize, style="bullet"}
    \item アイテム1
    \end{itemize}

実際の表示形式は Word 生成側の実装に依存します．

---

##### 7. 注意

\end{itemize} がない場合は警告になります．

また，\item の前に入れ子 itemize がある場合も警告になります．

"""