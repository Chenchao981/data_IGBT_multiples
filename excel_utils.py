#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Excel性能优化工具模块
为DC、DVDS、RG等数据处理器提供高性能的Excel读写功能

优化要点：
1. 使用calamine引擎进行快速Excel读取（比openpyxl快2-3倍）
2. 使用xlsxwriter引擎进行快速Excel写入（比openpyxl快2-3倍）
3. 提供统一的批次信息提取工具
4. 提供通用的文件扫描工具
5. 提供性能监控和日志记录
"""

import os
import pandas as pd
import re
import logging
import importlib.util
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Union, Dict, Any
import time
from functools import wraps


class ExcelOptimizer:
    """Excel性能优化器主类"""
    _calamine_available: Optional[bool] = None

    @staticmethod
    def _pandas_supports_calamine() -> bool:
        try:
            major, minor = (int(part) for part in pd.__version__.split(".")[:2])
            return (major, minor) >= (2, 2)
        except Exception:
            return False

    @classmethod
    def _can_use_calamine(cls) -> bool:
        if cls._calamine_available is None:
            cls._calamine_available = (
                cls._pandas_supports_calamine()
                and importlib.util.find_spec("python_calamine") is not None
            )
        return cls._calamine_available
    
    def __init__(self, log_performance: bool = True):
        """
        初始化Excel优化器
        
        Args:
            log_performance: 是否记录性能日志
        """
        self.log_performance = log_performance
        self.logger = logging.getLogger(__name__)
        
    def read_excel_fast(self, file_path: Union[str, Path], **kwargs) -> pd.DataFrame:
        """
        快速读取Excel文件
        
        Args:
            file_path: Excel文件路径
            **kwargs: 其他pandas.read_excel参数
            
        Returns:
            DataFrame: 读取的数据
        """
        start_time = time.time()
        
        try:
            # 默认使用calamine引擎
            if 'engine' not in kwargs:
                kwargs['engine'] = 'calamine' if self._can_use_calamine() else 'openpyxl'
            
            df = pd.read_excel(file_path, **kwargs)
            
            if self.log_performance:
                elapsed = time.time() - start_time
                self.logger.info(f"快速读取Excel: {Path(file_path).name} "
                               f"({df.shape[0]}行x{df.shape[1]}列) 耗时: {elapsed:.3f}秒")
            
            return df
            
        except Exception as e:
            # 如果calamine失败，回退到openpyxl
            if kwargs.get('engine') == 'calamine':
                self.logger.warning(f"calamine引擎失败，回退到openpyxl: {str(e)}")
                kwargs['engine'] = 'openpyxl'
                return self.read_excel_fast(file_path, **kwargs)
            else:
                raise e
    
    def write_excel_fast(self, df: pd.DataFrame, file_path: Union[str, Path], 
                        **kwargs) -> bool:
        """
        快速写入Excel文件
        
        Args:
            df: 要写入的DataFrame
            file_path: 输出文件路径
            **kwargs: 其他to_excel参数
            
        Returns:
            bool: 写入是否成功
        """
        start_time = time.time()
        
        try:
            excel_max_rows = 1048576
            header_rows = 1 if kwargs.get('header', True) else 0
            max_data_rows_per_sheet = excel_max_rows - header_rows

            # 默认使用xlsxwriter引擎
            if 'engine' not in kwargs:
                kwargs['engine'] = 'xlsxwriter'
            
            # 默认不写入索引
            if 'index' not in kwargs:
                kwargs['index'] = False
            
            if len(df) > max_data_rows_per_sheet:
                engine = kwargs.get('engine', 'xlsxwriter')
                sheet_name = kwargs.get('sheet_name', 'Sheet1')
                to_excel_kwargs = dict(kwargs)
                to_excel_kwargs.pop('engine', None)
                to_excel_kwargs.pop('sheet_name', None)
                with pd.ExcelWriter(file_path, engine=engine) as writer:
                    for chunk_index, start_row in enumerate(range(0, len(df), max_data_rows_per_sheet), start=1):
                        chunk = df.iloc[start_row:start_row + max_data_rows_per_sheet]
                        chunk_sheet_name = f"{sheet_name}_{chunk_index}"[:31]
                        chunk.to_excel(writer, sheet_name=chunk_sheet_name, **to_excel_kwargs)
                self.logger.warning(
                    f"数据行数超过Excel单sheet限制，已拆分为 "
                    f"{(len(df) + max_data_rows_per_sheet - 1) // max_data_rows_per_sheet} 个工作表"
                )
            else:
                df.to_excel(file_path, **kwargs)
            
            if self.log_performance:
                elapsed = time.time() - start_time
                self.logger.info(f"快速写入Excel: {Path(file_path).name} "
                               f"({len(df)}行x{len(df.columns)}列) 耗时: {elapsed:.3f}秒")
            
            return True
            
        except Exception as e:
            # 如果xlsxwriter失败，回退到openpyxl
            if kwargs.get('engine') == 'xlsxwriter':
                self.logger.warning(f"xlsxwriter引擎失败，回退到openpyxl: {str(e)}")
                kwargs['engine'] = 'openpyxl'
                return self.write_excel_fast(df, file_path, **kwargs)
            else:
                self.logger.error(f"Excel写入失败: {str(e)}")
                return False
    
    def extract_batch_id(self, filename: str, pattern: str = r'[A-Z0-9]{4}-[0-9]{4}') -> str:
        """
        从文件名中提取批次信息
        
        Args:
            filename: 文件名
            pattern: 正则表达式模式
            
        Returns:
            str: 批次ID
        """
        match = re.search(pattern, filename)
        
        if match:
            lot_id = match.group()
            self.logger.debug(f"提取批次信息: {filename} -> {lot_id}")
            return lot_id
        else:
            # 如果正则匹配失败，使用文件名（去除扩展名）
            lot_id = Path(filename).stem
            self.logger.warning(f"正则匹配失败，使用完整文件名: {filename} -> {lot_id}")
            return lot_id
    
    def scan_excel_files(self, directory: Union[str, Path], 
                        pattern: str = "*.xlsx") -> List[Path]:
        """
        扫描目录下的Excel文件
        
        Args:
            directory: 目录路径
            pattern: 文件匹配模式
            
        Returns:
            List[Path]: Excel文件路径列表
        """
        directory = Path(directory)
        
        if not directory.exists():
            self.logger.error(f"目录不存在: {directory}")
            return []
        
        # 扫描文件，排除临时文件(~$开头)
        xlsx_files = []
        for file_path in directory.glob(pattern):
            if not file_path.name.startswith("~$") and file_path.is_file():
                xlsx_files.append(file_path)
        
        self.logger.info(f"扫描目录 {directory}，找到 {len(xlsx_files)} 个Excel文件")
        for file_path in xlsx_files:
            self.logger.info(f"  - {file_path.name}")
        
        return xlsx_files
    
    def generate_output_filename(self, prefix: str, extension: str = ".xlsx") -> str:
        """
        生成带时间戳的输出文件名
        
        Args:
            prefix: 文件名前缀
            extension: 文件扩展名
            
        Returns:
            str: 生成的文件名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}{extension}"


