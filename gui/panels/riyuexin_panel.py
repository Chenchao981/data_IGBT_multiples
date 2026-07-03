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
    pat_analysis_types = ["PAT"]
    yield_analysis_types = ["SYL&SBL"]
    default_input = str(Path.home() / "Desktop")
    default_output = str(Path.home() / "Desktop")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_default_paths(*self._default_paths_for_type(self._selected_type))

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

        elif data_type == "PAT":
            from factories.riyuexin.pat_cleaner import generate_pat
            source_files = self.selected_input_files()
            return lambda: self._require_success(
                "PAT", bool(generate_pat(source_files=source_files, output_dir=out))
            )

        elif data_type == "SYL&SBL":
            from factories.riyuexin.yield_report import generate_report
            return lambda: self._require_success(
                "SYL&SBL", bool(generate_report(source_file=inp, output_dir=out))
            )

        return lambda: False

    def _require_success(self, label: str, result: bool) -> bool:
        if result:
            return True
        raise RuntimeError(
            f"日月新 {label} 处理没有生成有效结果。"
            "PAT 请选择一个或多个已清洗 DC/DVDS/RG Excel 文件；"
            "SYL&SBL 请选择封装厂良率 Excel 文件。"
        )
