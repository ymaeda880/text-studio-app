# pages/11_pdf_to_png_unprocessed.py
# ============================================================
# 📄→🖼 未PNGのPDFだけ列挙 → 選択 → 実行してPNG生成
# - base_pdf_dir 直下の *.pdf を「未処理」とみなす（処理後は移動されるため）
# - 出力先フォルダが既に存在する場合はスキップ（固定仕様）
# - zoom はスライダー（デフォルト 1.0）
# - 連番ゼロ埋め桁数はページ数から自動
# ============================================================

from __future__ import annotations
from pathlib import Path
import os, shutil
import streamlit as st

# ---- TOML ロード（Py3.11+ は tomllib、以下は toml フォールバック） ----
try:
    import tomllib  # Python 3.11+
    def load_toml(path: Path) -> dict:
        with open(path, "rb") as f:
            return tomllib.load(f)
except ImportError:
    import toml
    def load_toml(path: Path) -> dict:
        return toml.load(path)

import fitz  # PyMuPDF: pip install pymupdf

st.set_page_config(page_title="未PNGのPDFを処理", page_icon="🖼", layout="wide")
st.title("📄→🖼 未PNGのPDFだけ列挙して処理")

with st.expander("ℹ️ このページで行うこと（処理フロー）", expanded=False):
    st.markdown(
    """
    1. **未処理PDFの抽出**  
       - `base_pdf_dir` 直下にある `*.pdf` を走査し、まだ PNG 化されていないものだけを候補として表示。  
       - 既に `base_pdf_dir/<ファイル名>/png/` に画像があるものは除外します。

    2. **対象PDFの選択（radioボタン）**  
       - 候補の中から1つ選びます。  
       - 画面には「選択したPDF」「出力先フォルダ」「zoom（拡大倍率）」が表示されます。

    3. **実行（🚀 実行ボタン）**  
       - 出力先フォルダ `base_pdf_dir/<ファイル名>/` を作成。  
         （既に存在する場合は **スキップ**）  
       - `base_pdf_dir/_ref.tex` を `<ファイル名>_ref.tex` としてコピー。  
       - PDF を `base_pdf_dir/<ファイル名>/<ファイル名>.pdf` に **移動**。  
       - 各ページを PNG に変換して `png/` サブフォルダに保存。  
         - サブフォルダ名は常に `"png"`。  
         - `zoom`（拡大倍率）はスライダーで変更可能（既定値 1.0）。  
         - ファイル名は `<ファイル名>_<ページ番号>.png`。  
         - **ゼロ埋め桁数** はページ数から自動決定（例：9p→1桁、10p→2桁、123p→3桁）。  
       - 処理中は進行状況バーを表示し、完了後に先頭数枚をプレビュー。

    #### 固定仕様と前提
    - 設定ファイル：`.streamlit/settings.toml`（または環境変数 `APP_SETTINGS_FILE`）  
    - `paths.base_pdf_dir` に PDF と `_ref.tex` を置く。  
    - サブフォルダ名 `"png"` は固定。  
    - 出力先が存在する場合はスキップ（安全優先）。

    #### 出力例
    ```
    base_pdf_dir/Officer1975/
    ├─ Officer1975.pdf           （移動）
    ├─ Officer1975_ref.tex       （テンプレ複製）
    └─ png/
       ├─ Officer1975_00.png
       ├─ Officer1975_01.png
       └─ ...
    ```
    """
    )


# ------------------------------------------------------------
# 設定ファイルの読み込み
# ------------------------------------------------------------
DEFAULT_SETTINGS_FILE = os.environ.get("APP_SETTINGS_FILE", "./.streamlit/settings.toml")
settings_path = Path(DEFAULT_SETTINGS_FILE).expanduser().resolve()

with st.sidebar:
    st.subheader("⚙️ 設定ファイルの場所")
    st.code(str(settings_path), language="bash")
    zoom = st.slider("🔍 PNG化ズーム（拡大倍率）", 0.5, 4.0, 1.0, 0.1)

if not settings_path.exists():
    st.error(f"設定ファイルが見つかりません: {settings_path}")
    st.stop()

try:
    settings = load_toml(settings_path)
except Exception as e:
    st.error(f"設定ファイルの読み込みに失敗: {e}")
    st.stop()

paths = settings.get("paths", {})
base_pdf_dir = Path(paths.get("base_pdf_dir", "")).expanduser().resolve()
ref_template_name = paths.get("ref_template_name", "_ref.tex")

if not base_pdf_dir.exists():
    st.error(f"base_pdf_dir が存在しません: {base_pdf_dir}")
    st.stop()

template_path = base_pdf_dir / ref_template_name
if not template_path.exists():
    st.error(f"テンプレートが見つかりません: {template_path}")
    st.stop()

