#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
杰群 · 数据格式1 — DC 数据清洗器

从 CSV 提取 DC 参数（含测试条件增强），应用单位换算，输出 NUM + 周记 + 增强参数。
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
from factories.base.base_cleaner import BaseCleaner
from factories.jiequn.config import (
    JIEQUN_DC_PARAMS,
    JIEQUN_DC_SKIP_MATCH_COUNTS,
    UNIT_CONVERSIONS,
    TYPE_SUBDIRS,
)
from factories.jiequn.csv_parser import parse_dta_csv
from factories.jiequn.formatting import BATCH_COL, normalize_output_columns
from shared.excel_utils import create_output_run_dir, generate_run_filename, write_excel_fast

DC_PARAMS = JIEQUN_DC_PARAMS

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
        self.last_output_file: Path | None = None
        self.last_scatter_manifest: Path | None = None

    def _get_dc_subdir(self) -> Path:
        sub = TYPE_SUBDIRS.get("DC", "DC")
        base = Path(self.input_dir)
        if base.name.upper() == sub.upper() and base.is_dir() and list(base.glob("*.[cC][sS][vV]")):
            return base
        for p in base.rglob(sub):
            if p.is_dir() and list(p.glob("*.[cC][sS][vV]")):
                return p
        direct = base / sub
        if direct.exists():
            return direct
        # 杰群第三产线：产品目录下直接存放 DC DTA CSV，不设 DC 子目录。
        flat_dta_files = list(base.rglob("*DTA*.CSV")) + list(base.rglob("*DTA*.csv"))
        if flat_dta_files:
            return base
        raise FileNotFoundError(f"未找到 DC 目录: {base}/{sub}")

    @staticmethod
    def _scan_dc_files(dc_dir: Path) -> list[Path]:
        """Scan classic DC subdirectories and line-3 flat product folders."""
        all_csv = sorted(set(
            list(dc_dir.rglob("*.CSV")) + list(dc_dir.rglob("*.csv"))
        ))
        return [
            path for path in all_csv
            if "DTA" in path.name.upper()
            and "_DVDS" not in path.name.upper()
            and "_RG" not in path.name.upper()
            and "PAT" not in path.name.upper()
        ]

    def process_all(self, data_type: str = None) -> bool:
        logger.info("=" * 50)
        logger.info("杰群 DC 数据清洗")
        logger.info("=" * 50)
        self.last_output_file = None
        self.last_scatter_manifest = None

        try:
            dc_dir = self._get_dc_subdir()
            logger.info(f"DC 目录: {dc_dir}")

            csv_files = self._scan_dc_files(dc_dir)
            logger.info(f"文件: {len(csv_files)} 个")

            all_dfs = []
            all_spec_frames = []
            spec_unit_factors = {
                name: rule["factor"] for name, rule in UNIT_CONVERSIONS.items()
            }
            for f in csv_files:
                df = parse_dta_csv(
                    str(f),
                    DC_PARAMS,
                    unique_only=False,
                    skip_match_counts=JIEQUN_DC_SKIP_MATCH_COUNTS,
                    spec_unit_factors=spec_unit_factors,
                )
                if df is not None and not df.empty:
                    specs = df.attrs.get("scatter_specs")
                    source_id = df.attrs.get("source_id", f.stem)
                    df = df.copy()
                    df["_source_id"] = source_id
                    all_dfs.append(df)
                    if specs is not None and not specs.empty:
                        all_spec_frames.append(specs)

            if not all_dfs:
                logger.error("无数据")
                return False

            merged = pd.concat(all_dfs, ignore_index=True, sort=False)
            logger.info(f"合并: {len(merged):,} 行, {len(merged.columns)} 列")

            merged = self._apply_unit_conversions(merged)
            logger.info("单位换算完成")

            merged.dropna(subset=['周记'], inplace=True)
            merged.reset_index(drop=True, inplace=True)
            source_ids = merged.pop("_source_id")
            merged.insert(0, 'NUM', range(1, len(merged) + 1))
            merged = normalize_output_columns(merged, "DC")

            zhouji_list = merged[BATCH_COL].tolist() if BATCH_COL in merged.columns else ['unknown']
            run_dir = create_output_run_dir(self.output_dir, zhouji_list)
            out = run_dir / generate_run_filename(run_dir)
            if not write_excel_fast(merged, out, sheet_name='DC_Data'):
                raise OSError(f"杰群 DC 清洗结果写入失败: {out}")
            self.last_output_file = out.resolve()

            if not all_spec_frames:
                raise ValueError("没有从杰群源文件读取到测试参数上下限")
            from frontend.ft_scatter import export_scatter_bundle

            scatter_data = merged.rename(columns={BATCH_COL: "lot_ID"}).copy()
            scatter_data.insert(2, "Source_ID", source_ids.astype(str).tolist())
            specs = pd.concat(all_spec_frames, ignore_index=True, sort=False)
            self.last_scatter_manifest = export_scatter_bundle(
                scatter_data,
                specs,
                run_dir,
                cleaned_file=self.last_output_file,
                factory=self.factory_name,
                data_type="DC",
            ).resolve()

            logger.info(f"保存: {out} ({len(merged):,} 行)")
            logger.info(f"FT散点图数据包: {self.last_scatter_manifest}")
            return True

        except Exception as e:
            logger.error(f"DC 清洗出错: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    JiequnDCCleaner().process_all()
