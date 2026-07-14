import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from gui.panels.jiequn_panel import JiequnPanel


class JiequnPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = JiequnPanel()
        self.panel.input_edit.setText(r"F:\data\jq_input")
        self.panel.output_edit.setText(r"F:\data\jq_output")

    def tearDown(self):
        self.panel.close()

    def test_dc_ai_is_default_and_manual_dc_formats_remain_available(self):
        self.assertEqual(self.panel._selected_type, "DC-AI")
        self.assertEqual(
            self.panel.data_types,
            ["DC-AI", "DC-1", "DC-统一CSV", "DC-3", "DVDS", "RG"],
        )
        self.assertEqual(self.panel.start_btn.text(), "自动识别并清洗")

    def test_dc_ai_calls_factory_auto_dispatcher(self):
        with patch("factories.jiequn.dc_auto.run_auto_dc", return_value=True) as run_auto_dc:
            task = self.panel._get_cleaner_fn("DC-AI")

            self.assertTrue(task())

            run_auto_dc.assert_called_once_with(
                input_dir=r"F:\data\jq_input",
                output_dir=r"F:\data\jq_output",
            )


if __name__ == "__main__":
    unittest.main()
