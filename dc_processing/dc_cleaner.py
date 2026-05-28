#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DC数据清洗器 - 主程序 (已优化)
功能：将ASEData/DC目录下的所有xlsx测试数据文件清洗整理成统一格式的DC数据文件
作者：cc
创建时间：2025-06-18
最后优化：2025-06-19
"""

import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import re
import sys

# 将项目根目录添加到Python路径，以便导入excel_utils
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from excel_utils import (
    read_excel_fast, 
    write_excel_fast, 
    scan_excel_files, 
    extract_batch_id, 
    generate_lot_based_filename
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dc_cleaner.log', mode='w', encoding='utf-8'), # 每次运行时覆盖日志文件
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DCDataCleaner:
    """DC数据清洗器主类"""
    
    def __init__(self, input_dir: str = "../ASEData/DC", output_dir: str = "../output"):
        """
        初始化DC数据清洗器
        
        Args:
            input_dir: 输入目录路径
            output_dir: 输出目录路径
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.ensure_output_dir()
        
    def ensure_output_dir(self):
        """确保输出目录存在"""
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建输出目录: {self.output_dir}")
    
    def extract_test_condition_value(self, df: pd.DataFrame, param_col: int, row_index: int = 4) -> Optional[str]:
        """
        提取参数的测试条件数值
        
        Args:
            df: Excel数据表
            param_col: 参数所在列
            row_index: 测试条件所在行索引（默认为4，即第5行）
            
        Returns:
            测试条件数值字符串，如"40.0"，失败返回None
        """
        try:
            # 检查行数是否足够
            if df.shape[0] < row_index + 1:
                logger.warning(f"文件行数不足，无法获取第{row_index + 1}行测试条件")
                return None
            
            # 使用 .iat 进行快速单点访问
            condition_value = df.iat[row_index, param_col]
            if pd.isna(condition_value):
                logger.debug(f"参数列{param_col}在第{row_index + 1}行的测试条件为空")
                return None
            
            condition_str = str(condition_value).strip()
            logger.debug(f"第{row_index + 1}行测试条件原始值: '{condition_str}'")
            
            # 使用正则表达式提取数值部分
            match = re.search(r'(\d+\.?\d*)', condition_str)
            if match:
                numeric_value = match.group(1)
                logger.debug(f"提取到测试条件数值: '{numeric_value}'")
                return numeric_value
            else:
                logger.warning(f"无法从测试条件中提取数值: '{condition_str}'")
                return None
                
        except IndexError:
            logger.warning(f"参数列{param_col}超出第{row_index + 1}行范围")
            return None
        except Exception as e:
            logger.error(f"提取第{row_index + 1}行测试条件时出错: {str(e)}")
            return None

    def extract_dc_data(self, file_path: Path) -> Optional[pd.DataFrame]:
        """
        从单个xlsx文件中高效提取DC测试数据（向量化版本）
        
        Args:
            file_path: 单个xlsx文件路径
            
        Returns:
            DataFrame包含动态数量的测试参数和文件名，失败返回None
        """
        logger.info(f"开始处理文件: {file_path.name}")
        
        try:
            # 使用excel_utils中的快速读取函数
            df = read_excel_fast(file_path, header=None)
            logger.debug(f"文件读取成功，形状: {df.shape}")
            
            # 基础校验
            if df.shape[0] < 7: # 至少需要7行才能获取参数和单位
                logger.error(f"文件 {file_path.name} 行数不足 (小于7行)，跳过处理。")
                return None
            
            # 使用excel_utils中的批次提取函数
            lot_id = extract_batch_id(file_path.name)
            
            # 1. 定位第1行的CONT列和参数列
            row1 = df.iloc[1]
            
            # 快速定位CONT列
            cont_search = row1.astype(str).str.strip() == 'CONT'
            if not cont_search.any():
                logger.error(f"文件 {file_path.name} 未找到CONT列")
                return None
            cont_col = cont_search.idxmax()
            logger.debug(f"CONT列位置: {cont_col}")
            
            # 2. 提取CONT右边的所有参数
            test_params = []
            for i in range(cont_col + 1, len(row1)):
                val = row1.iloc[i]
                param_name = str(val).strip()
                if not pd.isna(val) and param_name and param_name != 'SAME':
                    test_params.append((i, param_name))
            
            logger.debug(f"找到 {len(test_params)} 个测试参数")
            
            # 3. 获取第6行的单位信息
            row6 = df.iloc[6]
            
            # 4. 参数-单位匹配与增强（包含相邻ISGS检测）
            param_unit_pairs = []
            
            # 首先进行基础参数增强
            enhanced_params = []
            for i, (col, param) in enumerate(test_params):
                unit_val = row6.iloc[col] if col < len(row6) else None
                unit_name = str(unit_val).strip() if not pd.isna(unit_val) and str(unit_val).strip() else None
                
                enhanced_param = param
                if param.upper() in ['IDSS', 'ISGS']:
                    test_condition = self.extract_test_condition_value(df, col, row_index=4)
                    if test_condition:
                        enhanced_param = f"{param}{test_condition}"
                        logger.debug(f"{param}参数增强: {param} -> {enhanced_param}")
                elif param.upper() == 'LRDON':
                    test_condition = self.extract_test_condition_value(df, col, row_index=5)
                    if test_condition:
                        enhanced_param = f"{param}{test_condition}"
                        logger.debug(f"{param}参数增强: {param} -> {enhanced_param}")
                
                enhanced_params.append((col, enhanced_param, unit_name))
            
            # 检测相邻的ISGS参数并处理IGSS转换
            for i, (col, param, unit) in enumerate(enhanced_params):
                # 检查当前是否为ISGS参数
                if param.upper().startswith('ISGS') and i < len(enhanced_params) - 1:
                    # 检查下一个参数
                    next_col, next_param, next_unit = enhanced_params[i + 1]
                    
                    # 如果下一个也是ISGS且测试条件相同
                    if (next_param.upper().startswith('ISGS') and 
                        param == next_param and  # 测试条件相同
                        next_col == col + 1):   # 相邻列
                        
                        # 将当前的ISGS改为IGSS
                        igss_param = param.replace('ISGS', 'IGSS', 1)
                        param_unit_pairs.append((col, igss_param, unit))
                        logger.info(f"相邻ISGS检测: {param} -> {igss_param} (左边改为IGSS)")
                        continue
                
                # 正常添加参数
                param_unit_pairs.append((col, param, unit))
            
            # 5. 构建最终参数列表（检查是否还有重复）
            from collections import Counter
            param_names = [pair[1] for pair in param_unit_pairs]
            param_counts = Counter(param_names)
            param_counters = {}
            final_params = []
            
            for col, param, unit in param_unit_pairs:
                # 如果参数仍然重复，添加位置区分
                if param_counts[param] > 1:
                    count = param_counters.get(param, 0) + 1
                    param_counters[param] = count

                    # 对于IGSS/ISGS，保持旧的命名方式，因为它们有自己的特殊处理逻辑
                    if param.upper().startswith('IGSS') or param.upper().startswith('ISGS'):
                        base_name = f"{param}({unit})" if unit else param
                        final_param_name = f"{base_name}_{count}"
                    else:
                        # 对于其他所有重复参数，应用新的命名规则 VTH -> VTH1(V)
                        new_param_name = f"{param}{count}"
                        final_param_name = f"{new_param_name}({unit})" if unit else new_param_name
                    
                    logger.warning(f"仍有重复参数: {param} -> {final_param_name}")
                else:
                    # 没有重复的参数
                    final_param_name = f"{param}({unit})" if unit else param
                
                final_params.append((col, final_param_name))
                logger.debug(f"最终参数: 列{col} -> {final_param_name}")
            
            logger.debug(f"最终参数列表: {[param[1] for param in final_params]}")
            
            # 6. 快速定位Test No.行
            test_no_loc = np.where(df.map(lambda x: isinstance(x, str) and "Test No" in x))
            if len(test_no_loc[0]) == 0:
                logger.error(f"文件 {file_path.name} 未找到'Test No.'行")
                return None
            
            test_no_row = test_no_loc[0][0]
            data_start_row = test_no_row + 1
            logger.debug(f"数据起始行: {data_start_row}")

            if data_start_row >= df.shape[0]:
                logger.warning(f"文件 {file_path.name} 没有找到有效数据行。")
                return pd.DataFrame()
            
            # 7. 向量化提取测试数据
            extract_cols = [p[0] for p in final_params]
            new_col_names = [p[1] for p in final_params]
            
            # 一次性提取所有数据
            result_df = df.iloc[data_start_row:, extract_cols].copy()
            result_df.columns = new_col_names

            # 插入lot_ID列
            result_df.insert(0, 'lot_ID', lot_id)

            # 将所有数据列转换为数值，无效值转为NaN（只转换实际存在的列）
            for col in result_df.columns:
                if col != 'lot_ID':  # 跳过lot_ID列
                    result_df[col] = pd.to_numeric(result_df[col], errors='coerce')

            # 删除所有参数值都为空的行（排除lot_ID列）
            data_cols = [col for col in result_df.columns if col != 'lot_ID']
            result_df.dropna(how='all', subset=data_cols, inplace=True)
            
            if not result_df.empty:
                logger.info(f"文件 {file_path.name} 提取成功，数据行数: {len(result_df)}")
                logger.info(f"参数列数: {len(final_params)}")
            else:
                logger.warning(f"文件 {file_path.name} 提取结果为空")
            
            return result_df
            
        except Exception as e:
            logger.error(f"处理文件 {file_path.name} 时出错: {str(e)}", exc_info=True)
            return None
    
    def merge_all_dc_data(self, data_frames: List[pd.DataFrame]) -> pd.DataFrame:
        """
        合并所有文件的DC数据
        
        Args:
            data_frames: 多个DataFrame
            
        Returns:
            统一的DataFrame
        """
        logger.info(f"开始合并 {len(data_frames)} 个数据框")
        
        if not data_frames:
            logger.warning("没有可合并的数据框")
            return pd.DataFrame()
        
        try:
            # 使用 sort=False 提高性能
            merged_df = pd.concat(data_frames, ignore_index=True, sort=False)
            logger.info(f"数据合并完成，总行数: {len(merged_df)}")
            return merged_df
            
        except Exception as e:
            logger.error(f"合并数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def clean_and_format_dc(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        DC数据清洗和格式化
        
        Args:
            df: 原始合并数据
            
        Returns:
            清洗后的标准格式数据
        """
        logger.info("开始DC数据清洗和格式化")
        
        if df.empty:
            logger.warning("输入数据为空，跳过清洗")
            return df
        
        try:
            # 先过滤，再重置索引
            df.dropna(subset=['lot_ID'], inplace=True)
            df.reset_index(drop=True, inplace=True)
            df.insert(0, 'NUM', range(1, len(df) + 1))
            
            df['lot_ID'] = df['lot_ID'].astype(str)
            
            # 重新排序列
            cols = ['NUM', 'lot_ID']
            other_cols = [col for col in df.columns if col not in cols]
            df = df[cols + other_cols]
            
            logger.info(f"数据清洗完成，最终行数: {len(df)}")
            logger.info(f"最终列数: {len(df.columns)}")
            
            return df
            
        except Exception as e:
            logger.error(f"数据清洗时出错: {str(e)}")
            return df
    
    def save_dc_result(self, df: pd.DataFrame) -> bool:
        """
        保存最终DC结果
        
        Args:
            df: 清洗后的数据
            
        Returns:
            保存是否成功
        """
        if df.empty:
            logger.warning("没有数据可保存")
            return False
        
        try:
            # 提取lot_ids用于生成文件名
            lot_ids = df['lot_ID'].tolist() if 'lot_ID' in df.columns else ['unknown']
            
            # 使用lot_id生成文件名
            filename = generate_lot_based_filename(lot_ids, "DC")
            output_file = self.output_dir / filename
            
            # 使用excel_utils中的快速写入函数
            success = write_excel_fast(df, output_file, sheet_name='DC_Data')
            
            if success:
                logger.info(f"DC数据保存成功: {output_file}")
                logger.info(f"总共处理 {len(df)} 行数据")
            else:
                logger.error(f"保存DC结果失败: {output_file}")
            
            return success
            
        except Exception as e:
            logger.error(f"保存DC结果时出错: {str(e)}")
            return False
    
    def process_all_dc_files(self) -> bool:
        """
        处理所有DC文件的主函数
        
        Returns:
            处理是否成功
        """
        logger.info("=" * 50)
        logger.info("开始DC数据清洗处理 (性能优化版)")
        logger.info("=" * 50)
        
        try:
            # 1. 使用excel_utils扫描文件
            dc_files = scan_excel_files(self.input_dir)
            if not dc_files:
                logger.error("没有找到DC文件")
                return False
            
            # 2. 提取每个文件的数据
            all_data_frames = []
            for file_path in dc_files:
                df = self.extract_dc_data(file_path)
                if df is not None and not df.empty:
                    all_data_frames.append(df)
            
            if not all_data_frames:
                logger.error("没有成功提取到任何数据")
                return False
            
            # 3. 合并所有数据
            merged_df = self.merge_all_dc_data(all_data_frames)
            if merged_df.empty:
                logger.error("数据合并失败")
                return False
            
            # 4. 数据清洗和格式化
            cleaned_df = self.clean_and_format_dc(merged_df)
            if cleaned_df.empty:
                logger.error("数据清洗失败")
                return False
            
            # 5. 保存结果
            success = self.save_dc_result(cleaned_df)
            
            if success:
                logger.info("=" * 50)
                logger.info("DC数据清洗处理完成")
                logger.info("=" * 50)
            
            return success
            
        except Exception as e:
            logger.error(f"处理DC文件时出现致命错误: {str(e)}", exc_info=True)
            return False


def main():
    """主函数"""
    try:
        # 创建DC数据清洗器实例
        cleaner = DCDataCleaner()
        
        # 处理所有DC文件
        success = cleaner.process_all_dc_files()
        
        if success:
            print("DC数据清洗完成！")
        else:
            print("DC数据清洗失败，请查看日志文件获取详细信息。")
            
    except Exception as e:
        logger.error(f"主程序执行错误: {str(e)}")
        print(f"程序执行出错: {str(e)}")


if __name__ == "__main__":
    main() 