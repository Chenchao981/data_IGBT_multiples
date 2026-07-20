import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from gui.panels.dianji_panel import DianjiPanel


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

    def test_ft_all_is_default_and_yield_report_remains_available(self):
        self.assertEqual(self.panel._selected_type, "FT-ALL")
        self.assertEqual(self.panel.data_types, ["FT-ALL"])
        self.assertEqual(self.panel.yield_analysis_types, ["SYL&SBL"])
        self.assertEqual(self.panel._input_mode_for("FT-ALL"), "directory")
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


if __name__ == "__main__":
    unittest.main()
