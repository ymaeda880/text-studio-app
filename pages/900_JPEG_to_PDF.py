# pages/53_JPEG_to_PDF.py
from __future__ import annotations

import io
from datetime import datetime
from typing import List, Tuple, Optional, Iterable
from pathlib import Path
import zipfile

import streamlit as st
from PIL import Image, ImageOps, ExifTags

# （任意）HEIC対応：pillow-heif を入れている場合のみ有効化
# pip install pillow-heif
try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
except Exception:
    pass

# ─────────────────────────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="JPEG/PNG → PDF 変換（ドロップ/フォルダ/ZIP）", page_icon="🖼️", layout="wide")
st.title("🖼️ 画像をPDFに結合（ドロップ + フォルダ + ZIP）")
st.caption("JPEG/PNG（HEICは任意対応）をまとめてPDF化。EXIFの回転補正、A4レイアウト、順序指定に対応。")

IMG_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG", ".heic", ".HEIC"}
MAX_FILES = 500  # 安全のための上限

# ─────────────────────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────────────────────
def _sniff_image_type(data: bytes) -> Optional[str]:
    """JPEG/PNG をマジックナンバーで判定（それ以外は None）"""
    if len(data) >= 3 and data[:3] == b"\xFF\xD8\xFF":
        return "jpeg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    # HEIF/HEIC（ftyp... 'heic','heif','mif1','msf1' 等）簡易判定
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heif"):
            return "heic"
    return None

def _is_appledouble(name: str) -> bool:
    """__MACOSX/ や ._xxxx を除外"""
    bn = name.split("/")[-1]
    return name.startswith("__MACOSX/") or bn.startswith("._")

def _read_image(file_or_path) -> Image.Image:
    """
    PIL Image を RGB で読み込む（EXIF 回転補正）。失敗時は例外を投げる。
    file_or_path: BytesIO / Path / UploadedFile
    """
    # BytesIO/UploadedFile は先頭へ
    try:
        if hasattr(file_or_path, "seek"):
            file_or_path.seek(0)
    except Exception:
        pass

    im = Image.open(file_or_path)
    # 破損チェック（verify 後は再オープンが必要）
    try:
        im.verify()
    except Exception:
        # verify失敗でも再オープンで読めることがある
        pass

    if hasattr(file_or_path, "seek"):
        file_or_path.seek(0)
    im = Image.open(file_or_path)

    # EXIF 回転補正
    try:
        exif = im.getexif()
        if exif:
            im = ImageOps.exif_transpose(im)
    except Exception:
        pass

    if im.mode != "RGB":
        im = im.convert("RGB")
    return im

