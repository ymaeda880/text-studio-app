# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/table/validator.py
# ============================================================
# SlideTex 表構文検証
#
# 機能：
# - 表の行数・列数を確認する
# - 行ごとの列数が一致しているか確認する
# - ヘッダー行数・列数の範囲を確認する
# - <同上>・<同左>の位置を確認する
# - セル結合の参照先が存在するか確認する
#
# 方針：
# - PowerPoint描画処理には依存しない
# - TableDefinitionを変更しない
# - 検証結果をエラーメッセージとして返す
# - frame番号を含む分かりやすいエラーを作る
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from lib.slide_creation.table.models import (
    TableCell,
    TableDefinition,
)


# ============================================================
# 定数
# ============================================================
SUPPORTED_MERGE_DIRECTIONS = {
    "",
    "up",
    "left",
}


# ============================================================
# 内部関数
# ============================================================
def _frame_prefix(
    frame_number: int,
) -> str:
    return (
        f"フレーム{frame_number}："
    )


def _cell_position_label(
    *,
    row_index: int,
    column_index: int,
) -> str:
    # ------------------------------------------------------------
    # 画面表示用のセル位置
    #
    # 内部indexは0始まりだが，
    # メッセージでは1始まりで表示する
    # ------------------------------------------------------------
    return (
        f"{row_index + 1}行"
        f"{column_index + 1}列"
    )


def _get_cell(
    table: TableDefinition,
    *,
    row_index: int,
    column_index: int,
) -> TableCell | None:
    # ------------------------------------------------------------
    # 指定位置のセルを安全に取得する
    # ------------------------------------------------------------
    if row_index < 0:
        return None

    if column_index < 0:
        return None

    if row_index >= len(table.rows):
        return None

    row = table.rows[row_index]

    if column_index >= len(row):
        return None

    return row[column_index]


def _resolve_origin_cell_position(
    table: TableDefinition,
    *,
    row_index: int,
    column_index: int,
) -> tuple[int, int] | None:
    # ------------------------------------------------------------
    # 結合セルが最終的に参照する基準セルを取得する
    #
    # 通常セル：
    #     自分自身を返す
    #
    # <同上>：
    #     上方向へ参照する
    #
    # <同左>：
    #     左方向へ参照する
    #
    # 循環参照や範囲外参照の場合はNoneを返す
    # ------------------------------------------------------------
    current_row = row_index
    current_column = column_index

    visited: set[tuple[int, int]] = set()

    while True:
        position = (
            current_row,
            current_column,
        )

        if position in visited:
            return None

        visited.add(
            position,
        )

        cell = _get_cell(
            table,
            row_index=current_row,
            column_index=current_column,
        )

        if cell is None:
            return None

        if cell.merge_direction == "":
            return (
                current_row,
                current_column,
            )

        if cell.merge_direction == "up":
            current_row -= 1
            continue

        if cell.merge_direction == "left":
            current_column -= 1
            continue

        return None


# ============================================================
# 基本構造検証
# ============================================================
def _validate_table_size(
    table: TableDefinition,
    *,
    frame_number: int,
    errors: list[str],
) -> None:
    prefix = _frame_prefix(
        frame_number,
    )

    if table.row_count <= 0:
        errors.append(
            prefix
            + "tableに行がありません．"
        )
        return

    if table.column_count <= 0:
        errors.append(
            prefix
            + "tableに列がありません．"
        )


def _validate_column_counts(
    table: TableDefinition,
    *,
    frame_number: int,
    errors: list[str],
) -> None:
    # ------------------------------------------------------------
    # すべての行の列数が一致するか確認する
    # ------------------------------------------------------------
    if not table.rows:
        return

    expected_column_count = len(
        table.rows[0],
    )

    prefix = _frame_prefix(
        frame_number,
    )

    for row_index, row in enumerate(
        table.rows,
    ):
        actual_column_count = len(
            row,
        )

        if actual_column_count == expected_column_count:
            continue

        errors.append(
            prefix
            + f"tableの{row_index + 1}行目の列数が"
            + "他の行と一致していません．"
            + f"期待列数={expected_column_count}，"
            + f"実際列数={actual_column_count}"
        )


