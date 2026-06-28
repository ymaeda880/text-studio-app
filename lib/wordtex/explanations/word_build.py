# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/word_build.py
# ============================================================
# wordTex 詳細説明：Word生成
# ============================================================

from __future__ import annotations


WORD_BUILD_LOGIC_TEXT = r"""

##### 1. Builder方式

Parserが作成したBlockを
Builderが順番にWordへ出力します．

---

##### 2. 現在のBuilder

- paragraph
- heading
- figureTable

---

##### 3. Builder分割

Builderは種類ごとに分離しています．

paragraph_builder.py

heading_builder.py

figuretable/

---

##### 4. 2パス処理

1パス目

label収集

↓

2パス目

Word出力

---

##### 5. メリット

Builder追加だけで

新しいBlockへ対応できます．

"""