def _get_exif_datetime(img: Image.Image) -> Optional[datetime]:
    """撮影日（DateTimeOriginal）を返す。無ければNone。"""
    try:
        exif = img.getexif()
        if not exif:
            return None
        tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
        dt = tag_map.get("DateTimeOriginal") or tag_map.get("DateTime")
        if not dt:
            return None
        return datetime.strptime(str(dt), "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None

def _a4_pixels(dpi: int, landscape: bool) -> Tuple[int, int]:
    """A4のピクセルサイズを返す。dpiはUI指定。"""
    inch_per_mm = 1.0 / 25.4
    w = int(round(210 * inch_per_mm * dpi))
    h = int(round(297 * inch_per_mm * dpi))
    return (h, w) if landscape else (w, h)

def _compose_on_a4(
    img: Image.Image,
    dpi: int,
    landscape: bool,
    fill_color: str,
    fit_mode: str,
    margin_pct: float,
) -> Image.Image:
    """A4キャンバスに画像をレイアウトして新しいページ画像を返す。"""
    aw, ah = _a4_pixels(dpi, landscape)
    canvas = Image.new("RGB", (aw, ah), fill_color)

    margin_w = int(aw * margin_pct / 100.0)
    margin_h = int(ah * margin_pct / 100.0)
    box_w = max(1, aw - 2 * margin_w)
    box_h = max(1, ah - 2 * margin_h)

    if fit_mode.startswith("余白内"):
        fitted = ImageOps.contain(img, (box_w, box_h))
    else:
        fitted = ImageOps.fit(img, (box_w, box_h), method=Image.Resampling.LANCZOS)

    x = margin_w + (box_w - fitted.width) // 2
    y = margin_h + (box_h - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas

def _build_pdf_bytes(pages: List[Image.Image]) -> bytes:
    """PIL画像のリストからPDFバイトを生成"""
    if not pages:
        return b""
    buf = io.BytesIO()
    first, rest = pages[0], pages[1:]
    first.save(buf, format="PDF", save_all=True, append_images=rest)
    buf.seek(0)
    return buf.read()

def _gather_from_folder(folder: Path, recursive: bool, pattern: str) -> List[Path]:
    if pattern.strip():
        paths = sorted(folder.rglob(pattern) if recursive else folder.glob(pattern))
    else:
        it: Iterable[Path] = folder.rglob("*") if recursive else folder.iterdir()
        paths = sorted(p for p in it if p.suffix in IMG_EXTS)
    return paths

def _gather_from_zip(zf: zipfile.ZipFile) -> List[Tuple[str, io.BytesIO]]:
    """ZIPから画像（JPEG/PNG/HEIC）を抽出（AppleDouble除外・マジックナンバー判定）"""
    items: List[Tuple[str, io.BytesIO]] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename
        if _is_appledouble(name):
            continue
        with zf.open(info, "r") as f:
            data = f.read()
        typ = _sniff_image_type(data)
        if typ is None:
            # 非画像はスキップ
            continue
        items.append((name, io.BytesIO(data)))
    items.sort(key=lambda x: x[0])
    return items

# ─────────────────────────────────────────────────────────────
# 入力モード
# ─────────────────────────────────────────────────────────────
mode = st.radio(
    "入力モード",
    ["ドロップ（複数ファイル）", "フォルダ指定（サーバ上のパス）", "ZIPをドロップ（一括）"],
    horizontal=True,
)

# 共通オプション
with st.expander("⚙️ オプション（共通）", expanded=True):
    order_by = st.selectbox(
        "並び順",
        ["アップロード/取得順", "名前（昇順）", "名前（降順）", "EXIF日時（昇順）", "EXIF日時（降順）"],
        index=0,
    )
    layout_mode = st.radio(
        "ページサイズ",
        ["画像ピクセルそのまま（1画像=1ページ）", "A4にレイアウト（1画像=1ページ）"],
        index=1,
    )
    dpi = st.slider("A4時の解像度（dpi）", 72, 600, 300, 24, disabled=layout_mode.startswith("画像ピクセル"))
    landscape = st.toggle("A4横向き", value=False, disabled=layout_mode.startswith("画像ピクセル"))
    fit_mode = st.selectbox(
        "A4時のフィット方法",
        ["余白内に収まるよう縮小（contain）", "余白いっぱいに塗りつぶし（cover）"],
        disabled=layout_mode.startswith("画像ピクセル"),
    )
    margin_pct = st.slider("A4時の余白（%）", 0, 20, 5, disabled=layout_mode.startswith("画像ピクセル"))
    bg_color = st.color_picker("余白の背景色（A4時）", value="#FFFFFF", disabled=layout_mode.startswith("画像ピクセル"))
    default_name = st.text_input("出力ファイル名", "merged_images.pdf")

st.divider()

# ─────────────────────────────────────────────────────────────
# 入力収集
# ─────────────────────────────────────────────────────────────
images_raw: List[Tuple[str, Image.Image, Optional[datetime]]] = []
skipped = 0

if mode == "ドロップ（複数ファイル）":
    uploaded_files = st.file_uploader(
        "ここに JPEG/PNG/HEIC を複数ドロップ",
        type=["jpg", "jpeg", "png", "heic"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        if len(uploaded_files) > MAX_FILES:
            st.warning(f"ファイル数が多いため先頭 {MAX_FILES} 件のみ処理します。")
        for uf in uploaded_files[:MAX_FILES]:
            name = getattr(uf, "name", "image")
            try:
                im = _read_image(uf)
                dt = _get_exif_datetime(im)
                images_raw.append((name, im, dt))
            except Exception as e:
                skipped += 1
                st.warning(f"読み込み失敗をスキップ: {name} ({e})")

elif mode == "フォルダ指定（サーバ上のパス）":
    colA, colB = st.columns([1.2, 1])
    with colA:
        folder_str = st.text_input("フォルダパス（サーバ側）", value=str(Path.home()))
        pattern = st.text_input("ファイルパターン（例: *.jpg, *.* / 空なら拡張子で自動判定）", value="")
    with colB:
        recursive = st.toggle("サブフォルダも含める（再帰）", value=True)
        st.caption("※ この方法はアプリが稼働するサーバ上のファイルにアクセスします。")
    if folder_str:
        folder = Path(folder_str).expanduser().resolve()
        if not folder.exists():
            st.error(f"フォルダが見つかりません: {folder}")
        else:
            paths = _gather_from_folder(folder, recursive, pattern)
            if not paths:
                st.warning("対象画像が見つかりません。パターンや拡張子を確認してください。")
            else:
                if len(paths) > MAX_FILES:
                    st.warning(f"ファイル数が多いため先頭 {MAX_FILES} 件のみ処理します。")
                paths = paths[:MAX_FILES]
                st.info(f"検出: {len(paths)} ファイル")
                for p in paths:
                    try:
                        im = _read_image(p)
                        dt = _get_exif_datetime(im)
                        images_raw.append((p.name, im, dt))
                    except Exception as e:
                        skipped += 1
                        st.warning(f"読み込み失敗をスキップ: {p} ({e})")

elif mode == "ZIPをドロップ（一括）":
    z = st.file_uploader("画像を含むZIPをドロップ", type=["zip"])
    if z is not None:
        try:
            with zipfile.ZipFile(z) as zf:
                items = _gather_from_zip(zf)
            if not items:
                st.warning("ZIP内にJPEG/PNG/HEICが見つかりません。(__MACOSX や ._ が混在している可能性)")
            else:
                if len(items) > MAX_FILES:
                    st.warning(f"ファイル数が多いため先頭 {MAX_FILES} 件のみ処理します。")
                items = items[:MAX_FILES]
                bad = 0
                for name, bio in items:
                    try:
                        im = _read_image(bio)
                        dt = _get_exif_datetime(im)
                        images_raw.append((name, im, dt))
                    except Exception as e:
                        bad += 1
                        st.warning(f"読み込み失敗をスキップ: {name} ({e})")
                if bad:
                    skipped += bad
                st.info(f"ZIP内から {len(items) - bad} 枚を読み込みました（{bad} 件スキップ）。")
        except zipfile.BadZipFile:
            st.error("ZIPが壊れているか、ZIP形式ではありません。")

# ─────────────────────────────────────────────────────────────
# 並び替え
# ─────────────────────────────────────────────────────────────
if images_raw:
    if order_by == "アップロード/取得順":
        images_sorted = images_raw
    elif order_by == "名前（昇順）":
        images_sorted = sorted(images_raw, key=lambda x: x[0])
    elif order_by == "名前（降順）":
        images_sorted = sorted(images_raw, key=lambda x: x[0], reverse=True)
    elif order_by == "EXIF日時（昇順）":
        images_sorted = sorted(images_raw, key=lambda x: (x[2] is None, x[2]))
    else:
        images_sorted = sorted(images_raw, key=lambda x: (x[2] is None, x[2]), reverse=True)

    # プレビュー
    st.subheader("プレビュー")
    cols = st.columns(4)
    for i, (name, im, dt) in enumerate(images_sorted):
        cap = f"{i+1}. {name}" + (f"\n{dt.strftime('%Y-%m-%d %H:%M:%S')}" if dt else "")
        with cols[i % 4]:
            st.image(im, caption=cap, use_container_width=True)

    # PDF生成
    st.subheader("PDF生成")
    pages: List[Image.Image] = []
    if layout_mode.startswith("画像ピクセル"):
        for _, im, _ in images_sorted:
            pages.append(im if im.mode == "RGB" else im.convert("RGB"))
    else:
        for _, im, _ in images_sorted:
            pages.append(
                _compose_on_a4(
                    im,
                    dpi=dpi,
                    landscape=landscape,
                    fill_color=bg_color,
                    fit_mode=fit_mode,
                    margin_pct=margin_pct,
                )
            )

    if pages:
        pdf_bytes = _build_pdf_bytes(pages)
        st.download_button(
            "📄 PDFをダウンロード",
            data=pdf_bytes,
            file_name=default_name or "merged_images.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.success(f"PDFを作成しました（{len(pages)}ページ / スキップ {skipped} 件）")
else:
    st.info("上の入力モードから画像を用意してください。")
