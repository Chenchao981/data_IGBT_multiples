#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Shared output formatting rules for Jiequn cleaners."""

import re
from typing import Iterable

import pandas as pd


BATCH_COL = "批次"
LEGACY_BATCH_COL = "周记"

PARAM_ORDER = [
    "VTH",
    "BVDSS",
    "IDSS",
    "ISGS",
    "IGSS",
    "RDON",
    "LRDON",
    "VF",
    "VFSD",
    "VFSDS",
    "DVDS",
    "RG",
    "CONT",
    "ABSDEL",
    "DELAY",
]

PARAM_ORDER_GROUPS = {
    "ISGS": "GATE_LEAKAGE",
    "IGSS": "GATE_LEAKAGE",
}


def normalize_output_columns(df: pd.DataFrame, data_type: str) -> pd.DataFrame:
    """Apply Jiequn's public output naming and parameter order."""
    df = df.rename(columns={LEGACY_BATCH_COL: BATCH_COL})

    front = [c for c in ("NUM", BATCH_COL, "lot_ID") if c in df.columns]
    params = [c for c in df.columns if c not in front]
    return df[front + sort_param_columns(params, data_type)]


def sort_param_columns(columns: Iterable[str], data_type: str) -> list[str]:
    effective_order = []
    for name in PARAM_ORDER:
        group = PARAM_ORDER_GROUPS.get(name, name)
        if group not in effective_order:
            effective_order.append(group)
    order = {name: idx for idx, name in enumerate(effective_order)}

    def key(col: str):
        base = _param_base(col)
        group = PARAM_ORDER_GROUPS.get(base, base)
        nums = tuple(int(n) for n in re.findall(r"-?\d+", col))
        gate_rank = 0 if base == "ISGS" else 1 if base == "IGSS" else 0
        return (order.get(group, len(order)), nums, gate_rank, col)

    return sorted(columns, key=key)


def _param_base(col: str) -> str:
    name = re.sub(r"\(.*?\)", "", str(col)).upper()
    name = re.sub(r"[-_\d.]+", "", name)
    if name.startswith("LCRRG"):
        return "RG"
    if name.startswith("VFSD") and not name.startswith("VFSDS"):
        return "VFSD"
    for base in PARAM_ORDER:
        if name.startswith(base.replace("-", "")):
            return base
    return name
