#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dianji factory configuration."""

FACTORY_NAME = "电基"
FACTORY_NAME_EN = "Dianji"
DATA_TYPES = ["FT-ALL"]
FILE_EXT = ".xls"

# PowerTECH writes a GB18030/tab-delimited text report but uses an .xls suffix.
SOURCE_SIGNATURE = "PowerTECH Test System"
SOURCE_ENCODINGS = ("utf-8-sig", "gb18030")

OUTPUT_SHEET_NAME = "RAW"
OUTPUT_FILE_SUFFIX = " DJ PAT.xlsx"

# The user's reference workbook selects these PowerTECH item numbers in this
# exact business order.  Names and bias values are still read dynamically from
# each source header, so products with different voltage conditions produce
# names such as IDSS100(nA) / IDSS90(nA) instead of hard-coded product values.
OUTPUT_ITEM_ORDER = (
    4,   # DVDS_EX
    12,  # LCR-RG
    16,  # VTH1 (the first VTH, item 14, is a fixture/program placeholder)
    19,  # VTH2
    20,  # BVDSS1
    21,  # BVDSS2
    22,  # first IDSS
    23,  # IGSS +25V
    24,  # IGSS -25V -> ISGS25
    25,  # IGSS +20V
    26,  # IGSS -20V -> ISGS20
    27,  # RDON
    28,  # VFSD
    31,  # IGSS -10V -> ISGS10 (reference workbook order)
    30,  # IGSS +10V
    29,  # second IDSS
    32,  # VTH3
    33,  # DELTA BV
    34,  # DELTA VTH
)

EXPECTED_ITEM_BASES = {
    4: {"DVDS", "DVDS_EX"},
    12: {"LCR-RG"},
    16: {"VTH"},
    19: {"VTH"},
    20: {"BVDSS"},
    21: {"BVDSS"},
    22: {"IDSS"},
    23: {"IGSS"},
    24: {"IGSS"},
    25: {"IGSS"},
    26: {"IGSS"},
    27: {"RDON"},
    28: {"VFSD"},
    29: {"IDSS"},
    30: {"IGSS"},
    31: {"IGSS"},
    32: {"VTH"},
    33: {"DELTA"},
    34: {"DELTA"},
}

EXPECTED_ITEM_COUNTS = {
    "DVDS_EX": 1,
    "LCR-RG": 1,
    "VTH": 4,
    "BVDSS": 2,
    "IDSS": 2,
    "IGSS": 6,
    "RDON": 1,
    "VFSD": 1,
    "DELTA": 2,
}

TARGET_UNITS = {
    "DVDS_EX": "mV",
    "DVDS": "mV",
    "LCR-RG": "R",
    "VTH": "V",
    "BVDSS": "V",
    "IDSS": "nA",
    "IGSS": "nA",
    "RDON": "mR",
    "VFSD": "V",
}

UNIT_FACTORS = {
    ("V", "mV"): 1000.0,
    ("A", "nA"): 1_000_000_000.0,
    ("R", "mR"): 1000.0,
}

# PowerTECH uses 9999 as an overflow/not-tested placeholder.  It must not enter
# PAT statistics as a real measurement.
INVALID_NUMERIC_MARKERS = {9999.0, -9999.0}
