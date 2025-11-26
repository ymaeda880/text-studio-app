# -*- coding: utf-8 -*-
#lib/graph/gantt/utils.py
import pandas as pd


def first_non_empty(values: pd.Series) -> str:
    """最初に見つかった非空備考を返す。"""
    for v in values:
        s = str(v).strip()
        if s:
            return s
    return ""
