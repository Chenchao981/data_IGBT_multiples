import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from factories.riyuexin.dc_cleaner import DCDataCleaner
from frontend.ft_scatter import load_scatter_bundle


def _synthetic_ase_dc_source() -> pd.DataFrame:
    frame = pd.DataFrame([[None] * 5 for _ in range(10)])
    frame.iat[1, 0] = "CONT"
    frame.iat[1, 1] = "VTH"
    frame.iat[1, 2] = "SAME"
    frame.iat[1, 3] = "IDSS"
    frame.iat[2, 1] = "*1.300"
    frame.iat[3, 1] = "<2.200"
    frame.iat[4, 1] = "(ID)250uA"
    frame.iat[6, 1] = "V"
    frame.iat[2, 3] = 0
    frame.iat[3, 3] = "<500.0n"
    frame.iat[4, 3] = "(VDS)40V"
    frame.iat[6, 3] = "nA"
    frame.iat[7, 0] = "Test No."
    frame.iat[8, 1] = 1.5
    frame.iat[8, 3] = 100
    frame.iat[9, 1] = 2.3
    frame.iat[9, 3] = 600
    return frame


class RiyuexinDCScatterTests(unittest.TestCase):
    def test_cleaning_exports_source_limits_without_changing_excel_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = root / "NCT5542087_demo_FA59-3997_20251024.xlsx"
            source_file.touch()
            output_dir = root / "output"
            cleaner = DCDataCleaner(root, output_dir)

            with patch(
                "factories.riyuexin.dc_cleaner.scan_excel_files",
                return_value=[source_file],
            ), patch(
                "factories.riyuexin.dc_cleaner.read_excel_fast",
                return_value=_synthetic_ase_dc_source(),
            ):
                self.assertTrue(cleaner.process_all_dc_files())

            self.assertTrue(cleaner.last_output_file.is_file())
            self.assertTrue(cleaner.last_scatter_manifest.is_file())
            cleaned = pd.read_excel(cleaner.last_output_file, sheet_name="DC_Data")
            self.assertNotIn("Source_ID", cleaned.columns)
            self.assertNotIn("_source_id", cleaned.columns)

            manifest, data, specs = load_scatter_bundle(cleaner.last_scatter_manifest)
            self.assertEqual(manifest["row_count"], 2)
            self.assertEqual(data["Source_ID"].tolist(), ["NCT5542087", "NCT5542087"])
            vth = specs.loc[specs["Parameter"] == "VTH(V)"].iloc[0]
            self.assertEqual(vth["Low_Limit_Raw"], "*1.300")
            self.assertEqual(vth["High_Limit_Raw"], "<2.200")
            self.assertEqual(float(vth["Low_Limit"]), 1.3)
            self.assertEqual(float(vth["High_Limit"]), 2.2)
            self.assertEqual(vth["Test_Condition"], "ID=250uA")
            idss = specs.loc[specs["Parameter"] == "IDSS40(nA)"].iloc[0]
            self.assertEqual(float(idss["High_Limit"]), 500.0)


if __name__ == "__main__":
    unittest.main()
