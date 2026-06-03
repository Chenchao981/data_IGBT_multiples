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
    # 第一行：原始数据文件格式/清洗入口；第二行：清洗后统计分析。
    data_types = ["DC", "DVDS", "RG", "统一CSV"]
    post_process_types = ["PAT"]
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
            return lambda: self._require_success("DC", JiequnDCCleaner(input_dir=inp, output_dir=out).process_all())

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
            from factories.jiequn.pat_cleaner import build_pat, save_pat
            return lambda: self._require_success("PAT", bool(save_pat(build_pat(out), out)))

        return lambda: False

    def _require_success(self, label: str, result: bool) -> bool:
        if result:
            return True
        raise RuntimeError(
            f"杰群 {label} 处理没有生成有效结果。请确认输入目录是否选对："
            "DC/DVDS/RG 使用 杰群 格式1目录（可选 data/杰群、产品 PAT 目录或对应子目录）；"
            "统一CSV 使用 data/杰群2/RAW；PAT 使用清洗后的输出目录。"
        )
