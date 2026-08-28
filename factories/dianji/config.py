#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dianji factory configuration."""

from dataclasses import dataclass

FACTORY_NAME = "电基"
FACTORY_NAME_EN = "Dianji"
DATA_TYPES = ["FT-ALL"]
FILE_EXT = ".xls"
FILE_EXTS = (".xls", ".xlsx", ".csv")

# PowerTECH writes a GB18030/tab-delimited text report but uses an .xls suffix.
SOURCE_SIGNATURE = "PowerTECH Test System"
SOURCE_ENCODINGS = ("utf-8-sig", "gb18030")

# PowerTECH native XLSX reports reviewed from dj7.  This is a separate source
# format from the tab-delimited pseudo-XLS reports above.  Only the evidenced
# NCE40ED120VT(LA) product and the exact tester-side filename/worksheet layouts
# are enabled; other products or workbook schemas must be reviewed first.
POWERTECH_XLSX_SIGNATURE = "PowerTECH Test System"
POWERTECH_XLSX_SUPPORTED_PRODUCTS = frozenset({"NCE40ED120VT(LA)"})
POWERTECH_XLSX_MANUFACTURING_LOT_PATTERN = (
    r"[mM]\d{9}-\d{3}(?:-[aA]-[bB])?"
)
POWERTECH_XLSX_BATCH_PATTERN = r"[fF][aA][A-Za-z0-9]{2}-\d{4}"
POWERTECH_XLSX_LABELS = frozenset({"", "ALL", "M05", "DC", "RT", "_"})
POWERTECH_XLSX_TRAILING_LOT_LABELS = frozenset(
    {"", "QC", "Q", "M05", "DC", "RT", "_"}
)

# Verified PowerTECH identity variants.  The optional ``-A-A`` suffix and
# ``DC M08`` test tag come from the reviewed dj6 corpus; keep them explicit so
# unrelated tester-side naming changes still fail closed.
POWERTECH_MANUFACTURING_LOT_PATTERN = r"[mMrR]\d{9}-\d{3}(?:-[aA]-[aA])?"
POWERTECH_BATCH_PATTERN = r"(?:[cC]\d{6}[.,，。]\d{2}|[fF][aA]\d{2}-\d{4})"
POWERTECH_TEST_TAG_PATTERN = r"(?:(?:[A-Za-z]+)|(?:DC\s+M08))?\d{12}"

# Some reviewed PowerTECH text exports omit the product from the outer .xls
# filename.  In that naming variant the product must be recovered from the
# tester-side TestFileName metadata, so keep exact program-to-product evidence
# instead of accepting an arbitrary program with a familiar product prefix.
POWERTECH_METADATA_FILENAME_PROGRAMS = {
    "NCEAP020N10LL(M)-7E00_ALL_M08M09_Ver1.07_20260520.ptf":
        "NCEAP020N10LL(M)-7E00",
}

# STS8203 writes a real UTF-8 CSV with metadata before the CSV header.  The
# source does not expose Bias voltages, so every supported product needs an
# explicit, reviewed output mapping instead of a guessed generic mapping.
STS8203_SIGNATURE = "STS8203 Station"
STS8203_ENCODING = "utf-8-sig"
# Verified filename/Lot Id variants.  Keep these explicit so a new tester-side
# naming convention cannot silently change source identity.
STS8203_SUPPORTED_LOT_DIGIT_COUNTS = frozenset({8, 9})
STS8203_SUPPORTED_LOT_SUFFIXES = frozenset({"A"})
STS8203_SUPPORTED_SOURCE_SEGMENTS = frozenset({"2"})
STS8203_EXPECTED_COLUMN_COUNT = 63
STS8203_EXPECTED_FIELD_INDEXES = {
    "SITE_NUM": 0,
    "PART_ID": 1,
    "PASSFG": 2,
    "SOFT_BIN": 3,
    "TEST_NUM": 5,
    "DVDS": 9,
    "Zmu_RG2": 18,
    "QC_VTH": 46,
    "QC_VTH2": 47,
    "QC_BVDSS": 48,
    "QC_BVDSS1": 49,
    "QC_IDSS": 50,
    "QC_IGSSF2": 51,
    "QC_IGSSR2": 52,
    "QC_IGSSF": 53,
    "QC_IGSSR": 54,
    "RDSON2": 55,
    "QC_VFSD": 56,
    "QC_IDSS1": 57,
    "QC_IGSSF1": 58,
    "QC_IGSSR1": 59,
    "QC_VTH1": 60,
    "QC_DELTA_BVDSS": 61,
    "QC_DELTA_VTH": 62,
}
STS8203_EXPECTED_SOURCE_UNITS = {
    "DVDS": "mV",
    "Zmu_RG2": "Ohm",
    "QC_VTH": "V",
    "QC_VTH2": "V",
    "QC_BVDSS": "V",
    "QC_BVDSS1": "V",
    "QC_IDSS": "nA",
    "QC_IGSSF2": "nA",
    "QC_IGSSR2": "nA",
    "QC_IGSSF": "nA",
    "QC_IGSSR": "nA",
    "RDSON2": "mOhm",
    "QC_VFSD": "V",
    "QC_IDSS1": "nA",
    "QC_IGSSF1": "nA",
    "QC_IGSSR1": "nA",
    "QC_VTH1": "V",
    "QC_DELTA_BVDSS": "",
    "QC_DELTA_VTH": "",
}
STS8203_PRODUCT_OUTPUT_FIELDS = {
    "NCEAP40T20AGU(M)-7E00": (
        ("DVDS", "DVDS(mV)", "mV"),
        ("Zmu_RG2", "Rg(R)", "R"),
        ("QC_VTH", "VTH1(V)", "V"),
        ("QC_VTH2", "VTH2(V)", "V"),
        ("QC_BVDSS", "BVDSS1(V)", "V"),
        ("QC_BVDSS1", "BVDSS2(V)", "V"),
        ("QC_IDSS", "IDSS40(nA)", "nA"),
        ("QC_IGSSF2", "IGSS25(nA)", "nA"),
        ("QC_IGSSR2", "ISGS25(nA)", "nA"),
        ("QC_IGSSF", "IGSS20(nA)", "nA"),
        ("QC_IGSSR", "ISGS20(nA)", "nA"),
        ("RDSON2", "RDON10(mR)", "mR"),
        ("QC_VFSD", "VFSD(V)", "V"),
        ("QC_IGSSR1", "ISGS10(nA)", "nA"),
        ("QC_IGSSF1", "IGSS10(nA)", "nA"),
        ("QC_IDSS1", "IDSS35(nA)", "nA"),
        ("QC_VTH1", "VTH3(V)", "V"),
        ("QC_DELTA_BVDSS", "DELTA BV", ""),
        ("QC_DELTA_VTH", "DELTA VTH", ""),
    ),
}

