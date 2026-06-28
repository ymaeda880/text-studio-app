# -*- coding: utf-8 -*-
# text_studio_app/lib/wordtex/explanations/library_structure.py
# ============================================================
# wordTex 詳細説明：ライブラリー構成
# ============================================================

from __future__ import annotations


LIBRARY_STRUCTURE_TEXT = r"""

##### 1. 基本方針

wordTexは，処理を機能単位で分割します．

ページ側にはUIを置き，
解析，設定，Word生成，プレビューはライブラリーへ切り出します．

---

##### 2. ページ側

    text_studio_app/pages/200_wordtex.py

担当する処理は次のとおりです．

- ページ表示
- wordTexソース入力
- 解析ボタン
- Word作成ボタン
- Wordプレビュー
- Word保存

---

##### 3. wordTex本体

    text_studio_app/lib/wordtex/

主なファイルは次のとおりです．

- explanation.py
- blocks.py
- settings.py
- parser.py
- builder.py

---

##### 4. 説明文

説明文は次のフォルダに分割します．

    text_studio_app/lib/wordtex/explanations/

機能ごとに分けることで，
図番号だけ，section番号だけ，プレビューだけを安全に更新できます．

---

##### 5. Builder

Word生成は次のように分割します．

    text_studio_app/lib/wordtex/builders/
        paragraph_builder.py
        heading_builder.py

画像表は専用フォルダに置きます．

    text_studio_app/lib/wordtex/figuretable/
        constants.py
        parser.py
        builder.py

---

##### 6. 画像埋め込み

画像解決や画像サイズ計算は，
既存の画像埋込機能を再利用します．

    text_studio_app/lib/image_embed/

---

##### 7. プレビュー

Wordプレビューは common_lib の共通プレビューを使います．

    common_lib.preview.file_preview

WordをPDF化してから，
ページ送り・拡大縮小付きで表示します．

"""