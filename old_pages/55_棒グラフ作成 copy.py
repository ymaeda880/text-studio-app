# -*- coding: utf-8 -*-
# pages/56_グラフ作成.py
# （棒グラフ専用・簡潔版：棒の太さのみで見た目を決定 / gapは使わない）
#
# Excel の表をコピペして、Word に貼り付け可能な 2D 棒グラフ(PNG)を生成
# ・1行目: タイトル
# ・2行目: ヘッダー
# ・3行目以降: データ
#
# プレビュー   : Plotly（棒グラフのみ）
# エクスポート : Matplotlib + Pillow（枠なし/四角/角丸）
#
from __future__ import annotations
import io, csv, textwrap, os, tempfile
from typing import List, Optional, Tuple, Dict

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# PNG 出力
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib import font_manager, rcParams
from PIL import Image, ImageDraw

# 解析ユーティリティ（別ファイル）
from lib.graph.parsing_utils import parse_pasted_robust

# =========================
# ページ設定
# =========================
st.set_page_config(page_title="📊 棒グラフ作成（Word貼り付け用｜簡潔版）", page_icon="📊", layout="wide")
st.title("📊 棒グラフ作成（Word貼り付け用｜簡潔版）")
st.caption("1行目=タイトル、2行目=ヘッダー、3行目以降=データ。Excelからそのまま貼り付けてください。")

# =========================
# パレット（最小セット）
# =========================
PALETTES: Dict[str, List[str]] = {
    "Minimal":   ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"],
    "Corporate": ["#2E86AB", "#F6AA1C", "#A23E48", "#33658A", "#55DDE0", "#758E4F"],
    "Playful":   ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6A4C93", "#1A8FE3", "#95D02B"],
}

# =========================
# ヘルパ
# =========================
def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def _auto_bar_width(preview_px: int, num_cats: int, bars_per_cat: int) -> float:
    """
    プレビュー幅から「棒の太さ（相対）」だけを自動算出（0..1）。
    gapは一切使わない方針のため、ここでは width のみ決める。
    """
    preview_px = max(600.0, float(preview_px))
    num_cats = max(1, int(num_cats))
    bars_per_cat = max(1, int(bars_per_cat))

    slot_px = max(24.0, (preview_px - 120.0) / num_cats)  # 左右余白控えめ
    target_px_per_bar = slot_px * 0.70 / bars_per_cat      # 見やすさで7割を棒へ
    target_px_per_bar = float(np.clip(target_px_per_bar, 6.0, 48.0))
    width_norm = float(np.clip(target_px_per_bar / slot_px, 0.10, 0.95))
    return width_norm

# =========================
# PNG用 日本語フォント
# =========================
def setup_japanese_font() -> str:
    uploaded = st.session_state.get("__jp_font_path")
    if uploaded is None:
        with st.sidebar.expander("🈺 日本語フォント（PNG用・任意）", expanded=False):
            st.caption("PNGで日本語が化ける場合は .ttf/.otf をアップロード（例: IPAexGothic, Noto Sans CJK JP）")
            f = st.file_uploader("日本語フォントファイル", type=["ttf","otf"], accept_multiple_files=False, key="__jp_font_upload_sidebar")
            if f:
                save_path = os.path.join(tempfile.gettempdir(), f.name)
                with open(save_path, "wb") as w:
                    w.write(f.read())
                font_manager.fontManager.addfont(save_path)
                st.session_state["__jp_font_path"] = save_path
                uploaded = save_path
                st.success("フォントを登録しました。")

    if uploaded:
        prop = font_manager.FontProperties(fname=uploaded)
        name = prop.get_name()
        rcParams["font.family"] = "sans-serif"
        rcParams["font.sans-serif"] = [name]
        rcParams["axes.unicode_minus"] = False
        return name

    for nm in ["IPAexGothic","IPAGothic","Noto Sans CJK JP","Noto Sans JP",
               "Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic","MS Gothic"]:
        try:
            path = font_manager.findfont(nm, fallback_to_default=False)
            if os.path.exists(path):
                rcParams["font.family"] = "sans-serif"
                rcParams["font.sans-serif"] = [nm]
                rcParams["axes.unicode_minus"] = False
                return nm
        except Exception:
            pass
    rcParams["axes.unicode_minus"] = False
    return "(system default)"


