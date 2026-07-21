#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""电基 PAT 统计入口。

电基清洗结果使用 ``RAW`` 工作表；统计公式和输出格式与日月新完全一致，
由共用 PAT 引擎计算。
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import pandas as pd

from factories.jiequn.pat_cleaner import build_pat as build_standard_pat
from shared.excel_utils import create_output_run_dir, generate_run_filename, write_excel_fast


RAW_DATA_LABELS = ("RAW",)
RAW_DATA_SHEET_PATTERN = re.compile(r"^(RAW)(?:_(\d+))?$", re.IGNORECASE)


def build_pat(
    source_dir: str | Path | None = None,
    source_files: Iterable[str | Path] | str | Path | None = None,
) -> pd.DataFrame:
    """对电基 ``RAW``/``RAW_n`` 清洗结果计算标准 PAT。"""
    if source_dir is None and source_files is None:
        source_dir = "output/电基-output"
    return build_standard_pat(
        source_dir=source_dir,
        source_files=source_files,
        data_labels=RAW_DATA_LABELS,
        data_sheet_pattern=RAW_DATA_SHEET_PATTERN,
    )


def save_pat(pat_df: pd.DataFrame, output_dir: str | Path) -> Path | None:
    """将电基 PAT 结果保存到独立的顺序运行目录。"""
    if pat_df.empty:
        return None

    run_dir = create_output_run_dir(output_dir, ["PAT"])
    output_path = run_dir / generate_run_filename(run_dir)
    if not write_excel_fast(pat_df, output_path, sheet_name="PAT", index=False):
        return None
    print(f"电基 PAT 保存成功: {output_path}")
    return output_path


def generate_pat(
    source_dir: str | Path | None = None,
    output_dir: str | Path = "output/电基-output",
    source_files: Iterable[str | Path] | str | Path | None = None,
) -> Path | None:
    """生成并保存电基 PAT 报表。"""
    return save_pat(build_pat(source_dir=source_dir, source_files=source_files), output_dir)
