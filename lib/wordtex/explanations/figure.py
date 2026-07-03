# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/figure.py
# ============================================================
# wordTex 詳細説明：図
# ============================================================

from __future__ import annotations


FIGURE_TEXT = r"""

##### 1. 図

wordTexでは，画像を1枚配置するために figure を使用します．

複数画像を表形式で並べる場合は figureTable を使用します．

---

##### 2. 基本形

    \begin{figure,
    title="現場写真",
    caption="現場全景",
    label="fig:site",
    width="100%",
    numbering=true}

        \item{
        file="site.png",
        title="北側",
        desp="現場北側から撮影"
        }

        \note{
        撮影日は2026年6月29日。
        }

    \end{figure}

---

##### 3. figure の属性

figure の開始タグでは，次の属性を指定できます．

- title
- caption
- label
- width
- numbering

---

##### 4. title

図ブロック全体のタイトルです．

    title="現場写真"

---

##### 5. caption

図番号と結合されるキャプションです．

    caption="現場全景"

出力例

    図1：現場全景

caption を指定しない場合は，図キャプションを出力しません．

    \begin{figure,
    label="fig:site",
    width="100%"}

        \item{
        file="site.png"
        }

    \end{figure}

この場合，図番号は進まず，label も登録されません．

そのため，本文中で

    図\ref{fig:site}

としても参照できません．

図番号と参照を使いたい場合は，必ず caption を指定してください．

---

##### 6. label

本文中から図を参照するためのラベルです．

    label="fig:site"

本文では次のように参照できます．

    図\ref{fig:site}

---

##### 7. width

画像の横幅を指定します．

    width="100%"

指定しない場合は，既定値として 100% が使われます．

---

##### 8. numbering

図番号を付けるかどうかを指定します．

    numbering=true

既定値は true です．

図番号を付けない場合は，次のようにします．

    numbering=false

---

##### 9. item

figure の中では，\item{...} で画像を指定します．

    \item{
    file="site.png",
    title="北側",
    desp="現場北側から撮影"
    }

file は必須です．

---

##### 10. desp / desc

画像の説明文です．

    desp="説明"

または

    desc="説明"

のどちらも使用できます．

---

##### 11. note

図全体の補足説明です．

    \note{
    撮影日は2026年6月29日。
    }

---

---

##### 12. 画像ファイルの読み込み先

figure では，画像ファイルの読み込み先を `fig_path` で指定できます．

通常のフォルダから画像を読む場合は，次のように指定します．

    \set{fig_path="/Users/macmini2025/Documents/myDocument/wordTex/2019003/fig"}

この場合，figure の item で指定した file 名を，
fig_path の下にある画像ファイルとして読み込みます．

    \begin{figure,caption="現場全景",label="fig:site",width="100%"}
    \item{
        file="図1.jpg",
        title="北側",
        desp="現場北側から撮影"
        }
    \end{figure}

上の例では，次の画像を読み込みます．

    /Users/macmini2025/Documents/myDocument/wordTex/2019003/fig/図1.jpg

---

##### 13. Inbox から画像を読み込む

Inbox に保存されている画像を使う場合は，fig_path に `"inbox"` を指定します．

    \set{fig_path="inbox"}

また，fig_path を指定しない場合も，従来どおり Inbox から画像を探します．

    \begin{figure,caption="現場全景",label="fig:site",width="100%"}
    \item{
        file="図1.jpg",
        title="北側",
        desp="現場北側から撮影"
        }
    \end{figure}

この場合，Inbox 内から `図1.jpg` を検索して読み込みます．

---

##### 14. 注意

fig_path の指定では，引用符は半角の `"` を使ってください．

正しい例：

    \set{fig_path="/Users/macmini2025/Documents/wordTex/2019003/fig"}

誤った例：

    \set{fig_path=”/Users/macmini2025/Documents/myDocument/wordTex/2019003/fig”}

全角の `”` を使うと，パスとして正しく認識されない場合があります．

"""