# =========================
# 1) データ貼り付け（ボタン式）
# =========================
st.subheader("1) データ貼り付け")

# 解析実行（ボタン）用コールバック
def _ingest_text():
    raw = st.session_state.get("raw_text", "")
    title, new_df, diag = parse_pasted_robust(raw)
    if new_df.empty:
        st.warning("貼り付けを認識できませんでした。タイトル1行 + 表形式にしてください。")
        # 失敗時は未確定のまま
        st.session_state["__confirmed"] = False
        return

    # 解析成功 → 最新データとして確定
    st.session_state["__df"] = new_df
    st.session_state["__title"] = title
    st.session_state["__diag"] = diag
    st.session_state["__confirmed"] = True
    st.session_state["__raw_hash"] = hash(raw)  # 解析時点の貼り付け内容ハッシュ
    st.session_state["__df_version"] = st.session_state.get("__df_version", 0) + 1

sample_hint = """クラス別成績
クラス\t国語\t数学\t英語
A\t68\t72\t81
B\t75\t65\t78
C\t80\t70\t88
"""

# on_change は使わず、単に入力だけ受ける
st.text_area(
    "Excelの表を貼り付け（1行目=タイトル、2行目=ヘッダー）",
    sample_hint,
    height=180,
    key="raw_text",
)

# 解析ボタン（これを押したときだけ作成を始める）
st.button("▶️ グラフ作成（解析を実行）", type="primary", on_click=_ingest_text, use_container_width=True)

# まだ一度も「グラフ作成」していない場合はここで終了
if "__df" not in st.session_state or not st.session_state.get("__confirmed", False):
    st.info("表を貼り付けたら『グラフ作成（解析を実行）』を押してください。")
    st.stop()

# 以降は、最後に確定したデータを使用
df = st.session_state["__df"]
title_default = st.session_state.get("__title", "")

# 貼り付け内容が解析後に変更されていたら注意喚起（再度ボタンを促す）
current_hash = hash(st.session_state.get("raw_text", ""))
if current_hash != st.session_state.get("__raw_hash"):
    st.warning("貼り付け内容が前回の解析後に変更されています。必要なら再度『グラフ作成』を押して反映してください。")

# 参考表示
st.success(f"タイトル候補：**{title_default or '(未設定)'}**")
st.dataframe(df.head(50), use_container_width=True)

with st.expander("🩺 パース診断（必要時のみ）", expanded=False):
    st.json(st.session_state.get("__diag", {}))


# =========================
# 2) 列選択・整形（棒グラフ専用）
# =========================
st.subheader("2) 列選択・整形")
all_cols = list(df.columns)
x_col = st.selectbox("カテゴリ列（X軸/ラベル）", all_cols, index=0)
y_cols = st.multiselect(
    "Y（系列）列（複数可）",
    [c for c in all_cols if c != x_col],
    default=[c for c in all_cols if c != x_col][:1]
)
if not y_cols:
    st.warning("Y 列を1つ以上選んでください。")
    st.stop()

with st.expander("🔧 グループ化（任意）", expanded=False):
    gc = st.selectbox("グループ化列（例：性別/クラス 等）", ["(なし)"] + all_cols, index=0)
    group_col: Optional[str] = None if gc == "(なし)" else gc
    agg_func = st.selectbox("集計方法", ["sum", "mean", "median", "max", "min"], index=0)

work_df = df[[x_col] + y_cols + ([group_col] if group_col else [])].copy()
if group_col:
    agg_map = {c: getattr(np, agg_func) for c in y_cols}
    work_df = work_df.groupby([x_col, group_col], dropna=False).agg(agg_map).reset_index()
work_df[x_col] = work_df[x_col].astype(str)
if work_df.empty:
    st.warning("プロット対象データが空です。列の選択をご確認ください。")
    st.stop()

