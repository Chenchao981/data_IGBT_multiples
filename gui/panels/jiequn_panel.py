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
    data_types = ["DC", "DC-3", "DVDS", "RG", "统一CSV"]
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

        if data_type in {"DC", "DC-3"}:
            from factories.jiequn.dc_cleaner import JiequnDCCleaner
            return lambda: self._require_success(
                data_type,
                JiequnDCCleaner(input_dir=inp, output_dir=out).process_all(),
            )

        elif data_type == "DVDS":
            from factories.jiequn.dvds_cleaner import JiequnDVDSCleaner
            return lambda: self._require_success("DVDS", JiequnDVDSCleaner(input_dir=inp, output_dir=out).process_all())

        elif data_type == "RG":
            from factories.jiequn.rg_cleaner import JiequnRGCleaner
            return lambda: self._require_success("RG", JiequnRGCleaner(input_dir=inp, output_dir=out).process_all())

        elif data_type == "统一CSV":
            from factories.jiequn.clean_unified import run
            return lambda: self._require_success("统一CSV", run(input_dir=inp, output_dir=out))

        elif data_type == "PAT":
            from factories.jiequn.pat_cleaner import generate_pat
            source_files = self.selected_input_files()
            return lambda: self._require_success(
                "PAT", bool(generate_pat(source_files=source_files, output_dir=out))
            )

        elif data_type == "SYL&SBL":
            from factories.jiequn.yield_report import generate_report
            return lambda: self._require_success(
                "SYL&SBL", bool(generate_report(source_file=inp, output_dir=out))
            )

        return lambda: False

    def _require_success(self, label: str, result: bool) -> bool:
        if result:
            return True
        raise RuntimeError(
            f"杰群 {label} 处理没有生成有效结果。请确认输入目录是否选对："
            "DC/DVDS/RG 使用杰群格式1目录；第三产线 DC 可选择 DC1 根目录或产品目录；"
            "PAT 选择一个或多个清洗结果 Excel 文件；SYL&SBL 使用单个良率 Excel 文件。"
        )
