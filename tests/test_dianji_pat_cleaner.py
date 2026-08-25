import tempfile
import unittest
from pathlib import Path

import pandas as pd

from factories.dianji.pat_cleaner import build_pat, build_raw_pat, generate_pat
from factories.jiequn.pat_cleaner import build_pat as build_standard_pat
from tests.test_dianji_powertech_xlsx_cleaner import _make_source


def _write_workbook(path: Path, sheets: dict[str, pd.DataFrame]) -> Path:
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
    return path


class DianjiPatTests(unittest.TestCase):
    def test_builds_pat_directly_from_registered_raw_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "raw"
            source.mkdir()
            _make_source(source)

            result = build_raw_pat(source, spool_dir=root / "spool", progress_interval=0)

        stats = result.iloc[1:].set_index("统计量")
        self.assertIn("DVCE(mV)", stats.index)
        self.assertEqual(int(stats.loc["DVCE(mV)", "总计数"]), 2)
        self.assertGreaterEqual(len(stats), 7)
        self.assertNotIn("批次", stats.index)

    def test_aggregates_raw_split_sheets_and_multiple_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = _write_workbook(
                root / "first.xlsx",
                {
                    "RAW_1": pd.DataFrame(
                        {
                            "NUM": [1, 2],
                            "批次": ["C1", "C1"],
                            "VTH1(V)": [1.0, 2.0],
                            "CONST(V)": [7.0, 7.0],
                            "SCI(A)": ["1e-3", "bad"],
                        }
                    ),
                    "RAW_2": pd.DataFrame(
                        {
                            "NUM": [3],
                            "批次": ["C2"],
                            "VTH1(V)": [3.0],
                            "CONST(V)": [7.0],
                            "SCI(A)": ["2E-3"],
                        }
                    ),
                },
            )
            second = _write_workbook(
                root / "second.xlsx",
                {
                    "RAW": pd.DataFrame(
                        {
                            "NUM": [4],
                            "批次": ["C3"],
                            "VTH1(V)": [4.0],
                            "CONST(V)": [7.0],
                            "SCI(A)": [None],
                        }
                    )
                },
            )

            result = build_pat(source_files=[first, second])

        self.assertEqual(result.iloc[0]["统计量"], "变量")
        stats = result.iloc[1:].set_index("统计量")
        self.assertEqual(set(stats.index), {"VTH1(V)", "CONST(V)", "SCI(A)"})
        self.assertNotIn("NUM", stats.index)
        self.assertNotIn("批次", stats.index)

        vth = stats.loc["VTH1(V)"]
        self.assertEqual(vth["总计数"], 4)
        self.assertAlmostEqual(vth["均值"], 2.5, places=6)
        self.assertAlmostEqual(vth["标准差"], 1.290994, places=6)
        self.assertAlmostEqual(vth["下四分位数"], 1.75, places=6)
        self.assertAlmostEqual(vth["中位数"], 2.5, places=6)
        self.assertAlmostEqual(vth["上四分位数"], 3.25, places=6)
        self.assertAlmostEqual(vth["Sigma"], 1.111111, places=6)
        self.assertAlmostEqual(vth["LCL\n计算值"], -4.166667, places=6)
        self.assertAlmostEqual(vth["UCL\n计算值"], 9.166667, places=6)

        constant = stats.loc["CONST(V)"]
        self.assertEqual(constant["Sigma"], 0)
        self.assertEqual(constant["LCL\n计算值"], 7)
        self.assertEqual(constant["UCL\n计算值"], 7)

        scientific = stats.loc["SCI(A)"]
        self.assertEqual(scientific["总计数"], 2)
        self.assertAlmostEqual(scientific["均值"], 0.0015, places=6)

    def test_handles_single_value_and_rejects_missing_raw_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            single = _write_workbook(
                root / "single.xlsx",
                {"RAW": pd.DataFrame({"NUM": [1], "VTH1(V)": [3.5]})},
            )
            wrong = _write_workbook(
                root / "wrong.xlsx",
                {"Sheet1": pd.DataFrame({"NUM": [1], "VTH1(V)": [3.5]})},
            )

            single_result = build_pat(source_files=[single])
            missing_result = build_pat(source_files=[wrong])

        row = single_result.iloc[1]
        self.assertEqual(row["总计数"], 1)
        self.assertTrue(pd.isna(row["标准差"]))
        self.assertEqual(row["Sigma"], 0)
        self.assertEqual(row["LCL\n计算值"], 3.5)
        self.assertEqual(row["UCL\n计算值"], 3.5)
        self.assertTrue(missing_result.empty)

    def test_keeps_standard_dc_contract_separate_from_dianji_raw(self):
        with tempfile.TemporaryDirectory() as temp:
            path = _write_workbook(
                Path(temp) / "mixed.xlsx",
                {
                    "DC_Data": pd.DataFrame({"NUM": [1, 2], "DC_PARAM": [2.0, 4.0]}),
                    "RAW": pd.DataFrame({"NUM": [1, 2], "DJ_PARAM": [3.0, 6.0]}),
                },
            )

            standard = build_standard_pat(source_files=[path])
            dianji = build_pat(source_files=[path])

        self.assertEqual(standard.iloc[1:]["统计量"].tolist(), ["DC_PARAM"])
        self.assertEqual(dianji.iloc[1:]["统计量"].tolist(), ["DJ_PARAM"])

    def test_generate_pat_writes_sequenced_pat_workbook(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = _write_workbook(
                root / "source.xlsx",
                {"RAW": pd.DataFrame({"NUM": [1, 2, 3], "VTH1(V)": [1.0, 2.0, 3.0]})},
            )

            output = generate_pat(source_files=[source], output_dir=root / "reports")

            self.assertIsNotNone(output)
            self.assertEqual(output.parent.name, "PAT_001")
            self.assertEqual(output.name, "PAT_001.xlsx")
            saved = pd.read_excel(output, sheet_name="PAT")
            self.assertEqual(saved.iloc[0]["统计量"], "变量")
            self.assertEqual(saved.iloc[1]["总计数"], 3)


if __name__ == "__main__":
    unittest.main()