def performance_monitor(func):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        
        logger = logging.getLogger(__name__)
        logger.info(f"函数 {func.__name__} 执行耗时: {elapsed:.3f}秒")
        
        return result
    return wrapper


# 全局优化器实例
_global_optimizer = None

def get_excel_optimizer(log_performance: bool = True) -> ExcelOptimizer:
    """获取全局Excel优化器实例"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = ExcelOptimizer(log_performance=log_performance)
    return _global_optimizer


# 便捷函数
def read_excel_fast(file_path: Union[str, Path], **kwargs) -> pd.DataFrame:
    """快速读取Excel文件的便捷函数"""
    optimizer = get_excel_optimizer()
    return optimizer.read_excel_fast(file_path, **kwargs)


def write_excel_fast(df: pd.DataFrame, file_path: Union[str, Path], **kwargs) -> bool:
    """快速写入Excel文件的便捷函数"""
    optimizer = get_excel_optimizer()
    return optimizer.write_excel_fast(df, file_path, **kwargs)


def extract_batch_id(filename: str, pattern: str = r'[A-Z0-9]{4}-[0-9]{4}') -> str:
    """从文件名提取批次ID的便捷函数"""
    optimizer = get_excel_optimizer()
    return optimizer.extract_batch_id(filename, pattern)


def scan_excel_files(directory: Union[str, Path], pattern: str = "*.xlsx") -> List[Path]:
    """扫描Excel文件的便捷函数"""
    optimizer = get_excel_optimizer()
    return optimizer.scan_excel_files(directory, pattern)


def generate_output_filename(prefix: str, extension: str = ".xlsx") -> str:
    """生成输出文件名的便捷函数"""
    optimizer = get_excel_optimizer()
    return optimizer.generate_output_filename(prefix, extension)


def generate_lot_based_filename(lot_ids: list, data_type: str, extension: str = ".xlsx") -> str:
    """
    基于lot_id生成输出文件名
    
    Args:
        lot_ids: lot_id列表
        data_type: 数据类型 (DC/DVDS/RG)
        extension: 文件扩展名
        
    Returns:
        str: 生成的文件名
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 如果只有一个lot_id，直接使用
    if len(set(lot_ids)) == 1:
        return f"{lot_ids[0]}_{data_type}_{timestamp}{extension}"
    else:
        # 如果有多个lot_id，使用"mixed"表示
        return f"mixed_{data_type}_{timestamp}{extension}"


