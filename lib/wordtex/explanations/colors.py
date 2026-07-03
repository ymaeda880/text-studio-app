# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/colors.py
# ============================================================
# wordTex 詳細説明：色
# ============================================================

from __future__ import annotations


COLORS_TEXT = r"""

##### 1. 色

wordTexでは，色名を使って色を指定します．

色は共通定義として管理されており，
図，表，figureTable などの各機能から利用できます．

---

##### 2. 基本的な指定例

    color="red"

    bc="lightgreen"

    background="lightblue"

どの属性で色を指定できるかは，各ブロックの仕様に依存します．

---

##### 3. 共通色

現在，共通色として次の色が定義されています．

- black
- gray / grey
- red
- green
- blue
- cyan
- magenta
- yellow
- orange
- purple
- brown

---

##### 4. figureTable 用背景色

figureTable の背景色には，次の色が使えます．

- white
- lightgray / lightgrey
- gray / grey
- beige
- lightblue
- lightgreen
- lightyellow

figureTable では，bc または background で背景色を指定できます．

    bc="lightgreen"

    background="lightgreen"

指定しない場合は，lightgray が使われます．

---

##### 5. 注意

共通色と figureTable 用背景色は別に管理されています．

共通色は Word の文字色などで使うための RGBColor 定義です．
figureTable 用背景色は，セル背景用の16進数カラーとして管理されています．

"""