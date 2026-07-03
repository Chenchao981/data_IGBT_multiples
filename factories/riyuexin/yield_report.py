#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""日月新 SYL/SBL 统计报表入口。

字段解析、良率、Bin fail rate、3Sigma/4Sigma 和取整规则与杰群一致；
这里只保留日月新的厂别命名和公开调用入口。
"""

from __future__ import annotations

from pathlib import Path

from factories.jiequn.yield_report import (
    YieldReportConfig,
    build_analysis,
    build_summary,
    find_source_file,
    load_source_rows,
    product_family_name,
    sequenced_output_path,
    write_report,
)


def default_output_name(summary) -> str:
    """生成带日月新厂别标识的报表文件名。"""
    product = product_family_name(summary["产品名"].dropna().astype(str).tolist())
    return f"{product} ASE SYL&SBL.xlsx"


def generate_report(
    data_dir: str | Path = ".",
    output_dir: str | Path = "output",
    source_file: str | Path | None = None,
    output_file: str | Path | None = None,
    config: YieldReportConfig | None = None,
) -> Path:
    """使用与杰群相同的计算逻辑生成日月新 SYL/SBL 报表。"""
    source = Path(source_file) if source_file else find_source_file(data_dir)
    rows = load_source_rows(source)
    summary = build_summary(rows, config)
    analysis = build_analysis(rows)
    target = Path(output_file) if output_file else sequenced_output_path(
        output_dir, default_output_name(summary)
    )
    result = write_report(summary, analysis, target)
    print(f"日月新 SYL/SBL 保存成功: {result}")
    return result
