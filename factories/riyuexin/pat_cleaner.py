#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""日月新 PAT 统计入口。

日月新清洗结果与杰群使用相同的标准工作表契约，因此复用同一套
PAT 统计公式和输出格式。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from factories.jiequn.pat_cleaner import build_pat as build_standard_pat
from shared.excel_utils import create_output_run_dir, generate_run_filename, write_excel_fast


def build_pat(
    source_dir: str | Path | None = None,
    source_files: Iterable[str | Path] | str | Path | None = None,
) -> pd.DataFrame:
    """使用标准多文件、多 Sheet PAT 聚合逻辑处理日月新清洗结果。"""
    return build_standard_pat(source_dir=source_dir, source_files=source_files)


def save_pat(pat_df: pd.DataFrame, output_dir: str | Path) -> Path | None:
    """将 PAT 结果保存到独立的顺序运行目录。"""
    if pat_df.empty:
        return None

    run_dir = create_output_run_dir(output_dir, ["PAT"])
    output_path = run_dir / generate_run_filename(run_dir)
    if not write_excel_fast(pat_df, output_path, sheet_name="PAT", index=False):
        return None
    print(f"日月新 PAT 保存成功: {output_path}")
    return output_path


def generate_pat(
    source_dir: str | Path | None = None,
    output_dir: str | Path = "output/日月新-output",
    source_files: Iterable[str | Path] | str | Path | None = None,
) -> Path | None:
    """生成并保存日月新 PAT 报表。"""
    return save_pat(build_pat(source_dir=source_dir, source_files=source_files), output_dir)
