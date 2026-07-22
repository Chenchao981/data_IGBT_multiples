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

# Required PowerTECH item numbers.  The parser derives the final business order
# from parameter names and bias conditions because verified test programs use
# two different arrangements for items 29-31.
REQUIRED_ITEM_NUMBERS = (
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
    29,  # second IDSS or IGSS -10V, depending on the verified program layout
    30,  # IGSS +10V
    31,  # IGSS -10V or second IDSS, depending on the verified program layout
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
    29: {"IDSS", "IGSS"},
    30: {"IGSS"},
    31: {"IDSS", "IGSS"},
    32: {"VTH"},
    33: {"DELTA"},
    34: {"DELTA"},
}

# Only these two item 29-31 layouts have been verified from real PowerTECH
# exports.  Counts alone are insufficient because they could accept a third,
# unverified permutation and silently change the RAW column meaning.
SUPPORTED_TAIL_LAYOUTS = {
    ((29, "IDSS"), (30, "IGSS"), (31, "IGSS")),
    ((29, "IGSS"), (30, "IGSS"), (31, "IDSS")),
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