# ------------------------------------------------------------
# 「未PNGのPDF」を列挙
# ルール: base_pdf_dir 直下の *.pdf は未処理とみなす（処理後は移動されるため）
# ただし念のため、<stem>/png が既に存在するものは除外
# ------------------------------------------------------------
def list_unprocessed_pdfs(base_dir: Path) -> list[Path]:
    candidates = sorted(base_dir.glob("*.pdf"))
    unprocessed = []
    for pdf in candidates:
        stem = pdf.stem
        target_dir = base_dir / stem
        png_dir = target_dir / "png"
        # まだ移動されていない（= base 直下にある）PDF かつ
        # 既に <stem>/png が無い or 空なら「未処理」とみなす
        if not png_dir.exists() or not any(png_dir.glob("*.png")):
            unprocessed.append(pdf)
    return unprocessed

unprocessed_pdfs = list_unprocessed_pdfs(base_pdf_dir)

if not unprocessed_pdfs:
    st.success("🎉 未PNGのPDFはありません。すべて処理済みです。")
    st.stop()

labels = [p.name for p in unprocessed_pdfs]
choice = st.radio("📝 処理するPDFを選択", labels, index=0)
src_pdf = unprocessed_pdfs[labels.index(choice)]
file_stem = src_pdf.stem
target_dir = base_pdf_dir / file_stem
png_dir = target_dir / "png"  # 固定

st.caption(f"選択: `{src_pdf.name}` / 出力先: `{target_dir}` / PNG dir: `png` / zoom={zoom}")

# ------------------------------------------------------------
# ユーティリティ
# ------------------------------------------------------------
def safe_mkdirs(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def copy_template_and_rename(template: Path, target: Path, stem: str) -> Path:
    copied = target / "_ref.tex"
    shutil.copy2(template, copied)
    renamed = target / f"{stem}_ref.tex"
    copied.rename(renamed)
    return renamed

def move_pdf_to_target(src: Path, target: Path, stem: str) -> Path:
    dst = target / f"{stem}.pdf"
    shutil.move(str(src), str(dst))
    return dst

def auto_pad_width(total_pages: int) -> int:
    # 例: 9p->1桁, 10p->2桁, 123p->3桁
    return len(str(total_pages))

def export_pdf_pages(pdf_path: Path, out_dir: Path, stem: str, zoom: float) -> int:
    safe_mkdirs(out_dir)
    doc = fitz.open(pdf_path)
    total = len(doc)
    width = auto_pad_width(total)
    prog = st.progress(0.0, text="PNG 生成中…")
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        out_path = out_dir / f"{stem}_{str(i).zfill(width)}.png"
        pix.save(out_path)  # 上書き保存
        prog.progress((i + 1) / total, text=f"PNG 生成中… ({i+1}/{total})")
    prog.empty()
    return total

# ------------------------------------------------------------
# 実行ボタン
# ------------------------------------------------------------
run = st.button("🚀 実行（このPDFをPNG化）", type="primary")


if run:
    # 固定仕様: 既に出力先フォルダがある場合はスキップ
    if target_dir.exists():
        st.warning(f"出力先フォルダが既に存在するため **スキップ** しました: {target_dir}")
        st.stop()

    with st.status("処理を開始します…", expanded=True) as status:
        st.write("1) 出力先フォルダの作成")
        safe_mkdirs(target_dir)
        safe_mkdirs(png_dir)

        st.write("2) _ref.tex のコピー＆改名")
        try:
            renamed = copy_template_and_rename(template_path, target_dir, file_stem)
            st.write(f"→ {renamed.name} を作成")
        except Exception as e:
            st.error(f"テンプレートの複製に失敗: {e}")
            st.stop()

        st.write("3) PDF を出力先に移動")
        try:
            dst_pdf = move_pdf_to_target(src_pdf, target_dir, file_stem)
            st.write(f"→ {dst_pdf}")
        except Exception as e:
            st.error(f"PDF の移動に失敗: {e}")
            st.stop()

        st.write("4) 各ページを PNG に書き出し（桁数はページ数から自動）")
        try:
            n = export_pdf_pages(dst_pdf, png_dir, file_stem, zoom=float(zoom))
            st.success(f"PNG 生成完了: {n} 枚 / 保存先: {png_dir}")
        except Exception as e:
            st.error(f"PNG 生成に失敗: {e}")
            st.stop()

        status.update(label="完了しました ✅", state="complete")

    # 先頭数枚プレビュー
    samples = sorted(png_dir.glob("*.png"))[:6]
    if samples:
        st.subheader("🖼 出力プレビュー（先頭数枚）")
        st.image([str(p) for p in samples], caption=[p.name for p in samples], use_column_width=True)
    else:
        st.info("PNG が見つかりませんでした。")
