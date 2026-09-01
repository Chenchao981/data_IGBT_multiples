#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""电基 PAT：直接读取已注册的原始 FT 文件目录并生成标准 PAT。"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import pandas as pd

from factories.jiequn.pat_cleaner import build_pat as build_standard_pat
from shared.excel_utils import create_output_run_dir, generate_run_filename, write_excel_fast
from shared.pat_engine import RawPatGroup, build_spooled_raw_pat


RAW_DATA_LABELS = ("RAW",)
RAW_DATA_SHEET_PATTERN = re.compile(r"^(RAW)(?:_(\d+))?$", re.IGNORECASE)
_POWERTECH_SOURCE_FORMATS = frozenset({"PowerTECH", "PowerTECH XLSX"})


def _parsed_parameter_keys(parsed) -> object | None:
    """Read an optional semantic parameter schema from a parser result."""

    for name in ("parameter_keys", "parameter_schema"):
        value = getattr(parsed, name, None)
        if value is not None:
            return value
    for name in ("parameter_keys", "parameter_schema"):
        value = parsed.data.attrs.get(name)
        if value is not None:
            return value
    return None


def _scan_raw_files(source_dir: str | Path) -> tuple[Path, ...]:
    from factories.dianji.models import DianjiFormatError
    from factories.dianji.source_registry import (
        SUPPORTED_SOURCE_EXTENSIONS,
        detect_dianji_source_format,
    )

    source = Path(source_dir).expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"电基 PAT 原始目录不存在: {source}")
    files = []
    unsupported = []
    formats = set()
    for path in source.rglob("*"):
        if not path.is_file() or path.name.startswith("~$"):
            continue
        relative_dirs = {part.upper() for part in path.relative_to(source).parts[:-1]}
        if "OUTPUT" in relative_dirs or any(
            re.fullmatch(r"PAT_\d+", part) for part in relative_dirs
        ):
            continue
        if path.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
            continue
        try:
            source_format = detect_dianji_source_format(path)
        except DianjiFormatError as exc:
            unsupported.append(f"{path.name} ({exc})")
            continue
        files.append(path.resolve())
        formats.add(source_format.display_name)

    if unsupported:
        raise DianjiFormatError(
            "输入目录混有不支持的电基 .xls/.xlsx/.csv 文件，请分开选择目录: "
            + ", ".join(unsupported[:5])
        )
    if not files:
        raise FileNotFoundError(
            f"未在 {source} 找到可用于 PAT 的电基原始文件"
        )
    if len(formats) != 1:
        raise DianjiFormatError(
            "电基 PAT 一次只能计算一种源格式，当前目录包含: "
            + ", ".join(sorted(formats))
        )
    return tuple(sorted(files, key=lambda path: str(path).lower()))


def build_raw_pat(
    source_dir: str | Path,
    spool_dir: str | Path | None = None,
    progress_interval: int = 25,
) -> pd.DataFrame:
    """逐个解析电基原始文件，以杰群低内存算法计算精确 PAT。"""
    from factories.dianji.models import DianjiFormatError
    from factories.dianji.source_registry import (
        detect_dianji_source_format,
        parse_dianji_source_file,
    )

    files = _scan_raw_files(source_dir)
    source_format = detect_dianji_source_format(files[0]).display_name
    schema_mode = (
        "nested_prefix"
        if source_format in _POWERTECH_SOURCE_FORMATS
        else "exact"
    )
    products: set[str] = set()
    formats: set[str] = set()

    def extract(path: Path) -> pd.DataFrame:
        parsed = parse_dianji_source_file(path)
        products.add(parsed.identity.product)
        formats.add(parsed.source_format)
        if len(products) != 1:
            raise DianjiFormatError(
                "电基 PAT 原始目录包含多个产品，不能合并计算: "
                + ", ".join(sorted(products))
            )
        if len(formats) != 1:
            raise DianjiFormatError(
                "电基 PAT 一次只能计算一种源格式，当前目录包含: "
                + ", ".join(sorted(formats))
            )
        if parsed.lot_identity_warning:
            print(f"WARNING: {parsed.lot_identity_warning}")
        frame = parsed.data.copy(deep=False)
        parameter_keys = _parsed_parameter_keys(parsed)
        if parameter_keys is not None:
            frame.attrs["parameter_keys"] = parameter_keys
        return frame

    return build_spooled_raw_pat(
        (RawPatGroup("FT-ALL", files, extract, schema_mode=schema_mode),),
        spool_dir=spool_dir,
        progress_interval=progress_interval,
        factory_label="电基",
    )


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


def generate_raw_pat(
    source_dir: str | Path,
    output_dir: str | Path = "output/电基-output",
) -> Path | None:
    """从电基原始文件目标目录直接生成 PAT。"""
    return save_pat(build_raw_pat(source_dir, spool_dir=output_dir), output_dir)
