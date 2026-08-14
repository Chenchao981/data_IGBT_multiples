#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""集佳（Jijia）FT 数据清洗面板。"""

from pathlib import Path

from factories.jijia.config import DATA_TYPES, FACTORY_NAME
from gui.panels.base_panel import BasePanel


class JijiaPanel(BasePanel):
    factory_name = FACTORY_NAME
    data_types = DATA_TYPES
    default_input = str(Path.home() / "Desktop")
    default_output = str(Path.home() / "Desktop")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_default_paths(*self._default_paths_for_type(self._selected_type))

    def _get_cleaner_fn(self, data_type: str):
        inp = self.input_edit.text().strip()
        out = self.output_edit.text().strip()
        if data_type == "FT-ALL":
            from factories.jijia.dc_cleaner import JijiaFTCleaner

            def _run_ft_all():
                cleaner = JijiaFTCleaner(inp, out)
                if not cleaner.process_all():
                    raise RuntimeError("集佳 FT-ALL 处理没有生成有效结果")
                return True

            return _run_ft_all
        return lambda: False
