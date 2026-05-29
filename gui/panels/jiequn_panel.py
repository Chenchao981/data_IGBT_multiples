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
    data_types = ["DC", "DVDS", "RG", "联合", "PAT"]
    default_input = "data/杰群"
    default_output = "output/杰群-output"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_default_paths(self.default_input, self.default_output)

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

        elif data_type == "联合":
            from factories.jiequn.unified_cleaner import process_unified
            return lambda: process_unified(input_dir=inp, output_dir=out)

        elif data_type == "PAT":
            from factories.jiequn.pat_cleaner import build_pat, save_pat
            return lambda: bool(save_pat(build_pat(out), out))

        return lambda: False
