# DVDS数据清洗工具

## 概述

DVDS数据清洗工具用于将ASEData/DVDS目录下的Excel测试数据文件清洗整理成统一格式的DVDS数据文件。

## 功能特点

- ✅ 自动扫描DVDS目录下的所有xlsx文件
- ✅ 智能定位Excel文件中的DVDS数据列和单位
- ✅ 批量提取和合并多个文件的DVDS数据
- ✅ 生成标准格式的输出文件（NUM, lot_ID, DVDS(mV)）
- ✅ 完整的日志记录和错误处理

## 快速开始

### 1. 运行主程序

在项目根目录下运行：

```bash
cd dvds_processing
python dvds_cleaner.py
```

### 2. 输出结果

程序会在`output/`目录下生成带时间戳的Excel文件，例如：

- `DVDS_20250103_165345.xlsx`

### 3. 输出格式

生成的Excel文件包含三列：

- `NUM`: 连续编号
- `lot_ID`: 文件名（lot标识）
- `DVDS(mV)`: DVDS数值（单位mV）

## 项目结构

```
dvds_processing/
├── dvds_cleaner.py        # 主程序文件
├── todo_DVDS.md          # 项目任务规划
├── dvds_core_logic.md    # 核心代码说明
├── test_extract.py       # 测试脚本
├── dvds_cleaner.log      # 运行日志
└── README.md             # 本文档
```

## 测试功能

如果需要测试单个文件的数据提取功能：

```bash
python test_extract.py
```

## 技术要求

- Python 3.x
- pandas
- openpyxl

## 开发状态

✅ **项目已完成** - 2025年1月3日

- [x] Phase 1: 基础框架搭建
- [x] Phase 2: 核心数据提取
- [x] Phase 3: 数据处理与合并
- [x] Phase 4: 输出与优化
- [x] Phase 5: 测试与文档

## 处理流程

1. **扫描文件**: 自动扫描ASEData/DVDS目录下的xlsx文件
2. **数据提取**: 从每个文件的第2行定位DVDS列，第20行开始提取数据
3. **数据合并**: 将所有文件的数据合并并生成连续编号
4. **数据清洗**: 清除无效数据，确保数据质量
5. **保存输出**: 生成标准格式的Excel文件

## 注意事项

- 确保ASEData/DVDS目录存在且包含有效的xlsx文件
- Excel文件应符合标准格式（第2行包含DVDS列，第19行为Test No.）
- 输出目录会自动创建
- 运行日志保存在dvds_cleaner.log中
