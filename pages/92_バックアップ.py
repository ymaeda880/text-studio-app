# -*- coding: utf-8 -*-
# projects/text_studio_project/text_studio_app/pages/92_バックアップ.py

from __future__ import annotations
from pathlib import Path
import shutil
import streamlit as st
import tomllib

st.set_page_config(page_title="バックアップ & 復元（出力付き）", page_icon="💾", layout="wide")
st.title("💾 data フォルダのバックアップ & 復元（コピー一覧付き）")

# 1) location → root1/root2
PROJECTS_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT      = Path(__file__).resolve().parents[1]
SECRETS_PATH  = PROJECTS_ROOT / "command_station_project" / "command_station_app" / ".streamlit" / "secrets.toml"

with SECRETS_PATH.open("rb") as f:
    location = tomllib.load(f)["env"]["location"]

if location in ("Home", "Portable", "Prec"):
    root1, root2 = Path("/Volumes/Extreme SSD"), Path("/Volumes/Extreme Pro")
elif location == "Server":
    root1, root2 = Path("/mnt/backup1"), Path("/mnt/backup2")
else:
    st.error("root1 / root2 が未定義です。location を確認してください。"); st.stop()

# 2) パス設定
SRC_ROOT   = APP_ROOT / "data"
choice     = st.radio("バックアップ先ルート", ("root1", "root2"), horizontal=True)
TARGET     = root1 if choice == "root1" else root2
BACKUP_DST = TARGET / "text_studio_backup" / "data"
#st.caption(f"location=**{location}**, src=`{SRC_ROOT}`, backup=`{BACKUP_DST}`")
# st.caption(
#     f"**location:** {location}\n"
#     f"**src:** `{SRC_ROOT}`\n"
#     f"**backup:** `{BACKUP_DST}`"
# )
st.markdown(
    f"**location:** {location}<br>"
    f"**src:** `{SRC_ROOT}`<br>"
    f"**backup:** `{BACKUP_DST}`",
    unsafe_allow_html=True,
)
# 3) ファイル比較 & コピー処理
def same_file(src: Path, dst: Path) -> bool:
    try:
        s, d = src.stat(), dst.stat()
        return int(s.st_mtime) == int(d.st_mtime) and s.st_size == d.st_size
    except FileNotFoundError:
        return False

def sync_dir(src_root: Path, dst_root: Path) -> tuple[int, int, int, list[str]]:
    copied = skipped = failed = 0
    copied_files: list[str] = []
    files = [p for p in src_root.rglob("*") if p.is_file()]
    total = max(len(files), 1)
    prog = st.progress(0)

    for i, s in enumerate(files, 1):
        rel = s.relative_to(src_root)
        d = dst_root / rel
        try:
            d.parent.mkdir(parents=True, exist_ok=True)
            if d.exists() and same_file(s, d):
                skipped += 1
            else:
                shutil.copy2(s, d)
                copied += 1
                copied_files.append(str(rel))
        except Exception as e:
            failed += 1
            st.write(f"❌ {rel}: {e}")
        prog.progress(i / total)
    return copied, skipped, failed, copied_files

# 4) 実行ボタン
b1, b2 = st.columns(2)
if not SRC_ROOT.exists():
    st.error(f"ソースが見つかりません: {SRC_ROOT}"); st.stop()
if not TARGET.exists():
    st.warning(f"選択ルートが存在しません: {TARGET}（外部SSDの接続を確認）")

if b1.button("⬆️ バックアップ（app → backup）", use_container_width=True):
    c, s, f, files = sync_dir(SRC_ROOT, BACKUP_DST)
    st.success(f"✅ backup 完了: コピー {c} / スキップ {s} / 失敗 {f}")
    if files:
        with st.expander("📋 コピーしたファイル一覧", expanded=False):
            st.code("\n".join(files), language="text")

if b2.button("⬇️ 復元（backup → app）", use_container_width=True):
    if not BACKUP_DST.exists():
        st.error("バックアップ元が見つかりません。先にバックアップを作成してください。")
    else:
        c, s, f, files = sync_dir(BACKUP_DST, SRC_ROOT)
        st.success(f"✅ restore 完了: コピー {c} / スキップ {s} / 失敗 {f}")
        if files:
            with st.expander("📋 コピーしたファイル一覧", expanded=False):
                st.code("\n".join(files), language="text")
