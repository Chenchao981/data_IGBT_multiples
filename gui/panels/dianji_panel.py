#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""电基（Dianji）面板。"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from gui.panels.base_panel import BasePanel
from gui.operation_result import OperationResult
from factories.dianji.config import DATA_TYPES, FACTORY_NAME


class DianjiPanel(BasePanel):
    factory_name = FACTORY_NAME
    data_types = DATA_TYPES
    pat_analysis_types = ["PAT"]
    yield_analysis_types = ["SYL&SBL"]
    scatter_supported_types = ["FT-ALL"]
    default_input = str(Path.home() / "Desktop")
    default_output = str(Path.home() / "Desktop")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_default_paths(*self._default_paths_for_type(self._selected_type))

    def _get_cleaner_fn(self, data_type: str):
        inp = self.input_edit.text().strip()
        out = self.output_edit.text().strip()

        if data_type == "FT-ALL":
            from factories.dianji.dc_cleaner import DianjiDCCleaner

            def _run_ft_all():
                cleaner = DianjiDCCleaner(inp, out)
                self._require_success("FT-ALL", cleaner.process_all())
                return OperationResult(
                    success=True,
                    output_file=cleaner.last_output_file,
                    scatter_manifest=cleaner.last_scatter_manifest,
                )

            return _run_ft_all

        if data_type == "PAT":
            from factories.dianji.pat_cleaner import generate_pat
            source_files = self.selected_input_files()
            return lambda: self._require_success(
                "PAT", bool(generate_pat(source_files=source_files, output_dir=out))
            )

        if data_type == "SYL&SBL":
            from factories.dianji.yield_report import generate_report
            return lambda: self._require_success(
                "SYL&SBL", bool(generate_report(source_file=inp, output_dir=out))
            )

        return lambda: False

    def _require_success(self, label: str, result: bool) -> bool:
        if result:
            return True
        raise RuntimeError(
            f"电基 {label} 处理没有生成有效结果。"
            "FT-ALL 请选择 PowerTECH .xls/.xlsx、STS8203 .csv 或 TF .csv 原始数据目录；"
            "PAT 请选择一个或多个含 RAW 工作表的电基清洗结果；"
            "SYL&SBL 请选择封装厂良率 Excel 文件。"
        )
