#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""杰群（Jiequn）面板"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from gui.panels.base_panel import BasePanel
from factories.jiequn.config import FACTORY_NAME


class JiequnPanel(BasePanel):
    factory_name = FACTORY_NAME
    data_types = ["DC", "DVDS", "RG", "统一CSV", "PAT"]  # 格式1: 分文件 / 格式2: 单文件 / 统计
    default_input = str(project_root / "data" / "杰群")
    default_output = str(project_root / "output" / "杰群-output")
    unified_input = str(project_root / "data" / "杰群2" / "RAW")
    unified_output = str(project_root / "output" / "杰群2")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_default_paths(self.default_input, self.default_output)

    def _on_type_selected(self, data_type: str):
        super()._on_type_selected(data_type)
        current_input = self.input_edit.text().strip()
        current_output = self.output_edit.text().strip()
        known_inputs = {self.default_input, self.unified_input}
        known_outputs = {self.default_output, self.unified_output}

        if data_type == "统一CSV":
            if not current_input or current_input in known_inputs:
                self.input_edit.setText(self.unified_input)
            if not current_output or current_output in known_outputs:
                self.output_edit.setText(self.unified_output)
        elif data_type in {"DC", "DVDS", "RG", "PAT"}:
            if not current_input or current_input in known_inputs:
                self.input_edit.setText(self.default_input)
            if not current_output or current_output in known_outputs:
                self.output_edit.setText(self.default_output)

    def _get_cleaner_fn(self, data_type: str):
        inp = self.input_edit.text().strip()
        out = self.output_edit.text().strip()

        if data_type == "DC":
            from factories.jiequn.dc_cleaner import JiequnDCCleaner
            return lambda: JiequnDCCleaner(input_dir=inp, output_dir=out).process_all()

        elif data_type == "DVDS":
            from factories.jiequn.dvds_cleaner import JiequnDVDSCleaner
            return lambda: JiequnDVDSCleaner(input_dir=inp, output_dir=out).process_all()

        elif data_type == "RG":
            from factories.jiequn.rg_cleaner import JiequnRGCleaner
            return lambda: JiequnRGCleaner(input_dir=inp, output_dir=out).process_all()

        elif data_type == "统一CSV":
            from factories.jiequn.clean_unified import run
            return lambda: run(input_dir=inp, output_dir=out)

        elif data_type == "PAT":
            from factories.jiequn.pat_cleaner import build_pat, save_pat
            return lambda: bool(save_pat(build_pat(out), out))

        return lambda: False
