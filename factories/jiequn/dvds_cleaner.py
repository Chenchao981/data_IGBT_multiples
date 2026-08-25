#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""杰群 · 数据格式1 — DVDS 清洗器 — 输出 NUM + 周记 + DVDS(mV)"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
from factories.base.base_cleaner import BaseCleaner
from factories.jiequn.config import TYPE_SUBDIRS, UNIT_CONVERSIONS
from factories.jiequn.csv_parser import parse_dta_csv
from factories.jiequn.formatting import BATCH_COL, normalize_output_columns
from factories.jiequn.result_detection import find_existing_specialized_result
from shared.excel_utils import create_output_run_dir, generate_run_filename, write_excel_fast

DVDS_PARAMS = ["DVDS"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class JiequnDVDSCleaner(BaseCleaner):
    factory_name = "杰群"
    unit_conversions = UNIT_CONVERSIONS

    def __init__(self, input_dir: str = None, output_dir: str = None):
        if input_dir is None:
            input_dir = "data/杰群"
        if output_dir is None:
            output_dir = "output/杰群-output"
        super().__init__(input_dir, output_dir)
        self.last_output_file: Path | None = None

    def _get_subdir(self) -> Path:
        sub = TYPE_SUBDIRS.get("DVDS", "DVDS")
        base = Path(self.input_dir)
        if base.name.upper() == sub.upper() and base.is_dir() and list(base.glob("*DVDS*.[cC][sS][vV]")):
            return base
        for p in base.rglob(sub):
            if p.is_dir() and list(p.glob("*DVDS*.[cC][sS][vV]")):
                return p
        direct = base / sub
        if direct.exists():
            return direct
        raise FileNotFoundError(f"未找到 DVDS 目录: {base}/{sub}")

    def process_all(self, data_type: str = None) -> bool:
        logger.info("=" * 50)
        logger.info("杰群 DVDS 数据清洗")
        logger.info("=" * 50)

        self.last_output_file = None
        try:
            existing = find_existing_specialized_result(self.input_dir, "DVDS")
            if existing is not None:
                self.last_output_file = existing
                logger.info(f"检测到已有 DVDS 清洗结果，跳过重复清洗: {existing}")
                return True

            dvds_dir = self._get_subdir()
            logger.info(f"DVDS 目录: {dvds_dir}")

            csv_files = sorted(set(
                list(dvds_dir.glob("*DVDS*.CSV")) + list(dvds_dir.glob("*DVDS*.csv"))
            ))
            if not csv_files:
                all_csv = sorted(set(list(dvds_dir.glob("*.CSV")) + list(dvds_dir.glob("*.csv"))))
                csv_files = [f for f in all_csv if 'DVDS' in f.name.upper()]
            logger.info(f"文件: {len(csv_files)} 个")

            all_dfs = []
            for f in csv_files:
                df = parse_dta_csv(str(f), DVDS_PARAMS, unique_only=True)
                if df is not None and not df.empty:
                    all_dfs.append(df)

            if not all_dfs:
                logger.error("无数据")
                return False

            merged = pd.concat(all_dfs, ignore_index=True, sort=False)
            merged = self._apply_unit_conversions(merged)  # V → mV
            merged.dropna(subset=['周记'], inplace=True)
            merged.reset_index(drop=True, inplace=True)
            merged.insert(0, 'NUM', range(1, len(merged) + 1))
            merged = normalize_output_columns(merged, "DVDS")

            zhouji_list = merged[BATCH_COL].tolist()
            run_dir = create_output_run_dir(self.output_dir, zhouji_list)
            out = run_dir / generate_run_filename(run_dir)
            if not write_excel_fast(merged, out, sheet_name='DVDS_Data'):
                raise OSError(f"杰群 DVDS 清洗结果写入失败: {out}")
            self.last_output_file = out.resolve()

            logger.info(f"保存: {out} ({len(merged):,} 行)")
            return True

        except Exception as e:
            logger.error(f"DVDS 清洗出错: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    JiequnDVDSCleaner().process_all()
