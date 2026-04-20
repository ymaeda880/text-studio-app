# -*- coding: utf-8 -*-
# lib/word_analysis/images.py
#
# 画像ファイル名抽出・ZIP 化

from __future__ import annotations

from typing import List
from io import BytesIO
import os
import zipfile

from docx import Document
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT


BLIP_PATH = ".//a:blip"  # <a:blip r:embed="rIdX"> を拾う


def get_image_filenames_from_paragraph(p: Paragraph) -> List[str]:
    """
    Paragraph 内の drawing から、関連付けられた画像ファイル名を推定して取得する。
    - /word/media/imageX.png などのパスの末尾ファイル名を返す
    """
    filenames: set[str] = set()

    # Paragraph が属する Part（通常 DocumentPart）
    part = p.part
    # rels: rId -> Relationship
    rels = getattr(part, "rels", {})

    for run in p.runs:
        try:
            blips = run._element.xpath(BLIP_PATH)
        except Exception:
            continue

        for blip in blips:
            r_id = blip.get(qn("r:embed"))
            if not r_id:
                continue

            rel = rels.get(r_id)
            if rel is None:
                continue

            # ------------------------------------------------------------
            # External relation は target_part を持たないため除外
            # ------------------------------------------------------------
            if getattr(rel, "is_external", False):
                continue

            try:
                img_part = rel.target_part
            except Exception:
                continue

            # partname: '/word/media/image1.png' → 'image1.png'
            name = os.path.basename(str(getattr(img_part, "partname", "")) or "")
            if name:
                filenames.add(name)

    return sorted(filenames)


def collect_images_as_zip(doc: Document) -> BytesIO:
    """
    Document から画像パーツを集めて ZIP (in-memory) を作成して返す。
    External link の画像は除外する。
    """
    buf = BytesIO()
    added_names: set[str] = set()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in doc.part.rels.values():

            # ------------------------------------------------------------
            # 画像以外は無視
            # ------------------------------------------------------------
            if rel.reltype != RT.IMAGE:
                continue

            # ------------------------------------------------------------
            # External relation は target_part を持たない
            # ------------------------------------------------------------
            if getattr(rel, "is_external", False):
                continue

            try:
                part = rel.target_part
            except Exception:
                continue

            name = os.path.basename(str(getattr(part, "partname", "")) or "")
            if not name:
                continue

            # ------------------------------------------------------------
            # 同名重複を避ける
            # ------------------------------------------------------------
            if name in added_names:
                continue

            try:
                zf.writestr(name, part.blob)
                added_names.add(name)
            except Exception:
                continue

    buf.seek(0)
    return buf


def paragraph_has_image(paragraph):
    """
    Word Paragraph 内に画像 (<w:drawing> or <w:pict>) があるか判定する
    """
    element = paragraph._element

    # drawing 要素（通常の画像）
    if element.xpath('.//w:drawing'):
        return True

    # pict 要素（旧形式）
    if element.xpath('.//w:pict'):
        return True

    # a:blip（画像参照）
    if element.xpath('.//a:blip'):
        return True

    return False