# =========================
# 3) 棒グラフ設定
# =========================
st.subheader("3) 棒グラフ設定")
cset1, cset2 = st.columns([1,2])
with cset1:
    orientation = st.radio("向き", ["縦", "横"], index=0, horizontal=True)
with cset2:
    stack_mode  = st.radio("積み上げ", ["なし", "積み上げ", "割合(%)"], index=0, horizontal=True)

# プレビュー幅
if "m_k_preview_width" not in st.session_state:
    st.session_state["m_k_preview_width"] = 820
preview_w = st.slider("プレビューの幅（px）", 300, 1200, st.session_state["m_k_preview_width"], 20, key="m_k_preview_width")

# —— スタイル用デフォルト
def _ensure_default(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default

_defaults = {
    "m_k_chart_title": "",
    "m_k_title_bold": True,
    "m_k_title_size": 22,
    "m_k_title_align": "中央",
    "m_k_show_legend": True,
    "m_k_show_grid": True,
    "m_k_palette_name": "Minimal",
    "m_k_color_alpha": 0.6,
    "m_k_font_family": "(system default)",
    "m_k_frame_style": "角丸",
    "m_k_corner_radius": 20,
    "m_k_out_w": 1200,
    "m_k_out_h": 700,
    "m_k_out_dpi": 220,
}
for _k, _v in _defaults.items():
    _ensure_default(_k, _v)

with st.expander("🎨 スタイル（クイック調整）", expanded=False):
    # フォント
    st.markdown("**🈺 フォント（プレビュー/PNG 共通）**")
    colf1, colf2 = st.columns([1,1])
    with colf1:
        f = st.file_uploader("日本語フォント（.ttf/.otf）", type=["ttf","otf"], key="m_k_font_upload")
        if f:
            save_path = os.path.join(tempfile.gettempdir(), f.name)
            with open(save_path, "wb") as w:
                w.write(f.read())
            font_manager.fontManager.addfont(save_path)
            st.session_state["__jp_font_path"] = save_path
            st.success("フォントを登録しました。")
    with colf2:
        CANDIDATES = [
            "IPAexGothic", "IPAGothic",
            "Noto Sans CJK JP", "Noto Sans JP",
            "Hiragino Sans", "Hiragino Kaku Gothic ProN",
            "Yu Gothic", "Yu Gothic UI",
            "Meiryo", "Meiryo UI",
            "MS Gothic", "MS PGothic"
        ]
        available = []
        for nm in CANDIDATES:
            try:
                p = font_manager.findfont(nm, fallback_to_default=False)
                if os.path.exists(p):
                    available.append(nm)
            except Exception:
                pass
        if st.session_state.get("__jp_font_path"):
            try:
                nm_up = font_manager.FontProperties(fname=st.session_state["__jp_font_path"]).get_name()
                if nm_up and nm_up not in available:
                    available.insert(0, nm_up)
            except Exception:
                pass
        if not available:
            available = ["(system default)"]
        current = st.session_state.get("m_k_font_family")
        if current not in available:
            st.session_state["m_k_font_family"] = available[0]
        current_index = available.index(st.session_state["m_k_font_family"])
        st.selectbox("フォントファミリー", options=available, index=current_index, key="m_k_font_family")

    st.divider()

    # タイトル & 図全体
    c1, c2, c3 = st.columns([1.2,1,1])
    with c1:
        if st.session_state.get("m_k_chart_title", "") == "":
            st.session_state["m_k_chart_title"] = (title_default or "")
        st.text_input("タイトル", key="m_k_chart_title")
        st.checkbox("タイトル太字", key="m_k_title_bold")
        st.slider("タイトル文字サイズ", 10, 36, st.session_state["m_k_title_size"], step=1, key="m_k_title_size")
        st.radio("タイトル位置", ["左","中央"],
                 index=0 if st.session_state["m_k_title_align"] == "左" else 1,
                 horizontal=True, key="m_k_title_align")
    with c2:
        st.checkbox("凡例を表示", key="m_k_show_legend")
        st.checkbox("グリッド表示", key="m_k_show_grid")
        st.selectbox("色パレット", list(PALETTES.keys()),
                     index=list(PALETTES.keys()).index(st.session_state["m_k_palette_name"]),
                     key="m_k_palette_name")
        st.slider("色の透明度（0=透明〜1=不透明）", 0.0, 1.0, st.session_state["m_k_color_alpha"], 0.05, key="m_k_color_alpha")
    with c3:
        # --- PNG 幅（px）：唯一の入力欄 ---
        png_width_px = st.number_input(
            "PNG 幅(px)",
            min_value=300,
            max_value=4000,
            value=st.session_state["m_k_out_w"],
            step=100,
            key="m_k_out_w"
        )
        # cm換算（DPI考慮）
        dpi_val = st.session_state["m_k_out_dpi"]
        png_width_cm = png_width_px / dpi_val * 2.54
        st.caption(f"約 **{png_width_cm:.2f} cm**（DPI={dpi_val}）")

        # 高さ / DPI
        st.number_input("PNG 高さ(px)", min_value=400, max_value=3000, value=st.session_state["m_k_out_h"], step=50,  key="m_k_out_h")
        st.number_input("PNG DPI",      min_value=72,  max_value=600,  value=st.session_state["m_k_out_dpi"], step=10, key="m_k_out_dpi")

    st.divider()

    # 棒の太さ（相対）
    st.markdown("**🧱 棒の太さ（相対・0〜1）**")
    if "k_bar_mode" not in st.session_state:
        st.session_state["k_bar_mode"] = "自動"
    bar_mode = st.radio("モード", ["自動", "手動"], index=0, horizontal=True, key="k_bar_mode")

    if "m_manual_bar_width" not in st.session_state:
        st.session_state["m_manual_bar_width"] = 0.60

    if bar_mode == "手動":
        st.slider("棒の太さ（相対）", 0.10, 1.00, value=float(st.session_state["m_manual_bar_width"]), step=0.01, key="m_manual_bar_width")
    else:
        # 読み取り専用サンプル表示（参考値）
        st.slider("棒の太さ（相対）", 0.10, 1.00, value=0.60, step=0.01, disabled=True)

# —— スタイル値（描画で使用）
chart_title   = st.session_state["m_k_chart_title"]
title_bold    = st.session_state["m_k_title_bold"]
title_size    = st.session_state["m_k_title_size"]
title_align   = st.session_state["m_k_title_align"]
show_legend   = st.session_state["m_k_show_legend"]
show_grid     = st.session_state["m_k_show_grid"]
palette_name  = st.session_state["m_k_palette_name"]
out_w         = int(st.session_state["m_k_out_w"])
out_h         = int(st.session_state["m_k_out_h"])
out_dpi       = int(st.session_state["m_k_out_dpi"])
frame_style   = st.session_state["m_k_frame_style"]
corner_radius = int(st.session_state["m_k_corner_radius"])
color_alpha   = float(st.session_state["m_k_color_alpha"])
font_family   = st.session_state["m_k_font_family"]

# ==== 自動/手動の棒幅を決定 ====
cats = work_df[x_col].astype(str).tolist()
groups_list = work_df[group_col].astype(str).unique().tolist() if ("group_col" in locals() and group_col) else []
num_cats = len(cats)
num_series = len(y_cols)
is_stacked = (stack_mode != "なし")
bars_per_cat = 1 if is_stacked else max(1, num_series * (len(groups_list) if groups_list else 1))

if st.session_state["k_bar_mode"] == "自動":
    bar_width = _auto_bar_width(preview_w, num_cats, bars_per_cat)
else:
    bar_width = float(st.session_state["m_manual_bar_width"])

# 重なりソフト警告（積み上げでない時）
if not is_stacked:
    slots = (len(groups_list) if group_col else 1) * len(y_cols)
    if bar_width * slots > 0.98:
        st.info("棒が重なり気味です。『棒の太さ』を少し下げると見やすくなります。")

# Plotly/PNG 共通カラー
base_colors = PALETTES[palette_name]
plotly_colors_rgba = [_hex_to_rgba(c, color_alpha) for c in base_colors]

# Matplotlib のフォント反映
if font_family and font_family != "(system default)":
    try:
        rcParams["font.family"] = "sans-serif"
        rcParams["font.sans-serif"] = [font_family]
        rcParams["axes.unicode_minus"] = False
    except Exception:
        pass

# =========================
# 4) Plotly プレビュー（棒のみ）
# =========================
st.subheader("4) プレビュー")

# 🔁 再描画ボタン
st.markdown("### 🔄 プレビュー再描画")
if st.button("🔁 再描画を実行", type="primary", use_container_width=True, key="rerender_button"):
    st.session_state["__force_rerender"] = not st.session_state.get("__force_rerender", False)
    st.rerun()

preview_h = int(max(320, min(800, preview_w * 0.58)))


try:
    fig = go.Figure()

    # ---- 棒トレース追加（棒幅は trace の width のみで制御） ----
    color_idx = 0
    if group_col:
        for g in groups_list:
            tmp = work_df[work_df[group_col].astype(str) == g]
            for yc in y_cols:
                col = plotly_colors_rgba[color_idx % len(plotly_colors_rgba)]; color_idx += 1
                name = f"{yc} ({g})" if len(y_cols)>1 else str(g)
                if orientation == "縦":
                    fig.add_trace(go.Bar(x=tmp[x_col], y=tmp[yc], name=name, width=bar_width,
                                         marker=dict(color=col, line=dict(width=0))))
                else:
                    fig.add_trace(go.Bar(y=tmp[x_col], x=tmp[yc], name=name, orientation="h", width=bar_width,
                                         marker=dict(color=col, line=dict(width=0))))
    else:
        for yc in y_cols:
            col = plotly_colors_rgba[color_idx % len(plotly_colors_rgba)]; color_idx += 1
            if orientation == "縦":
                fig.add_trace(go.Bar(x=work_df[x_col], y=work_df[yc], name=yc, width=bar_width,
                                     marker=dict(color=col, line=dict(width=0))))
            else:
                fig.add_trace(go.Bar(y=work_df[x_col], x=work_df[yc], name=yc, orientation="h", width=bar_width,
                                     marker=dict(color=col, line=dict(width=0))))

    # 積み上げ
    fig.update_layout(barmode=("group" if stack_mode=="なし" else "stack" if stack_mode=="積み上げ" else "relative"))

    # レジェンド設定
    legend_cfg = (dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0)
                  if show_legend else dict(visible=False))

    # レイアウト（gapを渡さない）
    fig.update_layout(
        title=dict(
            text=f"<b>{chart_title}</b>" if title_bold else chart_title,
            x=0.5 if title_align=="中央" else 0.0,
            xanchor="center" if title_align=="中央" else "left",
            y=0.95,
            font=dict(size=title_size, family=None if font_family=="(system default)" else font_family)
        ),
        legend=legend_cfg,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=40),
        width=preview_w,
        height=preview_h,
        autosize=False
    )

    # 枠線（必要なら）
    if frame_style := st.session_state["m_k_frame_style"]:
        if frame_style != "なし":
            shape = dict(type="rect", xref="paper", yref="paper", x0=0, y0=0, x1=1, y1=1,
                         line=dict(color="rgba(0,0,0,0.65)" if frame_style=="角丸" else "black", width=2),
                         fillcolor="rgba(0,0,0,0)", layer="above")
            if frame_style == "角丸":
                shape["line"]["dash"] = "dot"
            fig.add_shape(shape)

    # グリッド
    if show_grid:
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.08)")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.08)")
    else:
        fig.update_xaxes(showgrid=False); fig.update_yaxes(showgrid=False)

    st.plotly_chart(fig, use_container_width=False, theme=None, config={"responsive": False})

