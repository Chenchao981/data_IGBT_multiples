#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from factories.dianji.dc_cleaner import DianjiDCCleaner
from factories.dianji.models import DianjiFormatError
from factories.dianji.source_registry import detect_dianji_source_format
from factories.dianji.tf_csv_parser import (
    TF_COLUMN_COUNT,
    TF_HEADER,
    TF_ITEM_NAMES,
    TF_OUTPUT_FIELDS,
    parse_dianji_tf_file,
    parse_dianji_tf_filename,
)


VALID_NAME = ",NCE40ED120VT(LA)-M260108039-001-A-B FA5Y-9413 1-SW+Trr-2602021050.csv"


def _write_tf(path: Path, *, bad_item: bool = False, bad_marker: bool = False) -> None:
    rows = [[""] * TF_COLUMN_COUNT for _ in range(30)]
    metadata = (
        (0, "设备名称", "DP1205"),
        (1, "工号", "YLC"),
        (2, "程序名称", "NCE40ED120VT(LA) Ver2.1 20251205 陪测10Ω"),
        (3, "保存路径", r"D:\数据保存"),
        (4, "批次信息", "M260108039-001-A-B FA5Y-9413 1"),
        (5, "测试类型", "SW+Trr"),
    )
    for index, label, value in metadata:
        rows[index][0:2] = [label, value]
    rows[2][2] = "被测10Ω.out"
    rows[6][0:3] = ["开始时间", "2026-02-02", " 10:50:32"]
    rows[7][0:3] = ["结束时间", "2026-02-02", " 10:52:00"]
    rows[17][6:] = ["Test", *(f"{number:.6f}" for number in range(1, 51))]
    source_items = list(TF_ITEM_NAMES)
    if bad_item:
        source_items[10] = "Changed"
    rows[19][6:] = ["Low  Limit", *("0.000000" for _ in range(50))]
    rows[20][6:] = ["High Limit", *("999999.000000" for _ in range(50))]
    rows[22][6:] = ["Item", *source_items]
    rows[28] = list(TF_HEADER)
    chinese = ["序号", "日期", "时间", "测试时间(ms)", "BIN", "不通过项", "测试结果"]
    chinese += ["接触检测", "器件检测"]
    chinese += [
        f"{field.source_name}({field.unit})" if field.unit else field.source_name
        for field in TF_OUTPUT_FIELDS
    ]
    chinese += ["器件检测"]
    rows[29] = chinese
    rows[18][6:] = ["Item", *chinese[7:]]

    values = [str(number + 0.25) for number in range(len(TF_OUTPUT_FIELDS))]
    row1 = ["1", "2026-02-02", "10:50:32:834", "0.71", "1", "", "pass", "pass", "pass", *values, "pass"]
    row2 = ["2", "2026-02-02", "10:50:34:000", "0.65", "6", "Eoff2", "fault", "pass", "pass", *values, "pass"]
    row2[9] = "/"
    row2[10] = "bad" if bad_marker else "/"
    rows.extend([row1, row2])
    with path.open("w", encoding="gb18030", newline="") as handle:
        csv.writer(handle).writerows(rows)


class DianjiTFCSVTests(unittest.TestCase):
    def test_filename_and_registry(self):
        identity = parse_dianji_tf_filename(VALID_NAME)
        self.assertEqual(identity.product, "NCE40ED120VT(LA)")
        self.assertEqual(identity.batch, "FA5Y-9413")
        self.assertEqual(identity.source_segment, "1")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / VALID_NAME
            _write_tf(path)
            self.assertEqual(detect_dianji_source_format(path).key, "dianji_tf_csv")

    def test_parser_outputs_47_parameters_and_source_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / VALID_NAME
            _write_tf(path)
            parsed = parse_dianji_tf_file(path)
            self.assertEqual(parsed.source_rows, 2)
            self.assertEqual(parsed.kept_rows, 1)
            self.assertEqual(len(parsed.data.columns), 48)
            self.assertEqual(len(parsed.specs), 47)
            self.assertEqual(parsed.data.columns[0], "批次")
            self.assertEqual(parsed.data.columns[1], "Udc(V)")
            self.assertEqual(parsed.data.columns[-1], "IF(A)")
            self.assertEqual(parsed.invalid_marker_counts["Udc(V)"], 1)
            self.assertEqual(parsed.specs.iloc[0]["Low_Limit"], 0.0)
            self.assertEqual(parsed.specs.iloc[0]["High_Limit"], 999999.0)

    def test_unknown_schema_and_marker_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_schema = Path(tmp) / VALID_NAME
            _write_tf(bad_schema, bad_item=True)
            with self.assertRaisesRegex(DianjiFormatError, "Item"):
                parse_dianji_tf_file(bad_schema)
        with tempfile.TemporaryDirectory() as tmp:
            bad_marker = Path(tmp) / VALID_NAME
            _write_tf(bad_marker, bad_marker=True)
            # The row is dropped at Udc before later values are relevant; put
            # an unknown marker on a retained row to prove strict conversion.
            with bad_marker.open("r", encoding="gb18030") as handle:
                rows = list(csv.reader(handle))
            rows[-2][10] = "bad"
            with bad_marker.open("w", encoding="gb18030", newline="") as handle:
                csv.writer(handle).writerows(rows)
            with self.assertRaisesRegex(DianjiFormatError, "非数值标记"):
                parse_dianji_tf_file(bad_marker)

    def test_cleaner_writes_same_raw_contract_and_scatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            output = Path(tmp) / "output"
            source.mkdir()
            _write_tf(source / VALID_NAME)
            cleaner = DianjiDCCleaner(source, output)
            self.assertTrue(cleaner.process_all())
            result = pd.read_excel(cleaner.last_output_file, sheet_name="RAW")
            self.assertEqual(result.columns[0:3].tolist(), ["NUM", "批次", "Udc(V)"])
            self.assertEqual(result["NUM"].tolist(), [1])
            self.assertEqual(cleaner.last_run_summary["retention_parameter"], "Udc(V)")
            self.assertTrue(cleaner.last_scatter_manifest.is_file())


if __name__ == "__main__":
    unittest.main()
