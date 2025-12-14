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
            # python-docx の BaseOxmlElement.xpath は nsmap を内部で解決してくれる
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

            img_part = rel.target_part
            # partname: '/word/media/image1.png' → 'image1.png'
            name = os.path.basename(str(getattr(img_part, "partname", "")) or "")
            if name:
                filenames.add(name)

    return sorted(filenames)


def collect_images_as_zip(doc: Document) -> BytesIO:
    """
    Document から画像パーツを集めて ZIP (in-memory) を作成して返す。
    """
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in doc.part.rels.values():
            if rel.reltype == RT.IMAGE:
                part = rel.target_part
                name = os.path.basename(str(part.partname))
                if not name:
                    continue
                zf.writestr(name, part.blob)
    buf.seek(0)
    return buf


def paragraph_has_image(paragraph):
    """
    Word Paragraph 内に画像 (<w:drawing> or <w:pict>) があるか判定する
    """
    # docx の XML ノードを直接見る
    element = paragraph._element

    # drawing 要素を探す（Word 画像の基本パターン）
    if element.xpath('.//w:drawing'):
        return True

    # pict 要素（古い Word 形式の画像）
    if element.xpath('.//w:pict'):
        return True

    # a:blip があるか確認（画像の実体を指す r:embed）
    if element.xpath('.//a:blip'):
        return True

    return False

