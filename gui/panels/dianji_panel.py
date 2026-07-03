#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""电基（Dianji）面板。"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from gui.panels.base_panel import BasePanel
from factories.dianji.config import FACTORY_NAME


class DianjiPanel(BasePanel):
    factory_name = FACTORY_NAME
    data_types = []
    yield_analysis_types = ["SYL&SBL"]
    default_input = str(Path.home() / "Desktop")
    default_output = str(Path.home() / "Desktop")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_default_paths(*self._default_paths_for_type(self._selected_type))

    def _get_cleaner_fn(self, data_type: str):
        inp = self.input_edit.text().strip()
        out = self.output_edit.text().strip()

        if data_type == "SYL&SBL":
            from factories.dianji.yield_report import generate_report
            return lambda: self._require_success(
                "SYL&SBL", bool(generate_report(source_file=inp, output_dir=out))
            )

        return lambda: False

    def _require_success(self, label: str, result: bool) -> bool:
        if result:
            return True
        raise RuntimeError(f"电基 {label} 处理没有生成有效结果。请确认良率 Excel 文件和输出目录是否选择正确。")
