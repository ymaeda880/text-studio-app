# -*- coding: utf-8 -*-
from __future__ import annotations
import io
from typing import List, Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from PIL import Image, ImageDraw

from .presets import PALETTES

# ---- Plotly プレビュー ----
def make_plotly_fig(
    *, data_kind: str, chart_type: str, work_df: pd.DataFrame,
    x_col: str, y_cols: List[str], group_col: Optional[str],
    chart_title: str, title_bold: bool, title_size: int, title_align: str,
    show_legend: bool, show_grid: bool, markers_on: bool, line_width: float
) -> go.Figure:
    fig = go.Figure()
    if data_kind == "時系列":
        for yc in y_cols:
            if chart_type in ("折れ線", "面"):
                fig.add_trace(go.Scatter(
                    x=work_df[x_col], y=work_df[yc],
                    mode="lines+markers" if markers_on else "lines",
                    line=dict(width=line_width),
                    name=yc, marker=dict(size=6),
                    fill="tozeroy" if chart_type=="面" else None,
                ))
            elif chart_type in ("棒", "積み上げ棒"):
                fig.add_trace(go.Bar(x=work_df[x_col], y=work_df[yc], name=yc))
            elif chart_type == "散布":
                fig.add_trace(go.Scatter(x=work_df[x_col], y=work_df[yc], mode="markers", name=yc, marker=dict(size=8)))
        if chart_type == "積み上げ棒":
            fig.update_layout(barmode="stack")
    else:
        if chart_type == "円":
            yc = y_cols[0]
            if group_col:
                first_g = work_df[group_col].astype(str).unique().tolist()[0]
                tmp = work_df[work_df[group_col].astype(str) == first_g]
                fig.add_trace(go.Pie(labels=tmp[x_col].astype(str), values=tmp[yc], name=str(first_g)))
            else:
                fig.add_trace(go.Pie(labels=work_df[x_col].astype(str), values=work_df[yc]))
        else:
            if group_col:
                for g in work_df[group_col].astype(str).unique():
                    tmp = work_df[work_df[group_col].astype(str) == g]
                    for yc in y_cols:
                        name = f"{yc} ({g})" if len(y_cols)>1 else str(g)
                        if chart_type in ("棒", "積み上げ棒"):
                            fig.add_trace(go.Bar(x=tmp[x_col].astype(str), y=tmp[yc], name=name))
                        elif chart_type == "横棒":
                            fig.add_trace(go.Bar(y=tmp[x_col].astype(str), x=tmp[yc], name=name, orientation="h"))
                if chart_type == "積み上げ棒":
                    fig.update_layout(barmode="stack")
            else:
                for yc in y_cols:
                    if chart_type in ("棒", "積み上げ棒"):
                        fig.add_trace(go.Bar(x=work_df[x_col].astype(str), y=work_df[yc], name=yc))
                    elif chart_type == "横棒":
                        fig.add_trace(go.Bar(y=work_df[x_col].astype(str), x=work_df[yc], name=yc, orientation="h"))
                if chart_type == "積み上げ棒":
                    fig.update_layout(barmode="stack")

    fig.update_layout(
        title=dict(text=f"<b>{chart_title}</b>" if title_bold else chart_title,
                   x=0.5 if title_align=="中央" else 0.0,
                   xanchor="center" if title_align=="中央" else "left",
                   y=0.95, font=dict(size=title_size)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0) if show_legend else dict(visible=False),
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=40),
    )
    if show_grid:
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.08)")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.08)")
    else:
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=False)
    return fig

