import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from gui.operation_result import OperationResult
from gui.panels.riyuexin_panel import RiyuexinPanel


class RiyuexinPanelScatterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = RiyuexinPanel()
        self.panel.input_edit.setText(r"F:\data\ase_dc")
        self.panel.output_edit.setText(r"F:\data\ase_output")

    def tearDown(self):
        self.panel.close()

    def test_dc_returns_manifest_and_enables_scatter_only_after_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "ft_scatter_manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            output = Path(temp_dir) / "cleaned.xlsx"
            output.touch()
            with patch("factories.riyuexin.dc_cleaner.DCDataCleaner") as cleaner_cls:
                cleaner = cleaner_cls.return_value
                cleaner.process_all_dc_files.return_value = True
                cleaner.last_output_file = output
                cleaner.last_scatter_manifest = manifest
                result = self.panel._get_cleaner_fn("DC")()

            self.assertIsInstance(result, OperationResult)
            self.assertTrue(result)
            self.assertEqual(result.scatter_manifest, manifest)
            self.assertFalse(self.panel.scatter_btn.isEnabled())

            self.panel.worker = SimpleNamespace(result=result)
            with patch("gui.panels.base_panel.QMessageBox.information"):
                self.panel._on_finished("日月新 DC 完成", True)
            self.assertTrue(self.panel.scatter_btn.isEnabled())

            self.panel._on_type_selected("DVDS")
            self.assertTrue(self.panel.scatter_btn.isHidden())
            self.panel._on_type_selected("DC")
            self.assertFalse(self.panel.scatter_btn.isHidden())
            self.assertTrue(self.panel.scatter_btn.isEnabled())

    def test_action_order_is_clean_first_then_scatter(self):
        action_layout = self.panel.layout().itemAt(2).layout()
        widgets = [
            action_layout.itemAt(index).widget()
            for index in range(action_layout.count())
            if action_layout.itemAt(index).widget() is not None
        ]
        self.assertLess(
            widgets.index(self.panel.start_btn), widgets.index(self.panel.scatter_btn)
        )

    def test_pat_uses_raw_directory_and_direct_pat_entrypoint(self):
        self.panel._on_type_selected("PAT")
        self.panel.input_edit.setText(r"F:\data\ase_raw")
        self.panel.output_edit.setText(r"F:\data\ase_pat")

        self.assertEqual(self.panel._input_mode_for("PAT"), "directory")
        self.assertEqual(self.panel.input_label.text(), "PAT 原始文件目录:")
        self.assertEqual(self.panel.input_browse_btn.text(), "预览文件目录...")
        self.assertEqual(self.panel.start_btn.text(), "计算 PAT")

        with patch(
            "factories.riyuexin.pat_cleaner.generate_raw_pat",
            return_value=Path(r"F:\data\ase_pat\PAT_001\PAT_001.xlsx"),
        ) as generate_raw_pat:
            result = self.panel._get_cleaner_fn("PAT")()

        self.assertIsInstance(result, OperationResult)
        self.assertEqual(result.output_file.name, "PAT_001.xlsx")
        generate_raw_pat.assert_called_once_with(
            source_dir=r"F:\data\ase_raw",
            output_dir=r"F:\data\ase_pat",
        )


if __name__ == "__main__":
    unittest.main()
