# -*- coding:utf-8 -*-
# text_studio_app/lib/wordtex/explanations/figure_number.py
# ============================================================
# wordTex 詳細説明：図番号
# ============================================================

from __future__ import annotations


FIGURE_NUMBER_TEXT = r"""

##### 1. 図番号

図番号は自動管理されます．

例

    図1
    図2
    図3

---

##### 2. 階層番号

例えば

    \set{fig_numbers=3,1}

では

    図3-1

から開始できます．

---

##### 3. 表示形式

表示形式は

    \set{fig_format="{1}-{2}"}

や

    \set{fig_format="{1}({2})"}

など自由に変更できます．

---

##### 4. 増加階層

    \set{fig_increment_level=2}

なら

    図3-1
    図3-2
    図3-3

になります．

---

##### 5. 将来対応

さらに

    図1-1-1

や

    図1-1(1)

など任意階層へ対応する予定です．

"""