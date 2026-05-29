#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""日月新（ASE）面板"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from gui.panels.base_panel import BasePanel
from factories.riyuexin.config import FACTORY_NAME, DATA_TYPES


class RiyuexinPanel(BasePanel):
    factory_name = FACTORY_NAME
    data_types = DATA_TYPES
    default_input = "ASEData"
    default_output = "output"

    def __init__(self, parent=None):
        super().__init__(parent)
        desktop = str(Path.home() / "Desktop")
        self.set_default_paths(desktop, desktop)

    def _get_cleaner_fn(self, data_type: str):
        inp = self.input_edit.text().strip()
        out = self.output_edit.text().strip()

        if data_type == "DC":
            from factories.riyuexin.dc_cleaner import DCDataCleaner
            return lambda: DCDataCleaner(input_dir=inp, output_dir=out).process_all_dc_files()

        elif data_type == "DVDS":
            from factories.riyuexin.dvds_cleaner import DVDSCleaner
            def _run():
                c = DVDSCleaner(base_dir=str(Path(inp).parent.parent))
                c.dvds_dir = inp
                c.output_dir = out
                return bool(c.process_all())
            return _run

        elif data_type == "RG":
            from factories.riyuexin.rg_cleaner import RGCleaner
            return lambda: bool(RGCleaner(input_dir=inp, output_dir=out).run())

        return lambda: False
