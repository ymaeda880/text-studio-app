# -*- coding: utf-8 -*-
# lib/graph/bar/data_input.py
#
# 「1) データ貼り付け」パネル（完全スリム版）
# - Excel貼り付け → DataFrame 化
# - タイトル候補表示（m_k_chart_title を利用）
# - パース診断
#
# 呼び出し側:
#   df = render_data_input(sample_hint, mini_toggle)

from __future__ import annotations

import io
import streamlit as st
import pandas as pd

from lib.graph.parsing_utils import parse_pasted_robust


def render_data_input(sample_hint: str, mini_toggle) -> pd.DataFrame:
    """
    「1) データ貼り付け」UI を描画し、解析済み DataFrame を返す。
    """
    # ※ 見出しは pages 側で出しているのでここでは出さない

    # ---- タイトルなし用の簡易パーサ ----
    def _parse_no_title(raw: str) -> tuple[pd.DataFrame, dict]:
        """
        1行目をヘッダー、2行目以降をデータとして解釈する簡易パーサ。
        デリミタはタブ/カンマ/セミコロンのどれかを優先的に使用。
        """
        diag: dict = {"mode": "no_title", "lines": 0, "delimiter": None}

        # テキスト整形
        t = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
        lines = [ln.rstrip() for ln in t.split("\n")]

        # 先頭の空行を削除
        while lines and lines[0].strip() == "":
            lines.pop(0)
        # 末尾側の余計な空行を削る
        while len(lines) >= 2 and lines[-1].strip() == "" and lines[-2].strip() == "":
            lines.pop()

        diag["lines"] = len(lines)

        if len(lines) < 2:
            diag["reason"] = "need_header_and_at_least_1_data_row"
            return pd.DataFrame(), diag

        header_line = lines[0]
        data_lines = lines[1:]
        text_for_pandas = "\n".join([header_line] + data_lines)

        # デリミタ判定（Excel貼り付けを想定してタブ優先）
        delim = None
        for cand in ["\t", ",", ";"]:
            if cand in header_line:
                delim = cand
                break

        diag["delimiter"] = repr(delim) if delim is not None else None

        try:
            if delim is not None:
                df = pd.read_csv(io.StringIO(text_for_pandas), sep=delim)
            else:
                # デリミタ不明 → header=0 で pandas に任せる
                df = pd.read_csv(io.StringIO(text_for_pandas), header=0)
        except Exception as e:
            diag["reason"] = f"pandas_error: {e}"
            return pd.DataFrame(), diag

        diag["reason"] = "ok"
        return df, diag

    # ---- 内部コールバック：貼り付けテキストを解析 ----
    def _ingest_text():
        raw = st.session_state.get("raw_text", "")
        title_row_mode = st.session_state.get("m_k_title_row_mode", "1行目はタイトル")

        if title_row_mode.startswith("タイトルなし"):
            # 1行目 = ヘッダー として解釈（グラフタイトルは空）
            new_df, diag = _parse_no_title(raw)
            title = ""
        else:
            # 従来どおり：1行目=タイトル, 2行目=ヘッダー
            title, new_df, diag = parse_pasted_robust(raw)

        if new_df.empty:
            if title_row_mode.startswith("タイトルなし"):
                st.warning(
                    "貼り付けを認識できませんでした。"
                    "『タイトルなし（1行目からヘッダー）』として処理しましたが、"
                    "表形式になっているかご確認ください。"
                )
            else:
                st.warning("貼り付けを認識できませんでした。タイトル1行 + 表形式にしてください。")
            return

        # パース結果を保存
        st.session_state["data_df"] = new_df
        st.session_state["data_diag"] = diag
        st.session_state["data_title"] = title or ""

        # グラフタイトル：タイトル行があるときはそれを、ないときは空にする
        st.session_state["m_k_chart_title"] = title or ""

        # 軸タイトルも毎回上書き
        cols = list(new_df.columns)
        if cols:
            st.session_state["m_k_x_title"] = cols[0]

        y_cols = cols[1:]
        if y_cols:
            st.session_state["m_k_y_title"] = (
                " / ".join(y_cols) if len(y_cols) <= 3 else f"{len(y_cols)}系列"
            )

    # ---- テキスト入力欄 ----
    st.text_area(
        "Excelの表を貼り付け（1行目=タイトル or ヘッダー）",
        sample_hint,
        height=180,
        key="raw_text",
    )

    # ---- 解析実行ボタン ----
    st.button(
        "▶️ グラフ作成（データの解析を実行）",
        type="primary",
        on_click=_ingest_text,
        use_container_width=True,
    )

    # ---- 解析前なら案内して停止 ----
    if "data_df" not in st.session_state:
        st.info("表を貼り付けたら『グラフ作成（データの解析を実行）』を押してください。")
        st.stop()

    # ---- 解析済み ----
    df = st.session_state["data_df"]
    chart_title = st.session_state.get("m_k_chart_title", "")

    # タイトル候補表示
    st.success(f"タイトル候補：**{chart_title or '(未設定)'}**")

    # 上位 50 行のプレビュー
    st.dataframe(df.head(50), use_container_width=True)

    # ---- パース診断（ミニトグル + エクスパンダ） ----
    st.markdown('<div class="mini-toggle-row"></div>', unsafe_allow_html=True)
    mini_toggle("🩺 パース診断を開く（状態を保持）", key="exp_diag_open")

    with st.expander("🩺 パース診断（必要時のみ）", expanded=st.session_state["exp_diag_open"]):
        st.json(st.session_state.get("data_diag", {}))

    return df
