# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/explanation.py
# ============================================================
# SlideTexスライド作成ページ 説明UI
#
# 機能：
# - SlideTexファイルからPowerPointを作成する流れを説明する
# - SlideTexの基本構文を説明する
# - テーマ，ページ種別，スタイルの役割を説明する
# - 現在の制限と注意事項を表示する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from typing import Any

import streamlit as st

from common_lib.ui.help_expander import render_themed_help_expander
from common_lib.ui.intro_panel import (
    render_info_card_bullets_compact_custom,
    render_info_card_compact,
)
from common_lib.ui.tab_style import apply_tab_css

# ============================================================
# ページ上部説明UI
# ============================================================
def render_slide_creation_page_intro() -> None:

    # --------------------------------------------------------
    # AI利用
    # --------------------------------------------------------
    render_info_card_compact(
        body_html="""
🟢 このページでは，<b>AIを使用しません．</b>
SlideTexファイルに記述された内容を読み込み，
ローカル処理でPowerPointファイルを作成します．
""",
    )

    # --------------------------------------------------------
    # ページ概要
    # --------------------------------------------------------
    render_info_card_compact(
        body_html="""
このページでは，PowerPoint作成用のテキストファイル
「SlideTex（.stex）」をドラッグ＆ドロップして読み込みます．
読み込んだ内容から，テーマ，ページ種別，スタイル，
タイトル，本文などを解析し，PowerPointファイルを作成します．
""",
    )

    # --------------------------------------------------------
    # 使い方
    # --------------------------------------------------------
    render_info_card_bullets_compact_custom(
        title="使い方",
        items=[
            (
                "①",
                "<b>SlideTex形式で記述した.stexファイルを用意します．</b>",
            ),
            (
                "②",
                "<b>.stexファイルを画面へドラッグ＆ドロップします．</b>",
            ),
            (
                "③",
                "<b>解析結果とスライド構成を確認します．</b>",
            ),
            (
                "④",
                "<b>「PowerPointを作成」を押します．</b>",
            ),
            (
                "⑤",
                "<b>作成されたPowerPointファイルをダウンロードします．</b>",
            ),
        ],
    )

    st.markdown(
        "<div style='height:16px'></div>",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # 注意事項
    # --------------------------------------------------------
    render_info_card_compact(
        title="お願い",
        body_html="""
　.stexファイルはUTF-8で保存してください．
構文に誤りがある場合は，PowerPointを作成できません．
画面に表示された構文エラーを確認し，
.stexファイルを修正してください．<br>
　文字数や行数が多い場合は，PowerPoint上で文字が枠内に
収まらないことがあります．作成後はPowerPointを開き，
文字サイズ，改行位置，配置などを確認してください．
""",
    )

    st.markdown(
        "<div style='height:16px'></div>",
        unsafe_allow_html=True,
    )


# ============================================================
# public API：詳細説明 expander
# ============================================================
def render_slide_creation_logic_expander(
    *,
    theme: dict[str, Any] | None = None,
    banner_key: str = "purple_light",
) -> None:
    render_themed_help_expander(
        expander_key=HELP_EXPANDER_KEY,
        expander_title=HELP_EXPANDER_TITLE,
        tabs=HELP_TABS,
        theme=theme,
        banner_key=banner_key,
        expanded=False,
         before_tabs=lambda: apply_tab_css(
            columns=5,
        ),
    )


# ============================================================
# expander設定
# ============================================================
HELP_EXPANDER_KEY = "slide_creation_help_expander"
HELP_EXPANDER_TITLE = "📌 詳細説明（クリックで展開）"


# ============================================================
# 詳細説明：概要
# ============================================================
OVERVIEW_TEXT = r"""

##### このページでできること

- `.stex`ファイルのドラッグ＆ドロップ
- SlideTex構文の解析
- 構文エラーと警告の確認
- スライド構成の確認
- PowerPointファイルの作成
- テーマ共通背景画像の自動適用
- PowerPointファイルのダウンロード

SlideTexは，PowerPoint作成専用の独自テキスト形式です．

LaTeXやBeamerのファイルではありませんが，
内容を読みやすく記述できるように，
一部にLaTeXに似た記法を使用しています．

`.stex`ファイル内に資料全体の設定と，
複数のスライドを記述します．

```text
\set{
    theme=business_blue,
    header=title_band,
    footer=standard
}

\begin{frame, type=title, style=left_accent}
\title{PAIS}
\subtitle{社内AIシステム}
\end{frame}
```

</div>
"""


# ============================================================
# 詳細説明：SlideTex構文
# ============================================================
STEX_TEXT = r"""

##### SlideTexの基本構成

SlideTexファイルは，次の2つで構成します．

1. 資料全体の設定
2. 各スライドの定義

---

##### 資料全体の設定

資料全体の設定は，`\set{...}`内へ記述します．

```text
\set{
    title="PAISの概要",
    theme=business_blue,
    header=title_band,
    footer=standard,
    company="株式会社プレック研究所",
    presenter="",
    date=""
}
```

主な設定項目は次のとおりです．

- `title`：資料名
- `theme`：資料全体のテーマ
- `header`：本文ページのヘッダー
- `footer`：本文ページのフッター
- `image_path`：スライド画像を検索する場所
- `company`：会社名
- `presenter`：発表者名
- `date`：発表日

`title`，`company`，`presenter`，`date`は省略できます．

`theme`，`header`，`footer`を省略した場合は，
既定の設定を使用します．

---

##### スライドの定義

各スライドは，次の形式で記述します．

```text
\begin{frame, type=content, style=bullet}
\title{主な機能}

\begin{itemize}
\item 文書検索
\item RAGチャット
\item 議事録作成
\end{itemize}

\end{frame}
```

`\begin{frame, ...}`から`\end{frame}`までが，
PowerPointのスライド1枚に対応します．

`type`にはスライドの役割を指定し，
`style`にはデザインを指定します．

画像を配置する構文は「画像」タブ，
表を配置する構文は「表」タブを参照してください．

</div>
"""


# ============================================================
# 詳細説明：画像
# ============================================================
IMAGE_TEXT = r"""

##### 画像の検索場所

`image_path`には，スライドで使用する画像の検索場所を指定します．

画像の検索場所は，セミコロン（`;`）で区切って
複数指定できます．

指定された場所を上から順番に検索し，
最初に見つかった画像を使用します．

探索先には，通常のフォルダーと`inbox`を
混在して指定できます．

```text
\set{
    title="森林調査報告書",
    theme=forest_illustration,
    header=title_band,
    footer=standard,

    image_path="
        /Users/macmini2025/Documents/myDocument/プレックフォルダー/_自主研究/slideTex/image/common;
        /Users/macmini2025/Documents/myDocument/プレックフォルダー/_自主研究/slideTex/image/forest;
        inbox
    "
}
```

この例では，次の順番で画像を検索します．

1. `image/common`フォルダー
2. `image/forest`フォルダー
3. 現在のユーザーの`inbox`

各スライドでは，画像のファイル名だけを指定できます．

```text
\image{forest_observation_map.png}
```

画像が最初のフォルダーにない場合は，
次のフォルダーを検索します．

すべてのフォルダーにない場合は，
最後に`inbox`を検索します．

`\image{...}`に画像の絶対パスを指定した場合は，
`image_path`の探索先よりも絶対パスを優先します．

```text
\image{
    /Users/macmini2025/Documents/images/forest_observation_map.png
}
```

---

##### 画像付き本文ページ

左側に文章，右側に画像を配置する場合は，
本文ページに`style=text_image`を指定します．

```text
\begin{frame,
    type=content,
    style=text_image
}

\title{森林調査地点の概要}

\begin{itemize}

\item 調査区域を植生区分ごとに整理する
\item 林縁部，林内部，水辺を重点的に確認する
\item 現地写真と位置情報を対応させて記録する
\item 調査結果を今後の保全計画へ反映する

\end{itemize}

\image{forest_observation_map.png}

\imagecaption{
森林調査地点の配置イメージ
}

\end{frame}
```

`style=text_image`では，
左側に`\begin{itemize}...\end{itemize}`の文章を配置し，
右側に`\image{...}`で指定した画像を配置します．

`\image{...}`には，画像ファイル名を指定します．

```text
\image{forest_observation_map.png}
```

画像ファイル名だけを指定した場合は，
`\set{...}`の`image_path`に記述された探索先を
上から順番に検索します．

画像の下へ説明を表示する場合は，
`\imagecaption{...}`を指定します．

```text
\imagecaption{
森林調査地点の配置イメージ
}
```

画像の説明が不要な場合は，
`\imagecaption{...}`を省略できます．

`style=text_image`を使用する場合は，
`\image{...}`の指定が必要です．

</div>
"""


# ============================================================
# 詳細説明：表
# ============================================================
TABLE_TEXT = r"""

##### 表を配置する本文ページ

表を大きく配置する場合は，
本文ページに`style=table`を指定します．

```text
\begin{frame,
    type=content,
    style=table
}

\title{年度別売上}

\begin{table,
    style=grid,
    header={1,1}
}

\caption{表1　年度別売上}

項目,2024年,2025年//
売上,100,120//
費用,80,90//
利益,20,{3,000}

\end{table}

\end{frame}
```

`style=table`では，
タイトルの下へ表を大きく配置します．

表の前に説明文を表示する場合は，
`\description{...}`を指定します．

```text
\description{
2025年は，売上の増加に対して
費用の増加が抑えられています．
}
```

表の下に補足を表示する場合は，
`\note{...}`を指定します．

```text
\note{
単位：百万円
}
```

`\description{...}`と`\note{...}`は任意です．

指定がない場合は，説明文または補足を表示せず，
表の表示領域を広く使用します．

---

##### 左側に文章・右側に表を配置する

左側に文章，右側に表を配置する場合は，
`style=text_table`を指定します．

```text
\begin{frame,
    type=content,
    style=text_table
}

\title{2025年度 売上分析}

\begin{itemize}

\item 2025年度は売上が増加した
\item 利益率も前年より改善した
\item 関東地区の伸びが大きい

\end{itemize}

\begin{table,
    style=grid,
    header={1,1}
}

\caption{表1　地域別売上}

項目,関東,関西,中部//
売上,{3,000},{2,400},{1,800}//
利益,520,410,250

\end{table}

\end{frame}
```

`style=text_table`では，

- 左側に`\begin{itemize}...\end{itemize}`の文章
- 右側に`\begin{table,...}...\end{table}`の表

を配置します．

右側の表の上に説明文を表示する場合は，
`\description{...}`を指定します．

右側の表の下に補足を表示する場合は，
`\note{...}`を指定します．

---

##### tableの基本構文

表は，次の形式で記述します．

```text
\begin{table,
    style=grid,
    header={1,1}
}

\caption{表1　年度別売上}

項目,2024年,2025年//
売上,100,120//
費用,80,90//
利益,20,{3,000}

\end{table}
```

表の主な構成は次のとおりです．

- `style`：表の見た目
- `header`：ヘッダーとして扱う行数・列数
- `\caption{...}`：表題
- `,`：セルの区切り
- `//`：行の区切り

---

##### tableのheader

`header`は，表の先頭から何行・何列を
ヘッダーとして扱うかを指定します．

```text
header={1}
```

第1行をヘッダーとして扱います．

```text
header={2}
```

第1行から第2行までをヘッダーとして扱います．

```text
header={0,1}
```

第1列をヘッダーとして扱います．

```text
header={1,1}
```

第1行と第1列をヘッダーとして扱います．

2つの値を指定する場合は，

```text
header={ヘッダー行数,ヘッダー列数}
```

という順番です．

---

##### カンマを含むセル

セル内の文字列にカンマを含む場合は，
セル全体を`{...}`で囲みます．

```text
売上,{3,000},{2,400},{1,800}
```

この例では，`3,000`，`2,400`，`1,800`が，
それぞれ1つのセルとして扱われます．

`{...}`で囲まない場合は，
カンマがセルの区切りとして解釈されます．

---

##### セル内改行

セル内で改行する場合は，
`<改行>`を使用します．

```text
担当,{田中<改行>佐藤},鈴木,山田
```

PowerPoint上では，1つのセル内で次のように表示されます．

```text
田中
佐藤
```

---

##### セル結合

上のセルと縦方向に結合する場合は，
`<同上>`を使用します．

```text
担当,田中,鈴木//
担当,<同上>,佐藤
```

左側のセルと横方向に結合する場合は，
`<同左>`を使用します．

```text
項目,評価1,評価2//
売上,良好,<同左>
```

`<同上>`は第1行では使用できません．

`<同左>`は第1列では使用できません．

結合範囲は，連続した長方形になるように
指定してください．

---

##### tableで使用できるstyle

表自体の見た目は，
`\begin{table,...}`内の`style`で指定します．

現在は次の表スタイルを使用できます．

- `simple`
- `grid`
- `banded`
- `accent`
- `minimal`

```text
\begin{table,
    style=grid,
    header={1,1}
}
```

`simple`は，装飾を抑えた標準的な表です．

`grid`は，縦横の罫線を表示する業務資料向けの表です．

`banded`は，行ごとに背景色を切り替えます．

`accent`は，ヘッダー行やヘッダー列を
テーマ色で強調します．

`minimal`は，罫線や背景色を抑えた
簡潔な表です．

フレーム側の`style=table`または
`style=text_table`は，スライド内の配置を指定します．

table環境側の`style=grid`などは，
表自体の見た目を指定します．

```text
\begin{frame,
    type=content,
    style=text_table
}

...

\begin{table,
    style=grid,
    header={1,1}
}
```

この例では，

- `style=text_table`：左文章・右表の配置
- `style=grid`：表の罫線や色

をそれぞれ指定しています．

</div>
"""



# ============================================================
# 詳細説明：ページ種別
# ============================================================
TYPE_TEXT = r"""

##### typeとは

`type`は，スライドの役割を指定する項目です．

現在は次のページ種別を使用できます．

- `title`
- `section`
- `subsection`
- `content`
- `ending`

---

##### title

資料全体の表紙に使用します．

```text
\begin{frame, type=title, style=left_accent}
\title{PAIS}
\subtitle{社内AIシステム}
\end{frame}
```

---

##### section

章や大きなテーマの開始位置に使用します．

```text
\begin{frame, type=section, style=large_number}
\sectionnumber{01}
\title{PAISとは}
\end{frame}
```

---

##### subsection

章の途中にある小見出しや，
話題の切り替えに使用します．

```text
\begin{frame, type=subsection, style=accent_band}
\title{文書検索機能}
\subtitle{社内文書を横断的に検索します}
\end{frame}
```

---

##### content

箇条書き，2カラム，比較，メッセージ，
文章と画像を組み合わせたページなど，
通常の本文ページに使用します．

```text
\begin{frame, type=content, style=bullet}
\title{主な機能}

\begin{itemize}
\item 文書検索
\item RAGチャット
\item 議事録作成
\end{itemize}
\end{frame}
```

---

##### ending

資料の最終ページに使用します．

```text
\begin{frame, type=ending, style=thank_you}
\title{ご清聴ありがとうございました}
\end{frame}
```

</div>
"""


# ============================================================
# 詳細説明：スタイル
# ============================================================
STYLE_TEXT = r"""

##### styleとは

`style`は，スライド内の配置やデザインを指定する項目です．

`type`ごとに使用できる`style`が異なります．

---

##### titleで使用できるstyle

- `left_accent`
- `centered`
- `full_color`
- `minimal`

---

##### sectionで使用できるstyle

- `full_color`
- `large_number`
- `left_aligned`
- `centered`

---

##### subsectionで使用できるstyle

- `accent_band`
- `card`
- `minimal`
- `dark_panel`

---

##### contentで使用できるstyle

- `bullet`
- `text_image`
- `two_column`
- `comparison`
- `message`

---

##### endingで使用できるstyle

- `thank_you`
- `contact`
- `summary`
- `minimal`

`style`を省略した場合は，
ページ種別ごとに設定された既定のスタイルを使用します．

ただし，意図したレイアウトを明確にするため，
通常は`style`を指定してください．

</div>
"""


# ============================================================
# 詳細説明：テーマ
# ============================================================
THEME_TEXT = r"""

##### themeとは

`theme`は，資料全体に適用するデザイン設定です．

テーマは，大きく次の2つで構成されています．

- 配色：色，フォント，文字サイズなど
- レイアウト：各ページの構成要素，配置，位置，大きさなど

配色は`SlideTheme`で管理し，
レイアウトは`lib/slide_creation/theme_layouts/`で管理します．

配色とレイアウトを分離しているため，
同じレイアウトを利用しながら，
色だけを変更したテーマを追加できます．

例えば，`business_blue`と`academic_green`は，
異なる配色を使用しますが，
どちらも`basic`レイアウトを使用します．

テーマには，主に次の情報が含まれます．

- テーマキー
- 表示名
- 説明
- レイアウトキー
- 背景色
- メインカラー
- アクセントカラー
- 本文パネルの色
- 本文パネルの枠線色
- タイトル文字色
- 本文文字色
- 補足文字色
- フォント
- タイトル文字サイズ
- 本文文字サイズ
- フッター文字サイズ
- タイトル・見出し・小見出し用の共通背景画像
- 背景画像フォルダーのキー

---

##### 配色とレイアウトの関係

テーマを指定すると，
そのテーマに登録されている`layout_key`から，
使用するレイアウトファイルが決まります．

例えば，`business_blue`では，
次のように`basic`レイアウトを指定します．

```text
business_blue
    ↓
layout_key="basic"
    ↓
theme_layouts/basic.py
```

`academic_green`も同じ`basic`レイアウトを指定します．

```text
academic_green
    ↓
layout_key="basic"
    ↓
theme_layouts/basic.py
```

したがって，`business_blue`と`academic_green`は，

- タイトルの位置
- 見出しの位置
- 本文パネルの位置
- 箇条書きの位置
- 2カラムの構成
- 比較ページの構成
- 最終ページの構成

などが共通です．

一方で，

- メインカラー
- アクセントカラー
- 背景色
- パネル色
- 文字色

は，それぞれのテーマ設定によって異なります．

---

##### 現在使用できるテーマ

現在は次のテーマを使用できます．

- `business_blue`
- `simple_light`
- `modern_dark`
- `academic_green`
- `forest_green`
- `forest_illustration`
- `ocean`

---

##### 標準テーマ

次のテーマは，標準テーマです．

- `business_blue`
- `simple_light`
- `modern_dark`
- `academic_green`

これらはすべて，
次の共通レイアウトを使用します．

```text
lib/slide_creation/theme_layouts/basic.py
```

標準テーマでは，
ページの構成と配置を`basic.py`で共通化し，
配色を`themes.py`で個別に定義します．

対応関係は次のとおりです．

```text
business_blue
simple_light
modern_dark
academic_green
        ↓
layout_key="basic"
        ↓
theme_layouts/basic.py
```

例えば，`business_blue`は，

```text
basicレイアウト
    ＋
青を基調とした配色
```

です．

`academic_green`は，

```text
basicレイアウト
    ＋
緑を基調とした配色
```

です．

このため，標準テーマの色だけを変更する場合は，
`themes.py`の対象テーマを編集します．

標準テーマのページ構成や配置を変更する場合は，
`theme_layouts/basic.py`を編集します．

`basic.py`を変更すると，
`basic`レイアウトを使用しているすべての標準テーマへ
変更が反映されます．

---

##### basicレイアウト

`theme_layouts/basic.py`には，
標準テーマで使用するページレイアウトを定義します．

主に次の描画関数を持ちます．

```text
render_title()
render_section()
render_subsection()
render_content()
render_ending()
```

`render_title()`では，
タイトルページの構成と文字配置を行います．

`render_section()`では，
見出しページの章番号，タイトル，
補足説明などを配置します．

`render_subsection()`では，
小見出しページのタイトルと
補足説明などを配置します．

`render_content()`では，
本文ページのヘッダー，本文パネル，
箇条書き，2カラム，比較，メッセージ，
フッターなどを配置します．

`render_ending()`では，
最終ページの終了メッセージ，
問い合わせ先，まとめなどを配置します．

例えば，次の本文ページでは，

```text
\begin{frame,
    type=content,
    style=bullet
}
\title{主な機能}

\begin{itemize}
\item 文書検索
\item RAGチャット
\item 議事録作成
\end{itemize}
\end{frame}
```

`type=content`によって本文ページが選択され，
`style=bullet`によって箇条書き形式が選択されます．

標準テーマの場合は，
`theme_layouts/basic.py`の`render_content()`が呼び出されます．

その中で，

- ヘッダーを配置する
- 本文パネルを配置する
- 箇条書きを配置する
- フッターを配置する

というページ構成が決まります．

実際の配色は，
選択された`SlideTheme`から取得します．

したがって，同じ`style=bullet`でも，

```text
theme=business_blue
```

では青系の配色になり，

```text
theme=academic_green
```

では緑系の配色になります．

ページ内の配置は共通で，
色だけが変わります．

---

##### 新しい共通レイアウト

`basic.py`とは異なる共通レイアウトを作成する場合は，
`theme_layouts/`の中へ新しいファイルを追加します．

例えば，

```text
theme_layouts/basic2.py
```

を作成できます．

`basic2.py`には，必要に応じて次の関数を定義します．

```text
render_title()
render_section()
render_subsection()
render_content()
render_ending()
```

その後，`themes.py`で，

```text
layout_key="basic2"
```

を指定します．

例えば，次のようにテーマを定義した場合は，

```text
business_red
    ↓
layout_key="basic2"
    ↓
theme_layouts/basic2.py
```

`business_red`は，
`basic2.py`のレイアウトを使用します．

さらに，別のテーマにも

```text
layout_key="basic2"
```

を指定すれば，
複数の配色テーマで同じ`basic2`レイアウトを共有できます．

---

##### 特別テーマ

次のテーマは，特別テーマです．

- `forest_green`
- `forest_illustration`
- `ocean`

特別テーマは，
テーマごとのPythonファイルで，
配色と専用レイアウトを管理します．

```text
lib/slide_creation/theme_layouts/
├── basic.py
├── forest_green.py
├── forest_illustration.py
├── ocean.py
├── discovery.py
└── registry.py
```

`forest_green`は，
木や森などの自然を基調としたデザインです．

`forest_illustration`は，
森林をモチーフにした
幾何学的なイラスト背景を使用します．

`ocean`は，
海をモチーフにした背景画像と配色を使用します．

各特別テーマファイルには，
次のような内容を定義します．

```text
THEME
render_title()
render_section()
render_subsection()
```

必要に応じて，次の関数も追加できます．

```text
render_content()
render_ending()
```

---

##### 特別テーマのTHEME

特別テーマファイルの`THEME`には，
`SlideTheme`を定義します．

主に次の情報を保持します．

- テーマキー
- 表示名
- 説明
- レイアウトキー
- フォント
- メインカラー
- アクセントカラー
- 背景色
- パネル色
- パネル枠線色
- タイトル文字色
- 本文文字色
- 補足文字色
- 文字サイズ
- 背景画像フォルダーのキー

例えば，`forest_green.py`では，
次の対応になります．

```text
theme.key="forest_green"
layout_key="forest_green"
theme_asset_key="forest_green"
```

この場合，

```text
レイアウト
    ↓
theme_layouts/forest_green.py

背景画像
    ↓
assets/slide/themes/forest_green/
```

が使用されます．

---

##### 特別テーマのレイアウト

`render_title()`では，
タイトルページの文字配置を行います．

`render_section()`では，
見出しページの章番号，タイトル，
補足説明などを配置します．

`render_subsection()`では，
小見出しページのタイトルと
補足説明などを配置します．

特別テーマに`render_content()`がある場合は，
本文ページもそのテーマ専用のレイアウトで描画します．

特別テーマに`render_ending()`がある場合は，
最終ページもそのテーマ専用のレイアウトで描画します．

特別テーマに`render_content()`または
`render_ending()`がない場合は，
`basic.py`にある共通レイアウトを使用します．

例えば，`forest_green.py`に，

```text
render_title()
render_section()
render_subsection()
```

だけが定義されている場合は，

```text
title
section
subsection
    ↓
forest_green.py

content
ending
    ↓
basic.py
```

という構成になります．

このため，タイトル・見出し・小見出しだけを
テーマ専用デザインにし，
本文と最終ページは標準レイアウトのまま使用することもできます．

---

##### 背景画像

画像付きテーマでは，
次のスライド種別に応じて
背景画像が自動的に適用されます．

- `type=title` → `title.png`
- `type=section` → `section.png`
- `type=subsection` → `subsection.png`

背景画像は，次のフォルダーへ保存します．

```text
text_studio_app/
└── assets/
    └── slide/
        └── themes/
            ├── forest_green/
            │   ├── title.png
            │   ├── section.png
            │   └── subsection.png
            ├── forest_illustration/
            │   ├── title.png
            │   ├── section.png
            │   └── subsection.png
            └── ocean/
                ├── title.png
                ├── section.png
                └── subsection.png
```

背景画像ファイル名は，
必ず次の名前にします．

- `title.png`
- `section.png`
- `subsection.png`

テーマファイルの`theme_asset_key`には，
背景画像フォルダー名を指定します．

例えば，

```text
theme_asset_key="ocean"
```

の場合は，

```text
assets/slide/themes/ocean/
```

を参照します．

---

##### テーマの指定例

SlideTexでは，
資料全体の設定にテーマを指定します．

```text
\set{
    theme=forest_illustration,
    header=title_band,
    footer=standard
}
```

`theme=forest_illustration`を指定すると，

- `forest_illustration`の配色
- `forest_illustration`のレイアウト
- `forest_illustration`の背景画像

が適用されます．

標準テーマを使用する場合は，
次のように指定します．

```text
\set{
    theme=business_blue,
    header=title_band,
    footer=standard
}
```

この場合は，

- 配色：`business_blue`
- レイアウト：`basic.py`

となります．

---

##### 標準テーマを追加する場合

既存のレイアウトを利用して，
色だけが異なる標準テーマを追加する場合は，
`themes.py`へ`SlideTheme`を追加します．

例えば，`business_red`を追加し，
`basic`レイアウトを使用する場合は，

```text
key="business_red"
layout_key="basic"
```

と指定します．

この場合，新しいレイアウトファイルを
作成する必要はありません．

配色だけを定義すれば，
`basic.py`のページ構成を利用できます．

---

##### 新しいレイアウトを追加する場合

新しいレイアウトを追加する場合は，
次の手順で行います．

1. `theme_layouts/basic2.py`などのファイルを作成する
2. `render_title()`を実装する
3. `render_section()`を実装する
4. `render_subsection()`を実装する
5. `render_content()`を実装する
6. `render_ending()`を実装する
7. `themes.py`のテーマに`layout_key="basic2"`を指定する

複数のテーマに同じ`layout_key`を指定すれば，
1つのレイアウトを複数の配色で利用できます．

---

##### 背景画像を使用する特別テーマを追加する場合

背景画像を使用する特別テーマを追加する場合は，
次の手順で行います．

1. `theme_layouts/<テーマキー>.py`を作成する
2. テーマファイル内に`THEME`を定義する
3. `layout_key`にテーマキーを指定する
4. `theme_asset_key`に背景画像フォルダー名を指定する
5. `render_title()`を実装する
6. `render_section()`を実装する
7. `render_subsection()`を実装する
8. 必要に応じて`render_content()`を実装する
9. 必要に応じて`render_ending()`を実装する
10. `assets/slide/themes/<テーマキー>/`へ背景画像を保存する

特別テーマは，
`theme_layouts/discovery.py`によって自動的に検出されます．

そのため，新しい特別テーマを追加する際に，
`themes.py`へ重複してテーマを定義する必要はありません．

また，`theme_layouts/registry.py`へ
テーマ名を個別に登録する必要もありません．

テーマファイル名，`THEME.key`，
`layout_key`は，同じ名前にすると
構成が分かりやすくなります．

例えば，`ocean`の場合は，

```text
ファイル名
    ocean.py

THEME.key
    ocean

layout_key
    ocean

theme_asset_key
    ocean
```

とします．

---

##### テーマファイルの自動検出

特別テーマは，
`theme_layouts/discovery.py`が
`theme_layouts/`内のPythonファイルを検索し，
各ファイルの`THEME`を読み込みます．

ただし，次の補助ファイルは，
テーマとして登録しません．

- `__init__.py`
- `basic.py`
- `discovery.py`
- `registry.py`

`basic.py`はテーマ定義ではなく，
標準テーマが共有するレイアウト定義であるため，
テーマの自動検出対象から除外します．

---

##### レイアウトの振り分け

`theme_layouts/registry.py`は，
選択されたテーマの`layout_key`を確認し，
対応するレイアウトモジュールを読み込みます．

例えば，

```text
theme=business_blue
    ↓
layout_key="basic"
    ↓
theme_layouts/basic.py
```

となります．

また，

```text
theme=ocean
    ↓
layout_key="ocean"
    ↓
theme_layouts/ocean.py
```

となります．

テーマ専用レイアウトに
該当する描画関数がない場合は，
`basic.py`の同じ描画関数を使用します．

これにより，
テーマごとに必要なページだけを
専用レイアウトへ変更できます．

---

##### 配色とレイアウトの変更場所

今回の構成では，
配色とレイアウトの変更場所を分けています．

標準テーマの配色を変更する場合は，

```text
lib/slide_creation/themes.py
```

を編集します．

標準テーマのページ構成を変更する場合は，

```text
lib/slide_creation/theme_layouts/basic.py
```

を編集します．

特別テーマの配色や専用レイアウトを変更する場合は，

```text
lib/slide_creation/theme_layouts/<テーマキー>.py
```

を編集します．

背景画像を変更する場合は，

```text
assets/slide/themes/<テーマキー>/
```

の画像ファイルを変更します．

---

##### まとめ

今回の構成では，

```text
配色
    ↓
SlideTheme

レイアウト
    ↓
theme_layouts/

背景画像
    ↓
assets/slide/themes/
```

という役割分担になっています．

標準テーマは，
`themes.py`で配色を定義し，
`theme_layouts/basic.py`で
共通レイアウトを定義します．

```text
business_blue
simple_light
modern_dark
academic_green
        ↓
basic.py
```

特別テーマは，
テーマごとのPythonファイルで，
配色と専用レイアウトを管理します．

```text
forest_green
        ↓
forest_green.py

forest_illustration
        ↓
forest_illustration.py

ocean
        ↓
ocean.py
```

新しい配色テーマを追加する場合は，
既存の`layout_key`を指定します．

新しいレイアウトを追加する場合は，
`basic2.py`などを作成し，
テーマから`layout_key`で指定します．

この構成により，

- 同じレイアウトを複数の配色で利用する
- 特定のテーマだけ専用レイアウトを使用する
- 一部のページだけ専用レイアウトへ変更する
- レイアウトと配色を別々に管理する

ことができます．

</div>
"""

# ============================================================
# 詳細説明：ヘッダー
# ============================================================
HEADER_TEXT = r"""

##### headerとは

`header`は，本文スライド上部のタイトル表示形式です．

現在は次のヘッダーを使用できます．

- `title_band`
- `simple_line`
- `none`

---

##### title_band

スライド上部に色付きのタイトル帯を表示します．

##### simple_line

タイトルの下にアクセントラインを表示します．

##### none

装飾を付けず，タイトル文字だけを表示します．

設定例は次のとおりです．

```text
\set{
    header=title_band
}
```

テーマとヘッダーは独立しているため，
同じテーマでも異なるタイトル表示を使用できます．

</div>
"""


# ============================================================
# 詳細説明：フッター
# ============================================================
FOOTER_TEXT = r"""

##### footerとは

`footer`は，本文スライド下部に表示する情報の形式です．

現在は次のフッターを使用できます．

- `standard`
- `detailed`
- `confidential`
- `none`

---

##### standard

- 資料名
- ページ番号

##### detailed

- 会社名
- 資料名
- 日付
- ページ番号

##### confidential

- 資料名
- 社外秘
- ページ番号

##### none

フッターを表示しません．

設定例は次のとおりです．

```text
\set{
    footer=standard
}
```

</div>
"""

# ============================================================
# 詳細説明：記述例
# ============================================================
EXAMPLE_TEXT = r"""

##### SlideTex記述例

次の例では，森林調査を題材として，
タイトルページ，見出しページ，箇条書きページ，
画像付き本文ページ，最終ページを作成します．

```text
\set{
    title="森林調査報告書",
    theme=forest_illustration,
    header=title_band,
    footer=standard,

    image_path="
        /Users/macmini2025/Documents/myDocument/slideTex/image/common;
        /Users/macmini2025/Documents/myDocument/slideTex/image/forest;
        inbox
    ",

    company="株式会社プレック研究所",
    presenter="",
    date="2026年8月"
}


%============================================================
% タイトルページ
%============================================================

\begin{frame,
    type=title,
    style=left_accent
}

\title{森林調査報告書}

\subtitle{
調査対象地の自然環境と保全方針
}

\end{frame}


%============================================================
% 見出しページ
%============================================================

\begin{frame,
    type=section,
    style=large_number
}

\sectionnumber{01}

\title{森林調査の概要}

\subtitle{
調査の目的と対象地点を整理します
}

\end{frame}


%============================================================
% 本文ページ
%============================================================

\begin{frame,
    type=content,
    style=bullet
}

\title{調査の目的}

\begin{itemize}

\item 調査区域の植生区分を把握する
\item 林縁部と林内部の環境差を確認する
\item 水辺周辺の動植物を記録する
\item 今後の保全計画に必要な情報を整理する

\end{itemize}

\end{frame}


%============================================================
% 本文ページ（左側に文章・右側に画像）
%============================================================

\begin{frame,
    type=content,
    style=text_image
}

\title{森林調査地点}

\begin{itemize}

\item 林縁部，林内部，水辺に調査地点を設定する
\item 各地点の植生と土地利用を確認する
\item 現地写真と位置情報を対応させて記録する
\item 調査結果を保全対象区域の検討に使用する

\end{itemize}

\image{forest_observation_map.png}

\imagecaption{
森林調査地点の配置イメージ
}

\end{frame}


%============================================================
% 最終ページ
%============================================================

\begin{frame,
    type=ending,
    style=thank_you
}

\title{ご清聴ありがとうございました}

\subtitle{
森林環境の保全と適切な管理に向けて
}

\end{frame}
```

この例では，次の5枚のスライドを作成します．

1. 森林調査報告書のタイトルページ
2. 「森林調査の概要」の見出しページ
3. 調査目的を示す箇条書きの本文ページ
4. 左側に文章，右側に画像を配置した本文ページ
5. 最終ページ

画像付き本文ページでは，
`style=text_image`を指定しています．

```text
style=text_image
```

配置する画像は，ファイル名で指定します．

```text
\image{forest_observation_map.png}
```

画像は，`\set{...}`の`image_path`に記述した場所を
上から順番に検索します．

この例では，次の順番です．

1. `image/common`フォルダー
2. `image/forest`フォルダー
3. 現在のユーザーの`inbox`

最初に見つかった`forest_observation_map.png`を使用します．

画像の下に表示する説明は，
`\imagecaption{...}`で指定します．

</div>
"""

# ============================================================
# 詳細説明：注意点
# ============================================================
NOTES_TEXT = r"""

##### ファイル形式

SlideTexファイルの拡張子は`.stex`です．

文字コードはUTF-8を使用してください．

UTF-8 BOM付きのファイルも読み込めます．

---

##### 構文エラー

次のような場合は，構文エラーになります．

- `type`が指定されていない
- 未登録の`type`が指定されている
- 未登録の`style`が指定されている
- `type`と`style`の組み合わせが正しくない
- 未登録のテーマが指定されている
- 未登録のヘッダーが指定されている
- 未登録のフッターが指定されている
- `frame`が1つも記述されていない

構文エラーがある場合は，
PowerPoint作成ボタンを使用できません．

---

##### 現在の制限

現在は，主にテキストを使用したスライドを作成します．

テーマ共通背景画像については，`title`，`section`，
`subsection`へ自動配置できます．

ただし，各スライドへ個別の写真や図を指定して配置する機能は，
まだ実装していません．

次の機能は，今後追加する予定です．

- スライドごとの個別画像配置
- 表の配置
- グラフの配置
- ロゴ配置
- PowerPointテンプレートの読み込み
- スライドの画像プレビュー
- AIによる構成案作成
- AIによる本文生成

---

##### 文字量

本文の文字数や行数が多い場合は，
PowerPointの枠内に文字が収まらないことがあります．

PowerPoint作成後は，必ずファイルを開き，
次の内容を確認してください．

- 文字サイズ
- 改行位置
- 文字のはみ出し
- 左右の配置
- スライド全体のバランス

</div>
"""


# ============================================================
# 詳細説明タブ
# ============================================================
HELP_TABS = [
    ("概要", OVERVIEW_TEXT),
    ("SlideTex構文", STEX_TEXT),
    ("ページ種別", TYPE_TEXT),
    ("スタイル", STYLE_TEXT),
    ("画像", IMAGE_TEXT),
    ("表", TABLE_TEXT),
    ("テーマ", THEME_TEXT),
    ("ヘッダー", HEADER_TEXT),
    ("フッター", FOOTER_TEXT),
    ("記述例", EXAMPLE_TEXT),
    ("注意点", NOTES_TEXT),
]