# 性能统计工具
class PerformanceStats:
    """性能统计工具"""
    
    def __init__(self):
        self.stats = {}
    
    def record(self, operation: str, duration: float, data_size: int = 0):
        """记录性能数据"""
        if operation not in self.stats:
            self.stats[operation] = []
        
        self.stats[operation].append({
            'duration': duration,
            'data_size': data_size,
            'timestamp': datetime.now()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        summary = {}
        
        for operation, records in self.stats.items():
            durations = [r['duration'] for r in records]
            data_sizes = [r['data_size'] for r in records if r['data_size'] > 0]
            
            summary[operation] = {
                'count': len(records),
                'total_time': sum(durations),
                'avg_time': sum(durations) / len(durations) if durations else 0,
                'min_time': min(durations) if durations else 0,
                'max_time': max(durations) if durations else 0,
                'total_data': sum(data_sizes),
                'avg_throughput': sum(data_sizes) / sum(durations) if durations and data_sizes else 0
            }
        
        return summary
    
    def print_summary(self):
        """打印性能摘要"""
        summary = self.get_summary()
        
        print("\n" + "=" * 60)
        print("Excel处理器性能摘要")
        print("=" * 60)
        
        for operation, stats in summary.items():
            print(f"\n📊 {operation}:")
            print(f"   执行次数: {stats['count']}")
            print(f"   总耗时: {stats['total_time']:.3f}秒")
            print(f"   平均耗时: {stats['avg_time']:.3f}秒")
            if stats['avg_throughput'] > 0:
                print(f"   平均处理速度: {stats['avg_throughput']:.0f} 行/秒")
        
        print("\n" + "=" * 60)


# 全局性能统计实例
_global_stats = PerformanceStats()

def get_performance_stats() -> PerformanceStats:
    """获取全局性能统计实例"""
    return _global_stats


if __name__ == "__main__":
    # 模块测试代码
    print("Excel性能优化工具模块")
    print("提供的功能:")
    print("1. 快速Excel读写 (calamine + xlsxwriter)")
    print("2. 批次信息提取")
    print("3. 文件扫描")
    print("4. 性能监控")
    print("5. 统一的便捷接口") 
