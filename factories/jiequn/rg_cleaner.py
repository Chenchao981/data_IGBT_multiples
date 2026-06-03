#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""杰群 · 数据格式1 — RG 清洗器 — 输出 NUM + 周记 + RG(R)"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
from factories.base.base_cleaner import BaseCleaner
from factories.jiequn.config import TYPE_SUBDIRS
from factories.jiequn.csv_parser import parse_dta_csv
from factories.jiequn.formatting import BATCH_COL, normalize_output_columns
from shared.excel_utils import write_excel_fast, generate_lot_based_filename

RG_PARAMS = ["LCR-RG"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class JiequnRGCleaner(BaseCleaner):
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
            if p.is_dir() and list(p.glob("*RG*.[cC][sS][vV]")):
                return p
        direct = base / sub
        if direct.exists():
            return direct
        raise FileNotFoundError(f"未找到 RG 目录: {base}/{sub}")

    def process_all(self, data_type: str = None) -> bool:
        logger.info("=" * 50)
        logger.info("杰群 RG 数据清洗")
        logger.info("=" * 50)

        try:
            rg_dir = self._get_subdir()
            logger.info(f"RG 目录: {rg_dir}")

            csv_files = sorted(set(
                list(rg_dir.glob("*RG*.CSV")) + list(rg_dir.glob("*RG*.csv"))
            ))
            if not csv_files:
                all_csv = sorted(set(list(rg_dir.glob("*.CSV")) + list(rg_dir.glob("*.csv"))))
                csv_files = [f for f in all_csv
                           if 'RG' in f.name.upper() and 'DVDS' not in f.name.upper()]
            logger.info(f"文件: {len(csv_files)} 个")

            all_dfs = []
            for f in csv_files:
                df = parse_dta_csv(str(f), RG_PARAMS, unique_only=True)
                if df is not None and not df.empty:
                    all_dfs.append(df)

            if not all_dfs:
                logger.error("无数据")
                return False

            merged = pd.concat(all_dfs, ignore_index=True, sort=False)
            merged.dropna(subset=['周记'], inplace=True)
            merged.reset_index(drop=True, inplace=True)
            merged.insert(0, 'NUM', range(1, len(merged) + 1))
            merged = normalize_output_columns(merged, "RG")

            zhouji_list = merged[BATCH_COL].tolist()
            filename = generate_lot_based_filename(zhouji_list, "RG_JQ")
            out = self.output_dir / filename
            write_excel_fast(merged, out, sheet_name='RG_Data')

            logger.info(f"保存: {out} ({len(merged):,} 行)")
            return True

        except Exception as e:
            logger.error(f"RG 清洗出错: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    JiequnRGCleaner().process_all()
