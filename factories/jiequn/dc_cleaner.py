#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
杰群 DC 数据清洗器

从 CSV 提取 DC 参数（含测试条件增强），应用单位换算，输出 NUM + 周记 + 增强参数。
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
from factories.base.base_cleaner import BaseCleaner
from factories.jiequn.config import UNIT_CONVERSIONS, TYPE_SUBDIRS
from factories.jiequn.csv_parser import parse_dta_csv
from shared.excel_utils import write_excel_fast, generate_lot_based_filename

DC_PARAMS = ["BVDSS", "IDSS", "IGSS", "ISGS", "VTH", "Rdson", "LRDON", "VF", "VFSDS", "CONT"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class JiequnDCCleaner(BaseCleaner):
    factory_name = "杰群"
    unit_conversions = UNIT_CONVERSIONS

    def __init__(self, input_dir: str = None, output_dir: str = None):
        if input_dir is None:
            input_dir = "data/杰群"
        if output_dir is None:
            output_dir = "output/杰群-output"
        super().__init__(input_dir, output_dir)

    def _get_dc_subdir(self) -> Path:
        sub = TYPE_SUBDIRS.get("DC", "DC")
        base = Path(self.input_dir)
        for p in base.rglob(sub):
            if p.is_dir() and list(p.glob("*.[cC][sS][vV]")):
                return p
        direct = base / sub
        if direct.exists():
            return direct
        raise FileNotFoundError(f"未找到 DC 目录: {base}/{sub}")

    def process_all(self, data_type: str = None) -> bool:
        logger.info("=" * 50)
        logger.info("杰群 DC 数据清洗")
        logger.info("=" * 50)

        try:
            dc_dir = self._get_dc_subdir()
            logger.info(f"DC 目录: {dc_dir}")

            csv_files = sorted(set(
                list(dc_dir.glob("*DTA*.CSV")) + list(dc_dir.glob("*DTA*.csv"))
            ))
            if not csv_files:
                all_csv = sorted(set(list(dc_dir.glob("*.CSV")) + list(dc_dir.glob("*.csv"))))
                csv_files = [f for f in all_csv
                           if '_DVDS' not in f.name.upper()
                           and '_RG' not in f.name.upper()
                           and 'PAT' not in f.name.upper()]
            logger.info(f"文件: {len(csv_files)} 个")

            all_dfs = []
            for f in csv_files:
                df = parse_dta_csv(str(f), DC_PARAMS, unique_only=False)
                if df is not None and not df.empty:
                    all_dfs.append(df)

            if not all_dfs:
                logger.error("无数据")
                return False

            merged = pd.concat(all_dfs, ignore_index=True, sort=False)
            logger.info(f"合并: {len(merged):,} 行, {len(merged.columns)} 列")

            merged = self._apply_unit_conversions(merged)
            logger.info("单位换算完成")

            merged.dropna(subset=['周记'], inplace=True)
            merged.reset_index(drop=True, inplace=True)
            merged.insert(0, 'NUM', range(1, len(merged) + 1))

            zhouji_list = merged['周记'].tolist() if '周记' in merged.columns else ['unknown']
            filename = generate_lot_based_filename(zhouji_list, "DC_JQ")
            out = self.output_dir / filename
            write_excel_fast(merged, out, sheet_name='DC_Data')

            logger.info(f"保存: {out} ({len(merged):,} 行)")
            return True

        except Exception as e:
            logger.error(f"DC 清洗出错: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    JiequnDCCleaner().process_all()
