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
import hashlib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
import numpy as np
from factories.jiequn.formatting import BATCH_COL
from shared.excel_utils import create_output_run_dir, generate_run_filename, write_excel_fast

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_LABELS = ("DC", "DVDS", "RG")
IDENTIFIER_COLUMNS = {"NUM", "lot_ID", "周记", BATCH_COL}
DATA_SHEET_PATTERN = re.compile(r"^(DC|DVDS|RG)_Data(?:_(\d+))?$", re.IGNORECASE)
RAW_PROGRESS_INTERVAL = 25

# PAT 表头
PAT_HEADERS = [
    "统计量", "总计数", "均值", "标准差", "最小值", "下四分位数",
    "中位数", "上四分位数", "最大值", "Sigma",
    "LCL\n计算值", "UCL\n计算值",
    "LCL\n更新前", "UCL\n更新前",
    "LCL\n更新后", "UCL\n更新后",
    "是否\n更新",
]


@dataclass(frozen=True)
class RawPatSourceGroup:
    """One strict Jiequn raw-source group processed with one parser contract."""

    label: str
    files: tuple[Path, ...]
    target_params: tuple[str, ...]
    unique_only: bool = False
    skip_match_counts: dict[str, int] | None = None


def compute_pat_stats(series: pd.Series, lsl: float = None, usl: float = None) -> dict:
    """
    计算单个参数的 PAT 统计量。

    Sigma = 标准差（大样本下与总体标准差近似）
    LCL = mean - 6*sigma, UCL = mean + 6*sigma
    """
    vals = pd.to_numeric(series, errors='coerce').dropna()
    if len(vals) == 0:
        return {}

    count = len(vals)
    mean_v = vals.mean()
    std_v = vals.std(ddof=1)
    q1 = vals.quantile(0.25)
    q2 = vals.quantile(0.50)
    q3 = vals.quantile(0.75)

    # Sigma = (Q3 - Q1) / 1.35
    sigma = (q3 - q1) / 1.35 if q3 > q1 else 0.0
    # LCL = 中位数 - 6*Sigma, UCL = 中位数 + 6*Sigma
    lcl = q2 - 6 * sigma
    ucl = q2 + 6 * sigma

    return {
        "统计量": series.name,
        "总计数": count,
        "均值": round(mean_v, 6),
        "标准差": round(std_v, 6),
        "最小值": round(vals.min(), 6),
        "下四分位数": round(q1, 6),
        "中位数": round(q2, 6),
        "上四分位数": round(q3, 6),
        "最大值": round(vals.max(), 6),
        "Sigma": round(sigma, 6),
        "LCL\n计算值": round(lcl, 6),
        "UCL\n计算值": round(ucl, 6),
        "LCL\n更新前": lsl,
        "UCL\n更新前": usl,
        "LCL\n更新后": np.nan,
        "UCL\n更新后": np.nan,
        "是否\n更新": np.nan,
    }


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


def _build_pat_frame(rows: list[dict]) -> pd.DataFrame:
    """Create the stable PAT table, including the editable template header row."""
    if not rows:
        return pd.DataFrame()
    pat_df = pd.DataFrame(rows)
    existing_cols = [column for column in PAT_HEADERS if column in pat_df.columns]
    pat_df = pat_df[existing_cols]
    header_row = {column: column for column in pat_df.columns}
    header_row["统计量"] = "变量"
    return pd.concat([pd.DataFrame([header_row]), pat_df], ignore_index=True)


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


def _spool_filename(column: str) -> str:
    digest = hashlib.sha256(column.encode("utf-8")).hexdigest()[:16]
    return f"parameter_{digest}.float64"


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
    total_files = sum(len(group.files) for group in groups)
    if total_files == 0:
        raise ValueError("PAT 原始目录没有可处理的 DTA CSV")
    print(f"PAT 原始数据识别: 产品={product}, 分组={len(groups)}, 文件={total_files}")

    spool_parent = Path(spool_dir).expanduser().resolve() if spool_dir else None
    if spool_parent is not None:
        spool_parent.mkdir(parents=True, exist_ok=True)

    ordered_columns: list[str] = []
    counts: dict[str, int] = defaultdict(int)
    file_index = 0
    parsed_rows = 0

    with TemporaryDirectory(
        prefix="jiequn_pat_",
        dir=str(spool_parent) if spool_parent is not None else None,
    ) as temp_name:
        temp_path = Path(temp_name)
        spool_paths: dict[str, Path] = {}
        handles: dict[str, object] = {}
        try:
            for group in groups:
                expected_columns: list[str] | None = None
                group_columns: set[str] = set()
                for file_path in group.files:
                    frame = parse_dta_csv(
                        str(file_path),
                        list(group.target_params),
                        unique_only=group.unique_only,
                        preserve_source_order=True,
                        skip_match_counts=group.skip_match_counts,
                        log_result=False,
                    )
                    if frame is None or frame.empty:
                        raise ValueError(f"PAT 文件未解析出目标参数: {file_path}")
                    frame = apply_conv(frame)
                    value_columns = [
                        str(column)
                        for column in frame.columns
                        if column not in IDENTIFIER_COLUMNS and str(column) != "周记"
                    ]
                    if not value_columns:
                        raise ValueError(f"PAT 文件没有数值参数: {file_path}")
                    if expected_columns is None:
                        expected_columns = value_columns
                        duplicate_columns = set(value_columns) & set(ordered_columns)
                        if duplicate_columns:
                            raise ValueError(
                                f"PAT 分组存在重复参数 {sorted(duplicate_columns)}，"
                                "为避免重复计数已停止"
                            )
                        ordered_columns.extend(value_columns)
                        group_columns = set(value_columns)
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
                            spool_path = temp_path / _spool_filename(column)
                            spool_paths[column] = spool_path
                            handles[column] = spool_path.open("ab")
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
                if not group_columns:
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
                raise ValueError(f"PAT 参数没有有效数值: {column}")
            rows.append(stats)
            print(f"PAT 参数完成: {column}，有效数值 {len(values):,}")
            del values

    print(
        f"PAT 原始数据汇总完成: 产品={product}, 文件={total_files}, "
        f"解析行={parsed_rows:,}, 参数={len(rows)}"
    )
    return _build_pat_frame(rows)


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
