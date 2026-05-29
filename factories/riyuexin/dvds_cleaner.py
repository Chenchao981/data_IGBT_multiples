#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DVDS数据清洗主程序
功能：将ASEData/DVDS目录下的xlsx测试数据文件清洗整理成统一格式
作者：cc
创建时间：20250618
"""

import os
import pandas as pd
from datetime import datetime
import logging
import re
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from shared.excel_utils import generate_lot_based_filename, read_excel_fast, write_excel_fast

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dvds_cleaner.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class DVDSCleaner:
    """DVDS数据清洗器"""
    
    def __init__(self, base_dir=None):
        """
        初始化DVDS清洗器
        
        Args:
            base_dir (str): 项目根目录，默认为当前目录的上级目录
        """
        if base_dir is None:
            # 默认为当前文件所在目录的上级目录
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.base_dir = base_dir
            
        self.dvds_dir = os.path.join(self.base_dir, 'ASEData', 'DVDS')
        self.output_dir = os.path.join(self.base_dir, 'output')
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        logging.info(f"DVDS数据清洗器初始化完成")
        logging.info(f"源数据目录: {self.dvds_dir}")
        logging.info(f"输出目录: {self.output_dir}")
    
    def scan_dvds_files(self):
        """
        扫描DVDS目录下的所有xlsx文件
        
        Returns:
            list: 有效文件路径列表
        """
        try:
            if not os.path.exists(self.dvds_dir):
                logging.error(f"DVDS目录不存在: {self.dvds_dir}")
                return []
            
            xlsx_files = []
            
            # 遍历目录中的所有文件
            for filename in os.listdir(self.dvds_dir):
                # 检查文件扩展名
                if not filename.lower().endswith('.xlsx'):
                    continue
                
                # 排除Excel临时文件（以~$开头）
                if filename.startswith('~$'):
                    logging.info(f"跳过临时文件: {filename}")
                    continue
                
                file_path = os.path.join(self.dvds_dir, filename)
                
                # 检查文件是否存在且大小大于0
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    xlsx_files.append(file_path)
                    logging.info(f"找到有效文件: {filename}")
                else:
                    logging.warning(f"文件无效或为空: {filename}")
            
            logging.info(f"共找到 {len(xlsx_files)} 个有效的xlsx文件")
            return xlsx_files
            
        except Exception as e:
            logging.error(f"扫描文件时发生错误: {str(e)}")
            return []
    
    def extract_batch_info(self, file_path):
        """
        从文件名中提取批次信息
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            str: 批次字符串（使用正则表达式提取FA4Z-2484这样的模式）
        """
        filename = os.path.basename(file_path)
        
        # 使用正则表达式提取形如FA4Z-2484的模式（4个字母数字 + 短横线 + 4个数字）
        pattern = r'[A-Z0-9]{4}-[0-9]{4}'
        match = re.search(pattern, filename)
        
        if match:
            lot_id = match.group()
            logging.debug(f"提取批次信息: {filename} -> {lot_id}")
            return lot_id
        else:
            # 如果正则匹配失败，回退到使用完整文件名
            lot_id = os.path.splitext(filename)[0]
            logging.warning(f"正则匹配失败，使用完整文件名: {filename} -> {lot_id}")
            return lot_id
    
    def extract_dvds_data(self, file_path):
        """
        从单个xlsx文件中提取DVDS数据
        
        Excel文件结构:
        - 第2行: 参数名称行，包含DVDS
        - 第7行: 单位行，DVDS列对应单位(如mV)
        - 第19行: 表头行(Test No.)
        - 第20行开始: 实际数据
        
        Args:
            file_path (str): Excel文件路径
        
        Returns:
            pd.DataFrame: 包含NUM, lot_ID, DVDS(mV)的DataFrame
        """
        try:
            filename = os.path.basename(file_path)
            logging.info(f"开始提取DVDS数据: {filename}")
            
            # 读取Excel文件 - 优先使用calamine，不支持时自动回退openpyxl
            df = read_excel_fast(file_path, header=None)
            logging.info(f"文件形状: {df.shape}")
            
            # 1. 在第2行查找DVDS列
            row_2 = df.iloc[1]  # 第2行 (索引为1)
            dvds_col = None
            
            for i in range(len(row_2)):
                if pd.notna(row_2.iloc[i]) and str(row_2.iloc[i]).strip().upper() == "DVDS":
                    dvds_col = i
                    logging.info(f"找到DVDS列在第{i+1}列")
                    break
            
            if dvds_col is None:
                logging.error(f"在第2行未找到DVDS列: {filename}")
                return pd.DataFrame()
            
            # 2. 获取DVDS单位
            unit_value = df.iloc[6, dvds_col]  # 第7行 (索引为6)
            logging.info(f"DVDS单位: {unit_value}")
            
            # 3. 确认第19行是Test No.行
            test_no_row = 18  # 第19行 (索引为18)
            if str(df.iloc[test_no_row, 0]).strip() != "Test No.":
                logging.warning(f"第19行第1列不是'Test No.': {filename}")
            
            # 4. 从第20行开始提取数据
            data_start_row = 19  # 第20行 (索引为19)
            dvds_values = []
            
            for row_idx in range(data_start_row, df.shape[0]):
                dvds_value = df.iloc[row_idx, dvds_col]
                
                # 跳过空值，继续处理后面的数据
                if pd.isna(dvds_value):
                    continue
                
                # 转换为数值
                if isinstance(dvds_value, (int, float)):
                    dvds_values.append(float(dvds_value))
                elif isinstance(dvds_value, str):
                    try:
                        numeric_value = float(dvds_value)
                        dvds_values.append(numeric_value)
                    except ValueError:
                        # 跳过非数值数据
                        logging.warning(f"跳过非数值数据 行{row_idx+1}: '{dvds_value}'")
                        continue
            
            logging.info(f"成功提取 {len(dvds_values)} 个DVDS数据点")
            
            # 5. 创建结果DataFrame
            if dvds_values:
                # 从文件名提取lot_ID (使用正则表达式)
                lot_id = self.extract_batch_info(file_path)
                
                result_df = pd.DataFrame({
                    'lot_ID': [lot_id] * len(dvds_values),
                    f'DVDS({unit_value})': dvds_values
                })
                
                logging.info(f"成功创建DataFrame: {result_df.shape}")
                return result_df
            else:
                logging.warning(f"未提取到任何有效数据: {filename}")
                return pd.DataFrame()
                
        except Exception as e:
            logging.error(f"提取DVDS数据时发生错误 {filename}: {str(e)}")
            return pd.DataFrame()
    
    def merge_all_data(self, data_list):
        """
        合并所有文件的数据
        
        Args:
            data_list (list): 包含各文件数据的DataFrame列表
        
        Returns:
            pd.DataFrame: 合并后的统一数据，包含NUM, lot_ID, DVDS(mV)
        """
        try:
            if not data_list:
                logging.warning("没有数据需要合并")
                return pd.DataFrame()
            
            # 过滤掉空的DataFrame
            valid_data_list = [df for df in data_list if not df.empty]
            
            if not valid_data_list:
                logging.warning("所有DataFrame都为空")
                return pd.DataFrame()
            
            logging.info(f"开始合并 {len(valid_data_list)} 个DataFrame")
            
            # 合并所有DataFrame
            merged_df = pd.concat(valid_data_list, ignore_index=True)
            
            # 生成连续NUM编号
            merged_df['NUM'] = range(1, len(merged_df) + 1)
            
            # 重新排列列顺序: NUM, lot_ID, DVDS(mV)
            columns = ['NUM', 'lot_ID']
            dvds_columns = [col for col in merged_df.columns if 'DVDS' in col]
            if dvds_columns:
                columns.extend(dvds_columns)
            
            merged_df = merged_df[columns]
            
            logging.info(f"数据合并完成，总共 {len(merged_df)} 行数据")
            return merged_df
            
        except Exception as e:
            logging.error(f"合并数据时发生错误: {str(e)}")
            return pd.DataFrame()
    
    def clean_and_format(self, df):
        """
        数据清洗和格式化
        
        Args:
            df (pd.DataFrame): 原始合并数据
        
        Returns:
            pd.DataFrame: 清洗后的数据
        """
        try:
            if df.empty:
                logging.warning("输入数据为空，无需清洗")
                return df
            
            logging.info(f"开始数据清洗，原始数据: {df.shape}")
            
            # 1. 删除空值行
            dvds_columns = [col for col in df.columns if 'DVDS' in col]
            if dvds_columns:
                df_clean = df.dropna(subset=dvds_columns)
                logging.info(f"删除空值后: {df_clean.shape}")
            else:
                df_clean = df.copy()
            
            # 2. 数据类型转换和清洗
            for col in dvds_columns:
                # 转换为数值类型
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                
                # 删除转换失败的行
                df_clean = df_clean.dropna(subset=[col])
                
                logging.info(f"清洗{col}列后: {df_clean.shape}")
            
            # 3. 重新生成连续编号
            df_clean['NUM'] = range(1, len(df_clean) + 1)
            
            logging.info(f"数据清洗完成，最终数据: {df_clean.shape}")
            return df_clean
            
        except Exception as e:
            logging.error(f"数据清洗时发生错误: {str(e)}")
            return df
    
    def save_result(self, df):
        """
        保存结果到Excel文件
        
        Args:
            df (pd.DataFrame): 清洗后的数据
        
        Returns:
            str: 输出文件路径
        """
        try:
            if df.empty:
                logging.warning("没有数据需要保存")
                return ""
            
            # 提取lot_ids用于生成文件名
            lot_ids = df['lot_ID'].tolist() if 'lot_ID' in df.columns else ['unknown']
            
            # 使用lot_id生成文件名
            filename = generate_lot_based_filename(lot_ids, "DVDS")
            filepath = os.path.join(self.output_dir, filename)
            
            # 保存到Excel - 使用xlsxwriter引擎提升写入速度
            if not write_excel_fast(df, filepath, index=False, engine='xlsxwriter', sheet_name='DVDS_Data'):
                logging.error(f"DVDS数据保存失败: {filepath}")
                return ""
            
            logging.info(f"数据保存成功: {filepath}")
            logging.info(f"保存了 {len(df)} 行数据")
            
            return filepath
            
        except Exception as e:
            logging.error(f"保存数据时发生错误: {str(e)}")
            return ""
    
    def process_all(self):
        """
        执行完整的数据处理流程
        
        Returns:
            str: 输出文件路径，如果失败返回空字符串
        """
        try:
            # Phase 1: 扫描文件
            logging.info("=== Phase 1: 扫描DVDS文件 ===")
            files = self.scan_dvds_files()
            
            if not files:
                logging.error("未找到任何有效的xlsx文件")
                return ""
            
            # Phase 2: 提取数据
            logging.info("=== Phase 2: 提取DVDS数据 ===")
            data_list = []
            
            for file_path in files:
                df = self.extract_dvds_data(file_path)
                if not df.empty:
                    data_list.append(df)
            
            if not data_list:
                logging.error("未能从任何文件中提取到有效数据")
                return ""
            
            # Phase 3: 合并和清洗数据
            logging.info("=== Phase 3: 合并和清洗数据 ===")
            merged_df = self.merge_all_data(data_list)
            
            if merged_df.empty:
                logging.error("数据合并失败")
                return ""
            
            cleaned_df = self.clean_and_format(merged_df)
            
            if cleaned_df.empty:
                logging.error("数据清洗失败")
                return ""
            
            # Phase 4: 保存结果
            logging.info("=== Phase 4: 保存结果 ===")
            output_file = self.save_result(cleaned_df)
            
            if output_file:
                logging.info("=== 处理完成 ===")
                logging.info(f"成功处理 {len(files)} 个文件")
                logging.info(f"输出文件: {output_file}")
                return output_file
            else:
                logging.error("保存结果失败")
                return ""
            
        except Exception as e:
            logging.error(f"处理过程中发生错误: {str(e)}")
            return ""


def main():
    """主函数"""
    print("=" * 60)
    print("DVDS数据清洗工具 - 完整流程处理")
    print("=" * 60)
    
    # 创建清洗器实例
    cleaner = DVDSCleaner()
    
    # 执行完整处理流程
    print("\n开始执行完整的DVDS数据处理流程...")
    output_file = cleaner.process_all()
    
    if output_file:
        print("\n处理完成！")
        print(f"输出文件: {os.path.basename(output_file)}")
        print(f"文件路径: {output_file}")
        
        # 显示简单统计
        try:
            result_df = pd.read_excel(output_file)
            print("\n数据统计:")
            print(f"   总数据点: {len(result_df)}")
            dvds_col = [col for col in result_df.columns if 'DVDS' in col][0]
            print(f"   DVDS范围: {result_df[dvds_col].min():.1f} ~ {result_df[dvds_col].max():.1f} mV")
            print(f"   DVDS平均: {result_df[dvds_col].mean():.2f} mV")
            print(f"   不同lot数: {result_df['lot_ID'].nunique()}")
        except:
            pass
    else:
        print("\n处理失败，请查看日志了解详细信息")
    
    print("\n" + "=" * 60)
    print("DVDS数据清洗工具运行完成")
    print("=" * 60)


if __name__ == "__main__":
    main() 
