import tempfile
import unittest
from pathlib import Path

import pandas as pd

from factories.jiequn.dvds_cleaner import JiequnDVDSCleaner
from factories.jiequn.rg_cleaner import JiequnRGCleaner


class JiequnSpecializedResultDetectionTests(unittest.TestCase):
    def _write_result(self, directory: Path, name: str, sheet_name: str):
        path = directory / name
        pd.DataFrame(
            {"NUM": [1], "批次": ["CJSx185"], sheet_name.split("_")[0]: [1.0]}
        ).to_excel(path, sheet_name=sheet_name, index=False)
        return path.resolve()

    def test_rg_output_directory_is_recognized_without_recleaning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "CJSx185_001"
            source.mkdir()
            existing = self._write_result(source, "CJSx185_001_RG.xlsx", "RG_Data")

            cleaner = JiequnRGCleaner(source, root / "new_output")

            self.assertTrue(cleaner.process_all())
            self.assertEqual(cleaner.last_output_file, existing)
            self.assertEqual(list((root / "new_output").iterdir()), [])

    def test_dvds_output_directory_is_recognized_without_recleaning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "CJSx185_001"
            source.mkdir()
            existing = self._write_result(
                source, "CJSx185_001_DVDS.xlsx", "DVDS_Data"
            )

            cleaner = JiequnDVDSCleaner(source, root / "new_output")

            self.assertTrue(cleaner.process_all())
            self.assertEqual(cleaner.last_output_file, existing)

    def test_multiple_rg_results_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "ambiguous"
            source.mkdir()
            self._write_result(source, "first_RG.xlsx", "RG_Data")
            self._write_result(source, "second_RG.xlsx", "RG_Data")

            cleaner = JiequnRGCleaner(source, root / "new_output")

            self.assertFalse(cleaner.process_all())
            self.assertIsNone(cleaner.last_output_file)


if __name__ == "__main__":
    unittest.main()
