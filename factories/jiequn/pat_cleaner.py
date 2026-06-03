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

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
import numpy as np
from factories.jiequn.formatting import BATCH_COL
from shared.excel_utils import write_excel_fast

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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


def build_pat(output_dir: str = "output/杰群-output") -> pd.DataFrame:
    """
    从 output/杰群-output/ 下的 DC/DVDS/RG 输出构建 PAT 表。

    扫描最新的 mixed_DC_JQ_*.xlsx, mixed_DVDS_JQ_*.xlsx, mixed_RG_JQ_*.xlsx，
    对每个参数列计算统计量。
    """
    output_path = Path(output_dir)
    rows = []

    # 查找最新的各类型输出
    for prefix, label in [("mixed_DC_JQ_", "DC"), ("mixed_DVDS_JQ_", "DVDS"), ("mixed_RG_JQ_", "RG")]:
        files = sorted(output_path.glob(f"{prefix}*.xlsx"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            logger.warning(f"  未找到 {label} 输出文件 ({prefix}*.xlsx)")
            continue

        fpath = files[0]
        logger.info(f"  读取 {label}: {fpath.name}")

        try:
            df = pd.read_excel(fpath, engine='calamine')
        except Exception:
            df = pd.read_excel(fpath, engine='openpyxl')

        # 跳过 NUM / lot_ID 列
        param_cols = [c for c in df.columns if c not in ('NUM', 'lot_ID', '周记', BATCH_COL)]

        for col in param_cols:
            stats = compute_pat_stats(df[col])
            if stats:
                rows.append(stats)

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
    output_path = Path(output_dir) / "PAT.xlsx"
    try:
        write_excel_fast(pat_df, output_path, sheet_name='PAT', index=False)
        logger.info(f"PAT 保存成功: {output_path}")
        return True
    except Exception as e:
        logger.error(f"PAT 保存失败: {e}")
        return False


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
