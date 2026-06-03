#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
杰群 CSV 数据解析器

杰群测试机台导出的 DTA CSV 文件结构：
    行 ~1-14:  元数据
    行 ~15:    Test,,1,2,3,...          ← 测试编号行
    行 ~16:    Item,,IDSS,VTH,...       ← 参数名称行 ⭐
    行 ~17-18: Min/Max Limit
    行 ~19:    Limit Units,,A,V,...     ← 单位行
    行 ~20:    Bias 1,,IDS,...          ← Bias 描述
    行 ~21:    Bias 1 Value,,1E-2,...   ← 测试条件数值 ⭐
    行 ~22:    Bias 1 Units,,A,...      ← Bias 单位
    行 ~31-34: Min/Max/Average/STD DEV 公式
    行 ~35:    Serial,Bin,...           ← 数据表头行 ⭐
    行 ~36+:   数据行
"""

import pandas as pd
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


def _read_header_lines(file_path: str, max_scan: int = 40) -> List[str]:
    """读取 CSV 头部行"""
    lines = []
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f):
            if i >= max_scan:
                break
            lines.append(line)
    return lines


def _split_line(line: str) -> List[str]:
    return [p.strip() for p in line.strip().split(',')]


def extract_zhouji(filename: str) -> str:
    """
    从杰群文件名提取周记（第二个 _ 和第三个 _ 之间的内容）

    例: NCEAP065NHD40AG(M)-1J00_1JT1124_250004FA_20260206035739DTA.CSV
        → 1JT1124

    例: NCEAP020N10LL(M)-7J00_CJSx185_200000FA_20260104064208DTA.CSV
        → CJSx185
    """
    stem = Path(filename).stem  # 去掉扩展名
    parts = stem.split('_')
    if len(parts) >= 2:
        return parts[1]
    return stem


def locate_key_rows(file_path: str, max_scan: int = 40) -> Tuple[int, int, List[str], List[str]]:
    """
    扫描 CSV 头部，定位关键行。
    Returns: (item_row_idx, data_start_idx, item_names, serial_headers)
    """
    item_row_idx = -1
    data_start_idx = -1
    item_names = []
    serial_headers = []

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for idx, line in enumerate(f):
            if idx >= max_scan:
                break
            parts = _split_line(line)
            if not parts:
                continue
            first = parts[0]
            if first == 'Item' and item_row_idx < 0:
                item_row_idx = idx
                item_names = parts[1:]
            if first == 'Serial' and data_start_idx < 0:
                data_start_idx = idx + 1
                serial_headers = parts

    return item_row_idx, data_start_idx, item_names, serial_headers


def read_header_info(file_path: str, max_scan: int = 40) -> dict:
    """
    读取 CSV 头部关键信息。
    Returns:
        { "item_names": [...], "limit_units": [...], "bias1_values": [...],
          "data_start": int, "item_idx": int }
    """
    lines = _read_header_lines(file_path, max_scan)
    info = {"item_names": [], "limit_units": [], "bias1_values": [],
            "data_start": -1, "item_idx": -1}

    for idx, line in enumerate(lines):
        parts = _split_line(line)
        if not parts:
            continue
        first = parts[0]

        if first == 'Item' and info["item_idx"] < 0:
            info["item_idx"] = idx
            info["item_names"] = parts[1:]

        elif first == 'Limit Units':
            info["limit_units"] = parts[1:]

        elif first == 'Bias 1 Value':
            info["bias1_values"] = parts[1:]

        elif first == 'Serial' and info["data_start"] < 0:
            info["data_start"] = idx + 1

    return info


# 参数类型 → 命名规则
# "seq": 顺序编号 + 单位，如 VTH1(V)
# "bias": 测试条件 + 单位，如 IDSS100(nA)
# "unit": 仅单位，如 VFSD(V)、DVDS(mV)

_PARAM_NAME_RULES = {
    "VTH":    "seq",
    "BVDSS":  "seq",
    "IDSS":   "bias",
    "IGSS":   "bias",
    "ISGS":   "bias",
    "RDON":   "bias",
    "VF":     "unit",
    "VFSDS":  "unit",
    "VFSD":   "unit",
    "DVDS":   "unit",
    "CONT":   "unit",
    "ABSDEL": "seq",
    "DELAY":  "unit",
    "LRDON":  "bias",
}

# 参数 → 固定单位名
_PARAM_UNITS = {
    "VTH":    "V",
    "BVDSS":  "V",
    "IDSS":   "nA",
    "IGSS":   "nA",
    "ISGS":   "nA",
    "RDON":   "mR",
    "VF":     "V",
    "VFSDS":  "V",
    "VFSD":   "V",
    "DVDS":   "mV",
    "CONT":   "V",
    "ABSDEL": "",
    "DELAY":  "",
    "LCR-RG": "R",
    "LRDON":  "mR",
}


def _normalize_item_name(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(name).upper())


def _item_matches_param(item_name: str, target_param: str) -> bool:
    """Match DTA Item cells without letting short names eat longer params."""
    item = str(item_name).strip().upper()
    target = str(target_param).strip().upper()
    norm_item = _normalize_item_name(item)
    norm_target = _normalize_item_name(target)

    aliases = {
        "RDSON": {"RDON", "RDSON"},
        "RDON": {"RDON", "RDSON"},
        "LCRRG": {"LCRRG"},
        "VFSD": {"VFSD"},
        "VFSDS": {"VFSDS"},
    }
    allowed = aliases.get(norm_target)
    if allowed is not None:
        return norm_item in allowed

    if norm_target == "VF":
        return norm_item == "VF" or item.startswith("VF_") or item.startswith("VF-")

    if norm_item == norm_target:
        return True
    return item.startswith(target) and len(item) > len(target) and not item[len(target)].isalnum()


def _get_bias_value(bias_values: List[str], csv_field_idx: int) -> str:
    """获取某列的 Bias 1 Value"""
    # bias_values 从 parts[1:] 开始，bias_values[i] 对应 csv_field_idx = i+1
    i = csv_field_idx - 1
    if 0 <= i < len(bias_values):
        val = bias_values[i].strip()
        if val:
            # 科学计数法 → 整数
            try:
                num = float(val)
                if num == int(num) and num != 0:
                    return str(int(num))
                elif num != 0:
                    return str(num).rstrip('0').rstrip('.')
            except ValueError:
                return val
    return ""


def _get_unit(limit_units: List[str], csv_field_idx: int, param_base: str) -> str:
    """获取某列的单位"""
    # 优先用预定义单位
    for key, unit in _PARAM_UNITS.items():
        if key.upper() == param_base.upper():
            return unit
    # 从 Limit Units 行读取
    i = csv_field_idx - 1
    if 0 <= i < len(limit_units):
        u = limit_units[i].strip()
        if u:
            return u
    return ""


def _build_param_name(param_base: str, rule: str, bias_val: str, unit: str,
                      seq_counter: dict) -> str:
    """
    构建增强参数名。
    - seq:  参数名 + 序号 + (单位)  →  VTH1(V)
    - bias: 参数名 + 测试条件 + (单位)  →  IDSS100(nA)
    - unit: 参数名 + (单位)  →  DVDS(mV)
    """
    if rule == "seq":
        seq_counter[param_base] = seq_counter.get(param_base, 0) + 1
        num = seq_counter[param_base]
        if unit:
            return f"{param_base}{num}({unit})"
        return f"{param_base}{num}"

    elif rule == "bias":
        if param_base.upper() == "ISGS" and bias_val.startswith("-"):
            param_base = "IGSS"
            bias_val = bias_val[1:]
        suffix = bias_val if bias_val else str(seq_counter.get(param_base, 0) + 1)
        seq_counter[param_base] = seq_counter.get(param_base, 0) + 1
        if unit:
            return f"{param_base}{suffix}({unit})"
        return f"{param_base}{suffix}"

    else:  # "unit" or default
        cnt = seq_counter.get(param_base, 0) + 1
        seq_counter[param_base] = cnt
        if cnt > 1:
            if unit:
                return f"{param_base}{cnt}({unit})"
            return f"{param_base}{cnt}"
        if unit:
            return f"{param_base}({unit})"
        return param_base


# ─── 旧的兼容函数（其他模块可能引用） ───

def extract_lot_id_jiequn(filename: str) -> str:
    """兼容旧接口：返回周记"""
    return extract_zhouji(filename)


def parse_dta_csv(file_path: str, target_params: List[str],
                  max_scan: int = 40,
                  unique_only: bool = False,
                  preserve_source_order: bool = False) -> Optional[pd.DataFrame]:
    """
    解析杰群 DTA CSV，提取目标参数并用增强名称（含测试条件+单位）。

    Args:
        file_path: CSV 路径
        target_params: 目标参数名列表，如 ["DVDS"] 匹配 Item 中的 DVDS_EX
        max_scan: 头部扫描行数
        preserve_source_order: True 时按 Item 行从左到右匹配，适用于统一 CSV 对照源数据

    Returns:
        DataFrame，含 周记 + 增强参数列，失败返回 None
    """
    fname = Path(file_path).name
    info = read_header_info(file_path, max_scan)

    if info["item_idx"] < 0:
        print(f"  [WARN] {fname}: 未找到 Item 行")
        return None
    if info["data_start"] < 0:
        print(f"  [WARN] {fname}: 未找到 Serial,Bin 行")
        return None

    item_names = info["item_names"]
    bias_vals = info["bias1_values"]
    limit_units = info["limit_units"]

    # 找到所有匹配列
    col_matches = []  # [(csv_field_idx, param_base)]
    if preserve_source_order:
        seen_params = set()
        for i, name in enumerate(item_names):
            if not name:
                continue
            for bp in target_params:
                if unique_only and bp in seen_params:
                    continue
                if _item_matches_param(name, bp):
                    csv_field_idx = i + 1
                    col_matches.append((csv_field_idx, bp))
                    seen_params.add(bp)
                    break
    else:
        for bp in target_params:
            found = False
            for i, name in enumerate(item_names):
                if name and _item_matches_param(name, bp):
                    csv_field_idx = i + 1
                    col_matches.append((csv_field_idx, bp))
                    if unique_only:
                        found = True
                        break  # 只取第一个匹配
            if unique_only and found:
                continue

    if not col_matches:
        print(f"  [WARN] {fname}: 未找到目标参数 {target_params}")
        return None

    # 构建增强列名
    seq_counters = {}
    use_cols = [0, 1]      # Serial, Bin
    col_names = ["Serial", "Bin"]
    for fidx, pbase in col_matches:
        rule = _PARAM_NAME_RULES.get(pbase.upper(), "unit")
        bias_val = _get_bias_value(bias_vals, fidx) if rule == "bias" else ""
        unit = _get_unit(limit_units, fidx, pbase)
        name = _build_param_name(pbase, rule, bias_val, unit, seq_counters)
        use_cols.append(fidx)
        col_names.append(name)

    # 重命名 LCR-RG → RG
    col_names = [n.replace("LCR-RG", "RG") for n in col_names]

    # 去重（同名参数可能因 bias 相同而产生）
    seen = {}
    final_cols, final_names = [], []
    for c, n in zip(use_cols, col_names):
        if n not in seen:
            seen[n] = True
            final_cols.append(c)
            final_names.append(n)

    # 用 Serial 行推断总列数（避免第一行数据字段数少导致列数误判）
    with open(file_path, 'r', encoding='utf-8', errors='replace') as _f:
        for _i, _line in enumerate(_f):
            if _i == info["data_start"] - 1:  # Serial 行
                n_cols = len(_line.strip().split(','))
                break
        else:
            n_cols = 100  # fallback

    raw = pd.read_csv(file_path, skiprows=info["data_start"], header=None,
                      names=range(n_cols),
                      low_memory=False, encoding='utf-8')

    valid = [(c, n) for c, n in zip(final_cols, final_names) if c < n_cols]
    if len(valid) <= 2:
        return pd.DataFrame()

    df = raw.iloc[:, [v[0] for v in valid]].copy()
    df.columns = [v[1] for v in valid]

    # 周记
    zhouji = extract_zhouji(fname)
    df["周记"] = zhouji
    df.drop(columns=["Serial", "Bin"], inplace=True, errors='ignore')

    # 去空行
    val_cols = [c for c in df.columns if c != "周记"]
    df.dropna(how='all', subset=val_cols, inplace=True)

    # 数值化
    for col in val_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    print(f"  [OK] {fname}: {len(df):,} 行, 参数: {val_cols}")
    return df
