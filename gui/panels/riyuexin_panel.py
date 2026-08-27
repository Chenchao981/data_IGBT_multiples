#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""日月新（Riyuexin）面板。"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from gui.panels.base_panel import BasePanel
from gui.operation_result import OperationResult
from factories.riyuexin.config import FACTORY_NAME, DATA_TYPES


class RiyuexinPanel(BasePanel):
    factory_name = FACTORY_NAME
    data_types = DATA_TYPES
    pat_analysis_types = ["PAT"]
    yield_analysis_types = ["SYL&SBL"]
    scatter_supported_types = ["DC"]
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

            def _run_dc():
                cleaner = DCDataCleaner(input_dir=inp, output_dir=out)
                success = cleaner.process_all_dc_files()
                return OperationResult(
                    success=success,
                    output_file=cleaner.last_output_file,
                    scatter_manifest=cleaner.last_scatter_manifest,
                )

            return _run_dc

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
            from factories.riyuexin.pat_cleaner import generate_raw_pat

            def _run_raw_pat():
                output_file = generate_raw_pat(source_dir=inp, output_dir=out)
                self._require_success("PAT", bool(output_file))
                return OperationResult(success=True, output_file=Path(output_file))

            return _run_raw_pat

        elif data_type == "SYL&SBL":
            from factories.riyuexin.yield_report import generate_report
            return lambda: self._require_success(
                "SYL&SBL", bool(generate_report(source_file=inp, output_dir=out))
            )

        return lambda: False

    def _apply_operation_ui(self, data_type: str):
        super()._apply_operation_ui(data_type)
        if data_type == "PAT" and hasattr(self, "input_edit"):
            self.input_label.setText("PAT 原始文件目录:")
            self.input_edit.setPlaceholderText(
                "选择日月新产品根目录或 DC/DVDS/RG 原始文件目录..."
            )
            self.input_browse_btn.setText("预览文件目录...")

    def _input_mode_for(self, data_type: str) -> str:
        if data_type == "PAT":
            return "directory"
        return super()._input_mode_for(data_type)

    def _action_text_for(self, data_type: str) -> str:
        if data_type == "PAT":
            return "计算 PAT"
        return super()._action_text_for(data_type)

    def _missing_input_message(self) -> str:
        if self._selected_type == "PAT":
            return "请选择包含日月新原始 XLSX 的目标目录"
        return super()._missing_input_message()

    def _require_success(self, label: str, result: bool) -> bool:
        if result:
            return True
        raise RuntimeError(
            f"日月新 {label} 处理没有生成有效结果。"
            "PAT 请选择产品根目录或原始 DC/DVDS/RG XLSX 目录；"
            "SYL&SBL 请选择封装厂良率 Excel 文件。"
        )
