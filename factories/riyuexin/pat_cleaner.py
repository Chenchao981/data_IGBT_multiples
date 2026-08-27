#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""日月新 PAT：直接读取原始 DC/DVDS/RG 目录并生成标准 PAT。"""

from __future__ import annotations

from pathlib import Path
import logging
import re
from typing import Iterable

import pandas as pd

from factories.jiequn.pat_cleaner import build_pat as build_standard_pat
from shared.excel_utils import create_output_run_dir, generate_run_filename, write_excel_fast
from shared.pat_engine import RawPatGroup, build_spooled_raw_pat


RAW_TYPES = ("DC", "DVDS", "RG")
_PRODUCT_PATTERN = re.compile(
    r"(NCE[A-Z0-9]+(?:\([A-Z0-9]+\))?-\d[A-Z]\d{2})",
    re.IGNORECASE,
)


def _raw_product(path: Path) -> str:
    match = _PRODUCT_PATTERN.search(path.stem)
    if not match:
        raise ValueError(f"无法从日月新原始文件名识别产品: {path.name}")
    return match.group(1).upper()


def _valid_raw_xlsx(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() == ".xlsx"
        and not path.name.startswith("~$")
    )


def _classify_flat_file(path: Path) -> str:
    """Classify a Riyuexin workbook from its parameter header without reading data rows."""
    try:
        header = pd.read_excel(path, header=None, nrows=7, engine="calamine")
    except Exception:
        header = pd.read_excel(path, header=None, nrows=7, engine="openpyxl")
    if len(header) < 2:
        raise ValueError(f"日月新原始文件缺少参数表头: {path.name}")
    values = {
        str(value).strip().upper()
        for value in header.iloc[1].tolist()
        if pd.notna(value)
    }
    if "CONT" in values:
        return "DC"
    if "RG" in values:
        return "RG"
    if "DVDS" in values:
        return "DVDS"
    raise ValueError(f"无法识别日月新 DC/DVDS/RG 原始格式: {path.name}")


def _resolve_raw_files(source_dir: str | Path) -> dict[str, tuple[Path, ...]]:
    source = Path(source_dir).expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"日月新 PAT 原始目录不存在: {source}")

    by_type: dict[str, list[Path]] = {label: [] for label in RAW_TYPES}
    selected_type = source.name.upper()
    if selected_type in by_type:
        by_type[selected_type] = sorted(
            (path.resolve() for path in source.iterdir() if _valid_raw_xlsx(path)),
            key=lambda path: str(path).lower(),
        )
    else:
        typed_dirs = {
            child.name.upper(): child
            for child in source.iterdir()
            if child.is_dir() and child.name.upper() in by_type
        }
        if typed_dirs:
            for label, directory in typed_dirs.items():
                by_type[label] = sorted(
                    (
                        path.resolve()
                        for path in directory.iterdir()
                        if _valid_raw_xlsx(path)
                    ),
                    key=lambda path: str(path).lower(),
                )
        else:
            flat_files = sorted(
                (path.resolve() for path in source.iterdir() if _valid_raw_xlsx(path)),
                key=lambda path: str(path).lower(),
            )
            for path in flat_files:
                by_type[_classify_flat_file(path)].append(path)

    selected = [path for files in by_type.values() for path in files]
    if not selected:
        raise FileNotFoundError(
            f"未找到日月新原始 DC/DVDS/RG XLSX: {source}"
        )
    products = {_raw_product(path) for path in selected}
    if len(products) != 1:
        raise ValueError(
            "日月新 PAT 原始目录包含多个产品，不能合并计算: "
            + ", ".join(sorted(products))
        )
    return {
        label: tuple(files)
        for label, files in by_type.items()
        if files
    }


def build_raw_pat(
    source_dir: str | Path,
    spool_dir: str | Path | None = None,
    progress_interval: int = 25,
) -> pd.DataFrame:
    """逐个解析日月新原始 XLSX，以杰群低内存算法计算精确 PAT。"""
    from factories.riyuexin.dc_cleaner import DCDataCleaner
    from factories.riyuexin.dvds_cleaner import DVDSCleaner
    from factories.riyuexin.rg_cleaner import RGCleaner

    files_by_type = _resolve_raw_files(source_dir)

    dc_cleaner = object.__new__(DCDataCleaner)
    dc_cleaner._parsed_specs = {}
    dc_cleaner._parsed_source_ids = {}
    dvds_cleaner = object.__new__(DVDSCleaner)
    rg_cleaner = object.__new__(RGCleaner)
    rg_cleaner.logger = logging.getLogger("factories.riyuexin.rg_cleaner")

    def extract_dc(path: Path) -> pd.DataFrame:
        return dc_cleaner.extract_dc_data(path)

    def extract_dvds(path: Path) -> pd.DataFrame:
        return dvds_cleaner.extract_dvds_data(str(path))

    def extract_rg(path: Path) -> pd.DataFrame:
        frame = rg_cleaner.extract_rg_data(path)
        if frame is None or frame.empty:
            return frame
        values = pd.to_numeric(frame["RG(R)"], errors="coerce")
        return frame.loc[(values > 0) & (values < 1000)].reset_index(drop=True)

    extractors = {"DC": extract_dc, "DVDS": extract_dvds, "RG": extract_rg}
    groups = tuple(
        RawPatGroup(label, files, extractors[label])
        for label, files in files_by_type.items()
    )
    return build_spooled_raw_pat(
        groups,
        spool_dir=spool_dir,
        progress_interval=progress_interval,
        factory_label="日月新",
    )


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


def generate_raw_pat(
    source_dir: str | Path,
    output_dir: str | Path = "output/日月新-output",
) -> Path | None:
    """从日月新原始文件目标目录直接生成 PAT。"""
    return save_pat(build_raw_pat(source_dir, spool_dir=output_dir), output_dir)
