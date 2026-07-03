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
from pathlib import Path
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

# PAT 表头
PAT_HEADERS = [
    "统计量", "总计数", "均值", "标准差", "最小值", "下四分位数",
    "中位数", "上四分位数", "最大值", "Sigma",
    "LCL\n计算值", "UCL\n计算值",
    "LCL\n更新前", "UCL\n更新前",
    "LCL\n更新后", "UCL\n更新后",
    "是否\n更新",
]


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


def _matching_data_sheets(sheet_names: Iterable[str]) -> dict[str, list[str]]:
    """Return DC/DVDS/RG sheets, including numbered split sheets."""
    matches: dict[str, list[tuple[int, str]]] = {label: [] for label in DATA_LABELS}
    for sheet_name in sheet_names:
        match = DATA_SHEET_PATTERN.fullmatch(str(sheet_name).strip())
        if not match:
            continue
        label = match.group(1).upper()
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


def _inspect_workbook(path: Path) -> dict[str, list[str]]:
    try:
        with _open_workbook(path) as workbook:
            return _matching_data_sheets(workbook.sheet_names)
    except Exception as exc:
        logger.warning(f"跳过无法读取的 Excel: {path}: {exc}")
        return {label: [] for label in DATA_LABELS}


def _resolve_sheet_sources(
    source_dir: str | Path | None,
    source_files: Iterable[str | Path] | str | Path | None,
) -> dict[str, list[tuple[Path, str]]]:
    """Resolve explicit files or the legacy directory input into sheet sources."""
    resolved: dict[str, list[tuple[Path, str]]] = {label: [] for label in DATA_LABELS}

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
            sheets = _inspect_workbook(path)
            for label in DATA_LABELS:
                resolved[label].extend((path, sheet) for sheet in sheets[label])
        return resolved

    source_path = Path(source_dir or "output/杰群-output").expanduser().resolve()
    if source_path.is_file():
        return _resolve_sheet_sources(None, [source_path])
    if not source_path.is_dir():
        raise FileNotFoundError(f"PAT 清洗结果目录不存在: {source_path}")

    # 兼容原目录入口：每种数据类型仍选最近的一个工作簿，但读取其全部编号 Sheet。
    candidates: dict[str, list[tuple[float, Path, list[str]]]] = {
        label: [] for label in DATA_LABELS
    }
    for path in source_path.rglob("*.xlsx"):
        if not _valid_source_file(path):
            continue
        sheets = _inspect_workbook(path)
        for label in DATA_LABELS:
            if sheets[label]:
                candidates[label].append((path.stat().st_mtime, path, sheets[label]))

    for label in DATA_LABELS:
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


def build_pat(
    source_dir: str | Path | None = "output/杰群-output",
    source_files: Iterable[str | Path] | str | Path | None = None,
) -> pd.DataFrame:
    """Build PAT from explicit workbooks or a legacy cleaned-result directory.

    Numbered sheets such as ``DC_Data_1`` / ``DC_Data_2`` are read one at a
    time. Values with the same parameter name are combined before quartiles and
    control limits are calculated, so the PAT covers the complete workbook.
    """
    sheet_sources = _resolve_sheet_sources(source_dir, source_files)
    rows: list[dict] = []

    for label in DATA_LABELS:
        sources = sheet_sources[label]
        if not sources:
            logger.warning(f"未找到 {label} 清洗结果 Sheet")
            continue
        rows.extend(_build_label_rows(label, sources))

    if not rows:
        logger.error("未生成任何 PAT 统计行")
        return pd.DataFrame()

    pat_df = pd.DataFrame(rows)
    # 按 PAT_HEADERS 排序列
    existing_cols = [c for c in PAT_HEADERS if c in pat_df.columns]
    pat_df = pat_df[existing_cols]

    # 添加变量行（表头行）
    header_row = {c: c for c in pat_df.columns}
    header_row["统计量"] = "变量"
    pat_df = pd.concat([pd.DataFrame([header_row]), pat_df], ignore_index=True)

    return pat_df


def save_pat(pat_df: pd.DataFrame, output_dir: str = "output/杰群-output") -> bool:
    """保存 PAT 到 Excel"""
    if pat_df.empty:
        return False
    run_dir = create_output_run_dir(output_dir, ["PAT"])
    output_path = run_dir / generate_run_filename(run_dir)
    try:
        write_excel_fast(pat_df, output_path, sheet_name='PAT', index=False)
        logger.info(f"PAT 保存成功: {output_path}")
        return True
    except Exception as e:
        logger.error(f"PAT 保存失败: {e}")
        return False


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
