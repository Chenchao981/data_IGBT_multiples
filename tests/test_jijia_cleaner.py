from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from factories.jijia.config import (
    EXPECTED_SOURCE_HEADER,
    EXPECTED_SOURCE_UNITS,
    OUTPUT_PARAMETER_NAMES,
)
from factories.jijia.dc_cleaner import JijiaFTCleaner
from factories.jijia.parser import (
    JijiaFormatError,
    parse_jijia_file,
    parse_jijia_filename,
)


SOURCE_NAME = "NCE15TD120BT_C178121.00_26PA06370031-02_DC_260409034023.csv"


def _make_source(
    root: Path,
    *,
    name: str = SOURCE_NAME,
    changed_header: tuple[int, str] | None = None,
    changed_unit: tuple[int, str] | None = None,
    invalid_value: tuple[int, str] | None = None,
) -> Path:
    header = list(EXPECTED_SOURCE_HEADER)
    units = list(EXPECTED_SOURCE_UNITS)
    if changed_header:
        header[changed_header[0]] = changed_header[1]
    if changed_unit:
        units[changed_unit[0]] = changed_unit[1]
    low = ["LimitL", *("" for _ in header[1:])]
    high = ["LimitU", *("" for _ in header[1:])]

    full = ["" for _ in header]
    full[:6] = ["1", "1", "True", "1", "886", "1"]
    for index in range(6, len(full)):
        full[index] = str(index + 0.25)
    if invalid_value:
        full[invalid_value[0]] = invalid_value[1]
    failed = ["2", "2", "False", "37", "10", "2", "8.5", "9.5"]

    buffer = StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    for row in (
        ["STS8203 StationA"],
        ["Date:2026-4-9"],
        ["Tester ID:"],
        ["Program:C:\\Program\\NCE15TD120BT(80)-YX(1.0).pgs"],
        ["Lot Id:26PA06370031-02-FT1"],
        ["Beginning Time: 2026-4-8 17:26:55"],
        ["Ending Time: 2026-4-9 2:19:38"],
        [],
        [*header, ""],
        [*units, ""],
        [*low, ""],
        [*high, ""],
        [*full, ""],
        [*failed, ""],
    ):
        writer.writerow(row)
    path = root / name
    path.write_bytes(buffer.getvalue().encode("gb18030"))
    return path


class JijiaFilenameTests(unittest.TestCase):
    def test_extracts_batch_from_approved_filename(self):
        identity = parse_jijia_filename(SOURCE_NAME)
        self.assertEqual(identity.product, "NCE15TD120BT")
        self.assertEqual(identity.batch, "C178121.00")
        self.assertEqual(identity.test_lot, "26PA06370031-02")

    def test_rejects_unapproved_product_or_batch_shape(self):
        with self.assertRaisesRegex(JijiaFormatError, "尚未验证"):
            parse_jijia_filename(SOURCE_NAME.replace("NCE15TD120BT", "UNKNOWN"))
        with self.assertRaisesRegex(JijiaFormatError, "文件名必须符合"):
            parse_jijia_filename(SOURCE_NAME.replace("C178121.00", "C178121"))


class JijiaParserTests(unittest.TestCase):
    def test_outputs_ase_style_contract_without_system_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_jijia_file(_make_source(Path(temp)))

        self.assertEqual(parsed.source_rows, 2)
        self.assertEqual(parsed.pass_rows, 1)
        self.assertEqual(parsed.fail_rows, 1)
        self.assertEqual(
            list(parsed.data.columns),
            ["lot_ID", *OUTPUT_PARAMETER_NAMES],
        )
        self.assertNotIn("PASSFG", parsed.data.columns)
        self.assertNotIn("SOFT_BIN", parsed.data.columns)
        self.assertNotIn("PART_ID", parsed.data.columns)
        self.assertEqual(parsed.data["lot_ID"].tolist(), ["C178121.00"] * 2)
        self.assertAlmostEqual(parsed.data.loc[0, "CONT_C3(mA)"], 6.25)
        self.assertAlmostEqual(parsed.data.loc[1, "CONT_C3(mA)"], 8.5)
        self.assertTrue(pd.isna(parsed.data.loc[1, "CONT_GL5(mA)"]))

    def test_rejects_changed_schema_unit_and_unknown_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(JijiaFormatError, "参数结构未经验证"):
                parse_jijia_file(_make_source(root, changed_header=(6, "CONT_CHANGED")))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(JijiaFormatError, "单位结构未经验证"):
                parse_jijia_file(_make_source(root, changed_unit=(6, "A")))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(JijiaFormatError, "未经验证的非数值"):
                parse_jijia_file(_make_source(root, invalid_value=(6, "/")))

    def test_rejects_filename_and_metadata_test_lot_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = _make_source(root)
            text = source.read_bytes().decode("gb18030")
            source.write_bytes(
                text.replace("26PA06370031-02-FT1", "26PA06370031-03-FT1").encode("gb18030")
            )
            with self.assertRaisesRegex(JijiaFormatError, "Lot Id 不一致"):
                parse_jijia_file(source)


class JijiaCleanerTests(unittest.TestCase):
    def test_merges_all_rows_and_writes_dc_data_sheet(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            input_dir.mkdir()
            _make_source(input_dir)
            cleaner = JijiaFTCleaner(input_dir, root / "output")

            self.assertTrue(cleaner.process_all())

            self.assertEqual(cleaner.last_output_file.parent.name, "C178121.00_001")
            self.assertEqual(cleaner.last_output_file.name, "C178121.00_001.xlsx")
            result = pd.read_excel(cleaner.last_output_file, sheet_name="DC_Data")
            self.assertEqual(result.shape, (2, 119))
            self.assertEqual(result["NUM"].tolist(), [1, 2])
            self.assertEqual(result["lot_ID"].tolist(), ["C178121.00"] * 2)
            self.assertNotIn("PASSFG", result.columns)
            self.assertNotIn("SOFT_BIN", result.columns)
            self.assertEqual(cleaner.last_run_summary["source_rows"], 2)
            self.assertEqual(cleaner.last_run_summary["kept_rows"], 2)


if __name__ == "__main__":
    unittest.main()
