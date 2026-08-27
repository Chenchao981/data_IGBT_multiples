import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from factories.tms_adapters.identity import (
    parse_riyueguang_dc_filename,
    parse_riyuexin_dc_filename,
)
from factories.tms_adapters.riyueguang_dc import RiyueguangTmsDCCleaner
from factories.tms_adapters.riyuexin_dc import RiyuexinTmsDCCleaner


def _write_dc_source(path: Path, *, unit_row: int, test_no_row: int, time_row=None):
    rows = max(test_no_row + 3, unit_row + 1)
    frame = pd.DataFrame([[None] * 6 for _ in range(rows)])
    frame.iat[1, 0] = "Item"
    frame.iat[1, 2] = "CONT"
    frame.iat[1, 3] = "VTH"
    frame.iat[1, 4] = "IDSS"
    frame.iat[2, 3] = 1
    frame.iat[2, 4] = 0
    frame.iat[3, 3] = 5
    frame.iat[3, 4] = 0.001
    frame.iat[4, 4] = 40
    frame.iat[unit_row, 0] = "Unit"
    frame.iat[unit_row, 3] = "V"
    frame.iat[unit_row, 4] = "A"
    if time_row is not None:
        frame.iat[time_row, 0] = "Time"
        frame.iat[time_row, 3] = "80.0mS"
        frame.iat[time_row, 4] = "80.0mS"
    frame.iat[test_no_row, 0] = "Test No."
    frame.iat[test_no_row + 1, 3] = 2.5
    frame.iat[test_no_row + 1, 4] = 0.000001
    frame.iat[test_no_row + 2, 3] = 2.6
    frame.iat[test_no_row + 2, 4] = 0.000002
    frame.to_excel(path, sheet_name="Test Data", index=False, header=False)


class FtIdentityTest(unittest.TestCase):
    def test_riyuexin_accepts_both_approved_filename_directions(self):
        source_first = parse_riyuexin_dc_filename(
            "NCT5542087_NCEAP40PT15D(M)-2B00_FA59-3997_20251024_182422.xlsx"
        )
        product_first = parse_riyuexin_dc_filename(
            "NCEAP0178AK(M)-3B00_FA5Y-5566_NCT4550014_DC_251217134416.XLSX"
        )
        self.assertEqual(source_first.source_id, "NCT5542087")
        self.assertEqual(source_first.product, "NCEAP40PT15D(M)-2B00")
        self.assertEqual(product_first.source_id, "NCT4550014")
        self.assertEqual(product_first.lot_id, "FA5Y-5566")

    def test_riyueguang_rejects_product_first_filename(self):
        with self.assertRaisesRegex(ValueError, "日月光"):
            parse_riyueguang_dc_filename(
                "NCEA75ED120BT(LA)-3B00_FA54-9744_NCT6528068_DC_250722070217.xlsx"
            )


class FtAdapterTest(unittest.TestCase):
    def test_riyuexin_keeps_unit_and_source_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            source.mkdir()
            _write_dc_source(
                source / "NCEAP0178AK(M)-3B00_FA5Y-5566_NCT4550014_DC_251217134416.xlsx",
                unit_row=6,
                test_no_row=18,
            )
            cleaner = RiyuexinTmsDCCleaner(source, root / "output")
            self.assertTrue(cleaner.process_all_dc_files())
            cleaned = pd.read_excel(cleaner.last_output_file, sheet_name="DC_Data")
            self.assertIn("VTH(V)", cleaned.columns)
            manifest = json.loads(cleaner.last_scatter_manifest.read_text("utf-8"))
            self.assertEqual(manifest["factory_code"], "RIYUEXIN")
            self.assertEqual(
                manifest["sources"],
                ["NCEAP0178AK(M)-3B00_FA5Y-5566_NCT4550014_DC_251217134416"],
            )

    def test_riyueguang_removes_time_row_only_in_temporary_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            source.mkdir()
            source_file = source / "NCT6528068_NCEA75ED120BT(LA)-3B00_FA54-9744_20250722_070217.xlsx"
            _write_dc_source(source_file, unit_row=7, test_no_row=14, time_row=6)
            original_bytes = source_file.read_bytes()
            cleaner = RiyueguangTmsDCCleaner(source, root / "output")
            self.assertTrue(cleaner.process_all_dc_files())
            self.assertEqual(source_file.read_bytes(), original_bytes)
            cleaned = pd.read_excel(cleaner.last_output_file, sheet_name="DC_Data")
            self.assertIn("VTH(V)", cleaned.columns)
            self.assertNotIn("VTH(80.0mS)", cleaned.columns)
            manifest = json.loads(cleaner.last_scatter_manifest.read_text("utf-8"))
            self.assertEqual(manifest["factory_code"], "RIYUEGUANG")
            self.assertEqual(manifest["factory"], "日月光")

    def test_riyueguang_unknown_header_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            source.mkdir()
            path = source / "NCT6528068_NCEA75ED120BT(LA)-3B00_FA54-9744_20250722_070217.xlsx"
            _write_dc_source(path, unit_row=6, test_no_row=18)
            cleaner = RiyueguangTmsDCCleaner(source, root / "output")
            with self.assertRaisesRegex(ValueError, "Unit 行"):
                cleaner.extract_dc_data(path)


if __name__ == "__main__":
    unittest.main()
