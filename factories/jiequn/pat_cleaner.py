#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
杰群 PAT 统计清洗器

从已清洗的 DC/DVDS/RG 输出文件中计算统计汇总表，生成 PAT.xlsx。

公式：
    Sigma = (Q3 - Q1) / 1.35
    LCL = 中位数 - 6 * Sigma
    UCL = 中位数 + 6 * Sigma

输出列：
    统计量 | 总计数 | 均值 | 标准差 | 最小值 | 下四分位数 | 中位数 |
    上四分位数 | 最大值 | Sigma | LCL计算值 | UCL计算值 |
    LCL更新前 | UCL更新前 | LCL更新后 | UCL更新后 | 是否更新
"""

import gc
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
import numpy as np
from factories.jiequn.formatting import BATCH_COL
from shared.excel_utils import create_output_run_dir, generate_run_filename, write_excel_fast
from shared.pat_engine import (
    PAT_HEADERS,
    RawPatGroup,
    build_pat_frame as _build_pat_frame,
    build_spooled_raw_pat,
    compute_pat_stats,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_LABELS = ("DC", "DVDS", "RG")
IDENTIFIER_COLUMNS = {"NUM", "lot_ID", "周记", BATCH_COL}
DATA_SHEET_PATTERN = re.compile(r"^(DC|DVDS|RG)_Data(?:_(\d+))?$", re.IGNORECASE)
RAW_PROGRESS_INTERVAL = 25

@dataclass(frozen=True)
class RawPatSourceGroup:
    """One strict Jiequn raw-source group processed with one parser contract."""

    label: str
    files: tuple[Path, ...]
    target_params: tuple[str, ...]
    unique_only: bool = False
    skip_match_counts: dict[str, int] | None = None


def _open_workbook(path: Path) -> pd.ExcelFile:
    """Open a workbook with Calamine first and a compatible fallback."""
    try:
        return pd.ExcelFile(path, engine="calamine")
    except Exception as exc:
        logger.warning(f"Calamine 打开失败，回退到 openpyxl: {path.name}: {exc}")
        return pd.ExcelFile(path, engine="openpyxl")


def _matching_data_sheets(
    sheet_names: Iterable[str],
    data_labels: tuple[str, ...] = DATA_LABELS,
    data_sheet_pattern: re.Pattern[str] = DATA_SHEET_PATTERN,
) -> dict[str, list[str]]:
    """Return matching data sheets, including numbered split sheets."""
    matches: dict[str, list[tuple[int, str]]] = {label: [] for label in data_labels}
    for sheet_name in sheet_names:
        match = data_sheet_pattern.fullmatch(str(sheet_name).strip())
        if not match:
            continue
        label = match.group(1).upper()
        if label not in matches:
            continue
        sequence = int(match.group(2) or 0)
        matches[label].append((sequence, sheet_name))
    return {
        label: [name for _, name in sorted(items, key=lambda item: (item[0], item[1]))]
        for label, items in matches.items()
    }


def _valid_source_file(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in {".xlsx", ".xls"}
        and not path.name.startswith("~$")
        and not path.parent.name.upper().startswith("PAT_")
    )


def _inspect_workbook(
    path: Path,
    data_labels: tuple[str, ...] = DATA_LABELS,
    data_sheet_pattern: re.Pattern[str] = DATA_SHEET_PATTERN,
) -> dict[str, list[str]]:
    try:
        with _open_workbook(path) as workbook:
            return _matching_data_sheets(
                workbook.sheet_names,
                data_labels=data_labels,
                data_sheet_pattern=data_sheet_pattern,
            )
    except Exception as exc:
        logger.warning(f"跳过无法读取的 Excel: {path}: {exc}")
        return {label: [] for label in data_labels}


def _resolve_sheet_sources(
    source_dir: str | Path | None,
    source_files: Iterable[str | Path] | str | Path | None,
    data_labels: tuple[str, ...] = DATA_LABELS,
    data_sheet_pattern: re.Pattern[str] = DATA_SHEET_PATTERN,
) -> dict[str, list[tuple[Path, str]]]:
    """Resolve explicit files or the legacy directory input into sheet sources."""
    resolved: dict[str, list[tuple[Path, str]]] = {label: [] for label in data_labels}

    if source_files is not None:
        values = [source_files] if isinstance(source_files, (str, Path)) else list(source_files)
        selected: list[Path] = []
        for value in values:
            path = Path(value).expanduser().resolve()
            if not _valid_source_file(path):
                raise ValueError(f"PAT 输入不是有效的 Excel 文件: {path}")
            if path not in selected:
                selected.append(path)
        if not selected:
            raise ValueError("PAT 至少需要选择一个清洗结果 Excel 文件")

        for path in selected:
            sheets = _inspect_workbook(path, data_labels, data_sheet_pattern)
            for label in data_labels:
                resolved[label].extend((path, sheet) for sheet in sheets[label])
        return resolved

    source_path = Path(source_dir or "output/杰群-output").expanduser().resolve()
    if source_path.is_file():
        return _resolve_sheet_sources(
            None,
            [source_path],
            data_labels=data_labels,
            data_sheet_pattern=data_sheet_pattern,
        )
    if not source_path.is_dir():
        raise FileNotFoundError(f"PAT 清洗结果目录不存在: {source_path}")

    # 兼容原目录入口：每种数据类型仍选最近的一个工作簿，但读取其全部编号 Sheet。
    candidates: dict[str, list[tuple[float, Path, list[str]]]] = {
        label: [] for label in data_labels
    }
    for path in source_path.rglob("*.xlsx"):
        if not _valid_source_file(path):
            continue
        sheets = _inspect_workbook(path, data_labels, data_sheet_pattern)
        for label in data_labels:
            if sheets[label]:
                candidates[label].append((path.stat().st_mtime, path, sheets[label]))

    for label in data_labels:
        if not candidates[label]:
            continue
        _, path, sheets = max(candidates[label], key=lambda item: item[0])
        resolved[label].extend((path, sheet) for sheet in sheets)
    return resolved


def _read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=sheet_name, engine="calamine")
    except Exception as exc:
        logger.warning(
            f"Calamine 读取失败，回退到 openpyxl: {path.name}/{sheet_name}: {exc}"
        )
        return pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")


def _build_label_rows(label: str, sources: list[tuple[Path, str]]) -> list[dict]:
    """Read one sheet at a time and merge numeric values by parameter."""
    parameter_chunks: dict[str, list[np.ndarray]] = defaultdict(list)
    total_rows = 0

    for path, sheet_name in sources:
        logger.info(f"读取 {label}: {path.name} / {sheet_name}")
        frame = _read_sheet(path, sheet_name)
        sheet_rows = len(frame)
        total_rows += sheet_rows
        for column in frame.columns:
            if column in IDENTIFIER_COLUMNS:
                continue
            values = (
                pd.to_numeric(frame[column], errors="coerce")
                .dropna()
                .to_numpy(dtype=np.float64, copy=True)
            )
            if values.size:
                parameter_chunks[str(column)].append(values)
        logger.info(f"完成 {sheet_name}: {sheet_rows:,} 行")
        del frame
        gc.collect()

    retained_mb = sum(
        chunk.nbytes for chunks in parameter_chunks.values() for chunk in chunks
    ) / (1024 * 1024)
    logger.info(
        f"{label} Sheet 合并完成: {len(sources)} 个 Sheet, "
        f"{total_rows:,} 行, 参数缓存约 {retained_mb:.1f} MB"
    )

    rows: list[dict] = []
    for column, chunks in parameter_chunks.items():
        merged = chunks[0] if len(chunks) == 1 else np.concatenate(chunks)
        stats = compute_pat_stats(pd.Series(merged, name=column, copy=False))
        if stats:
            rows.append(stats)
        del merged
    return rows


def _raw_product_identity(path: Path) -> str:
    """Return the full product/program identity before the first underscore."""
    return path.stem.split("_", 1)[0].strip().upper()


def _scan_auxiliary_raw_files(source_dir: Path, label: str) -> tuple[Path, ...]:
    """Find classic DVDS/RG DTA CSV files without mixing other data types."""
    roots = [source_dir]
    if source_dir.name.upper() == "DC":
        roots.insert(0, source_dir.parent)
    candidates: set[Path] = set()
    label_upper = label.upper()
    for root in roots:
        for path in root.rglob("*"):
            if (
                path.is_file()
                and path.suffix.lower() == ".csv"
                and "DTA" in path.name.upper()
                and not path.name.startswith("~$")
            ):
                relative_dirs = {part.upper() for part in path.relative_to(root).parts[:-1]}
                name = path.name.upper()
                if label_upper in relative_dirs or f"_{label_upper}" in name:
                    candidates.add(path.resolve())
    return tuple(sorted(candidates, key=lambda path: str(path).lower()))


def _resolve_raw_pat_groups(source_dir: str | Path) -> tuple[str, tuple[RawPatSourceGroup, ...]]:
    """Resolve one approved Jiequn raw layout and reject mixed products."""
    from factories.jiequn.config import JIEQUN_DC_PARAMS, JIEQUN_DC_SKIP_MATCH_COUNTS
    from factories.jiequn.dc_auto import (
        DC_FORMAT_1,
        DC_FORMAT_3,
        DC_FORMAT_UNIFIED,
        detect_dc_format,
    )

    source_path = Path(source_dir).expanduser().resolve()
    detection = detect_dc_format(source_path)
    all_files = list(detection.files)
    groups: list[RawPatSourceGroup] = []

    if detection.format_name == DC_FORMAT_UNIFIED:
        groups.append(
            RawPatSourceGroup(
                label="统一CSV",
                files=tuple(detection.files),
                target_params=tuple(JIEQUN_DC_PARAMS) + ("DVDS",),
                skip_match_counts=dict(JIEQUN_DC_SKIP_MATCH_COUNTS),
            )
        )
    else:
        dc_params = tuple(param for param in JIEQUN_DC_PARAMS if param != "LCR-RG")
        groups.append(
            RawPatSourceGroup(
                label="DC",
                files=tuple(detection.files),
                target_params=dc_params,
                skip_match_counts=dict(JIEQUN_DC_SKIP_MATCH_COUNTS),
            )
        )
        if detection.format_name == DC_FORMAT_1:
            for label, params in (("DVDS", ("DVDS",)), ("RG", ("LCR-RG",))):
                files = _scan_auxiliary_raw_files(source_path, label)
                if files:
                    groups.append(
                        RawPatSourceGroup(
                            label=label,
                            files=files,
                            target_params=params,
                            unique_only=True,
                        )
                    )
                    all_files.extend(files)
        elif detection.format_name != DC_FORMAT_3:
            raise ValueError(f"不支持的杰群 PAT 原始格式: {detection.format_name}")

    products = {_raw_product_identity(path) for path in all_files}
    if len(products) != 1:
        raise ValueError(
            "PAT 原始目录包含多个产品，不能合并计算: " + ", ".join(sorted(products))
        )
    product = next(iter(products))
    return product, tuple(groups)


def build_raw_pat(
    source_dir: str | Path,
    spool_dir: str | Path | None = None,
    progress_interval: int = RAW_PROGRESS_INTERVAL,
) -> pd.DataFrame:
    """Build exact PAT statistics directly from Jiequn raw DTA CSV files.

    Each raw file is parsed independently. Numeric parameter values are appended
    to temporary float64 streams and only one parameter is loaded for the final
    exact quartile calculation, keeping memory bounded for multi-gigabyte runs.
    """
    from factories.jiequn.clean_unified import apply_conv
    from factories.jiequn.csv_parser import parse_dta_csv

    product, groups = _resolve_raw_pat_groups(source_dir)
    def extractor_for(group: RawPatSourceGroup):
        def _extract(file_path: Path) -> pd.DataFrame:
            frame = parse_dta_csv(
                str(file_path),
                list(group.target_params),
                unique_only=group.unique_only,
                preserve_source_order=True,
                skip_match_counts=group.skip_match_counts,
                log_result=False,
            )
            return apply_conv(frame) if frame is not None else frame

        return _extract

    raw_groups = tuple(
        RawPatGroup(group.label, group.files, extractor_for(group))
        for group in groups
    )
    print(f"杰群 PAT 产品识别: {product}")
    return build_spooled_raw_pat(
        raw_groups,
        spool_dir=spool_dir,
        identifier_columns=IDENTIFIER_COLUMNS,
        progress_interval=progress_interval,
        factory_label="杰群",
    )


def build_pat(
    source_dir: str | Path | None = "output/杰群-output",
    source_files: Iterable[str | Path] | str | Path | None = None,
    data_labels: Iterable[str] = DATA_LABELS,
    data_sheet_pattern: re.Pattern[str] = DATA_SHEET_PATTERN,
) -> pd.DataFrame:
    """Build PAT from explicit workbooks or a legacy cleaned-result directory.

    Numbered sheets such as ``DC_Data_1`` / ``DC_Data_2`` are read one at a
    time. Values with the same parameter name are combined before quartiles and
    control limits are calculated, so the PAT covers the complete workbook.
    """
    normalized_labels = tuple(
        dict.fromkeys(str(label).upper() for label in data_labels)
    )
    if not normalized_labels:
        raise ValueError("PAT 至少需要一个数据工作表类型")
    sheet_sources = _resolve_sheet_sources(
        source_dir,
        source_files,
        data_labels=normalized_labels,
        data_sheet_pattern=data_sheet_pattern,
    )
    rows: list[dict] = []

    for label in normalized_labels:
        sources = sheet_sources[label]
        if not sources:
            logger.warning(f"未找到 {label} 清洗结果 Sheet")
            continue
        rows.extend(_build_label_rows(label, sources))

    if not rows:
        logger.error("未生成任何 PAT 统计行")
        return pd.DataFrame()

    return _build_pat_frame(rows)


def save_pat(
    pat_df: pd.DataFrame,
    output_dir: str | Path = "output/杰群-output",
) -> Path | None:
    """保存 PAT 到 Excel"""
    if pat_df.empty:
        return None
    run_dir = create_output_run_dir(output_dir, ["PAT"])
    output_path = run_dir / generate_run_filename(run_dir)
    try:
        if not write_excel_fast(pat_df, output_path, sheet_name='PAT', index=False):
            return None
        logger.info(f"PAT 保存成功: {output_path}")
        return output_path.resolve()
    except Exception as e:
        logger.error(f"PAT 保存失败: {e}")
        return None


def generate_raw_pat(
    source_dir: str | Path,
    output_dir: str | Path = "output/杰群-output",
) -> Path | None:
    """从杰群原始 DTA CSV 目录直接生成低内存 PAT。"""
    pat_df = build_raw_pat(source_dir=source_dir, spool_dir=output_dir)
    return save_pat(pat_df, output_dir)


def generate_pat(
    source_dir: str | Path | None = None,
    output_dir: str | Path = "output/杰群-output",
    source_files: Iterable[str | Path] | str | Path | None = None,
) -> bool:
    """从显式清洗文件或兼容目录生成 PAT，并保存到独立输出目录。"""
    return save_pat(build_pat(source_dir=source_dir, source_files=source_files), str(output_dir))


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("杰群 PAT 统计清洗")
    logger.info("=" * 50)

    pat_df = build_pat()
    if not pat_df.empty:
        save_pat(pat_df)
        logger.info(f"PAT 完成: {len(pat_df)-1} 个参数")
    else:
        logger.error("PAT 生成失败")