OUTPUT_SHEET_NAME = "RAW"
OUTPUT_FILE_SUFFIX = " DJ PAT.xlsx"

@dataclass(frozen=True)
class PowerTechItemLayout:
    """One explicitly reviewed PowerTECH Item-number layout."""

    name: str
    item_count: int
    expected_item_bases: dict[int, frozenset[str]]
    output_prefix: tuple[int, ...]
    tail_item_numbers: tuple[int, int, int]
    supported_tail_bases: frozenset[tuple[str, str, str]]
    output_suffix: tuple[int, ...]


# The original program has two verified Item 29-31 permutations.  The dj6
# compact program removes two SAME placeholders (old Items 17-18), shifting all
# later business Items down by two while retaining the same 19 output values.
POWERTECH_ITEM_LAYOUTS = (
    PowerTechItemLayout(
        name="standard-34",
        item_count=34,
        expected_item_bases={
            4: frozenset({"DVDS", "DVDS_EX"}),
            12: frozenset({"LCR-RG"}),
            16: frozenset({"VTH"}),
            19: frozenset({"VTH"}),
            20: frozenset({"BVDSS"}),
            21: frozenset({"BVDSS"}),
            22: frozenset({"IDSS"}),
            23: frozenset({"IGSS"}),
            24: frozenset({"IGSS"}),
            25: frozenset({"IGSS"}),
            26: frozenset({"IGSS"}),
            27: frozenset({"RDON"}),
            28: frozenset({"VFSD"}),
            29: frozenset({"IDSS", "IGSS"}),
            30: frozenset({"IGSS"}),
            31: frozenset({"IDSS", "IGSS"}),
            32: frozenset({"VTH"}),
            33: frozenset({"DELTA"}),
            34: frozenset({"DELTA"}),
        },
        output_prefix=(4, 12, 16, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28),
        tail_item_numbers=(29, 30, 31),
        supported_tail_bases=frozenset(
            {
                ("IDSS", "IGSS", "IGSS"),
                ("IGSS", "IGSS", "IDSS"),
            }
        ),
        output_suffix=(32, 33, 34),
    ),
    PowerTechItemLayout(
        name="compact-32",
        item_count=32,
        expected_item_bases={
            4: frozenset({"DVDS", "DVDS_EX"}),
            12: frozenset({"LCR-RG"}),
            16: frozenset({"VTH"}),
            17: frozenset({"VTH"}),
            18: frozenset({"BVDSS"}),
            19: frozenset({"BVDSS"}),
            20: frozenset({"IDSS"}),
            21: frozenset({"IGSS"}),
            22: frozenset({"IGSS"}),
            23: frozenset({"IGSS"}),
            24: frozenset({"IGSS"}),
            25: frozenset({"RDON"}),
            26: frozenset({"VFSD"}),
            27: frozenset({"IGSS"}),
            28: frozenset({"IGSS"}),
            29: frozenset({"IDSS"}),
            30: frozenset({"VTH"}),
            31: frozenset({"DELTA"}),
            32: frozenset({"DELTA"}),
        },
        output_prefix=(4, 12, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26),
        tail_item_numbers=(27, 28, 29),
        supported_tail_bases=frozenset({("IGSS", "IGSS", "IDSS")}),
        output_suffix=(30, 31, 32),
    ),
)

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
