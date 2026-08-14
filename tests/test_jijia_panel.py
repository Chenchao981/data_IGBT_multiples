import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from gui.main_window import FACTORIES
from gui.panels.jijia_panel import JijiaPanel


class JijiaPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = JijiaPanel()
        self.panel.input_edit.setText(r"F:\data\集佳\NCE15TD120BT")
        self.panel.output_edit.setText(r"F:\data\集佳\output")

    def tearDown(self):
        self.panel.close()

    def test_ft_all_is_the_only_default_operation(self):
        self.assertEqual(self.panel._selected_type, "FT-ALL")
        self.assertEqual(self.panel.data_types, ["FT-ALL"])
        self.assertEqual(self.panel._input_mode_for("FT-ALL"), "directory")
        self.assertEqual(self.panel.start_btn.text(), "开始清洗")
        self.assertFalse(self.panel.scatter_btn.isVisible())

    def test_ft_all_calls_jijia_cleaner(self):
        with patch("factories.jijia.dc_cleaner.JijiaFTCleaner") as cleaner_cls:
            cleaner_cls.return_value.process_all.return_value = True
            task = self.panel._get_cleaner_fn("FT-ALL")

            self.assertTrue(task())

            cleaner_cls.assert_called_once_with(
                r"F:\data\集佳\NCE15TD120BT",
                r"F:\data\集佳\output",
            )
            cleaner_cls.return_value.process_all.assert_called_once_with()

    def test_main_window_registry_keeps_existing_factories_and_adds_jijia(self):
        names = [factory["name"] for factory in FACTORIES]
        self.assertEqual(
            names,
            [
                "日月新 (ASE)",
                "杰群 (Jiequn)",
                "电基 (Dianji)",
                "集佳 (Jijia)",
            ],
        )


if __name__ == "__main__":
    unittest.main()
