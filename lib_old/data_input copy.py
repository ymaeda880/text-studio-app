# -*- coding: utf-8 -*-
# lib/graph/bar/data_input.py
#
# 「1) データ貼り付け」パネル（スケーリング付き）
# - Excel貼り付け → DataFrame 化
# - スケール指数 10^x を指定して数値列をスケーリング
# - スケーリング対象列を選択可能
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
    「1) データ貼り付け」UI を描画し、スケーリング後 DataFrame を返す。
    """

    # -----------------------------
    # 0) スケール指数入力（10^x を掛ける）
    # -----------------------------
    # 旧キー scale_exponent が残っている場合も吸収しつつ、
    # 最終的には m_k_scale_exp_data を正とする
    if "m_k_scale_exp_data" not in st.session_state:
        # ① まず昔のキー scale_exponent があればそれを採用
        if "scale_exponent" in st.session_state:
            st.session_state["m_k_scale_exp_data"] = int(st.session_state["scale_exponent"])
        else:
            # ② それも無ければ 0（または DEFAULTS の値）で初期化
            st.session_state["m_k_scale_exp_data"] = 0

    st.number_input(
        "スケール指数 × (10^x を掛ける)",
        min_value=-15,
        max_value=15,
        step=1,
        key="m_k_scale_exp_data",   # ★ ここを m_k_scale_exp_data に変更
    )

    # -----------------------------
    # 1) タイトルなし用の簡易パーサ
    # -----------------------------
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

    # -----------------------------
    # 2) 内部コールバック：貼り付けテキストを解析 & スケーリング
    # -----------------------------
    def _ingest_text():
        raw = st.session_state.get("raw_text", "")
        title_row_mode = st.session_state.get("m_k_title_row_mode", "1行目はタイトル")

        # ① 生データ DataFrame を作る
        if title_row_mode.startswith("タイトルなし"):
            # 1行目 = ヘッダー として解釈（グラフタイトルは空）
            base_df, diag = _parse_no_title(raw)
            title = ""
        else:
            # 1行目=タイトル, 2行目=ヘッダー
            title, base_df, diag = parse_pasted_robust(raw)

        if base_df.empty:
            if title_row_mode.startswith("タイトルなし"):
                st.warning(
                    "貼り付けを認識できませんでした。"
                    "『タイトルなし（1行目からヘッダー）』として処理しましたが、"
                    "表形式になっているかご確認ください。"
                )
            else:
                st.warning("貼り付けを認識できませんでした。タイトル1行 + 表形式にしてください。")
            return

        # ② デフォルトのスケーリング対象列（初回のみ）
        if "scale_target_cols" not in st.session_state:
            # 通常は 1列目がカテゴリなので，2列目以降をデフォルト候補にする
            if len(base_df.columns) >= 2:
                st.session_state["scale_target_cols"] = list(base_df.columns[1:])
            else:
                st.session_state["scale_target_cols"] = list(base_df.columns)

        target_cols = st.session_state.get("scale_target_cols", [])
        exp = int(st.session_state.get("m_k_scale_exp_data", 0))
        factor = 10 ** exp

        # （互換用）旧キーにもミラーしておきたい場合は
        st.session_state["scale_exponent"] = exp

        # ③ スケーリング（base_df → scaled_df）
        scaled_df = base_df.copy()
        if factor != 1:
            for col in target_cols:
                if col not in scaled_df.columns:
                    continue
                s = pd.to_numeric(scaled_df[col], errors="coerce")
                mask = s.notna()
                # 数値に変換できたセルだけスケーリング
                scaled_df.loc[mask, col] = s[mask] * factor

        # ④ 結果を session_state に保存
        st.session_state["data_df_base"] = base_df          # 元データ（非スケーリング）
        st.session_state["data_df"] = scaled_df             # グラフに使うデータ
        st.session_state["data_diag"] = diag
        st.session_state["data_title"] = title or ""

        # グラフタイトル：タイトル行があるときはそれを、ないときは空にする
        st.session_state["m_k_chart_title"] = title or ""

        # 軸タイトルも毎回上書き
        cols = list(base_df.columns)
        if cols:
            st.session_state["m_k_x_title"] = cols[0]

        y_cols = cols[1:]
        if y_cols:
            st.session_state["m_k_y_title"] = (
                " / ".join(y_cols) if len(y_cols) <= 3 else f"{len(y_cols)}系列"
            )

    # -----------------------------
    # 3) テキスト入力欄
    # -----------------------------
    st.text_area(
        "Excelの表を貼り付け（1行目=タイトル or ヘッダー）",
        sample_hint,
        height=180,
        key="raw_text",
    )

    # -----------------------------
    # 4) 解析実行ボタン
    # -----------------------------
    st.button(
        "▶️ グラフ作成（データの解析を実行）",
        type="primary",
        on_click=_ingest_text,
        use_container_width=True,
    )

    # -----------------------------
    # 5) 解析前なら案内して停止
    # -----------------------------
    if "data_df" not in st.session_state:
        st.info("表を貼り付けたら『グラフ作成（データの解析を実行）』を押してください。")
        st.stop()

    # -----------------------------
    # 6) 解析済み：スケーリング対象列の選択 + プレビュー
    # -----------------------------
    df = st.session_state["data_df"]
    chart_title = st.session_state.get("m_k_chart_title", "")

    # スケーリング対象列の選択（グラフ作成後に出る）
    current_targets = st.session_state.get("scale_target_cols", [])
    st.multiselect(
        "スケーリング対象列（10^x を掛ける列）",
        options=list(df.columns),
        default=current_targets,
        key="scale_target_cols",
        help="列の選択を変えた場合は、もう一度『グラフ作成』ボタンを押してください。",
    )

    # タイトル候補表示
    st.success(f"タイトル候補：**{chart_title or '(未設定)'}**")

    # 上位 50 行のプレビュー（スケーリング後）
    st.markdown("#### グラフ用データ（スケーリング後 df）")
    st.dataframe(df.head(50), use_container_width=True)

    # -----------------------------
    # 7) パース診断（ミニトグル + エクスパンダ）
    # -----------------------------
    st.markdown('<div class="mini-toggle-row"></div>', unsafe_allow_html=True)
    mini_toggle("🩺 パース診断を開く（状態を保持）", key="exp_diag_open")

    with st.expander("🩺 パース診断（必要時のみ）", expanded=st.session_state["exp_diag_open"]):
        st.json(st.session_state.get("data_diag", {}))

    return df
