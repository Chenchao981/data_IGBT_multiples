#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
杰群 DC 数据清洗器

从 CSV 文件中提取所有 DC 测试参数，应用单位换算（IDSS/IGSS/ISGS→nA, Rdson→mR），
合并后输出为统一格式的 Excel 文件。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import logging
import pandas as pd
from factories.base.base_cleaner import BaseCleaner
from factories.jiequn.config import UNIT_CONVERSIONS, TYPE_SUBDIRS
from factories.jiequn.csv_parser import parse_dta_csv, extract_lot_id_jiequn
from shared.excel_utils import write_excel_fast, generate_lot_based_filename

# DC 测试中需要提取的所有参数（匹配 Item 行中的名称）
DC_PARAMS = [
    "BVDSS", "IDSS", "IGSS", "ISGS", "VTH",
    "Rdson", "LRDON", "VF", "GFS", "CONT",
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JiequnDCCleaner(BaseCleaner):
    """杰群 DC 数据清洗器"""

    factory_name = "杰群"
    unit_conversions = UNIT_CONVERSIONS

    def __init__(self, input_dir: str = None, output_dir: str = None):
        if input_dir is None:
            input_dir = "data/杰群"
        if output_dir is None:
            output_dir = "output/杰群-output"
        super().__init__(input_dir, output_dir)

    def _get_dc_subdir(self) -> Path:
        """获取 DC 数据子目录"""
        sub = TYPE_SUBDIRS.get("DC", "DC")
        # 尝试找到实际的数据子目录（可能嵌套了一层产品目录）
        base = Path(self.input_dir)
        if not base.exists():
            raise FileNotFoundError(f"输入目录不存在: {base}")
        # 查找包含 DC 子目录的路径
        for p in base.rglob(sub):
            if p.is_dir():
                # 检查是否包含 CSV 文件
                if list(p.glob("*.csv")) or list(p.glob("*.CSV")):
                    return p
        # 直接拼接
        direct = base / sub
        if direct.exists():
            return direct
        raise FileNotFoundError(f"未找到 DC 数据目录: {base} / {sub}")

    def process_all(self, data_type: str = None) -> bool:
        """处理所有 DC CSV 文件"""
        logger.info("=" * 50)
        logger.info("杰群 DC 数据清洗 (CSV)")
        logger.info("=" * 50)

        try:
            dc_dir = self._get_dc_subdir()
            logger.info(f"DC 数据目录: {dc_dir}")

            # 扫描 CSV 文件
            csv_files = sorted(set(dc_dir.glob("*DTA*.[cC][sS][vV]")))
            if not csv_files:
                csv_files = sorted(set(dc_dir.glob("*.[cC][sS][vV]")))
                csv_files = [f for f in csv_files 
                           if '_DVDS' not in f.name.upper() and '_RG' not in f.name.upper()
                           and 'PAT' not in f.name.upper()]

            logger.info(f"找到 {len(csv_files)} 个 DC CSV 文件")

            if not csv_files:
                logger.error("未找到 DC CSV 文件")
                return False

            # 解析每个文件
            all_dfs = []
            for f in csv_files:
                df = parse_dta_csv(str(f), DC_PARAMS)
                if df is not None and not df.empty:
                    all_dfs.append(df)

            if not all_dfs:
                logger.error("未能从任何文件中提取到 DC 数据")
                return False

            # 合并
            merged = pd.concat(all_dfs, ignore_index=True, sort=False)
            logger.info(f"合并完成: {len(merged)} 行, {len(merged.columns)} 列")

            # 单位换算
            merged = self._apply_unit_conversions(merged)
            logger.info("单位换算完成 (IDSS/IGSS/ISGS→nA, Rdson→mR)")

            # 清洗
            merged.dropna(subset=['lot_ID'], inplace=True)
            merged.reset_index(drop=True, inplace=True)
            merged.insert(0, 'NUM', range(1, len(merged) + 1))

            # 保存
            lot_ids = merged['lot_ID'].tolist() if 'lot_ID' in merged.columns else ['unknown']
            filename = generate_lot_based_filename(lot_ids, "DC_JQ")
            output_path = self.output_dir / filename
            success = write_excel_fast(merged, output_path, sheet_name='DC_Data_JQ')

            if success:
                logger.info(f"杰群 DC 数据保存成功: {output_path}")
                logger.info(f"总行数: {len(merged)}, 列数: {len(merged.columns)}")
                return True
            else:
                logger.error("保存失败")
                return False

        except Exception as e:
            logger.error(f"杰群 DC 清洗出错: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    cleaner = JiequnDCCleaner()
    cleaner.process_all()
