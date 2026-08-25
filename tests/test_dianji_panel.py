import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from gui.panels.dianji_panel import DianjiPanel
from gui.operation_result import OperationResult


class DianjiPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = DianjiPanel()
        self.panel.input_edit.setText(r"F:\data\dianji_input")
        self.panel.output_edit.setText(r"F:\data\dianji_output")

    def tearDown(self):
        self.panel.close()

    def test_ft_all_is_default_and_reports_remain_available(self):
        self.assertEqual(self.panel._selected_type, "FT-ALL")
        self.assertEqual(self.panel.data_types, ["FT-ALL"])
        self.assertEqual(self.panel.pat_analysis_types, ["PAT"])
        self.assertEqual(self.panel.yield_analysis_types, ["SYL&SBL"])
        self.assertEqual(self.panel._input_mode_for("FT-ALL"), "directory")
        self.assertEqual(self.panel._input_mode_for("PAT"), "directory")
        self.assertEqual(self.panel._input_mode_for("SYL&SBL"), "file")
        self.assertEqual(self.panel.start_btn.text(), "开始清洗")

    def test_ft_all_calls_dianji_cleaner(self):
        with patch("factories.dianji.dc_cleaner.DianjiDCCleaner") as cleaner_cls:
            cleaner_cls.return_value.process_all.return_value = True
            task = self.panel._get_cleaner_fn("FT-ALL")

            self.assertTrue(task())

            cleaner_cls.assert_called_once_with(
                r"F:\data\dianji_input",
                r"F:\data\dianji_output",
            )
            cleaner_cls.return_value.process_all.assert_called_once_with()

    def test_ft_all_returns_manifest_and_enables_scatter_after_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "dianji_ft_scatter_manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            output = root / "cleaned.xlsx"
            output.touch()
            with patch("factories.dianji.dc_cleaner.DianjiDCCleaner") as cleaner_cls:
                cleaner = cleaner_cls.return_value
                cleaner.process_all.return_value = True
                cleaner.last_output_file = output
                cleaner.last_scatter_manifest = manifest
                result = self.panel._get_cleaner_fn("FT-ALL")()

            self.assertIsInstance(result, OperationResult)
            self.assertEqual(result.scatter_manifest, manifest)
            self.panel.worker = SimpleNamespace(result=result)
            with patch("gui.panels.base_panel.QMessageBox.information"):
                self.panel._on_finished("电基 FT-ALL 完成", True)
            self.assertTrue(self.panel.scatter_btn.isEnabled())

    def test_pat_uses_raw_directory_and_direct_pat_entrypoint(self):
        self.panel._on_type_selected("PAT")
        self.panel.input_edit.setText(r"F:\data\dianji_raw")
        self.panel.output_edit.setText(r"F:\data\dianji_output")

        self.assertEqual(self.panel.input_label.text(), "PAT 原始文件目录:")
        self.assertEqual(self.panel.input_browse_btn.text(), "预览文件目录...")
        self.assertEqual(self.panel.start_btn.text(), "计算 PAT")

        with patch(
            "factories.dianji.pat_cleaner.generate_raw_pat",
            return_value=Path(r"F:\data\PAT_001\PAT_001.xlsx"),
        ) as generate_raw_pat:
            result = self.panel._get_cleaner_fn("PAT")()

        self.assertIsInstance(result, OperationResult)
        self.assertEqual(result.output_file.name, "PAT_001.xlsx")
        generate_raw_pat.assert_called_once_with(
            source_dir=r"F:\data\dianji_raw",
            output_dir=r"F:\data\dianji_output",
        )


if __name__ == "__main__":
    unittest.main()