# ---- Matplotlib + Pillow PNG 出力 ----
def export_png(
    *, data_kind: str, chart_type: str, work_df: pd.DataFrame,
    x_col: str, y_cols: List[str], group_col: Optional[str], stack_mode: str,
    chart_title: str, title_bold: bool, title_size: int, title_align: str,
    show_legend: bool, show_grid: bool, markers_on: bool, line_width: float,
    palette_name: str, out_w: int, out_h: int, out_dpi: int,
    frame_style: str, corner_radius: int, ts_is_datetime: bool
) -> bytes:
    plt.close("all")
    colors = PALETTES[palette_name]
    w_in = out_w / out_dpi
    h_in = out_h / out_dpi
    fig, ax = plt.subplots(figsize=(w_in, h_in), dpi=out_dpi)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")

    if chart_title:
        weight = "bold" if title_bold else "normal"
        loc = "center" if title_align == "中央" else "left"
        ax.set_title(chart_title, fontsize=title_size, weight=weight, loc=loc, pad=12)

    if data_kind == "時系列":
        x = work_df[x_col]
        for i, yc in enumerate(y_cols):
            c = colors[i % len(colors)]
            if chart_type in ("折れ線", "面"):
                ax.plot(x, work_df[yc], linewidth=line_width, marker="o" if markers_on else None, label=yc, color=c)
                if chart_type == "面":
                    ax.fill_between(x, work_df[yc], color=c, alpha=0.25)
            elif chart_type in ("棒", "積み上げ棒"):
                ax.bar(range(len(x)), work_df[yc], label=yc, alpha=0.9, color=c)
                ax.set_xticks(range(len(x)))
                labels = pd.to_datetime(x).dt.strftime("%Y-%m-%d") if ts_is_datetime else pd.Series(x).astype(str)
                ax.set_xticklabels(labels, rotation=0)
            elif chart_type == "散布":
                ax.scatter(x, work_df[yc], label=yc, s=28, color=c)
        if show_grid:
            ax.grid(True, axis="both", alpha=0.25)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=8))
    else:
        if chart_type == "円":
            yc = y_cols[0] if y_cols else None
            if yc:
                if group_col:
                    first = str(work_df[group_col].astype(str).unique()[0])
                    tmp = work_df[work_df[group_col].astype(str) == first]
                    ax.pie(tmp[yc], labels=tmp[x_col].astype(str), autopct="%1.1f%%", startangle=90)
                else:
                    ax.pie(work_df[yc], labels=work_df[x_col].astype(str), autopct="%1.1f%%", startangle=90)
        else:
            cats = work_df[x_col].astype(str).tolist()
            ind = np.arange(len(cats))
            width = max(0.8 / max(1, len(y_cols)), 0.15) if (chart_type != "積み上げ棒") else 0.8

            if group_col:
                groups = work_df[group_col].astype(str).unique().tolist()
                if chart_type == "積み上げ棒":
                    bottoms = np.zeros(len(ind))
                    for gi, g in enumerate(groups):
                        tmp = work_df[work_df[group_col].astype(str) == g]
                        for yi, yc in enumerate(y_cols):
                            vals = tmp.set_index(x_col)[yc].reindex(cats).fillna(0).values
                            if stack_mode == "percent":
                                total = np.zeros(len(ind))
                                for gg in groups:
                                    for yyc in y_cols:
                                        total += work_df[work_df[group_col].astype(str) == gg] \
                                                 .set_index(x_col)[yyc].reindex(cats).fillna(0).values
                                vals = np.divide(vals, np.where(total == 0, 1, total)) * 100
                            ax.bar(ind, vals, bottom=bottoms,
                                   label=f"{g}" if len(y_cols) == 1 else f"{g}-{yc}",
                                   color=colors[(gi + yi) % len(colors)], width=0.8)
                            bottoms += vals
                else:
                    slot = width
                    start = - (len(groups) * len(y_cols) * slot) / 2 + slot / 2
                    for gi, g in enumerate(groups):
                        for yi, yc in enumerate(y_cols):
                            offs = start + (gi * len(y_cols) + yi) * slot
                            tmp = work_df[work_df[group_col].astype(str) == g]
                            vals = tmp.set_index(x_col)[yc].reindex(cats).fillna(0).values
                            if chart_type == "横棒":
                                ax.barh(ind + offs, vals, height=slot * 0.9,
                                        label=f"{g}" if len(y_cols) == 1 else f"{g}-{yc}",
                                        color=colors[(gi + yi) % len(colors)])
                            else:
                                ax.bar(ind + offs, vals, width=slot * 0.9,
                                       label=f"{g}" if len(y_cols) == 1 else f"{g}-{yc}",
                                       color=colors[(gi + yi) % len(colors)])
            else:
                if chart_type == "積み上げ棒":
                    bottoms = np.zeros(len(ind))
                    for yi, yc in enumerate(y_cols):
                        vals = work_df[yc].values
                        if stack_mode == "percent":
                            total = np.sum(np.column_stack([work_df[c].values for c in y_cols]), axis=1)
                            total = np.where(total == 0, 1, total)
                            vals = (vals / total) * 100
                        ax.bar(ind, vals, bottom=bottoms, label=yc, color=colors[yi % len(colors)], width=0.8)
                        bottoms += vals
                else:
                    slot = width
                    start = - (len(y_cols) * slot) / 2 + slot / 2
                    for yi, yc in enumerate(y_cols):
                        offs = start + yi * slot
                        vals = work_df[yc].values
                        if chart_type == "横棒":
                            ax.barh(ind + offs, vals, height=slot * 0.9, label=yc, color=colors[yi % len(colors)])
                        else:
                            ax.bar(ind + offs, vals, width=slot * 0.9, label=yc, color=colors[yi % len(colors)])
                if show_grid:
                    ax.grid(True, axis="y" if chart_type != "横棒" else "x", alpha=0.25)
                if chart_type != "横棒":
                    ax.set_xticks(ind); ax.set_xticklabels(cats, rotation=0)
                else:
                    ax.set_yticks(ind); ax.set_yticklabels(cats)

    if show_legend and ((data_kind == "時系列" and len(y_cols) > 0) or (data_kind == "クロスセクション")):
        ax.legend(loc="best", frameon=False)

    fig.tight_layout(pad=1.2)

    raw_buf = io.BytesIO()
    fig.savefig(raw_buf, format="png", dpi=out_dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none", pad_inches=0.1)
    plt.close(fig)
    raw_buf.seek(0)
    img = Image.open(raw_buf).convert("RGB")

    if frame_style == "なし":
        out_img = img
    else:
        margin = 24
        bg = Image.new("RGB", (img.width + margin * 2, img.height + margin * 2), "white")
        bg.paste(img, (margin, margin))
        draw = ImageDraw.Draw(bg)
        if frame_style == "四角":
            draw.rectangle([8, 8, bg.width - 8, bg.height - 8], outline=(0,0,0), width=2)
        elif frame_style == "角丸":
            rect = [8, 8, bg.width - 8, bg.height - 8]
            try:
                draw.rounded_rectangle(rect, radius=int(corner_radius), outline=(0,0,0), width=2)
            except Exception:
                draw.rectangle(rect, outline=(0,0,0), width=2)
        out_img = bg

    out = io.BytesIO()
    out_img.save(out, format="PNG")
    return out.getvalue()
