#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
封装厂数据清洗器 — 抽象基类

每个封装厂必须实现：
    - process_all() → bool
    - 从 config.py 读取工厂特定配置（数据类型列表、单位换算等）
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict


class BaseCleaner(ABC):
    """所有封装厂清洗器的抽象基类"""

    factory_name: str = ""
    data_types: List[str] = []
    unit_conversions: Dict[str, Dict] = {}  # { "IDSS": {"from":"A","to":"nA","factor":1e9} }

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def process_all(self, data_type: Optional[str] = None) -> bool:
        """
        执行完整的数据处理流程
        
        Args:
            data_type: 指定处理的数据类型（DC/DVDS/RG），为 None 时处理全部
            
        Returns:
            处理是否成功
        """
        ...

    def _apply_unit_conversions(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """
        根据 config.UNIT_CONVERSIONS 对 DataFrame 列进行单位换算。
        匹配规则：列名包含参数名（如 IDSS40.0）即触发换算。
        各封装厂可重写此方法实现自定义逻辑。
        """
        if not self.unit_conversions:
            return df

        import pandas as pd

        for param_name, rule in self.unit_conversions.items():
            factor = rule.get("factor", 1.0)
            if factor == 1.0:
                continue
            for col in df.columns:
                if param_name.upper() in col.upper():
                    # 只换算数值列，跳过 lot_ID / NUM 等非数值列
                    if pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = df[col] * factor
        return df
