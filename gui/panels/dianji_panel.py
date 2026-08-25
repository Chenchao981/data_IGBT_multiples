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
            from factories.dianji.pat_cleaner import generate_raw_pat

            def _run_raw_pat():
                output_file = generate_raw_pat(source_dir=inp, output_dir=out)
                self._require_success("PAT", bool(output_file))
                return OperationResult(success=True, output_file=Path(output_file))

            return _run_raw_pat

        if data_type == "SYL&SBL":
            from factories.dianji.yield_report import generate_report
            return lambda: self._require_success(
                "SYL&SBL", bool(generate_report(source_file=inp, output_dir=out))
            )

        return lambda: False

    def _apply_operation_ui(self, data_type: str):
        super()._apply_operation_ui(data_type)
        if data_type == "PAT" and hasattr(self, "input_edit"):
            self.input_label.setText("PAT 原始文件目录:")
            self.input_edit.setPlaceholderText(
                "选择一种电基原始 FT 文件格式所在目录..."
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
            return "请选择包含电基原始 FT 文件的目标目录"
        return super()._missing_input_message()

    def _require_success(self, label: str, result: bool) -> bool:
        if result:
            return True
        raise RuntimeError(
            f"电基 {label} 处理没有生成有效结果。"
            "FT-ALL 请选择 PowerTECH .xls/.xlsx、STS8203 .csv 或 TF .csv 原始数据目录；"
            "PAT 请选择一种电基原始 FT 文件格式所在目录；"
            "SYL&SBL 请选择封装厂良率 Excel 文件。"
        )
