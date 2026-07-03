#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
杰群封装厂 — 配置文件

杰群数据特点：
- CSV 格式，科学计数法编码
- DC: IDSS/IGSS/ISGS 需从 A 换算到 nA（×1e9）
- DC: Rdson 需从 Ω 换算到 mR（×1000）
"""

FACTORY_NAME = "杰群"
FACTORY_NAME_EN = "Jiequn"
DATA_TYPES = ["DC", "DVDS", "RG"]
FILE_EXT = ".csv"
INPUT_DIR = "data/杰群"
OUTPUT_DIR = "output/杰群-output"

# 杰群专用单位换算规则
# 参数名（部分匹配） → 换算因子
UNIT_CONVERSIONS = {
    # DC 参数
    "IDSS":  {"from": "A",  "to": "nA", "factor": 1_000_000_000},  # 1e9
    "IGSS":  {"from": "A",  "to": "nA", "factor": 1_000_000_000},
    "ISGS":  {"from": "A",  "to": "nA", "factor": 1_000_000_000},
    "RDON":  {"from": "Ω",  "to": "mR", "factor": 1_000},          # 1000
    "Rdson": {"from": "Ω",  "to": "mR", "factor": 1_000},          # compatibility
    # DVDS 参数
    "DVDS":  {"from": "V",  "to": "mV", "factor": 1_000},          # V → mV
}

# 各数据类型的子目录名（在 INPUT_DIR 下）
TYPE_SUBDIRS = {
    "DC": "DC",
    "DVDS": "DVDS",
    "RG": "RG",
}

# Shared DC selection rules for Jiequn format1 and format2.
# Keep this list as the single source of truth so both input formats
# filter parameters the same way.
JIEQUN_DC_PARAMS = [
    "LCR-RG",
    "VTH",
    "BVDSS",
    "IDSS",
    "ISGS",
    "RDON",
    "VFSDS",
    "ABSDEL",
]

# 第一个 VTH 是封装厂占位测试；IDSS 均为有效漏电测试，必须全部保留。
JIEQUN_DC_SKIP_MATCH_COUNTS = {"VTH": 1}