except Exception as e:
    st.error(f"プレビュー生成エラー: {e}")
    st.stop()


# =========================
# 4.5) Plotly 図を直接ダウンロード（PNG / SVG）
# =========================
import plotly.io as pio

st.markdown("### 📥 Plotly 図のダウンロード")

# Plotly 図 → PNG
try:
    png_bytes = pio.to_image(
        fig,
        format="png",
        width=preview_w,
        height=preview_h,
        scale=2  # 高解像度化（2〜4推奨）
    )
    st.download_button(
        "📊 PlotlyグラフをPNGでダウンロード",
        data=png_bytes,
        file_name="plotly_chart.png",
        mime="image/png",
        use_container_width=True
    )
except Exception as e:
    st.warning(f"PNG生成エラー（kaleido未導入？）: {e}")

# Plotly 図 → SVG
try:
    svg_bytes = pio.to_image(
        fig,
        format="svg",
        width=preview_w,
        height=preview_h,
        scale=1
    )
    st.download_button(
        "🖋️ PlotlyグラフをSVGでダウンロード（ベクター形式）",
        data=svg_bytes,
        file_name="plotly_chart.svg",
        mime="image/svg+xml",
        use_container_width=True
    )
except Exception as e:
    st.warning(f"SVG生成エラー: {e}")




