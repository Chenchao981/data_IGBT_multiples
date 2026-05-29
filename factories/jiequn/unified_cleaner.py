#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
杰群 联合清洗器 — 从统一 CSV 中一次提取 DC/DVDS/RG

适用于所有参数在同一个 CSV 文件中的批次，一次运行输出三个 Excel。
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
from factories.jiequn.csv_parser import parse_dta_csv
from factories.jiequn.config import UNIT_CONVERSIONS
from shared.excel_utils import write_excel_fast, generate_lot_based_filename

logger = logging.getLogger(__name__)

DC_PARAMS = ["VTH", "BVDSS", "IDSS", "IGSS", "ISGS", "RDON", "VF", "VFSDS"]
DVDS_PARAMS = ["DVDS"]
RG_PARAMS = ["LCR-RG"]

# 数值单位换算
NUM_CONV = {"IDSS": 1e9, "IGSS": 1e9, "ISGS": 1e9, "RDON": 1000, "DVDS": 1000}


def _apply_conv(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if col in ('周记', 'NUM'):
            continue
        for pn, factor in NUM_CONV.items():
            if pn.upper() in col.upper():
                df[col] = pd.to_numeric(df[col], errors='coerce') * factor
                break
    return df


def process_unified(input_dir: str, output_dir: str) -> bool:
    inp = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(inp.glob("*DTA.CSV")) or sorted(inp.glob("*DTA.csv")) or sorted(inp.glob("*.CSV")) or sorted(inp.glob("*.csv"))
    if not csv_files:
        logger.error(f"未找到 CSV: {input_dir}")
        return False

    logger.info(f"联合清洗: {len(csv_files)} 个文件")

    types = [
        ("DC",   DC_PARAMS,   False),   # DC: 获取所有实例
        ("DVDS", DVDS_PARAMS, True),    # DVDS: 只要第一个
        ("RG",   RG_PARAMS,   True),    # RG: 只要第一个
    ]
    all_ok = True

    for label, params, unique in types:
        dfs = []
        for f in csv_files:
            df = parse_dta_csv(str(f), params, unique_only=unique)
            if df is not None and not df.empty:
                dfs.append(df)

        if not dfs:
            logger.warning(f"  {label}: 无数据")
            all_ok = False
            continue

        merged = pd.concat(dfs, ignore_index=True, sort=False)
        merged = _apply_conv(merged)
        merged.dropna(subset=['周记'], inplace=True)
        merged.reset_index(drop=True, inplace=True)
        merged.insert(0, 'NUM', range(1, len(merged) + 1))

        zhouji_list = merged['周记'].tolist()
        fname = generate_lot_based_filename(zhouji_list, f"{label}_UNI")
        wpath = out / fname
        write_excel_fast(merged, wpath, sheet_name=f"{label}_Data")
        logger.info(f"  {label}: {len(merged):,} 行 → {wpath.name}")

    return all_ok