# ============================================================
# ヘッダー検証
# ============================================================
def _validate_header_spec(
    table: TableDefinition,
    *,
    frame_number: int,
    errors: list[str],
) -> None:
    prefix = _frame_prefix(
        frame_number,
    )

    row_count = table.header.row_count
    column_count = table.header.column_count

    if row_count < 0:
        errors.append(
            prefix
            + "tableのheader行数は"
            + "0以上で指定してください．"
        )

    if column_count < 0:
        errors.append(
            prefix
            + "tableのheader列数は"
            + "0以上で指定してください．"
        )

    if row_count > table.row_count:
        errors.append(
            prefix
            + "tableのheader行数が"
            + "表の行数を超えています．"
            + f"header行数={row_count}，"
            + f"表の行数={table.row_count}"
        )

    if column_count > table.column_count:
        errors.append(
            prefix
            + "tableのheader列数が"
            + "表の列数を超えています．"
            + f"header列数={column_count}，"
            + f"表の列数={table.column_count}"
        )


# ============================================================
# 結合方向検証
# ============================================================
def _validate_merge_directions(
    table: TableDefinition,
    *,
    frame_number: int,
    errors: list[str],
) -> None:
    prefix = _frame_prefix(
        frame_number,
    )

    for row_index, row in enumerate(
        table.rows,
    ):
        for column_index, cell in enumerate(
            row,
        ):
            if (
                cell.merge_direction
                in SUPPORTED_MERGE_DIRECTIONS
            ):
                continue

            position_label = _cell_position_label(
                row_index=row_index,
                column_index=column_index,
            )

            errors.append(
                prefix
                + f"tableの{position_label}に"
                + "未対応のセル結合指定があります："
                + cell.merge_direction
            )


def _validate_merge_positions(
    table: TableDefinition,
    *,
    frame_number: int,
    errors: list[str],
) -> None:
    # ------------------------------------------------------------
    # <同上>・<同左>の使用位置を確認する
    # ------------------------------------------------------------
    prefix = _frame_prefix(
        frame_number,
    )

    for row_index, row in enumerate(
        table.rows,
    ):
        for column_index, cell in enumerate(
            row,
        ):
            position_label = _cell_position_label(
                row_index=row_index,
                column_index=column_index,
            )

            if cell.merge_direction == "up":
                if row_index == 0:
                    errors.append(
                        prefix
                        + f"tableの{position_label}では"
                        + "<同上>を使用できません．"
                        + "第1行には上のセルがありません．"
                    )
                    continue

                above_cell = _get_cell(
                    table,
                    row_index=row_index - 1,
                    column_index=column_index,
                )

                if above_cell is None:
                    errors.append(
                        prefix
                        + f"tableの{position_label}の"
                        + "<同上>が参照するセルを"
                        + "取得できません．"
                    )

            elif cell.merge_direction == "left":
                if column_index == 0:
                    errors.append(
                        prefix
                        + f"tableの{position_label}では"
                        + "<同左>を使用できません．"
                        + "第1列には左のセルがありません．"
                    )
                    continue

                left_cell = _get_cell(
                    table,
                    row_index=row_index,
                    column_index=column_index - 1,
                )

                if left_cell is None:
                    errors.append(
                        prefix
                        + f"tableの{position_label}の"
                        + "<同左>が参照するセルを"
                        + "取得できません．"
                    )


def _validate_merge_origins(
    table: TableDefinition,
    *,
    frame_number: int,
    errors: list[str],
) -> None:
    # ------------------------------------------------------------
    # 結合セルが最終的に通常セルへ到達するか確認する
    # ------------------------------------------------------------
    prefix = _frame_prefix(
        frame_number,
    )

    for row_index, row in enumerate(
        table.rows,
    ):
        for column_index, cell in enumerate(
            row,
        ):
            if not cell.merge_direction:
                continue

            origin = _resolve_origin_cell_position(
                table,
                row_index=row_index,
                column_index=column_index,
            )

            if origin is not None:
                continue

            position_label = _cell_position_label(
                row_index=row_index,
                column_index=column_index,
            )

            errors.append(
                prefix
                + f"tableの{position_label}の"
                + "セル結合先を特定できません．"
            )


