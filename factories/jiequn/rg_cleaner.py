#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
杰群 RG 数据清洗器

从 CSV 文件中提取 LCR-RG 参数，合并后输出为统一格式的 Excel 文件。
RG 无单位换算需求（单位已是 R/Ω）。
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
from factories.base.base_cleaner import BaseCleaner
from factories.jiequn.config import TYPE_SUBDIRS
from factories.jiequn.csv_parser import parse_dta_csv
from shared.excel_utils import write_excel_fast, generate_lot_based_filename

# RG 目标参数
RG_PARAMS = ["LCR-RG"]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JiequnRGCleaner(BaseCleaner):
    """杰群 RG 数据清洗器"""

    factory_name = "杰群"

    def __init__(self, input_dir: str = None, output_dir: str = None):
        if input_dir is None:
            input_dir = "data/杰群"
        if output_dir is None:
            output_dir = "output/杰群-output"
        super().__init__(input_dir, output_dir)

    def _get_subdir(self) -> Path:
        sub = TYPE_SUBDIRS.get("RG", "RG")
        base = Path(self.input_dir)
        for p in base.rglob(sub):
            if p.is_dir():
                if list(p.glob("*RG*.csv")) or list(p.glob("*RG*.CSV")):
                    return p
        direct = base / sub
        if direct.exists():
            return direct
        raise FileNotFoundError(f"未找到 RG 数据目录: {base} / {sub}")

    def process_all(self, data_type: str = None) -> bool:
        logger.info("=" * 50)
        logger.info("杰群 RG 数据清洗 (CSV)")
        logger.info("=" * 50)

        try:
            rg_dir = self._get_subdir()
            logger.info(f"RG 数据目录: {rg_dir}")

            csv_files = sorted(set(rg_dir.glob("*RG*.[cC][sS][vV]")))
            if not csv_files:
                csv_files = sorted(set(rg_dir.glob("*.[cC][sS][vV]")))
                csv_files = [f for f in csv_files if 'RG' in f.name.upper() and 'DVDS' not in f.name.upper()]

            logger.info(f"找到 {len(csv_files)} 个 RG CSV 文件")

            if not csv_files:
                logger.error("未找到 RG CSV 文件")
                return False

            all_dfs = []
            for f in csv_files:
                df = parse_dta_csv(str(f), RG_PARAMS)
                if df is not None and not df.empty:
                    all_dfs.append(df)

            if not all_dfs:
                logger.error("未能提取到 RG 数据")
                return False

            merged = pd.concat(all_dfs, ignore_index=True, sort=False)
            logger.info(f"合并完成: {len(merged)} 行")

            merged.dropna(subset=['lot_ID'], inplace=True)
            merged.reset_index(drop=True, inplace=True)
            merged.insert(0, 'NUM', range(1, len(merged) + 1))

            lot_ids = merged['lot_ID'].tolist() if 'lot_ID' in merged.columns else ['unknown']
            filename = generate_lot_based_filename(lot_ids, "RG_JQ")
            output_path = self.output_dir / filename
            success = write_excel_fast(merged, output_path, sheet_name='RG_Data_JQ')

            if success:
                logger.info(f"杰群 RG 数据保存成功: {output_path}")
                logger.info(f"总行数: {len(merged)}")
                return True
            else:
                logger.error("保存失败")
                return False

        except Exception as e:
            logger.error(f"杰群 RG 清洗出错: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    cleaner = JiequnRGCleaner()
    cleaner.process_all()
