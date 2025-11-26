# -*- coding: utf-8 -*-
# lib/graph/bar/style_panel.py
#
# 棒グラフの「スタイル」設定用 UI（expander + 擬似タブ）をまとめたモジュール

from __future__ import annotations
from typing import Sequence, Mapping, Callable, Any

import streamlit as st

from lib.graph.bar.presets import HIGHLIGHT_COLOR_CHOICES, NON_HIGHLIGHT_COLOR_CHOICES


def render_style_panel(
    *,
    palettes: Mapping[str, Sequence[str]],
    font_candidates: Sequence[str],
    mini_toggle: Callable[[str, str], Any],
) -> None:
    """
    棒グラフのスタイル設定 UI 一式を描画する。
    - 上部にミニトグル
    - 中は 2 ペイン構成：
        「🎨 スタイル（クイック調整）」か
        「📝 カテゴリラベル（annotation）」かをラジオボタンで切替
      （選択状態は session_state["m_k_style_tab_choice"] に保持）
    """
    # パネル全体の開閉トグル
    mini_toggle("🎛 スタイル / カテゴリラベル設定を開く（状態を保持）", key="exp_style_all_open")

    with st.expander(
        "🎛 スタイル / カテゴリラベル設定",
        expanded=st.session_state.get("exp_style_all_open", False),  # ← False をデフォルトに
        #expanded=st.session_state.get("exp_style_all_open", True),
    ):
        # ===== 擬似タブ（状態を記憶する）=====
        tab_labels = ["🎨 スタイル（クイック調整）", "📝 カテゴリラベル（annotation）"]
        default_label = st.session_state.get("m_k_style_tab_choice", tab_labels[0])

        tab_choice = st.radio(
            "表示する設定",
            tab_labels,
            horizontal=True,
            key="m_k_style_tab_choice",
            index=tab_labels.index(default_label) if default_label in tab_labels else 0,
        )

        # ==============================
        # TAB: 🎨 スタイル（クイック調整）
        # ==============================
        if tab_choice.startswith("🎨"):
            # フォント
            st.markdown("**🈺 フォント（Plotly表示/書き出し）**")
            st.selectbox(
                "フォントファミリー（全体）",
                options=font_candidates,
                index=font_candidates.index(st.session_state["m_k_font_family"])
                if st.session_state["m_k_font_family"] in font_candidates
                else font_candidates.index("(system default)"),
                key="m_k_font_family",
            )

            st.divider()
            c1, c2, c3 = st.columns([1.3, 1.2, 1.2])

            # ------------------------------
            # c1: タイトル・色パレット + ハイライト
            # ------------------------------
            with c1:
                st.text_input("タイトル", key="m_k_chart_title")
                st.checkbox("タイトル太字", key="m_k_title_bold")
                st.slider(
                    "タイトル文字サイズ",
                    10,
                    36,
                    st.session_state["m_k_title_size"],
                    step=1,
                    key="m_k_title_size",
                )
                st.radio(
                    "タイトル位置",
                    ["左", "中央"],
                    index=0 if st.session_state["m_k_title_align"] == "左" else 1,
                    horizontal=True,
                    key="m_k_title_align",
                )
                st.selectbox(
                    "色パレット",
                    list(palettes.keys()),
                    index=list(palettes.keys()).index(st.session_state["m_k_palette_name"]),
                    key="m_k_palette_name",
                )
                st.slider(
                    "色の透明度（0=透明〜1=不透明）",
                    0.0,
                    1.0,
                    st.session_state["m_k_color_alpha"],
                    0.05,
                    key="m_k_color_alpha",
                )

                # 上位カテゴリのハイライト
                st.markdown("**上位カテゴリのハイライト**")
                st.checkbox(
                    "大きい値から順に色を変える",
                    key="m_k_enable_highlight",
                    value=st.session_state["m_k_enable_highlight"],
                )
                st.number_input(
                    "ハイライトする本数（大きい順）",
                    min_value=1,
                    max_value=50,
                    value=int(st.session_state["m_k_highlight_top_k"]),
                    step=1,
                    key="m_k_highlight_top_k",
                )

                # ハイライト色
                hl_label_list = list(HIGHLIGHT_COLOR_CHOICES.keys())
                current_hl_label = st.session_state["m_k_highlight_color_label"]
                hl_idx = hl_label_list.index(current_hl_label)

                selected_hl_label = st.selectbox(
                    "ハイライト色を選択",
                    hl_label_list,
                    index=hl_idx,
                    key="m_k_highlight_color_label",
                )
                st.session_state["m_k_highlight_color"] = HIGHLIGHT_COLOR_CHOICES[selected_hl_label]

                # 非ハイライト色
                nhl_label_list = list(NON_HIGHLIGHT_COLOR_CHOICES.keys())
                current_nhl_label = st.session_state["m_k_nonhighlight_color_label"]
                nhl_idx = nhl_label_list.index(current_nhl_label)

                selected_nhl_label = st.selectbox(
                    "ハイライトしていない棒の色",
                    nhl_label_list,
                    index=nhl_idx,
                    key="m_k_nonhighlight_color_label",
                )
                st.session_state["m_k_nonhighlight_color"] = NON_HIGHLIGHT_COLOR_CHOICES[selected_nhl_label]

            # ------------------------------
            # c2: 軸ラベル・目盛
            # ------------------------------
            with c2:
                st.markdown("**📐 軸ラベル**")
                st.checkbox(
                    "ヘッダー名を軸タイトルに自動適用（未入力のとき）",
                    key="m_k_use_headers_as_axis_title",
                    value=st.session_state.get("m_k_use_headers_as_axis_title", True),
                )
                ax1, ax2 = st.columns(2)
                with ax1:
                    st.text_input("X軸タイトル", key="m_k_x_title")
                    st.number_input(
                        "X軸 title_standoff（px）",
                        0,
                        80,
                        value=int(st.session_state["m_k_x_title_standoff"]),
                        step=1,
                        key="m_k_x_title_standoff",
                    )
                with ax2:
                    st.text_input("Y軸タイトル", key="m_k_y_title")
                    st.number_input(
                        "Y軸 title_standoff（px）",
                        0,
                        80,
                        value=int(st.session_state["m_k_y_title_standoff"]),
                        step=1,
                        key="m_k_y_title_standoff",
                    )
                st.number_input(
                    "軸タイトルのフォントサイズ",
                    8,
                    36,
                    value=int(st.session_state.get("m_k_axis_title_size", 14)),
                    step=1,
                    key="m_k_axis_title_size",
                )
                axis_fonts = ["(グラフ全体と同じ)"] + [f for f in font_candidates if f != "(system default)"]
                st.selectbox(
                    "軸タイトルのフォント",
                    axis_fonts,
                    index=axis_fonts.index(st.session_state.get("m_k_axis_title_family", "(グラフ全体と同じ)"))
                    if st.session_state.get("m_k_axis_title_family") in axis_fonts
                    else 0,
                    key="m_k_axis_title_family",
                )
                st.number_input(
                    "目盛（tick）のフォントサイズ",
                    6,
                    30,
                    value=int(st.session_state.get("m_k_tick_font_size", 12)),
                    step=1,
                    key="m_k_tick_font_size",
                )
                tick_fonts = ["(グラフ全体と同じ)"] + [f for f in font_candidates if f != "(system default)"]
                st.selectbox(
                    "目盛（tick）フォント",
                    tick_fonts,
                    index=tick_fonts.index(st.session_state.get("m_k_tick_font_family", "(グラフ全体と同じ)"))
                    if st.session_state.get("m_k_tick_font_family") in tick_fonts
                    else 0,
                    key="m_k_tick_font_family",
                )

                st.markdown("**📏 目盛（ticks / 長さ / ラベル配置 / 角度）**")
                tx1, tx2 = st.columns(2)
                with tx1:
                    st.selectbox(
                        "X軸 ticks",
                        ["outside", "inside", "(なし)"],
                        key="m_k_ticks_x",
                        index={"outside": 0, "inside": 1, "(なし)": 2}[st.session_state.get("m_k_ticks_x", "outside")],
                    )
                    st.number_input(
                        "X軸 ticklen(px)",
                        0,
                        40,
                        value=int(st.session_state.get("m_k_ticklen_x", 6)),
                        step=1,
                        key="m_k_ticklen_x",
                    )
                    st.selectbox(
                        "X軸 ラベル位置",
                        ["自動", "外-下", "外-上", "内-下", "内-上"],
                        key="m_k_ticklabelpos_x",
                        index=["自動", "外-下", "外-上", "内-下", "内-上"].index(
                            st.session_state.get("m_k_ticklabelpos_x", "自動")
                        ),
                    )
                    st.number_input(
                        "X軸 ラベル角度(°)",
                        -90,
                        90,
                        value=int(st.session_state.get("m_k_tickangle_x", 0)),
                        step=5,
                        key="m_k_tickangle_x",
                    )
                with tx2:
                    st.selectbox(
                        "Y軸 ticks",
                        ["outside", "inside", "(なし)"],
                        key="m_k_ticks_y",
                        index={"outside": 0, "inside": 1, "(なし)": 2}[st.session_state.get("m_k_ticks_y", "outside")],
                    )
                    st.number_input(
                        "Y軸 ticklen(px)",
                        0,
                        40,
                        value=int(st.session_state.get("m_k_ticklen_y", 6)),
                        step=1,
                        key="m_k_ticklen_y",
                    )
                    st.selectbox(
                        "Y軸 ラベル位置",
                        ["自動", "外-左", "外-右", "内-左", "内-右"],
                        key="m_k_ticklabelpos_y",
                        index=["自動", "外-左", "外-右", "内-左", "内-右"].index(
                            st.session_state.get("m_k_ticklabelpos_y", "自動")
                        ),
                    )
                    st.number_input(
                        "Y軸 ラベル角度(°)",
                        -90,
                        90,
                        value=int(st.session_state.get("m_k_tickangle_y", 0)),
                        step=5,
                        key="m_k_tickangle_y",
                    )

            # ------------------------------
            # c3: 凡例・値ラベル
            # ------------------------------
            with c3:
                st.markdown("**🏷️ 凡例・値ラベル**")
                st.checkbox("凡例を表示", key="m_k_show_legend")
                st.selectbox(
                    "凡例の位置",
                    ["外-上", "外-下", "外-左", "外-右", "内-右上", "内-右下", "内-左上", "内-左下"],
                    key="m_k_legend_location",
                )
                st.selectbox("凡例の向き", ["自動", "横(h)", "縦(v)"], key="m_k_legend_orientation")
                st.number_input(
                    "凡例フォントサイズ",
                    8,
                    30,
                    value=int(st.session_state.get("m_k_legend_font_size", 12)),
                    step=1,
                    key="m_k_legend_font_size",
                )
                st.text_input(
                    "凡例 背景色（rgba）",
                    key="m_k_legend_bg",
                    value=st.session_state.get("m_k_legend_bg", "rgba(255,255,255,0.0)"),
                )
                st.text_input(
                    "凡例 枠線色（rgba）",
                    key="m_k_legend_bordercolor",
                    value=st.session_state.get("m_k_legend_bordercolor", "rgba(0,0,0,0.3)"),
                )
                st.number_input(
                    "凡例 枠線幅(px)",
                    0,
                    5,
                    value=int(st.session_state.get("m_k_legend_borderwidth", 0)),
                    step=1,
                    key="m_k_legend_borderwidth",
                )

                st.markdown("**値表示（ラベル）設定**")
                st.selectbox(
                    "値の表示形式",
                    ["そのまま", "カンマ区切り"],
                    index=["そのまま", "カンマ区切り"].index(
                        st.session_state.get("m_k_value_format_mode", "そのまま")
                    ),
                    key="m_k_value_format_mode",
                )
                st.number_input(
                    "値ラベルのフォントサイズ（px）",
                    min_value=6,
                    max_value=40,
                    value=int(st.session_state.get("m_k_label_font_size", 11)),
                    step=1,
                    key="m_k_label_font_size",
                )
                st.selectbox(
                    "値ラベルのフォントファミリー",
                    ["(グラフ全体と同じ)"] + font_candidates,
                    key="m_k_label_font_family",
                )
                st.number_input(
                    "小数点以下の桁数（0〜3 桁）",
                    min_value=0,
                    max_value=3,
                    value=int(st.session_state.get("m_k_label_decimals", 0)),
                    step=1,
                    key="m_k_label_decimals",
                )

            # ------------------------------
            # 余白
            # ------------------------------
            st.divider()
            st.markdown("**📏 余白（margin）**")
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.number_input(
                    "左余白 l(px)",
                    0,
                    300,
                    value=st.session_state.get("m_k_margin_l", 60),
                    step=2,
                    key="m_k_margin_l",
                )
            with m2:
                st.number_input(
                    "右余白 r(px)",
                    0,
                    300,
                    value=st.session_state.get("m_k_margin_r", 20),
                    step=2,
                    key="m_k_margin_r",
                )
            with m3:
                st.number_input(
                    "上余白 t(px)",
                    0,
                    300,
                    value=st.session_state.get("m_k_margin_t", 60),
                    step=2,
                    key="m_k_margin_t",
                )
            with m4:
                st.number_input(
                    "下余白 b(px)",
                    0,
                    300,
                    value=st.session_state.get("m_k_margin_b", 60),
                    step=2,
                    key="m_k_margin_b",
                )

            # ------------------------------
            # 棒の太さ
            # ------------------------------
            st.divider()
            st.markdown("**🧱 棒の太さ（相対・0〜2）**")

            st.radio(
                "モード",
                ["自動", "手動"],
                index=0 if st.session_state.get("m_k_bar_mode", "自動") == "自動" else 1,
                horizontal=True,
                key="m_k_bar_mode",
            )

            st.slider(
                "棒の太さ（相対）",
                0.10,
                2.00,
                step=0.01,
                value=float(st.session_state.get("m_k_bar_width", 1.0)),
                key="m_k_bar_width",
            )

            # ------------------------------
            # 内側枠
            # ------------------------------
            st.divider()
            st.markdown("**🖼️ 枠線（プロット領域 内側）**")
            col_frame_style, col_frame_dash = st.columns(2)
            with col_frame_style:
                frame_style_options = ["なし", "四角"]
                current_frame_style = st.session_state["m_k_frame_style"]
                st.radio(
                    "枠の種類（内側）",
                    frame_style_options,
                    index=frame_style_options.index(current_frame_style),
                    key="m_k_frame_style",
                    horizontal=True,
                )
            with col_frame_dash:
                frame_dash_options = ["実線", "破線", "点線"]
                current_frame_dash = st.session_state["m_k_frame_dash"]
                st.radio(
                    "枠の線種（内側）",
                    frame_dash_options,
                    index=frame_dash_options.index(current_frame_dash),
                    key="m_k_frame_dash",
                    horizontal=True,
                )

            st.checkbox(
                "内側枠をプロット領域（x/y domain）に合わせる",
                key="m_k_frame_ref_domain",
                value=st.session_state.get("m_k_frame_ref_domain", True),
            )

            # ------------------------------
            # プレビュー幅・高さ
            # ------------------------------
            st.divider()
            st.markdown("**📤 プレビュー幅・高さ**")
            col_w, col_h, col_auto = st.columns([1, 1, 1])

            GOLDEN_RATIO = (5 ** 0.5 - 1) / 2  # ≒ 0.618

            with col_w:
                preview_w = st.slider(
                    "プレビューの幅（px）",
                    min_value=300,
                    max_value=1400,
                    value=st.session_state["m_k_preview_width"],
                    step=20,
                    key="m_k_preview_width",
                )
            with col_auto:
                if st.button("高さを自動に計算"):
                    auto_h = int(preview_w * GOLDEN_RATIO)
                    st.session_state["m_k_preview_height"] = auto_h
            with col_h:
                st.slider(
                    "プレビューの高さ（px）",
                    min_value=100,
                    max_value=2000,
                    value=st.session_state["m_k_preview_height"],
                    step=20,
                    key="m_k_preview_height",
                )

            # ------------------------------
            # エクスポート補助
            # ------------------------------
            st.divider()
            st.markdown("**📤 エクスポート補助**")
            st.checkbox(
                "エクスポートサイズをプレビューに同期する（幅=プレビュー幅/高さ=プレビュー高さ）",
                key="sync_export_to_preview",
                value=st.session_state.get("sync_export_to_preview", True),
            )
            st.checkbox(
                "出力を正方形にする（幅=高さ）",
                key="lock_export_square",
                value=st.session_state.get("lock_export_square", False),
            )
            cexp1, cexp2 = st.columns(2)
            with cexp1:
                st.number_input(
                    "出力 幅(px)",
                    min_value=300,
                    max_value=4000,
                    value=int(st.session_state.get("m_k_out_w", preview_w)),
                    step=100,
                    key="m_k_out_w",
                )
            with cexp2:
                st.number_input(
                    "出力 高さ(px)",
                    min_value=300,
                    max_value=4000,
                    value=int(st.session_state.get("m_k_out_h", st.session_state.get("m_k_preview_height", 480))),
                    step=50,
                    key="m_k_out_h",
                )
            st.number_input(
                "PNG DPI相当（scale換算）",
                min_value=72,
                max_value=600,
                value=int(st.session_state.get("m_k_out_dpi", 220)),
                step=10,
                key="m_k_out_dpi",
            )

        # ==============================
        # TAB: 📝 カテゴリラベル（annotation）
        # ==============================
        else:
            st.markdown(
                "軸ラベルではなく、**annotation を使ってカテゴリ名を描画**するための設定です。"
            )

            st.checkbox(
                "カテゴリラベルを annotation で描画する",
                key="m_k_use_annotation_labels",
                value=st.session_state.get("m_k_use_annotation_labels", False),
            )
            st.checkbox(
                "横棒グラフのときだけ annotation を使う",
                key="m_k_anno_horizontal_only",
                value=st.session_state.get("m_k_anno_horizontal_only", True),
            )

            st.divider()
            st.markdown("**フォント・位置**")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.number_input(
                    "annotation フォントサイズ（px）",
                    min_value=6,
                    max_value=40,
                    value=int(st.session_state.get("m_k_anno_font_size", 12)),
                    step=1,
                    key="m_k_anno_font_size",
                )
                anno_fonts = ["(グラフ全体と同じ)"] + [f for f in font_candidates if f != "(system default)"]
                st.selectbox(
                    "annotation フォントファミリー",
                    anno_fonts,
                    index=anno_fonts.index(
                        st.session_state.get("m_k_anno_font_family", "(グラフ全体と同じ)")
                    )
                    if st.session_state.get("m_k_anno_font_family") in anno_fonts
                    else 0,
                    key="m_k_anno_font_family",
                )
                st.text_input(
                    "annotation の文字色（CSSカラー / #000000 など）",
                    key="m_k_anno_color",
                    value=st.session_state.get("m_k_anno_color", "#000000"),
                )
            with col_f2:
                st.slider(
                    "annotation の X 位置（paper 座標 -1〜1）",
                    min_value=-1.0,
                    max_value=1.0,
                    step=0.01,
                    value=float(st.session_state.get("m_k_anno_x", 0.0)),
                    key="m_k_anno_x",
                )

                st.slider(
                    "annotation の Xシフト（px）",
                    min_value=-100,
                    max_value=100,
                    value=int(st.session_state.get("m_k_anno_xshift", -10)),
                    step=1,
                    key="m_k_anno_xshift",
                )

                st.selectbox(
                    "annotation の横方向揃え（align）",
                    ["left", "center", "right"],
                    index=["left", "center", "right"].index(
                        st.session_state.get("m_k_anno_align", "left")
                    ),
                    key="m_k_anno_align",
                )
                st.selectbox(
                    "annotation の X anchor",
                    ["left", "center", "right"],
                    index=["left", "center", "right"].index(
                        st.session_state.get("m_k_anno_xanchor", "right")
                    ),
                    key="m_k_anno_xanchor",
                )
                st.selectbox(
                    "annotation の縦方向位置（yanchor）",
                    ["top", "middle", "bottom"],
                    index=["top", "middle", "bottom"].index(
                        st.session_state.get("m_k_anno_valign", "middle")
                    ),
                    key="m_k_anno_valign",
                )

            st.divider()
            st.markdown("**左側余白の確保**")
            st.number_input(
                "annotation 用 左余白（px）",
                min_value=0,
                max_value=600,
                value=int(st.session_state.get("m_k_anno_margin_left", 260)),
                step=10,
                key="m_k_anno_margin_left",
            )
            st.caption(
                "※ 長い日本語ラベルの場合は 200〜300px 程度を目安に調整してください。"
            )
