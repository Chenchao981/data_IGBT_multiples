import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factories.jiequn import dc_auto


def _write_dta(directory: Path, items: list[str], name: str = "sampleDTA.CSV") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        "DTA File Name,sample.dta\n" + "Item,," + ",".join(items) + "\n",
        encoding="utf-8",
    )
    return path


class DetectDCFormatTests(unittest.TestCase):
    def test_detects_dc1_from_named_dc_subdirectory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_dta(root / "product" / "DC", ["VTH", "BVDSS", "RDON"])
            _write_dta(root / "product" / "DVDS", ["DVDS_EX"], "sample_DVDSDTA.CSV")

            result = dc_auto.detect_dc_format(root)

            self.assertEqual(result.format_name, dc_auto.DC_FORMAT_1)
            self.assertEqual(result.file_count, 1)
            self.assertEqual(result.source_dir, root)

    def test_detects_unified_csv_from_item_features(self):
        with tempfile.TemporaryDirectory() as temp:
            raw = Path(temp) / "RAW"
            _write_dta(raw, ["VTH", "BVDSS", "RDON", "DVDS_EX", "LCR-RG"])

            result = dc_auto.detect_dc_format(raw)

            self.assertEqual(result.format_name, dc_auto.DC_FORMAT_UNIFIED)
            self.assertEqual(result.source_dir, raw)

    def test_detects_dc3_from_flat_dc_only_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_dta(root / "product", ["VTH", "BVDSS", "RDON", "VFSDS"])

            result = dc_auto.detect_dc_format(root)

            self.assertEqual(result.format_name, dc_auto.DC_FORMAT_3)
            self.assertEqual(result.source_dir, root)

    def test_rejects_mixed_flat_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_dta(root / "dc3", ["VTH", "RDON"], "dc3DTA.CSV")
            _write_dta(
                root / "unified",
                ["VTH", "RDON", "DVDS_EX", "LCR-RG"],
                "unifiedDTA.CSV",
            )

            with self.assertRaisesRegex(dc_auto.DCFormatDetectionError, "多种杰群 DC 格式"):
                dc_auto.detect_dc_format(root)

    def test_rejects_partial_unified_signature(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_dta(root, ["VTH", "RDON", "DVDS_EX"])

            with self.assertRaisesRegex(dc_auto.DCFormatDetectionError, "缺少 LCR-RG"):
                dc_auto.detect_dc_format(root)


class RunAutoDCTests(unittest.TestCase):
    def test_dispatches_dc1_and_dc3_to_dc_cleaner(self):
        detection = dc_auto.DCFormatDetection(
            format_name=dc_auto.DC_FORMAT_3,
            source_dir=Path("source"),
            files=(Path("source/sampleDTA.CSV"),),
            reason="test",
        )
        with patch.object(dc_auto, "detect_dc_format", return_value=detection), patch.object(
            dc_auto, "JiequnDCCleaner"
        ) as cleaner_cls:
            cleaner_cls.return_value.process_all.return_value = True

            self.assertTrue(dc_auto.run_auto_dc("ignored", "output"))

            cleaner_cls.assert_called_once_with(
                input_dir=Path("source"),
                output_dir="output",
            )
            cleaner_cls.return_value.process_all.assert_called_once_with()

    def test_dispatches_unified_to_unified_cleaner(self):
        detection = dc_auto.DCFormatDetection(
            format_name=dc_auto.DC_FORMAT_UNIFIED,
            source_dir=Path("RAW"),
            files=(Path("RAW/sampleDTA.CSV"),),
            reason="test",
        )
        with patch.object(dc_auto, "detect_dc_format", return_value=detection), patch.object(
            dc_auto, "run_unified", return_value=True
        ) as run_unified:
            self.assertTrue(dc_auto.run_auto_dc("ignored", "output"))

            run_unified.assert_called_once_with(Path("RAW"), "output")


if __name__ == "__main__":
    unittest.main()
