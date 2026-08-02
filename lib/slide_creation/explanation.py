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

箇条書き，2カラム，比較，メッセージなど，
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

テーマには，主に次の情報が含まれます．

- 背景色
- メインカラー
- アクセントカラー
- 本文パネルの色
- 文字色
- フォント
- タイトル文字サイズ
- 本文文字サイズ
- タイトル・見出し・小見出し用の共通背景画像
- 背景画像に合わせたテーマ専用文字配置

現在は次のテーマを使用できます．

- `business_blue`
- `simple_light`
- `modern_dark`
- `academic_green`
- `forest_green`
- `forest_illustration`

`forest_green`は，木や森などの自然写真風背景を使用します．

`forest_illustration`は，森林をモチーフにした
幾何学的なイラスト背景を使用します．

画像付きテーマでは，次のスライド種別に応じて
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
            └── forest_illustration/
                ├── title.png
                ├── section.png
                └── subsection.png
```

背景画像を使用する特別テーマでは，
テーマ固有の設定と専用レイアウトを
`lib/slide_creation/theme_layouts/`で管理します．

```text
lib/slide_creation/theme_layouts/
├── registry.py
├── forest_green.py
└── forest_illustration.py
```

各テーマファイルには，次の内容をまとめて定義します．

```text
THEME
render_title()
render_section()
render_subsection()
```

`THEME`には，次のテーマ固有設定を保持します．

- テーマキー
- 表示名
- 説明
- フォント
- メインカラー
- アクセントカラー
- 背景色
- パネル色
- 文字色
- 文字サイズ
- 背景画像フォルダーのキー

`render_title()`では，タイトルページの文字配置を行います．

`render_section()`では，見出しページの章番号，
タイトル，補足説明などを配置します．

`render_subsection()`では，小見出しページのタイトルと
補足説明などを配置します．

設定例は次のとおりです．

```text
\set{
    theme=forest_illustration,
    header=title_band,
    footer=standard
}
```

背景画像を使用する特別テーマを追加する場合は，
次の手順で行います．

1. `theme_layouts/<テーマキー>.py`を作成する
2. テーマファイル内に`THEME`を定義する
3. `render_title()`を実装する
4. `render_section()`を実装する
5. `render_subsection()`を実装する
6. `assets/slide/themes/<テーマキー>/`へ背景画像を保存する
7. `themes.py`へテーマを登録する
8. `theme_layouts/registry.py`へテーマを登録する

背景画像ファイル名は，必ず次の名前にします．

- `title.png`
- `section.png`
- `subsection.png`

特別テーマのテーマ定義は，
各テーマのPythonファイルへ集約します．

例えば，`forest_green`の色，フォント，
背景画像キー，タイトル・見出し・小見出しの配置は，

```text
theme_layouts/forest_green.py
```

で一括して管理します．

`themes.py`では，特別テーマの設定を重複して定義せず，
各テーマファイルの`THEME`を読み込んで
`SLIDE_THEMES`へ登録します．

この構成により，テーマの色や配置を変更するときは，
原則として対象テーマのPythonファイルだけを
確認すればよくなります．

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

```text
\set{
    title="PAISの概要",
    theme=business_blue,
    header=title_band,
    footer=standard
}

\begin{frame, type=title, style=left_accent}
\title{PAIS}
\subtitle{社内AIシステム}
\end{frame}

\begin{frame, type=section, style=large_number}
\sectionnumber{01}
\title{PAISとは}
\end{frame}

\begin{frame, type=content, style=bullet}
\title{主な機能}

\begin{itemize}
\item 文書検索
\item RAGチャット
\item 議事録作成
\end{itemize}
\end{frame}

\begin{frame, type=ending, style=thank_you}
\title{ご清聴ありがとうございました}
\end{frame}
```

この例では，次の4枚のスライドを作成します．

1. タイトルページ
2. 見出しページ
3. 箇条書きの本文ページ
4. 最終ページ

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
    ("テーマ", THEME_TEXT),
    ("ヘッダー", HEADER_TEXT),
    ("フッター", FOOTER_TEXT),
    ("記述例", EXAMPLE_TEXT),
    ("注意点", NOTES_TEXT),
]