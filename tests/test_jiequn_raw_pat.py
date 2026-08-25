import tempfile
import unittest
from pathlib import Path

import pandas as pd

from factories.jiequn.pat_cleaner import build_raw_pat, generate_raw_pat


def _write_unified_dta(
    path: Path,
    rows: list[list[float]],
    *,
    include_rdon: bool = True,
) -> None:
    items = ["DVDS_EX", "LCR-RG", "VTH", "VTH", "IDSS"]
    units = ["V", "R", "V", "V", "A"]
    if include_rdon:
        items.append("RDON")
        units.append("R")
    lines = [
        f"DTA File Name,{path.stem}.dta",
        f"CSV File Name,{path.name}",
        f"Quantity Logged,{len(rows)}",
        "Test,," + ",".join(str(index) for index in range(1, len(items) + 1)),
        "Item,," + ",".join(items),
        "Min Limit,," + ",".join("" for _ in items),
        "Max Limit,," + ",".join("" for _ in items),
        "Limit Units,," + ",".join(units),
        "Bias 1,," + ",".join("" for _ in items),
        "Bias 1 Value,," + ",".join("" for _ in items),
        "Bias 1 Units,," + ",".join("" for _ in items),
        "Serial,Bin," + ",".join(items),
    ]
    for serial, values in enumerate(rows, start=1):
        selected = values if include_rdon else values[:-1]
        lines.append(f"{serial},1," + ",".join(str(value) for value in selected))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_classic_dta(path: Path, items: list[str], units: list[str], rows: list[list[float]]) -> None:
    lines = [
        f"DTA File Name,{path.stem}.dta",
        f"CSV File Name,{path.name}",
        f"Quantity Logged,{len(rows)}",
        "Test,," + ",".join(str(index) for index in range(1, len(items) + 1)),
        "Item,," + ",".join(items),
        "Limit Units,," + ",".join(units),
        "Serial,Bin," + ",".join(items),
    ]
    for serial, values in enumerate(rows, start=1):
        lines.append(f"{serial},1," + ",".join(str(value) for value in values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class JiequnRawPatTests(unittest.TestCase):
    def test_builds_exact_pat_directly_from_raw_unified_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "NCEAP020N10LL"
            source.mkdir()
            _write_unified_dta(
                source / "NCEAP020N10LL(M)-7J00_BATCH1_001FA_20260101000000DTA.CSV",
                [
                    [0.1, 2.0, 99.0, 3.0, 1e-7, 0.0020],
                    [0.2, 2.2, 99.0, 3.2, 2e-7, 0.0022],
                ],
            )
            _write_unified_dta(
                source / "NCEAP020N10LL(M)-7J00_BATCH2_002FA_20260102000000DTA.CSV",
                [
                    [0.3, 2.4, 99.0, 3.4, 3e-7, 0.0024],
                    [0.4, 2.6, 99.0, 3.6, 4e-7, 0.0026],
                ],
            )

            result = build_raw_pat(source, spool_dir=root / "spool", progress_interval=0)
            rows = result.iloc[1:].set_index("统计量")

            self.assertEqual(set(rows.index), {"DVDS(mV)", "RG(R)", "VTH1(V)", "IDSS1(nA)", "RDON1(mR)"})
            self.assertEqual(int(rows.loc["DVDS(mV)", "总计数"]), 4)
            self.assertAlmostEqual(float(rows.loc["DVDS(mV)", "中位数"]), 250.0)
            self.assertAlmostEqual(float(rows.loc["IDSS1(nA)", "中位数"]), 250.0)
            self.assertAlmostEqual(float(rows.loc["RDON1(mR)", "中位数"]), 2.3)
            expected_sigma = (325.0 - 175.0) / 1.35
            self.assertAlmostEqual(float(rows.loc["DVDS(mV)", "Sigma"]), expected_sigma, places=6)
            self.assertFalse(any((root / "spool").glob("jiequn_pat_*")))

    def test_builds_classic_dc_dvds_rg_directory_without_duplicate_parameters(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            for label in ("DC", "DVDS", "RG"):
                (source / label).mkdir()
            stem = "PRODUCTA_BATCH1_001FA_20260101000000DTA.CSV"
            _write_classic_dta(
                source / "DC" / stem,
                ["VTH", "VTH", "IDSS"],
                ["V", "V", "A"],
                [[99.0, 3.0, 1e-7], [99.0, 3.2, 2e-7]],
            )
            _write_classic_dta(
                source / "DVDS" / stem,
                ["DVDS_EX"],
                ["V"],
                [[0.1], [0.2]],
            )
            _write_classic_dta(
                source / "RG" / stem,
                ["LCR-RG"],
                ["R"],
                [[2.0], [2.2]],
            )

            result = build_raw_pat(source, progress_interval=0)
            rows = result.iloc[1:].set_index("统计量")

            self.assertEqual(set(rows.index), {"VTH1(V)", "IDSS1(nA)", "DVDS(mV)", "RG(R)"})
            self.assertEqual(int(rows.loc["DVDS(mV)", "总计数"]), 2)
            self.assertAlmostEqual(float(rows.loc["DVDS(mV)", "中位数"]), 150.0)

    def test_rejects_mixed_products(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            values = [[0.1, 2.0, 99.0, 3.0, 1e-7, 0.0020]]
            _write_unified_dta(source / "PRODUCTA_BATCH1_001FA_20260101000000DTA.CSV", values)
            _write_unified_dta(source / "PRODUCTB_BATCH2_002FA_20260102000000DTA.CSV", values)

            with self.assertRaisesRegex(ValueError, "多个产品"):
                build_raw_pat(source)

    def test_rejects_parameter_schema_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            values = [[0.1, 2.0, 99.0, 3.0, 1e-7, 0.0020]]
            _write_unified_dta(source / "PRODUCTA_BATCH1_001FA_20260101000000DTA.CSV", values)
            _write_unified_dta(
                source / "PRODUCTA_BATCH2_002FA_20260102000000DTA.CSV",
                values,
                include_rdon=False,
            )

            with self.assertRaisesRegex(ValueError, "参数结构不一致"):
                build_raw_pat(source)

    def test_generate_raw_pat_creates_collision_safe_workbooks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            _write_unified_dta(
                source / "PRODUCTA_BATCH1_001FA_20260101000000DTA.CSV",
                [[0.1, 2.0, 99.0, 3.0, 1e-7, 0.0020]],
            )

            first = generate_raw_pat(source, output)
            second = generate_raw_pat(source, output)

            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            self.assertEqual(first.parent.name, "PAT_001")
            self.assertEqual(second.parent.name, "PAT_002")
            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())
            saved = pd.read_excel(first, sheet_name="PAT")
            self.assertEqual(len(saved), 6)


if __name__ == "__main__":
    unittest.main()