# =========================
# 5) Matplotlib で PNG 生成
# =========================

# --- Plotlyプレビューのサイズに合わせたフォント補正 ---
# Plotlyでは pxベース, Matplotlibは ptベースなので縮小補正をかける
def _scaled_fontsize_for_png(title_size: int, preview_w: int, out_w: int) -> float:
    scale_ratio = min(1.0, preview_w / out_w)  # PNGが大きい場合、タイトルをやや縮小
    # Matplotlibの実フォントサイズはPlotlyより約1.3倍大きく見える → 0.77倍で補正
    return float(title_size * 0.77 * scale_ratio)

# --- 軸ラベル・目盛りフォント補正 ---
def _scaled_tick_fontsize(preview_w: int, out_w: int) -> float:
    # 画面プレビューとPNG幅の比でスケールダウン
    scale_ratio = min(1.0, preview_w / out_w)
    # MatplotlibはPlotlyより約1.3倍大きく見えるため 0.77 倍補正
    return 10.0 * 0.77 * scale_ratio   # 基準を10ptとする


def export_png() -> bytes:
    setup_japanese_font()

    plt.close("all")
    colors = PALETTES[palette_name]
    w_in = out_w / out_dpi
    h_in = out_h / out_dpi
    fig, ax = plt.subplots(figsize=(w_in, h_in), dpi=out_dpi)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    alpha_val = color_alpha

    if chart_title:

        # --- PNGタイトル設定 ---
        scaled_size = _scaled_fontsize_for_png(title_size, preview_w, out_w)
        pad_val = 8 + scaled_size * 0.4

        weight = "bold" if title_bold else "normal"
        loc = "center" if title_align == "中央" else "left"
        # ax.set_title(chart_title, fontsize=title_size, weight=weight, loc=loc, pad=12)
        ax.set_title(
            chart_title,
            fontsize=scaled_size,
            weight=("bold" if title_bold else "normal"),
            loc=("center" if title_align == "中央" else "left"),
            fontname=font_family if font_family != "(system default)" else None,
            pad=pad_val,
        )


    cats_local = work_df[x_col].astype(str).tolist()
    ind = np.arange(len(cats_local))

    # Matplotlib 側も gap を使わず、bar_width だけで見た目を決定
    if stack_mode == "なし":
        if 'group_col' in locals() and group_col:
            groups = work_df[group_col].astype(str).unique().tolist()
            nslots = max(1, len(groups) * len(y_cols))
            slot = bar_width / nslots
            start = - (nslots * slot) / 2 + slot / 2
            for gi, g in enumerate(groups):
                tmp = work_df[work_df[group_col].astype(str) == g]
                for yi, yc in enumerate(y_cols):
                    offs = start + (gi * len(y_cols) + yi) * slot
                    vals = tmp.set_index(x_col)[yc].reindex(cats_local).fillna(0).values
                    color = colors[(gi + yi) % len(colors)]
                    if orientation == "縦":
                        ax.bar(ind + offs, vals, width=slot*0.92, label=f"{g}" if len(y_cols)==1 else f"{g}-{yc}", color=color, alpha=alpha_val)
                    else:
                        ax.barh(ind + offs, vals, height=slot*0.92, label=f"{g}" if len(y_cols)==1 else f"{g}-{yc}", color=color, alpha=alpha_val)
        else:
            nslots = max(1, len(y_cols))
            slot = bar_width / nslots
            start = - (nslots * slot) / 2 + slot / 2
            for yi, yc in enumerate(y_cols):
                offs = start + yi * slot
                vals = work_df[yc].values
                color = colors[yi % len(colors)]
                if orientation == "縦":
                    ax.bar(ind + offs, vals, width=slot*0.92, label=yc, color=color, alpha=alpha_val)
                else:
                    ax.barh(ind + offs, vals, height=slot*0.92, label=yc, color=color, alpha=alpha_val)

    else:
        if orientation == "縦":
            bottoms = np.zeros(len(ind))
            if 'group_col' in locals() and group_col:
                groups = work_df[group_col].astype(str).unique().tolist()
                if stack_mode == "割合(%)":
                    total = np.zeros(len(ind))
                    for g in groups:
                        tmp = work_df[work_df[group_col].astype(str) == g]
                        for yc in y_cols:
                            total += tmp.set_index(x_col)[yc].reindex(cats_local).fillna(0).values
                    total = np.where(total == 0, 1, total)
                for gi, g in enumerate(groups):
                    tmp = work_df[work_df[group_col].astype(str) == g]
                    for yi, yc in enumerate(y_cols):
                        vals = tmp.set_index(x_col)[yc].reindex(cats_local).fillna(0).values
                        if stack_mode == "割合(%)":
                            vals = (vals / total) * 100
                        color = colors[(gi + yi) % len(colors)]
                        ax.bar(ind, vals, bottom=bottoms, width=bar_width, label=f"{g}" if len(y_cols)==1 else f"{g}-{yc}", color=color, alpha=alpha_val)
                        bottoms += vals
            else:
                if stack_mode == "割合(%)":
                    total = np.sum(np.column_stack([work_df[c].values for c in y_cols]), axis=1)
                    total = np.where(total == 0, 1, total)
                bottoms = np.zeros(len(ind))
                for yi, yc in enumerate(y_cols):
                    vals = work_df[yc].values
                    if stack_mode == "割合(%)":
                        vals = (vals / total) * 100
                    color = colors[yi % len(colors)]
                    ax.bar(ind, vals, bottom=bottoms, width=bar_width, label=yc, color=color, alpha=alpha_val)
                    bottoms += vals
        else:
            bottoms = np.zeros(len(ind))
            if 'group_col' in locals() and group_col:
                groups = work_df[group_col].astype(str).unique().tolist()
                if stack_mode == "割合(%)":
                    total = np.zeros(len(ind))
                    for g in groups:
                        tmp = work_df[work_df[group_col].astype(str) == g]
                        for yc in y_cols:
                            total += tmp.set_index(x_col)[yc].reindex(cats_local).fillna(0).values
                    total = np.where(total == 0, 1, total)
                for gi, g in enumerate(groups):
                    tmp = work_df[work_df[group_col].astype(str) == g]
                    for yi, yc in enumerate(y_cols):
                        vals = tmp.set_index(x_col)[yc].reindex(cats_local).fillna(0).values
                        if stack_mode == "割合(%)":
                            vals = (vals / total) * 100
                        color = colors[(gi + yi) % len(colors)]
                        ax.barh(ind, vals, left=bottoms, height=bar_width, label=f"{g}" if len(y_cols)==1 else f"{g}-{yc}", color=color, alpha=alpha_val)
                        bottoms += vals
            else:
                if stack_mode == "割合(%)":
                    total = np.sum(np.column_stack([work_df[c].values for c in y_cols]), axis=1)
                    total = np.where(total == 0, 1, total)
                bottoms = np.zeros(len(ind))
                for yi, yc in enumerate(y_cols):
                    vals = work_df[yc].values
                    if stack_mode == "割合(%)":
                        vals = (vals / total) * 100
                    color = colors[yi % len(colors)]
                    ax.barh(ind, vals, left=bottoms, height=bar_width, label=yc, color=color, alpha=alpha_val)
                    bottoms += vals


    # =========================
    # 軸・凡例・グリッド設定（フォント補正込み）
    # =========================

    tick_size = _scaled_tick_fontsize(preview_w, out_w)
    is_vertical = (orientation == "縦")

    if is_vertical:
        # 縦棒：カテゴリ軸 = X軸、値軸 = Y軸
        ax.set_xticks(ind)
        ax.set_xticklabels(cats_local, rotation=0)
        ax.yaxis.set_major_locator(MaxNLocator(nbins=min(12, len(ind))))
    else:
        # 横棒：カテゴリ軸 = Y軸、値軸 = X軸
        ax.set_yticks(ind)
        ax.set_yticklabels(cats_local)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=min(12, len(ind))))

    # 両軸の目盛フォントを統一して補正
    ax.tick_params(axis="x", labelsize=tick_size)
    ax.tick_params(axis="y", labelsize=tick_size)

    # グリッド
    if show_grid:
        ax.grid(True, axis=("y" if is_vertical else "x"), alpha=0.25)

    # 凡例
    if show_legend:
        ax.legend(loc="best", frameon=False, fontsize=tick_size)

    fig.tight_layout(pad=1.2)





    # PNG 保存 → PIL → 枠線付与
    raw_buf = io.BytesIO()
    fig.savefig(raw_buf, format="png", dpi=out_dpi,
                bbox_inches="tight", facecolor=fig.get_facecolor(),
                edgecolor="none", pad_inches=0.1)
    plt.close(fig)
    raw_buf.seek(0)
    img = Image.open(raw_buf).convert("RGB")

    # PNG側の枠線
    use_frame = frame_style
    if use_frame == "なし":
        out_img = img
    else:
        margin = 24
        bg = Image.new("RGB", (img.width + margin*2, img.height + margin*2), "white")
        bg.paste(img, (margin, margin))
        draw = ImageDraw.Draw(bg)
        if use_frame == "四角":
            draw.rectangle([8, 8, bg.width-8, bg.height-8], outline=(0,0,0), width=2)
        elif use_frame == "角丸":
            rect = [8, 8, bg.width-8, bg.height-8]
            try:
                draw.rounded_rectangle(rect, radius=int(corner_radius), outline=(0,0,0), width=2)
            except Exception:
                draw.rectangle(rect, outline=(0,0,0), width=2)
        out_img = bg

    out = io.BytesIO()
    out_img.save(out, format="PNG")
    return out.getvalue()

# =========================
# 6) 生成・ダウンロード
# =========================
st.subheader("5) 生成・ダウンロード")
if "__png_bytes" not in st.session_state:
    st.session_state["__png_bytes"] = None

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📊 PNGを生成", use_container_width=True):
        try:
            st.session_state["__png_bytes"] = export_png()
            st.success("PNG を生成しました。右のボタンからダウンロードできます。下にプレビューも表示します。")
        except Exception as e:
            st.session_state["__png_bytes"] = None
            st.error(f"PNG 生成エラー: {e}")

with c2:
    if st.session_state["__png_bytes"]:
        st.download_button("📥 PNG をダウンロード（Word用）",
                           data=st.session_state["__png_bytes"],
                           file_name="bar_chart.png", mime="image/png",
                           use_container_width=True)
    else:
        st.info("まず左のボタンで PNG を生成してください。")

with c3:
    if st.button("🧹 生成結果をクリア", use_container_width=True):
        st.session_state["__png_bytes"] = None
        st.rerun()

if st.session_state["__png_bytes"]:
    st.image(st.session_state["__png_bytes"], caption="Word貼り付け用 PNG", use_column_width=True)