# ============================================================
# 結合形状検証
# ============================================================
def _validate_rectangular_merge_groups(
    table: TableDefinition,
    *,
    frame_number: int,
    errors: list[str],
) -> None:
    # ------------------------------------------------------------
    # 同じ基準セルを参照するセル群が矩形になっているか確認する
    #
    # PowerPointのセル結合は矩形範囲だけを扱うため，
    # L字型や飛び地になる結合指定はエラーにする
    # ------------------------------------------------------------
    groups: dict[
        tuple[int, int],
        set[tuple[int, int]],
    ] = {}

    for row_index, row in enumerate(
        table.rows,
    ):
        for column_index, _cell in enumerate(
            row,
        ):
            origin = _resolve_origin_cell_position(
                table,
                row_index=row_index,
                column_index=column_index,
            )

            if origin is None:
                continue

            groups.setdefault(
                origin,
                set(),
            ).add(
                (
                    row_index,
                    column_index,
                )
            )

    prefix = _frame_prefix(
        frame_number,
    )

    for origin, positions in groups.items():
        if len(positions) <= 1:
            continue

        row_indexes = [
            position[0]
            for position in positions
        ]

        column_indexes = [
            position[1]
            for position in positions
        ]

        min_row = min(
            row_indexes,
        )

        max_row = max(
            row_indexes,
        )

        min_column = min(
            column_indexes,
        )

        max_column = max(
            column_indexes,
        )

        expected_positions = {
            (
                row_index,
                column_index,
            )
            for row_index in range(
                min_row,
                max_row + 1,
            )
            for column_index in range(
                min_column,
                max_column + 1,
            )
        }

        if positions == expected_positions:
            continue

        origin_label = _cell_position_label(
            row_index=origin[0],
            column_index=origin[1],
        )

        errors.append(
            prefix
            + f"tableの{origin_label}を基準とする"
            + "セル結合範囲が矩形ではありません．"
            + "<同上>と<同左>は，"
            + "連続した長方形の範囲になるように"
            + "指定してください．"
        )


# ============================================================
# 空セル・内容検証
# ============================================================
def _validate_merge_cell_text(
    table: TableDefinition,
    *,
    frame_number: int,
    errors: list[str],
) -> None:
    # ------------------------------------------------------------
    # 結合指定セルには通常文字列を持たせない
    # ------------------------------------------------------------
    prefix = _frame_prefix(
        frame_number,
    )

    for row_index, row in enumerate(
        table.rows,
    ):
        for column_index, cell in enumerate(
            row,
        ):
            if not cell.merge_direction:
                continue

            if not cell.text.strip():
                continue

            position_label = _cell_position_label(
                row_index=row_index,
                column_index=column_index,
            )

            errors.append(
                prefix
                + f"tableの{position_label}は"
                + "セル結合指定ですが，"
                + "文字列も設定されています．"
            )


# ============================================================
# 公開関数
# ============================================================
def validate_table_definition(
    table: TableDefinition,
    *,
    frame_number: int,
) -> list[str]:
    # ------------------------------------------------------------
    # 表定義全体を検証し，
    # エラーメッセージを返す
    # ------------------------------------------------------------
    errors: list[str] = []

    _validate_table_size(
        table,
        frame_number=frame_number,
        errors=errors,
    )

    _validate_column_counts(
        table,
        frame_number=frame_number,
        errors=errors,
    )

    _validate_header_spec(
        table,
        frame_number=frame_number,
        errors=errors,
    )

    _validate_merge_directions(
        table,
        frame_number=frame_number,
        errors=errors,
    )

    _validate_merge_positions(
        table,
        frame_number=frame_number,
        errors=errors,
    )

    _validate_merge_origins(
        table,
        frame_number=frame_number,
        errors=errors,
    )

    _validate_rectangular_merge_groups(
        table,
        frame_number=frame_number,
        errors=errors,
    )

    _validate_merge_cell_text(
        table,
        frame_number=frame_number,
        errors=errors,
    )

    return errors