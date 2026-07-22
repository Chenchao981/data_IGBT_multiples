import tempfile
import unittest
from pathlib import Path

import pandas as pd

from factories.jiequn.csv_parser import parse_dta_csv
from factories.jiequn.dc_cleaner import JiequnDCCleaner
from frontend.ft_scatter import load_scatter_bundle


def _write_dc_source(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "PRODUCT_1JT0001_100000FA_260101DTA.CSV"
    path.write_text(
        "\n".join(
            [
                "DTA File Name,sample.dta",
                "Item,,VTH,VTH,IDSS,RDON",
                "Min Limit,,,1.300E+00,,4.000E-03",
                "Max Limit,,5.000E+00,2.200E+00,1.000E-07,5.500E-03",
                "Limit Units,,V,V,A,R",
                "Bias 1,,ID,ID,VDS,ID",
                "Bias 1 Value,,2.500E-04,2.500E-04,4.000E+01,2.000E+01",
                "Bias 1 Units,,A,A,V,A",
                "Bias 2,,,,,VGS",
                "Bias 2 Value,,,,,1.000E+01",
                "Bias 2 Units,,,,,V",
                "Serial,Bin",
                "1,1,0,1.5,5.0E-08,4.5E-03",
                "2,1,0,2.3,2.0E-07,6.0E-03",
            ]
        ),
        encoding="utf-8",
    )
    return path


class JiequnScatterTests(unittest.TestCase):
    def test_parser_normalizes_reversed_p_type_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "PRODUCT_1JS0001_DTA.CSV"
            path.write_text(
                "\n".join(
                    [
                        "Item,,VTH",
                        "Min Limit,,-3.000E-01",
                        "Max Limit,,-2.300E+00",
                        "Limit Units,,V",
                        "Bias 1,,ID",
                        "Bias 1 Value,,-2.500E-04",
                        "Bias 1 Units,,A",
                        "Serial,Bin",
                        "1,1,-1.5",
                    ]
                ),
                encoding="utf-8",
            )

            parsed = parse_dta_csv(str(path), ["VTH"])
            spec = parsed.attrs["scatter_specs"].iloc[0]

            self.assertEqual(spec["Low_Limit_Raw"], "-3.000E-01")
            self.assertEqual(spec["High_Limit_Raw"], "-2.300E+00")
            self.assertEqual(float(spec["Low_Limit"]), -2.3)
            self.assertEqual(float(spec["High_Limit"]), -0.3)
            self.assertTrue(bool(spec["Limit_Order_Normalized"]))

    def test_dc_cleaning_exports_converted_limits_without_changing_excel(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_dc_source(root / "DC")
            cleaner = JiequnDCCleaner(root, root / "output")

            self.assertTrue(cleaner.process_all())
            self.assertTrue(cleaner.last_output_file.is_file())
            self.assertTrue(cleaner.last_scatter_manifest.is_file())

            cleaned = pd.read_excel(cleaner.last_output_file, sheet_name="DC_Data")
            self.assertNotIn("Source_ID", cleaned.columns)
            self.assertNotIn("_source_id", cleaned.columns)

            manifest, data, specs = load_scatter_bundle(cleaner.last_scatter_manifest)
            self.assertEqual(manifest["factory"], "杰群")
            self.assertEqual(data["lot_ID"].unique().tolist(), ["1JT0001"])
            self.assertEqual(data["Source_ID"].nunique(), 1)
            idss = specs.loc[specs["Parameter"] == "IDSS40(nA)"].iloc[0]
            self.assertEqual(float(idss["High_Limit"]), 100.0)
            rdon = specs.loc[specs["Parameter"] == "RDON20(mR)"].iloc[0]
            self.assertEqual(float(rdon["Low_Limit"]), 4.0)
            self.assertEqual(float(rdon["High_Limit"]), 5.5)
            self.assertIn("VGS=1.000E+01V", rdon["Test_Condition"])


if __name__ == "__main__":
    unittest.main()
