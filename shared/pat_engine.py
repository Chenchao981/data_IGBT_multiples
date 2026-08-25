#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Shared exact, bounded-memory PAT engine for raw FT source adapters."""

from __future__ import annotations

import gc
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Iterable

import numpy as np
import pandas as pd


PAT_HEADERS = [
    "统计量", "总计数", "均值", "标准差", "最小值", "下四分位数",
    "中位数", "上四分位数", "最大值", "Sigma",
    "LCL\n计算值", "UCL\n计算值",
    "LCL\n更新前", "UCL\n更新前",
    "LCL\n更新后", "UCL\n更新后",
    "是否\n更新",
]

DEFAULT_IDENTIFIER_COLUMNS = frozenset({"NUM", "lot_ID", "周记", "批次"})


@dataclass(frozen=True)
class RawPatGroup:
    """Files sharing one parser and one exact ordered parameter schema."""

    label: str
    files: tuple[Path, ...]
    extractor: Callable[[Path], pd.DataFrame]


def compute_pat_stats(
    series: pd.Series,
    lsl: float | None = None,
    usl: float | None = None,
) -> dict:
    """Calculate the approved Jiequn PAT statistics for one parameter."""
    values = pd.to_numeric(series, errors="coerce").dropna()
    if len(values) == 0:
        return {}

    q1 = values.quantile(0.25)
    median = values.quantile(0.50)
    q3 = values.quantile(0.75)
    sigma = (q3 - q1) / 1.35 if q3 > q1 else 0.0
    return {
        "统计量": series.name,
        "总计数": len(values),
        "均值": round(values.mean(), 6),
        "标准差": round(values.std(ddof=1), 6),
        "最小值": round(values.min(), 6),
        "下四分位数": round(q1, 6),
        "中位数": round(median, 6),
        "上四分位数": round(q3, 6),
        "最大值": round(values.max(), 6),
        "Sigma": round(sigma, 6),
        "LCL\n计算值": round(median - 6 * sigma, 6),
        "UCL\n计算值": round(median + 6 * sigma, 6),
        "LCL\n更新前": lsl,
        "UCL\n更新前": usl,
        "LCL\n更新后": np.nan,
        "UCL\n更新后": np.nan,
        "是否\n更新": np.nan,
    }


def build_pat_frame(rows: list[dict]) -> pd.DataFrame:
    """Create the stable editable PAT workbook table."""
    if not rows:
        return pd.DataFrame()
    pat_df = pd.DataFrame(rows)
    pat_df = pat_df[[column for column in PAT_HEADERS if column in pat_df.columns]]
    header_row = {column: column for column in pat_df.columns}
    header_row["统计量"] = "变量"
    return pd.concat([pd.DataFrame([header_row]), pat_df], ignore_index=True)


def _spool_filename(column: str) -> str:
    digest = hashlib.sha256(column.encode("utf-8")).hexdigest()[:16]
    return f"parameter_{digest}.float64"


def build_spooled_raw_pat(
    groups: Iterable[RawPatGroup],
    *,
    spool_dir: str | Path | None = None,
    identifier_columns: Iterable[str] = DEFAULT_IDENTIFIER_COLUMNS,
    progress_interval: int = 25,
    factory_label: str = "FT",
) -> pd.DataFrame:
    """Extract files one-by-one, spool values, then calculate exact PAT."""
    groups = tuple(groups)
    total_files = sum(len(group.files) for group in groups)
    if not groups or total_files == 0:
        raise ValueError(f"{factory_label} PAT 原始目录没有可处理的源文件")

    excluded = {str(column) for column in identifier_columns}
    spool_parent = Path(spool_dir).expanduser().resolve() if spool_dir else None
    if spool_parent is not None:
        spool_parent.mkdir(parents=True, exist_ok=True)

    ordered_columns: list[str] = []
    counts: dict[str, int] = defaultdict(int)
    parsed_rows = 0
    file_index = 0
    print(f"{factory_label} PAT 原始数据识别: 分组={len(groups)}, 文件={total_files}")

    with TemporaryDirectory(
        prefix="ft_pat_",
        dir=str(spool_parent) if spool_parent is not None else None,
    ) as temp_name:
        temp_path = Path(temp_name)
        spool_paths: dict[str, Path] = {}
        handles: dict[str, object] = {}
        try:
            for group in groups:
                expected_columns: list[str] | None = None
                for file_path in group.files:
                    frame = group.extractor(file_path)
                    if frame is None or frame.empty:
                        raise ValueError(f"PAT 文件未解析出目标参数: {file_path}")
                    value_columns = [
                        str(column)
                        for column in frame.columns
                        if str(column) not in excluded
                    ]
                    if not value_columns:
                        raise ValueError(f"PAT 文件没有数值参数: {file_path}")
                    if expected_columns is None:
                        expected_columns = value_columns
                        duplicates = set(value_columns) & set(ordered_columns)
                        if duplicates:
                            raise ValueError(
                                f"PAT 分组存在重复参数 {sorted(duplicates)}，"
                                "为避免重复计数已停止"
                            )
                        ordered_columns.extend(value_columns)
                    elif value_columns != expected_columns:
                        raise ValueError(
                            f"PAT 参数结构不一致: {file_path.name}; "
                            f"期望 {expected_columns}; 实际 {value_columns}"
                        )

                    parsed_rows += len(frame)
                    for column in value_columns:
                        values = (
                            pd.to_numeric(frame[column], errors="coerce")
                            .dropna()
                            .to_numpy(dtype=np.float64, copy=False)
                        )
                        if column not in handles:
                            path = temp_path / _spool_filename(column)
                            spool_paths[column] = path
                            handles[column] = path.open("ab")
                        values.tofile(handles[column])
                        counts[column] += int(values.size)
                    del frame
                    gc.collect()
                    file_index += 1
                    if (
                        file_index == 1
                        or file_index == total_files
                        or (progress_interval > 0 and file_index % progress_interval == 0)
                    ):
                        print(
                            f"PAT 进度: {file_index}/{total_files} 文件，"
                            f"累计解析 {parsed_rows:,} 行"
                        )
                if expected_columns is None:
                    raise ValueError(f"PAT 分组没有有效参数: {group.label}")
        finally:
            for handle in handles.values():
                handle.close()

        rows: list[dict] = []
        for column in ordered_columns:
            values = np.fromfile(spool_paths[column], dtype=np.float64)
            if len(values) != counts[column]:
                raise RuntimeError(
                    f"PAT 参数缓存计数不一致: {column}: "
                    f"{len(values)} != {counts[column]}"
                )
            stats = compute_pat_stats(pd.Series(values, name=column, copy=False))
            if not stats:
                print(f"PAT 参数跳过: {column}，没有有效数值")
                del values
                continue
            rows.append(stats)
            print(f"PAT 参数完成: {column}，有效数值 {len(values):,}")
            del values

    print(
        f"{factory_label} PAT 原始数据汇总完成: 文件={total_files}, "
        f"解析行={parsed_rows:,}, 参数={len(rows)}"
    )
    return build_pat_frame(rows)
