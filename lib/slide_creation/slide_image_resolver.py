# -*- coding: utf-8 -*-
# text_studio_app/lib/slide_creation/slide_image_resolver.py
# ============================================================
# SlideTex 画像パス解決
#
# 機能：
# - \image{...}で指定された画像の実パスを解決する
# - 画像自体のフルパス指定に対応する
# - 複数の画像探索先を指定順に検索する
# - inboxからの画像検索に対応する
# - 指定フォルダーを基準とした画像読込に対応する
#
# 方針：
# - WordTex側の処理は変更しない
# - image_pathの複数指定はセミコロンで区切る
# - inbox検索には既存の共通関数を利用する
# - 最初に見つかった画像を使用する
# ============================================================

from __future__ import annotations

# ============================================================
# imports
# ============================================================
from pathlib import Path

from lib.image_embed.inbox_image_resolver import (
    resolve_inbox_image_path_by_filename,
)


# ============================================================
# 探索先分割
# ============================================================
def split_slide_image_paths(
    image_path: str,
) -> list[str]:
    """
    image_pathを複数の探索先へ分割する．

    探索先はセミコロンで区切る．

    例：
        /Users/example/images;inbox

    空文字の場合はinboxだけを返す．
    """

    path_text = str(image_path or "").strip()

    if not path_text:
        return ["inbox"]

    search_paths = [
        value.strip()
        for value in path_text.split(";")
        if value.strip()
    ]

    if not search_paths:
        return ["inbox"]

    return search_paths


# ============================================================
# フォルダー内画像確認
# ============================================================
def _resolve_image_from_directory(
    *,
    directory_text: str,
    image_file: str,
) -> Path | None:
    """
    指定フォルダー内から画像を探す．

    画像が存在する場合はPathを返し，
    存在しない場合はNoneを返す．
    """

    directory = Path(
        directory_text
    ).expanduser()

    candidate_path = (
        directory
        / image_file
    )

    if (
        candidate_path.exists()
        and candidate_path.is_file()
    ):
        return candidate_path

    return None


# ============================================================
# inbox画像確認
# ============================================================
def _resolve_image_from_inbox(
    *,
    inbox_root: Path,
    sub: str,
    image_file: str,
) -> Path | None:
    """
    inboxから画像ファイル名を検索する．
    """

    resolved_path = (
        resolve_inbox_image_path_by_filename(
            inbox_root=inbox_root,
            sub=sub,
            file_name=image_file,
        )
    )

    if (
        resolved_path is not None
        and resolved_path.exists()
        and resolved_path.is_file()
    ):
        return resolved_path

    return None


# ============================================================
# 画像パス解決
# ============================================================
def resolve_slide_image_path(
    *,
    image_file: str,
    image_path: str,
    inbox_root: Path,
    sub: str,
) -> Path:
    """
    SlideTexで指定された画像の実パスを返す．

    優先順位：
    1．image_file自体が絶対パスなら，その画像を使用する
    2．image_pathの探索先を左から順番に検索する
    3．探索先がinboxなら，ユーザーのinboxを検索する
    4．探索先がフォルダーなら，
       フォルダーとimage_fileを結合して確認する

    最初に見つかった画像を返す．

    すべての探索先で見つからない場合は，
    FileNotFoundErrorを送出する．
    """

    image_file_text = str(
        image_file or ""
    ).strip()

    if not image_file_text:
        raise ValueError(
            "画像ファイルが指定されていません．"
        )

    raw_image_path = Path(
        image_file_text
    ).expanduser()

    # --------------------------------------------------------
    # \image{...}自体が絶対パス
    # --------------------------------------------------------
    if raw_image_path.is_absolute():
        if (
            raw_image_path.exists()
            and raw_image_path.is_file()
        ):
            return raw_image_path

        raise FileNotFoundError(
            "指定された画像が見つかりません："
            f"{raw_image_path}"
        )

    # --------------------------------------------------------
    # image_pathを探索先へ分割
    # --------------------------------------------------------
    search_paths = split_slide_image_paths(
        image_path
    )

    searched_locations: list[str] = []

    # --------------------------------------------------------
    # 指定された順番で探索
    # --------------------------------------------------------
    for search_path in search_paths:
        normalized_path = search_path.strip()

        if not normalized_path:
            continue

        # ----------------------------------------------------
        # inbox
        # ----------------------------------------------------
        if normalized_path.lower() == "inbox":
            searched_locations.append(
                f"inbox（ユーザー：{sub}）"
            )

            resolved_path = _resolve_image_from_inbox(
                inbox_root=inbox_root,
                sub=sub,
                image_file=image_file_text,
            )

            if resolved_path is not None:
                return resolved_path

            continue

        # ----------------------------------------------------
        # 指定フォルダー
        # ----------------------------------------------------
        expanded_directory = Path(
            normalized_path
        ).expanduser()

        candidate_path = (
            expanded_directory
            / image_file_text
        )

        searched_locations.append(
            str(candidate_path)
        )

        resolved_path = _resolve_image_from_directory(
            directory_text=normalized_path,
            image_file=image_file_text,
        )

        if resolved_path is not None:
            return resolved_path

    # --------------------------------------------------------
    # すべての探索先で見つからない
    # --------------------------------------------------------
    searched_text = "\n".join(
        f"・{location}"
        for location in searched_locations
    )

    raise FileNotFoundError(
        "画像が見つかりませんでした："
        f"{image_file_text}\n"
        "探索した場所：\n"
        f"{searched_text}"
    )