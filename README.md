# FT数据清洗工具集 — 多封装厂模块化架构

## 项目概述

FT数据清洗工具集是一个专业的半导体测试数据处理工具，支持多个封装厂的测试数据清洗和标准化。目前已支持的封装厂：

| 封装厂 | 数据类型 | 数据格式 | 状态 |
|--------|----------|----------|------|
| **日月新 (ASE)** | DC / DVDS / RG | .xlsx | ✅ 稳定 |
| **杰群 (Jiequn)** | DC / DVDS / RG | .csv (DTA) | ✅ 可用 |
| 杰群 PAT | PAT 统计 | .csv | 🔜 待开发 |

## 📁 项目结构

```
data_IGBT_multiple/
│
├── factories/                          ← 封装厂模块（各厂独立）
│   ├── base/
│   │   └── base_cleaner.py             ← 抽象基类
│   ├── riyuexin/                       ← 日月新（ASE）
│   │   ├── config.py                   ← 厂配置（数据类型、单位换算等）
│   │   ├── dc_cleaner.py
│   │   ├── dvds_cleaner.py
│   │   └── rg_cleaner.py
│   └── jiequn/                         ← 杰群（Jiequn）
│       ├── config.py                   ← 厂配置 + 单位换算规则
│       ├── csv_parser.py               ← DTA CSV 通用解析器
│       ├── dc_cleaner.py               ← 含 IDSS/IGSS/ISGS→nA, Rdson→mR
│       ├── dvds_cleaner.py             ← 含 DVDS V→mV
│       └── rg_cleaner.py
│
├── shared/
│   └── excel_utils.py                  ← 共享 Excel 工具（支持 .xls/.xlsx）
│
├── data/                               ← 原始测试数据
│   └── 杰群/                           ← 杰群 CSV 数据源
│
├── output/                             ← 清洗后输出
│   └── 杰群-output/                    ← 杰群输出目录
│
├── gui/                                ← 图形界面（待重构为多厂侧边栏）
│   ├── ft_data_cleaner_gui.py
│   └── start_gui.bat
│
├── dc_processing/                      ← [旧] 日月新 DC（保持兼容，GUI 仍依赖）
├── dvds_processing/                    ← [旧] 日月新 DVDS
├── rg_processing/                      ← [旧] 日月新 RG
│
├── requirements.txt
└── README.md
```

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 命令行使用

#### 日月新（ASE）
```bash
# 新模块路径（推荐）
python factories/riyuexin/dc_cleaner.py
python factories/riyuexin/dvds_cleaner.py
python factories/riyuexin/rg_cleaner.py
```

#### 杰群（Jiequn）
```bash
python factories/jiequn/dc_cleaner.py       # DC 清洗 + 单位换算
python factories/jiequn/dvds_cleaner.py     # DVDS 清洗 + V→mV
python factories/jiequn/rg_cleaner.py       # RG 清洗
```

### 图形界面
```bash
cd gui
python ft_data_cleaner_gui.py
```
> 注意：GUI 当前仅支持日月新。多厂 UI（侧边栏选厂）将在代码验证通过后重构。

## 🏭 封装厂架构

### 添加新封装厂只需 3 步：

1. **创建目录** `factories/<厂名>/`
2. **编写 `config.py`**：声明厂名、数据类型、文件格式、单位换算规则
3. **编写 Cleaner**：继承 `BaseCleaner`，实现 `process_all()`

每个厂有独立的：
- 数据解析逻辑（Excel vs CSV vs 其他）
- 参数提取规则
- 单位换算方法（`config.py` 中的 `UNIT_CONVERSIONS`）

## 📊 单位换算（杰群）

| 参数 | 原始单位 | 目标单位 | 换算因子 |
|------|----------|----------|----------|
| IDSS | A | nA | ×10⁹ |
| IGSS | A | nA | ×10⁹ |
| ISGS | A | nA | ×10⁹ |
| Rdson | Ω | mR | ×10³ |
| DVDS | V | mV | ×10³ |

日月新无需单位换算（数据已是目标单位）。

## 📋 系统要求

- **操作系统**：Windows 10/11
- **Python版本**：3.7+
- **内存**：建议 8GB 以上（杰群 CSV 单文件可达 70MB）

## 📦 依赖包

| 包名 | 用途 |
|------|------|
| pandas ≥2.2.0 | 数据处理 |
| openpyxl | .xlsx 读写 |
| xlrd | .xls 老格式支持 |
| python-calamine | 快速 Excel 读取 |
| xlsxwriter | 快速 Excel 写入 |
| PyQt5 | GUI 界面 |

## 🔄 版本历史

- **v2.0** (2025-05-29)：多封装厂模块化重构，新增杰群支持
- **v1.2** (2025-01-20)：GUI 优化，lot_ID 文件命名
- **v1.0** (2025-01-20)：初始版本，支持日月新 DC/DVDS/RG

---

**开发者**: cc  
**最后更新**: 2025-05-29
