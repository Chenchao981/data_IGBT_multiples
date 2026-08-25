#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""杰群（Jiequn）面板"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from gui.panels.base_panel import BasePanel
from gui.operation_result import OperationResult
from factories.jiequn.config import FACTORY_NAME


class JiequnPanel(BasePanel):
    factory_name = FACTORY_NAME
    data_types = ["DC-AI", "DVDS", "RG"]
    pat_analysis_types = ["PAT"]
    yield_analysis_types = ["SYL&SBL"]
    scatter_supported_types = ["DC-AI"]
    default_input = str(Path.home() / "Desktop")
    default_output = str(Path.home() / "Desktop")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_default_paths(*self._default_paths_for_type(self._selected_type))

    def _get_cleaner_fn(self, data_type: str):
        inp = self.input_edit.text().strip()
        out = self.output_edit.text().strip()

        if data_type == "DC-AI":
            from factories.jiequn.dc_auto import run_auto_dc

            def _run_auto_dc():
                result = run_auto_dc(input_dir=inp, output_dir=out)
                self._require_success("DC-AI", bool(result))
                return OperationResult(
                    success=True,
                    output_file=getattr(result, "output_file", None),
                    scatter_manifest=getattr(result, "scatter_manifest", None),
                )

            return _run_auto_dc

        if data_type in {"DC", "DC-1", "DC-3"}:
            from factories.jiequn.dc_cleaner import JiequnDCCleaner

            def _run_dc():
                cleaner = JiequnDCCleaner(input_dir=inp, output_dir=out)
                self._require_success(data_type, cleaner.process_all())
                return OperationResult(
                    success=True,
                    output_file=cleaner.last_output_file,
                    scatter_manifest=cleaner.last_scatter_manifest,
                )

            return _run_dc

        elif data_type == "DVDS":
            from factories.jiequn.dvds_cleaner import JiequnDVDSCleaner

            def _run_dvds():
                cleaner = JiequnDVDSCleaner(input_dir=inp, output_dir=out)
                self._require_success("DVDS", cleaner.process_all())
                return OperationResult(
                    success=True,
                    output_file=cleaner.last_output_file,
                )

            return _run_dvds

        elif data_type == "RG":
            from factories.jiequn.rg_cleaner import JiequnRGCleaner

            def _run_rg():
                cleaner = JiequnRGCleaner(input_dir=inp, output_dir=out)
                self._require_success("RG", cleaner.process_all())
                return OperationResult(
                    success=True,
                    output_file=cleaner.last_output_file,
                )

            return _run_rg

        elif data_type in {"统一CSV", "DC-统一CSV"}:
            from factories.jiequn.clean_unified import run_with_result

            def _run_unified():
                result = run_with_result(input_dir=inp, output_dir=out)
                self._require_success(data_type, bool(result))
                return OperationResult(
                    success=True,
                    output_file=result.output_file,
                    scatter_manifest=result.scatter_manifest,
                )

            return _run_unified

        elif data_type == "PAT":
            from factories.jiequn.pat_cleaner import generate_raw_pat

            def _run_raw_pat():
                output_file = generate_raw_pat(source_dir=inp, output_dir=out)
                self._require_success("PAT", bool(output_file))
                return OperationResult(success=True, output_file=Path(output_file))

            return _run_raw_pat

        elif data_type == "SYL&SBL":
            from factories.jiequn.yield_report import generate_report
            return lambda: self._require_success(
                "SYL&SBL", bool(generate_report(source_file=inp, output_dir=out))
            )

        return lambda: False

    def _apply_operation_ui(self, data_type: str):
        super()._apply_operation_ui(data_type)
        if data_type == "PAT" and hasattr(self, "input_edit"):
            self.input_label.setText("PAT 原始文件目录:")
            self.input_edit.setPlaceholderText(
                "选择包含杰群 DTA CSV 的产品目录或分类型数据根目录..."
            )
            self.input_browse_btn.setText("预览文件目录...")
        elif data_type == "DC-AI" and hasattr(self, "input_edit"):
            self.input_label.setText("杰群原始数据文件夹:")
            self.input_edit.setPlaceholderText(
                "选择一种杰群格式；分目录数据会自动连续清洗 DC、DVDS、RG..."
            )
        elif data_type in {"DVDS", "RG"} and hasattr(self, "input_edit"):
            self.input_label.setText(f"杰群 {data_type} 数据文件夹:")
            self.input_edit.setPlaceholderText(
                f"选择专用 {data_type} 目录，或包含该子目录的产品目录..."
            )

    def _action_text_for(self, data_type: str) -> str:
        if data_type == "DC-AI":
            return "自动识别并清洗"
        if data_type == "PAT":
            return "计算 PAT"
        return super()._action_text_for(data_type)

    def _input_mode_for(self, data_type: str) -> str:
        if data_type == "PAT":
            return "directory"
        return super()._input_mode_for(data_type)

    def _missing_input_message(self) -> str:
        if self._selected_type == "PAT":
            return "请选择包含杰群原始 DTA CSV 的文件目录"
        return super()._missing_input_message()

    def _require_success(self, label: str, result: bool) -> bool:
        if result:
            return True
        raise RuntimeError(
            f"杰群 {label} 处理没有生成有效结果。请确认输入目录是否选对："
            "DC-AI 一次只能选择一种杰群格式；分目录格式请选择包含 DC/DVDS/RG "
            "子目录的产品根目录（也可直接选 DC）；统一CSV选择 RAW 目录；"
            "第三产线可选择根目录或产品目录；"
            "专用 DVDS 或 RG 数据请使用对应的独立按钮；"
            "PAT 选择包含原始 DTA CSV 的产品目录或分类型数据根目录；"
            "SYL&SBL 使用单个良率 Excel 文件。"
        )
