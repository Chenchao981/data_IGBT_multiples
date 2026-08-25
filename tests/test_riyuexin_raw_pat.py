import tempfile
import unittest
from pathlib import Path

import pandas as pd

from factories.riyuexin.pat_cleaner import build_raw_pat, generate_raw_pat


PRODUCT = "NCEAP40PT15D(M)-2B00"


def _write_raw(
    path: Path,
    parameter: str,
    unit: str,
    values: list[float],
    *,
    cont=False,
    unit_row=6,
    test_no_row=18,
):
    frame = pd.DataFrame([[None] * 4 for _ in range(test_no_row + 1 + len(values))])
    frame.iat[1, 0] = "CONT" if cont else None
    frame.iat[1, 1] = parameter
    frame.iat[unit_row, 0] = "Unit"
    frame.iat[unit_row, 1] = unit
    frame.iat[test_no_row, 0] = "Test No."
    for index, value in enumerate(values, start=test_no_row + 1):
        frame.iat[index, 1] = value
    frame.to_excel(path, header=False, index=False)


class RiyuexinRawPatTests(unittest.TestCase):
    def test_builds_dc_dvds_rg_pat_directly_from_product_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for label in ("DC", "DVDS", "RG"):
                (root / label).mkdir()
            _write_raw(
                root / "DC" / f"NCT1_{PRODUCT}_FA61-3788_DC.xlsx",
                "VTH",
                "V",
                [1.0, 2.0, 3.0, 4.0],
                cont=True,
            )
            _write_raw(
                root / "DVDS" / f"NCT1_{PRODUCT}_FA61-3788_DVDS.xlsx",
                "DVDS",
                "mV",
                [100.0, 200.0, 300.0, 400.0],
                unit_row=4,
                test_no_row=16,
            )
            _write_raw(
                root / "RG" / f"NCT1_{PRODUCT}_FA61-3788_RG.xlsx",
                "RG",
                "R",
                [2.0, 2.2, 2.4, 2.6],
            )

            result = build_raw_pat(root, spool_dir=root / "spool", progress_interval=0)

        stats = result.iloc[1:].set_index("统计量")
        self.assertEqual(set(stats.index), {"VTH(V)", "DVDS(mV)", "RG(R)"})
        self.assertEqual(int(stats.loc["VTH(V)", "总计数"]), 4)
        self.assertAlmostEqual(float(stats.loc["DVDS(mV)", "中位数"]), 250.0)

    def test_rejects_mixed_products(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "DC").mkdir()
            _write_raw(
                root / "DC" / f"NCT1_{PRODUCT}_FA61-3788_DC.xlsx",
                "VTH",
                "V",
                [1.0],
                cont=True,
            )
            _write_raw(
                root / "DC" / "NCT2_NCEAP020N10LL(M)-7B00_FA61-3788_DC.xlsx",
                "VTH",
                "V",
                [2.0],
                cont=True,
            )
            with self.assertRaisesRegex(ValueError, "多个产品"):
                build_raw_pat(root)

    def test_generate_raw_pat_writes_sequenced_workbook(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "DC"
            source.mkdir()
            _write_raw(
                source / f"NCT1_{PRODUCT}_FA61-3788_DC.xlsx",
                "VTH",
                "V",
                [1.0, 2.0],
                cont=True,
            )
            output = generate_raw_pat(source, root / "reports")

            self.assertIsNotNone(output)
            self.assertEqual(output.parent.name, "PAT_001")
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
