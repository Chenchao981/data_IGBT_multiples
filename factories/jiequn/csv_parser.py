#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
杰群 CSV 数据解析器

杰群测试机台导出的 DTA CSV 文件结构：
    行 ~1-14:  元数据（DTA File Name, Station 等）
    行 ~15:    Test,,1,2,3,...          ← 测试编号行
    行 ~16:    Item,,IDSS,VTH,...       ← 参数名称行 ⭐
    行 ~17-22: Limit / Units / Bias / Time 信息
    行 ~21:    Limit Units,,A,V,...     ← 单位行
    行 ~31-34: Min/Max/Average/STD DEV 公式
    行 ~35:    Serial,Bin,...           ← 数据表头行 ⭐
    行 ~36+:   数据行                    ← 从此处开始读取数据
"""

import csv
import pandas as pd
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


def locate_key_rows(file_path: str, max_scan: int = 40) -> Tuple[int, int, List[str], List[str]]:
    """
    扫描 CSV 头部，定位关键行。

    Returns:
        (item_row_idx, data_start_idx, item_names, serial_headers)
        - item_row_idx: "Item," 行的 0-based 索引
        - data_start_idx: 数据第一行的 0-based 索引（Serial,Bin 的下一行）
        - item_names: Item 行中的参数名列表（对应每一列）
        - serial_headers: Serial,Bin 行中的列名列表
    """
    item_row_idx = -1
    data_start_idx = -1
    item_names = []
    serial_headers = []

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for idx, line in enumerate(f):
            if idx >= max_scan:
                break

            # 简单 split（CSV 不会在头部包含复杂引号）
            parts = [p.strip() for p in line.strip().split(',')]

            if not parts:
                continue

            first = parts[0]

            # 定位 Item 行
            if first == 'Item' and item_row_idx < 0:
                item_row_idx = idx
                item_names = parts[1:]  # 跳过 "Item"

            # 定位 Serial,Bin 行 → 数据从下一行开始
            if first == 'Serial' and data_start_idx < 0:
                data_start_idx = idx + 1  # 数据从下一行开始
                serial_headers = parts

    return item_row_idx, data_start_idx, item_names, serial_headers


def extract_lot_id_jiequn(filename: str) -> str:
    """
    从杰群文件名提取 lot_id（批次号）

    文件名格式: NCEAP065NHD40AG(M)-1J00_1JT1124_250004FA_20260206035739DTA.CSV
    提取: 1JT1124
    """
    pattern = r'(\d+JT\d+)'
    match = re.search(pattern, filename)
    if match:
        return match.group(1)
    return Path(filename).stem


def parse_dta_csv(file_path: str, target_params: List[str], 
                  max_scan: int = 40) -> Optional[pd.DataFrame]:
    """
    解析杰群 DTA CSV 文件，提取目标参数列的数据。

    Args:
        file_path: CSV 文件路径
        target_params: 目标参数名列表，如 ["DVDS_EX"] 或 ["LCR-RG"]
                       会匹配 Item 行中包含这些名称的列
        max_scan: 扫描头部最大行数

    Returns:
        DataFrame，包含 lot_ID 列和目标参数列；失败返回 None
    """
    fname = Path(file_path).name

    # 1. 定位关键行
    item_row_idx, data_start_idx, item_names, serial_headers = locate_key_rows(
        file_path, max_scan
    )

    if item_row_idx < 0:
        print(f"  [WARN] {fname}: 未找到 Item 行")
        return None
    if data_start_idx < 0:
        print(f"  [WARN] {fname}: 未找到 Serial,Bin 行")
        return None

    # 2. 确定目标列索引
    # Item 行和 Serial 行都是从第 3 列开始与数据对齐（前 2 列是 Item/Serial 本身）
    # 数据行: Serial,Bin,val1,val2,... → 从第 3 个字段开始与 item_names 对齐
    target_col_indices = []   # 0-based, 对应 CSV 行中的字段位置
    target_col_names = []     # 最终的列名

    for param in target_params:
        for i, name in enumerate(item_names):
            if param.upper() in name.upper():
                # CSV 字段索引 = i + 1
                # item_names 从 Item 行 parts[1:] 开始:
                #   item_names[0]='' → 无意义 (Item, 后面的空列)
                #   item_names[1]='CONT_TR' → data 字段 2 = val1
                #   通用: item_names[i] → data 字段 i+1
                csv_field_idx = i + 1
                if csv_field_idx not in [x[0] for x in target_col_indices]:
                    target_col_indices.append((csv_field_idx, param))
                    target_col_names.append(param)
                break  # 每组参数只取第一个匹配

    if not target_col_indices:
        print(f"  [WARN] {fname}: 未找到目标参数 {target_params}")
        return None

    # 3. 读取数据行
    lot_id = extract_lot_id_jiequn(fname)
    records = []

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for idx, line in enumerate(f):
            if idx < data_start_idx:
                continue

            parts = [p.strip() for p in line.strip().split(',')]
            if len(parts) < 3:
                continue

            row = {}
            for csv_field_idx, param_name in target_col_indices:
                if csv_field_idx < len(parts):
                    val_str = parts[csv_field_idx]
                    try:
                        row[param_name] = float(val_str)
                    except (ValueError, TypeError):
                        row[param_name] = None

            # 跳过全空行
            if all(v is None for v in row.values()):
                continue

            row['lot_ID'] = lot_id
            records.append(row)

    if not records:
        print(f"  [WARN] {fname}: 未提取到有效数据")
        return None

    df = pd.DataFrame(records)
    # 排序列：lot_ID 在前
    cols = ['lot_ID'] + [c for c in df.columns if c != 'lot_ID']
    df = df[cols]

    print(f"  [OK] {fname}: {len(df)} 行, 参数: {target_col_names}")
    return df
