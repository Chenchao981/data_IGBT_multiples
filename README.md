# FT数据清洗工具集

## 项目概述

FT数据清洗工具集是一个专业的半导体测试数据处理工具，用于清洗和标准化ASE测试数据。支持DC、DVDS、RG三种数据类型的处理，提供命令行和图形界面两种使用方式。

## 📁 项目结构

```
data_IGBT/
├── ASEData/                    # 原始测试数据
│   ├── DC/                     # DC测试数据
│   ├── DVDS/                   # DVDS测试数据
│   └── RG/                     # RG测试数据
├── dc_processing/              # DC数据清洗模块
│   ├── dc_cleaner.py          # DC清洗器主程序
│   ├── dc_core_logic.md       # DC处理逻辑文档
│   └── README.md              # DC模块说明
├── dvds_processing/            # DVDS数据清洗模块
│   ├── dvds_cleaner.py        # DVDS清洗器主程序
│   ├── dvds_core_logic.md     # DVDS处理逻辑文档
│   └── README.md              # DVDS模块说明
├── rg_processing/              # RG数据清洗模块
│   ├── rg_cleaner.py          # RG清洗器主程序
│   └── TODO_RG.md             # RG模块待办事项
├── gui/                        # 图形界面模块
│   ├── ft_data_cleaner_gui.py # GUI主程序
│   ├── start_gui.bat          # Windows启动脚本
│   └── README.md              # GUI模块说明
├── output/                     # 清洗后数据输出目录
├── excel_utils.py             # Excel处理工具函数
├── requirements.txt           # Python依赖包
└── README.md                  # 本文档
```

## 🚀 快速开始

### 安装依赖
```bash
python -m pip install -r requirements.txt
```

### 使用方式

#### 1. 图形界面（推荐）

```bash
# 方式1：使用启动脚本（Windows）
cd gui
start_gui.bat

# 方式2：直接运行Python
cd gui
python ft_data_cleaner_gui.py

# 方式3：从项目根目录
python gui/ft_data_cleaner_gui.py
```

#### 2. 命令行方式
```bash
# DC数据清洗
cd dc_processing
python dc_cleaner.py

# DVDS数据清洗
cd dvds_processing
python dvds_cleaner.py

# RG数据清洗
cd rg_processing
python rg_cleaner.py
```

## 📊 数据处理流程

### 输入数据
- **格式**：Excel (.xlsx) 文件
- **位置**：ASEData/{类型}/ 目录
- **来源**：ASE测试设备导出的原始数据

### 处理过程
1. **文件扫描**：自动扫描指定目录下的Excel文件
2. **数据提取**：根据各类型的数据结构提取有效测试数据
3. **数据清洗**：去除无效数据、标准化格式
4. **数据合并**：将多个文件的数据合并为统一格式
5. **结果输出**：生成带时间戳的Excel文件

### 输出数据
- **格式**：标准化的Excel文件
- **命名**：{lot_ID}_{类型}_{时间戳}.xlsx（多批次时为mixed_{类型}_{时间戳}.xlsx）
- **位置**：用户指定的输出目录
- **内容**：包含NUM、lot_ID和相应参数列

## 🛠️ 各模块功能

### DC数据清洗 (`dc_processing/`)
- **功能**：处理DC参数测试数据
- **支持参数**：IDSS、VTH、BVDSS、RDS(ON)、LRDON等
- **特性**：智能参数识别、重复参数处理、测试条件增强

### DVDS数据清洗 (`dvds_processing/`)
- **功能**：处理DVDS参数测试数据
- **输出格式**：NUM, lot_ID, DVDS(mV)
- **特性**：自动单位识别、数据验证

### RG数据清洗 (`rg_processing/`)
- **功能**：处理RG参数测试数据
- **输出格式**：NUM, lot_ID, RG(R)
- **特性**：动态位置定位、异常值过滤

### GUI界面 (`gui/`)
- **功能**：提供统一的图形用户界面
- **特性**：多线程处理、实时状态显示、桌面路径默认设置
- **支持**：所有三种数据类型的清洗
- **文件命名**：基于lot_ID的智能命名

## 📋 系统要求

- **操作系统**：Windows 10/11
- **Python版本**：3.7+
- **内存**：建议4GB以上
- **存储**：取决于数据文件大小

## 📦 依赖包

| 包名 | 版本 | 用途 |
|------|------|------|
| pandas | ≥1.5.0 | 数据处理 |
| openpyxl | ≥3.0.0 | Excel读写 |
| PyQt5 | ≥5.15.0 | GUI界面 |
| python-calamine | ≥0.2.0 | 快速Excel读取 |
| xlsxwriter | ≥3.0.0 | Excel写入优化 |

## 🐛 常见问题

### 1. 模块导入错误
**解决**：确保在正确的目录下运行程序，或检查Python路径设置

### 2. 文件读取失败
**解决**：检查Excel文件是否被其他程序占用，确保文件格式正确

### 3. GUI启动失败
**解决**：确保已安装PyQt5，检查系统是否支持GUI显示

### 4. 内存不足
**解决**：处理大文件时关闭其他应用程序，或分批处理数据

## 📈 性能优化

- 使用calamine引擎快速读取Excel文件
- 向量化数据处理提升pandas性能
- 多线程GUI防止界面卡顿
- 智能内存管理处理大数据集

## 🔄 版本历史

- **v1.2** (2025-01-20)：GUI界面优化，移除图表功能，基于lot_ID的文件命名
- **v1.1** (2025-01-20)：添加GUI界面，优化用户体验
- **v1.0** (2025-01-20)：基础功能实现，支持三种数据类型

## 🤝 贡献

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看LICENSE文件了解详情

---

**开发者**: cc  
**创建时间**: 2025-06-18  
**最后更新**: 2025-01-20 
