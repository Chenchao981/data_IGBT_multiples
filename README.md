# FT数据清洗工具集 — 多封装厂模块化架构

## 项目概述

半导体测试数据处理工具，支持多个封装厂的测试数据清洗和标准化。

### 已支持

| 封装厂 | 数据格式 | 数据处理 | 状态 |
|--------|----------|----------|------|
| **日月新 (ASE)** | .xlsx 分目录 | DC / DVDS / RG | ✅ 稳定 |
| **杰群 批次1** | .csv 分目录 | DC / DVDS / RG | ✅ 稳定 |
| **杰群 批次2** | .csv 统一CSV | DC+DVDS+RG 合并 | ✅ 稳定 |
| **杰群 第三产线** | .csv 产品目录平铺、可变尾空列 | DC | ✅ 可用 |
| 杰群 PAT | — | 统计汇总 | ✅ 可用 |

---

## 📁 项目结构

```
data_IGBT_multiple/
│
├── factories/
│   ├── base/
│   │   └── base_cleaner.py         ← 抽象基类（process_all、单位换算）
│   │
│   ├── riyuexin/                   ← 日月新模块
│   │   ├── config.py               ← 厂名、数据类型、路径
│   │   ├── dc_cleaner.py           ← DC 参数增强（IDSS40, VTH1...）
│   │   ├── dvds_cleaner.py
│   │   └── rg_cleaner.py
│   │
│   └── jiequn/                     ← 杰群模块
│       ├── config.py               ← 配置 + 单位换算规则
│       ├── csv_parser.py           ← ★ CSR 解析器（通用）
│       ├── formatting.py           ← ★ 杰群输出列名/参数排序规则
│       ├── dc_cleaner.py           ← 分目录 → DC
│       ├── dvds_cleaner.py         ← 分目录 → DVDS
│       ├── rg_cleaner.py           ← 分目录 → RG
│       ├── clean_unified.py        ← ★ 统一CSV → DC+DVDS+RG 一次输出
│       ├── pat_cleaner.py          ← PAT 统计 (Sigma=IQR/1.35)
│       └── unified_cleaner.py      ← [备选] 联合清洗
│
├── shared/
│   └── excel_utils.py              ← Excel/CSV 读写工具（.xls/.xlsx/.csv）
│
├── gui/
│   ├── main_window.py              ← ★ 侧边栏主窗口（选厂 + 面板切换）
│   ├── start_gui.bat
│   └── panels/
│       ├── base_panel.py           ← 面板基类（文件夹选 / 按钮 / 日志）
│       ├── riyuexin_panel.py       ← 日月新: 3 按钮
│       └── jiequn_panel.py         ← 杰群: 4 个清洗入口 + 清洗后统计
│
├── data/                           ← 原始数据
│   ├── 杰群/                       ← 批次1: 分目录 (DC/DVDS/RG)
│   ├── 杰群2/RAW/                  ← 批次2: 统一CSV
│   └── DC1/<产品>/                 ← 第三产线: DC DTA CSV 直接存放
│
├── output/                         ← 清洗输出
│
└── README.md
```

---

## 🎮 图形界面

启动：
```bash
python gui/main_window.py
```

### 杰群面板说明

第一行是原始数据文件格式/清洗入口，每次只选择一种：

| 按钮 | 处理的数据格式 | 输入目录示例 | 输出 |
|------|---------------|-------------|------|
| **DC** | 分目录（data/杰群/.../DC/） | 指向 `data/杰群` | NUM + 批次 + DC参数 |
| **DC-3** | 第三产线产品目录平铺 DTA CSV | 指向 `data/DC1` 或产品目录 | NUM + 批次 + DC参数 |
| **DVDS** | 分目录（data/杰群/.../DVDS/） | 指向 `data/杰群` | NUM + 批次 + DVDS(mV) |
| **RG** | 分目录（data/杰群/.../RG/） | 指向 `data/杰群` | NUM + 批次 + RG(R) |
| **统一CSV** | 单个CSV含全部参数（data/杰群2/RAW/） | 指向 `data/杰群2/RAW` | DC.xlsx + DVDS.xlsx + RG.xlsx |

第二行是清洗后统计/分析方法：

| 按钮 | 处理对象 | 输入目录示例 | 输出 |
|------|---------|-------------|------|
| **PAT** | 已清洗的 DC/DVDS/RG 输出 | 指向 `output/杰群-output` | PAT.xlsx（统计汇总） |

---

## 📊 杰群 CSV 格式说明

### 通用结构（DTA CSV）

所有杰群 CSV 文件遵循相同的头结构：

```
行  内容
──  ─────────────────────────
~1  DTA File Name, ...
~15 Test,,1,2,3,...        ← 测试编号
~16 Item,,IDSS,VTH,...     ← ★ 参数名称（解析器通过此行动态匹配）
~17 Min Limit,...
~18 Max Limit,...
~19 Limit Units,,A,V,...   ← 单位行
~20 Bias 1,,,IDS,...
~21 Bias 1 Value,,1E-2,... ← 测试条件值（用于参数增强）
~31 Min Result,...
~32 Max Result,...
~33 Average,...
~34 STD DEV,...
~35 Serial,Bin,...         ← 数据表头
~36 1,1,val,val,...        ← ★ 数据行从此开始
```

解析器通过 `Item` 行匹配目标参数名，不依赖固定列位置。

### 数据格式1 — 分文件格式（杰群厂线A）

```
data/杰群/NCEAP065NHD40AG(M)-1J00 JQ PAT/
├── DC/    *DTA.CSV         ← 每个文件只含 DC 参数
├── DVDS/  *_DVDSDTA.CSV    ← 每个文件只含 DVDS 参数
├── RG/    *_RGDTA.CSV      ← 每个文件只含 RG 参数
```

命令行：`python factories/jiequn/dc_cleaner.py`（自动扫描 DC 子目录）

### 数据格式2 — 单文件格式（杰群厂线B）

```
data/杰群2/RAW/
├── *_DTA.CSV               ← 每个文件含全部45项测试（DC+DVDS+RG 混合）
```

命令行：`python factories/jiequn/clean_unified.py data/杰群2/RAW output/杰群2`

格式2输出规则：
- 按源 CSV `Item` 行从左到右的顺序输出参数，方便和源数据逐列对比。
- 剔除 `CONT*` 计数字段（如 `CONT_TR`、`CONT_RF`、`CONT-B`、`CONT-C`、`CONT-E`）和 `SAME` 占位字段。
- DC 参数白名单为 `LCR-RG`、跳过第一个 `VTH` 后的所有 `VTH`、`BVDSS`、全部 `IDSS`、`ISGS`、`RDON`、`VFSDS`、`ABSDEL`。
- DC 只跳过源数据从左到右发现的第一个 `VTH`（封装厂占位测试），后续 `VTH` 从 `VTH1(V)` 开始重新编号；所有 `IDSS` 均保留并按 `Bias 1 Value` 命名，如 `IDSS-40(nA)`、`IDSS-35(nA)`，同名时输出为 `IDSS3.5-1(nA)`、`IDSS3.5-2(nA)`。
- DC 输出单位沿用杰群规则：`IDSS/IGSS/ISGS` 输出为 `nA`，`RDON` 输出为 `mR`，并执行对应数值换算；DVDS 输出为 `DVDS(mV)`。
- `DVDS(mV)` 为空的记录行会在输出前删除，空值不参与后续统计。

### 数据格式3 — 第三产线 DC

第三产线数据放在 `data/DC1/<产品>/`，没有单独的 `DC/` 子目录。GUI 使用
`DC-3` 按钮，文件名包含
`FADTA`、`FRDTA` 或 `FA1DTA`，现有 DC 入口会递归扫描并全部纳入。

头部的 Item、Limit Units、Bias 1 Value 和参数定义与杰群格式1一致；差异是
表头可能只有2列，也可能因末尾空逗号显示为26列，数据行因失效测试提前终止而
保留3～47个字段。解析器只根据实际数据段最宽行确定 pandas 列数，再读取目标
参数列，避免表头26列、数据25列导致 `ParserError`。

调用方式：

```python
from factories.jiequn.dc_cleaner import JiequnDCCleaner
JiequnDCCleaner("data/DC1", "output/DC1").process_all()
```

输出继续使用格式1契约：`NUM + 批次 + DC参数`、`DC_Data` 工作表、相同参数
命名/排序和单位换算。详见 `docs/杰群第三产线DC格式说明.md`。

---

## 🏷️ 输出格式规范

### 列定义

| 列名 | 说明 |
|------|------|
| NUM | 行号，从1开始 |
| 批次 | 从文件名提取的批次标识（`split('_')[1]`），旧代码内部变量名仍可能叫 `周记` |
| VTH1(V) | VTH 参数，顺序编号 + 单位 |
| BVDSS1(V) | BVDSS，顺序编号 + 单位 |
| IDSS100(nA) | IDSS，测试条件来自 `Bias 1 Value` 行（100=100V）；同名时在单位前加 `-1`、`-2` |
| ISGS25(nA) | ISGS，测试条件 + 单位 |
| IGSS25(nA) | 由正偏置 ISGS（如 `ISGS+25`）按杰群规则改名得到 |
| DVDS(mV) | DVDS，V→mV 换算 |
| RG(R) | RG，直接输出 |

### 批次提取规则

```
文件名: NCEAP020N10LL(M)-7J00_CJSx185_200000FA_20260104064208DTA.CSV
                                        ↑
                                split('_')[1] → CJSx185
```

### 参数增强命名规则

| 规则 | 示例 | 说明 |
|------|------|------|
| seq | VTH1(V), VTH2(V) | 顺序编号 + 单位 |
| bias | IDSS100(nA), RDON40(mR), IGSS25(nA) | Bias Value + 单位；IDSS 同名时在单位前加 `-1/-2`；杰群负偏置 ISGS 保留为 ISGS，正偏置 ISGS 改名为 IGSS |
| unit | DVDS(mV), VFSD(V) | 仅单位 |

### 参数排序规则

杰群格式1会通过 `factories/jiequn/formatting.py` 统一排序：

```text
NUM, 批次, VTH*, BVDSS*, IDSS*, ISGS*/IGSS*, RDON*, LRDON*, VF*, VFSD*, VFSDS*, DVDS*, RG*, CONT*, ABSDEL*, DELAY*
```

其中杰群 `ISGS` 和 `IGSS` 按同一偏置值成组排列，并保持 `ISGS` 在前、`IGSS` 在后；其他封装厂仍按各自规则处理。

杰群格式2（统一CSV）不做上述重排，按源 CSV `Item` 行从左到右保留参数顺序，只把内部 `周记` 列改名为 `批次`。

---

## 🔧 单位换算（杰群）

数值换算在数据提取后自动执行：

| 参数 | 原始 → 目标 | 因子 |
|------|-------------|------|
| IDSS | A → nA | ×1e9 |
| IGSS | A → nA | ×1e9 |
| ISGS | A → nA | ×1e9 |
| RDON | Ω → mR | ×1000 |
| DVDS | V → mV | ×1000 |

定义在 `factories/jiequn/config.py` 的 `UNIT_CONVERSIONS`。

---

## 📐 PAT 统计公式

```
Sigma = (Q3 - Q1) / 1.35
LCL = 中位数 - 6 * Sigma
UCL = 中位数 + 6 * Sigma
```

输出：`PAT.xlsx`，含每个参数的 count/mean/std/min/Q1/median/Q3/max/Sigma/LCL/UCL。

---

## 🧩 如何添加新格式

### 场景1：同一封装厂新增批次格式

在 `factories/jiequn/` 下新增一个 cleaner，使用 `csv_parser.py` 的 `parse_dta_csv()` 函数。

```python
from factories.jiequn.csv_parser import parse_dta_csv

df = parse_dta_csv(file_path, ["IDSS", "VTH"], unique_only=False)
```

然后在 `gui/panels/jiequn_panel.py` 的 `data_types` 加一个按钮即可。

### 场景2：新增封装厂

1. `mkdir factories/新厂/`
2. 写 `config.py`（厂名、数据类型、单位换算）
3. 写 cleaner，继承 `BaseCleaner`
4. 在 `gui/panels/` 下新建面板
5. 在 `gui/main_window.py` 的 `FACTORIES` 列表加入新厂

### 核心函数说明

| 函数 | 位置 | 用途 |
|------|------|------|
| `parse_dta_csv()` | `csv_parser.py` | 解析单个 CSV，返回增强参数名 DataFrame |
| `read_header_info()` | `csv_parser.py` | 读取 Item/Bias/Limit Units 等元信息 |
| `extract_zhouji()` | `csv_parser.py` | 从文件名提取周记 |
| `locate_key_rows()` | `csv_parser.py` | 定位 Item/Serial 关键行 |
| `_build_param_name()` | `csv_parser.py` | 构建增强参数名（seq/bias/unit） |
| `_apply_unit_conversions()` | `base_cleaner.py` | 按 config 的换算表乘以因子 |

---

## 🚀 快速命令速查

```bash
# 日月新 DC / DVDS / RG
python factories/riyuexin/dc_cleaner.py
python factories/riyuexin/dvds_cleaner.py
python factories/riyuexin/rg_cleaner.py

# 杰群 批次1（分目录）
python factories/jiequn/dc_cleaner.py
python factories/jiequn/dvds_cleaner.py
python factories/jiequn/rg_cleaner.py

# 杰群 批次2（统一CSV）
python factories/jiequn/clean_unified.py data/杰群2/RAW output/杰群2

# 杰群 第三产线 DC
python -c "from factories.jiequn.dc_cleaner import JiequnDCCleaner; JiequnDCCleaner('data/DC1', 'output/DC1').process_all()"

# PAT 统计
python -c "from factories.jiequn.pat_cleaner import build_pat, save_pat; save_pat(build_pat('output/杰群-output'))"

# GUI
python gui/main_window.py
```

---

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

- **v2.4.1** (2026-07-14)：修复杰群 DC-3/共用 DTA 解析器在多个 RDON 测试具有相同 Bias 1 条件时误删后续列；按源顺序输出 `RDON20-1(mR)`、`RDON20-2(mR)` 等唯一列名。
- **v2.4** (2026-07-03)：PAT 支持显式选择一个或多个清洗 Excel；逐个读取并合并 `DC_Data_1/2/3` 等编号 Sheet，Calamine 优先，确保整本工作簿数据参与统一四分位数计算。
- **v2.3.2** (2026-07-03)：修复 DC 清洗误跳过首个有效 IDSS；现在保留全部 IDSS，第三产线输出新增 `IDSS-40(nA)`。
- **v2.3.1** (2026-07-02)：修复 DC-3 完整数据中 Item/Serial 尾空列导致的 `expected 26 and found 25`；全量100文件、268万行验证通过。
- **v2.3** (2026-07-02)：支持杰群第三产线 DC 平铺目录和25～47字段可变尾空列格式；保持既有DC输出契约。
- **v2.2** (2026-06-03)：杰群输出统一为 `NUM + 批次 + 参数列`；新增 `formatting.py` 管理列排序；修复 `VF` 误匹配 `VFSDS`、`RDON/Rdson` 命名兼容、杰群 `ISGS/IGSS` 命名；PAT 跳过 `批次` 列。
- **v2.1** (2025-06-01)：杰群统一CSV格式支持，参数增强命名，周记提取
- **v2.0** (2025-05-29)：多封装厂模块化重构，新增杰群支持
- **v1.2** (2025-01-20)：GUI 优化，lot_ID 文件命名
- **v1.0** (2025-01-20)：初始版本，支持日月新 DC/DVDS/RG

---

## 🏛️ 架构概览

### 设计模式：Factory + Template Method

```
                   ┌─────────────────────────┐
                   │  gui/main_window.py     │
                   │  FACTORIES registry     │
                   └────────────┬────────────┘
                                │ instantiates
                                ▼
              ┌──────────────────────────────────┐
              │ gui/panels/base_panel.py        │
              │ BasePanel + CleanerWorker       │
              └────────────┬─────────┬──────────┘
                           │         │
              ┌────────────┘         └─────────────┐
              ▼                                    ▼
   gui/panels/riyuexin_panel.py       gui/panels/jiequn_panel.py
              │                                    │
              ▼                                    ▼
   factories/riyuexin/*.py            factories/jiequn/*.py
   (DCDataCleaner, DVDSCleaner,       (Jiequn*Cleaner, clean_unified,
    RGCleaner)                          pat_cleaner, unified_cleaner)
              │                                    │
              └────────────┬───────────────────────┘
                           ▼
              ┌──────────────────────────────────┐
              │  shared/excel_utils.py           │
              │  ExcelOptimizer (calamine/xlsxwriter)│
              └──────────────────────────────────┘
                           ▲
              factories/base/base_cleaner.py (仅杰群批次1使用)
              提供 _apply_unit_conversions
```

- **Factory 模式**：每个封装厂独立为 `factories/<厂名>/` 子包，新增厂 = 新增子包。
- **Template Method**：`BaseCleaner` 定义抽象 `process_all()`，子类实现具体清洗逻辑。
- **Abstract Base Class**：`BaseCleaner(ABC)` 提供统一接口（`process_all`、`_apply_unit_conversions`）。
- **模板面板**：`BasePanel` 封装通用 UI（按钮、文件夹选择、日志、线程），子类只实现 `_get_cleaner_fn(data_type)`。

### 重要说明

> ⚠️ **ASE（日月新）的三个 cleaner 是历史遗留代码，未继承 `BaseCleaner`**。它们直接调用 `shared/excel_utils` 的函数。**杰群批次1的 cleaner 才继承 `BaseCleaner`**。
>
> ⚠️ `factories/jiequn/unified_cleaner.py` 是 `clean_unified.py` 的备选实现（带 logger 的版本），目前**未被 GUI 或 CLI 使用**，可视为参考/历史代码。

---

## 🔄 数据流

### 杰群 批次1（分目录）

```
data/杰群/<product>/DC/*.CSV ─┐
data/杰群/<product>/DVDS/*.CSV ─┤── parse_dta_csv(target_params, unique_only)
data/杰群/<product>/RG/*.CSV ─┘          │
                                          ▼
                              pd.concat 所有 DataFrame
                                          │
                              BaseCleaner._apply_unit_conversions
                              (IDSS/IGSS/ISGS: A→nA ×1e9; Rdson: Ω→mR ×1e3; DVDS: V→mV ×1e3)
                                          │
                              dropna(周记) → reset_index → insert NUM
                                          │
                              generate_lot_based_filename(zhouji_list, "<TYPE>_JQ")
                                          │
                              write_excel_fast(sheet_name="<TYPE>_Data")
                                          ▼
output/杰群-output/<lot>_<TYPE>_JQ_<timestamp>.xlsx
                          (or mixed_<TYPE>_JQ_<timestamp>.xlsx)
```

### 杰群 批次2（统一CSV）

```
data/杰群2/RAW/*DTA.CSV
              │
              ├── for label in [DC, DVDS, RG]:
              │       parse_dta_csv with the per-type target_params
              │       (DC: all matches; DVDS, RG: unique_only)
              │       pd.concat all files for that label
              │       apply_conv()（列名子串单位换算）
              │       dropna(周记) → NUM 1..N
              │       write_excel_fast
              ▼
output/杰群2/mixed_<label>_JQ2_<timestamp>.xlsx  (每种类型一个)
```

### PAT 统计

```
output/杰群-output/mixed_DC_JQ_*.xlsx  (最新按 mtime)
output/杰群-output/mixed_DVDS_JQ_*.xlsx (最新按 mtime)
output/杰群-output/mixed_RG_JQ_*.xlsx  (最新按 mtime)
                │
                ▼
pd.read_excel (calamine → openpyxl fallback)
                │
                ▼
For each param column (skip NUM/lot_ID/周记):
    compute count, mean, std, Q1, Q2, Q3, Sigma = (Q3-Q1)/1.35,
                   LCL = Q2 - 6*Sigma, UCL = Q2 + 6*Sigma
                │
                ▼
写 PAT sheet (prepend 变量 header row)
                │
                ▼
output/杰群-output/PAT.xlsx
```

### ASE（日月新）

```
ASEData/<TYPE>/*.xlsx
              │
              ▼
  read_excel_fast (calamine)
              │
              ▼
  类型相关解析（位置固定，非按列名）：
    DC: row 1 (参数名) + row 4 (测试条件) + row 5 (LRDON测试条件) + row 6 (单位) + 定位 'Test No.'
    DVDS: row 1 ("DVDS") + row 6 (单位) + row 18 ("Test No.")
    RG: row 1 ("RG") + row 6 (R单位) + 定位 "Test No."
              │
              ▼
  build DataFrame [lot_ID, *params]  →  pd.concat
              │
              ▼
  clean_and_format (dropna / coerce / re-NUM / reorder)
              │
              ▼
  generate_lot_based_filename(lot_ids, "<TYPE>")
              │
              ▼
  write_excel_fast (sheet "<TYPE>_Data")
              │
              ▼
output/<lot>_<TYPE>_<timestamp>.xlsx
```

### GUI 流程

```
User clicks factory in QListWidget
            │
            ▼
MainWindow._on_factory_changed → QStackedWidget 切换到对应面板
            │
            ▼
User 选择数据文件格式或清洗后统计方法 + 输入/输出文件夹 + 点击 "开始清洗"
            │
            ▼
BasePanel._start:
  - 校验选择
  - 子类 _get_cleaner_fn(data_type) 返回无参 lambda
  - CleanerWorker(QThread) 在后台运行
            │
            ▼
Worker emits progress / finished / error
   → BasePanel 更新状态文本
   → 完成后弹 QMessageBox
```

---

## 📋 各模块详细说明

### `factories/base/base_cleaner.py`

**抽象基类** `BaseCleaner(ABC)`：

| 元素 | 类型 | 说明 |
|------|------|------|
| `factory_name` | 类属性 | 厂名 |
| `data_types` | 类属性 | 原始数据文件格式/清洗入口列表 |
| `post_process_types` | 类属性 | 清洗后处理/统计分析列表 |
| `unit_conversions` | 类属性 | `{param: {from, to, factor}}` 单位换算表 |
| `__init__(input_dir, output_dir)` | 构造 | 存储 Path，自动创建 output_dir |
| `process_all(data_type)` | 抽象方法 | **子类必须实现** |
| `_apply_unit_conversions(df)` | 实例方法 | 按 `unit_conversions` 匹配列名（子串）并乘以因子 |

`_apply_unit_conversions` 工作方式：
- 遍历 `self.unit_conversions`。
- 对每个 param（如 `"IDSS"`），找列名中**包含**该子串的列（大小写不敏感）。
- 如果是数值列，乘以配置的 `factor`。
- 跳过 `lot_ID` / `NUM` 等非数值列。
- 子类可重写自定义逻辑。

### `factories/jiequn/csv_parser.py` ★ 核心

DTA CSV 通用解析器，**杰群批次1和批次2 都依赖此模块**。

**关键函数：**

| 函数 | 输入 | 输出 | 用途 |
|------|------|------|------|
| `parse_dta_csv(file_path, target_params, max_scan=40, unique_only=False)` | 文件路径、目标参数列表 | DataFrame / None | **主入口**：解析 CSV 并返回增强参数名 DataFrame |
| `extract_zhouji(filename)` | 文件名 | 周记字符串 | 提取 `parts[1]` of `stem.split('_')` |
| `extract_lot_id_jiequn(filename)` | 文件名 | 周记字符串 | `extract_zhouji` 的别名（向后兼容） |
| `locate_key_rows(path, max_scan=40)` | 文件路径 | `(item_row_idx, data_start_idx, item_names, serial_headers)` | 定位 Item / Serial 关键行 |
| `read_header_info(path, max_scan=40)` | 文件路径 | dict `{item_names, limit_units, bias1_values, data_start, item_idx}` | 读取 Item/Bias/Limit Units 等元信息 |
| `_get_bias_value(bias_values, csv_field_idx)` | bias 行数据、列索引 | 字符串形式的 bias 值 | 解析科学计数法 (`1E+02` → `"100"`) |
| `_get_unit(limit_units, csv_field_idx, param_base)` | 单位行、列索引、参数基名 | 单位字符串 | 优先使用 `_PARAM_UNITS[param_base]`，回退到 `Limit Units` 行 |
| `_build_param_name(param_base, rule, bias_val, unit, seq_counter)` | 参数名、规则、bias、单位、序号 | 增强后的参数名 | 应用 seq/bias/unit 规则构建列名 |

**`parse_dta_csv` 流程：**
1. 调用 `read_header_info()` 读取头。
2. 验证 `Item` 和 `Serial,Bin` 行存在。
3. 对每个 base param，通过 `_item_matches_param()` 做精确/别名匹配。
4. 根据 `_PARAM_NAME_RULES` 中的命名规则（`seq` / `bias` / `unit`）和 `_PARAM_UNITS` 中的目标单位，调用 `_build_param_name()` 生成增强名（如 `IDSS100(nA)`、`VTH1(V)`、`DVDS(mV)`）。
5. `LCR-RG` → `RG` 重命名（保证输出一致）。
6. 按增强名去重（保留首个）。
7. 列数从 `Serial` 行长度推断（避免短数据行误判）。
8. `pd.read_csv(skiprows=data_start, header=None, names=range(n_cols))`。
9. 投影、rename、加内部 `周记` 列、drop `Serial`/`Bin`、drop 全 NaN 行、coerce numeric。
10. 返回清理后的 DataFrame。

**参数增强命名规则：**

```python
_PARAM_NAME_RULES = {
    "VTH": "seq", "BVDSS": "seq", "IDSS": "bias", "IGSS": "bias",
    "ISGS": "bias", "RDON": "bias", "VF": "unit", "VFSDS": "unit",
    "VFSD": "unit", "DVDS": "unit", "CONT": "unit",
    "ABSDEL": "seq", "DELAY": "unit", "LRDON": "bias",
}
_PARAM_UNITS = {
    "VTH": "V", "BVDSS": "V", "IDSS": "nA", "IGSS": "nA", "ISGS": "nA",
    "RDON": "mR", "VF": "V", "VFSDS": "V", "VFSD": "V", "DVDS": "mV",
    "CONT": "V", "ABSDEL": "", "DELAY": "", "LCR-RG": "R", "LRDON": "mR",
}
```

| 规则 | 公式 | 示例 |
|------|------|------|
| `seq` | `<base><N>(<unit>)` | `VTH1(V)`, `BVDSS2(V)` |
| `bias` | `<base><bias>(<unit>)` | `IDSS100(nA)`, `RDON40(mR)` |
| `unit` | `<base>(<unit>)` 或 `<base>2(<unit>)` | `DVDS(mV)`, `DVDS2(mV)` |

### `factories/jiequn/dc_cleaner.py` 等

- `JiequnDCCleaner(BaseCleaner)`：
  - `DC_PARAMS` 统一来自 `factories/jiequn/config.py` 的 `JIEQUN_DC_PARAMS`，适用于杰群格式1、格式2和第三产线：`LCR-RG`、跳过第一个 `VTH` 后的所有 `VTH`、`BVDSS`、全部 `IDSS`、`ISGS`、`RDON`、`VFSDS`、`ABSDEL`。
  - 文件 glob: `*DTA*.CSV`（不区分大小写），fallback 排除 `*_DVDS*`、`*_RG*`、`*PAT*`。
  - `unique_only=False`：保留**所有匹配列**（VTH1, VTH2, …）。
  - 输出：`DC_JQ` 前缀，最终列顺序由 `formatting.normalize_output_columns()` 统一。
- `JiequnDVDSCleaner(BaseCleaner)`：
  - `DVDS_PARAMS = ["DVDS"]`
  - 文件 glob: `*DVDS*.CSV`。
  - `unique_only=True`：仅首个 DVDS 列。
  - V→mV 换算。
- `JiequnRGCleaner(BaseCleaner)`：
  - `RG_PARAMS = ["LCR-RG"]`（自动 rename 为 `RG`）
  - 文件 glob: `*RG*.CSV`。
  - 不需要单位换算。

### `factories/jiequn/clean_unified.py` (杰群批次2)

模块级 `run(input_dir, output_dir)` 函数（非类）：
- `DC_PARAMS` 是杰群各 CSV 格式共用 DC 白名单：`LCR-RG`、跳过第一个 `VTH` 后的所有 `VTH`、`BVDSS`、全部 `IDSS`、`ISGS`、`RDON`、`VFSDS`、`ABSDEL`。
- DC 沿用杰群目标单位命名，并调用 `apply_conv()` 做 A→nA、R→mR 等换算；不参考日月新的源单位逻辑。
- `NUM_CONV` 用于格式2统一CSV的杰群单位换算。
- 对 `*DTA.CSV` 一次遍历，输出三个文件 `mixed_<label>_JQ2_<ts>.xlsx`。
- 输出前调用 `_normalize_unified_columns()`，统一 `批次` 列但保留源参数顺序。
- CLI: `python factories/jiequn/clean_unified.py <in> <out>`

### `factories/jiequn/pat_cleaner.py`

- 读取 `output/杰群-output/mixed_*_JQ_*.xlsx` 中**最新按 mtime** 的 DC/DVDS/RG 文件。
- ⚠️ **只识别 `_JQ` 前缀，不识别 `_JQ2`**（批次2 输出的 PAT 需另行支持）。
- 跳过 `NUM` / `lot_ID` / `周记` / `批次` 列。
- 对每个参数列调用 `compute_pat_stats()` 计算统计量。
- 输出 `output/杰群-output/PAT.xlsx`，sheet name `PAT`。

`compute_pat_stats(series)` 返回：
- `count`, `mean`, `std (ddof=1)`, `min`, `Q1`, `median (Q2)`, `Q3`, `max`
- `Sigma = (Q3 - Q1) / 1.35`
- `LCL = median - 6 * Sigma`, `UCL = median + 6 * Sigma`
- 预留字段：`LCL更新前/后`、`UCL更新前/后`、`是否更新`（占位，待人工更新 limit 工作流）

**PAT 输出列（PAT_HEADERS）：**

```
统计量, 总计数, 均值, 标准差, 最小值, 下四分位数, 中位数, 上四分位数, 最大值,
Sigma, LCL\n计算值, UCL\n计算值, LCL\n更新前, UCL\n更新前, LCL\n更新后, UCL\n更新后, 是否\n更新
```

### `factories/riyuexin/*.py`（ASE 历史遗留）

| 类 | 文件 | 关键方法 | 关键定位 |
|----|------|----------|----------|
| `DCDataCleaner` | `dc_cleaner.py` | `extract_dc_data`, `process_all_dc_files` | row 1 (参数名) + row 4 (测试条件) + row 5 (LRDON) + row 6 (单位) + locate "Test No." |
| `DVDSCleaner` | `dvds_cleaner.py` | `extract_dvds_data`, `process_all` | row 1 ("DVDS") + row 6 (单位) + row 18 ("Test No.") |
| `RGCleaner` | `rg_cleaner.py` | `extract_rg_data`, `run` | row 1 ("RG") + row 6 (R单位) + locate "Test No." |

**ASE DC 参数增强（业务逻辑）：**
- `IDSS` / `ISGS` 拉取 row 4 → `IDSS40`、`ISGS25` 等。
- `LRDON` 拉取 row 5 → `LRDON40`。
- 相邻 `ISGS` 列（相同测试条件 + 相邻列索引）：最左侧重命名为 `IGSS<cond>`。
  - **业务含义**：Jiequn 测试程序有时将 ISGS 列出两次（off-state + on-state at 同一 Vgs），按测试车间惯例 off-state 标为 IGSS。

**ASE RG 健全性过滤：** `0 < RG < 1000`（硬编码，可能误删某些器件家族的合理大值）。

### `shared/excel_utils.py`

`ExcelOptimizer` 类的关键方法：

| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `_pandas_supports_calamine()` | — | bool | pandas ≥ 2.2 |
| `_can_use_calamine()` | — | bool | pandas 版本 + calamine 可导入（缓存） |
| `read_excel_fast(path, **kwargs)` | 文件路径 | DataFrame | 默认 `engine='calamine'`，fallback `openpyxl` → `xlrd` → `pd.read_excel` |
| `write_excel_fast(df, path, **kwargs)` | DataFrame, 路径 | None | 默认 `engine='xlsxwriter'`，`index=False`；**>1,048,575 行自动按 sheet 拆分**（sheet name `<sheet>_1`, `<sheet>_2`...，截断 31 字符） |
| `extract_batch_id(filename, pattern=r'[A-Z0-9]{4}-[0-9]{4}')` | 文件名 | lot_id | regex 匹配，回退到 stem |
| `scan_excel_files(directory, pattern="*.xlsx")` | 目录 | 路径列表 | 排除 `~$*` 临时文件 |
| `generate_output_filename(prefix)` | 前缀 | 文件名 | `<prefix>_<YYYYMMDD_HHMMSS>.xlsx` |

**模块级便捷函数：**
- `read_excel_fast`、`write_excel_fast`、`extract_batch_id`、`scan_excel_files`、`generate_output_filename`
- `scan_csv_files(directory)`：扫描 `*.csv` 排除 `~$*`
- `scan_all_files(directory, extensions=None)`：默认 `['.xlsx', '.xls', '.csv']`
- `generate_lot_based_filename(lot_ids, data_type, ext=".xlsx")`：
  - 所有 lot_id 相同 → `<lot_id>_<data_type>_<timestamp><ext>`
  - 多 lot_id → `mixed_<data_type>_<timestamp><ext>`

**性能基础设施：**
- `performance_monitor(func)` 装饰器：记录每次调用耗时。
- `PerformanceStats` 类 + `get_performance_stats()` 全局：聚合吞吐量统计。

### `gui/`

**`main_window.py`：** 220px 左侧 `QListWidget` 厂列表 + 右侧 `QStackedWidget` 面板堆叠，`QSplitter` 支持拖动。

**`panels/base_panel.py`：** 通用 UI 外壳
- `CleanerWorker(QThread)`：后台线程运行 cleaner，信号 `progress(str)`、`finished(label, success)`、`error(str)`。
- `BasePanel(QWidget)`：构建处理类型按钮组 + 文件夹选择组 + 操作按钮 + 状态文本区。
  - 按钮通过 `QButtonGroup(exclusive=True)` 保持单选。
  - 第一行用于原始数据文件格式/清洗入口；可选第二行用于 PAT 等清洗后统计分析。
  - 抽象方法：`_get_cleaner_fn(data_type) -> Callable`，**子类必须实现**。
  - `_log(msg)`：时间戳 + 追加到状态区，自动滚动。
  - 样式：蓝色背景、加粗按钮、灰色边框。

**`panels/riyuexin_panel.py`：** 3 按钮（DC / DVDS / RG），默认路径 `~/Desktop`。
- DVDS 通过 monkey-patch 调整 `c.dvds_dir` / `c.output_dir`（因为 `DVDSCleaner` 内部用 `base_dir` 派生路径）。

**`panels/jiequn_panel.py`：** 第一行包含 DC / DC-3 / DVDS / RG / 统一CSV 清洗入口，第二行是 PAT 参数分析，第三行是 SYL&SBL 良率分析。
- 输入/输出默认路径与日月新一致，启动后都指向用户桌面。
- "统一CSV" 调 `clean_unified.run(inp, out)`。
- "PAT" 可显式多选一个或多个清洗 Excel；同一文件内的 `DC_Data_1/2/3` 等编号 Sheet 会逐个读取并按参数合并。
- 用户选择 DC/DVDS/RG/统一CSV/PAT 时不会覆盖手动选择的桌面或业务目录；历史样例路径仅作为代码中的备用常量保留。

---

## 🧠 关键算法 & 业务逻辑

### 1. DTA CSV 参数增强
- `parse_dta_csv` 不假定固定列顺序，锚定 `Item` 行（前 40 行内）。
- 对每个 base param，迭代 `item_names` 找匹配列；当前采用 `_item_matches_param()` 做精确/别名匹配，避免 `VF` 误吃 `VFSDS` 这类短名误匹配。
- `RDON` 与历史写法 `Rdson` 兼容，`LCR-RG` 统一输出为 `RG(R)`。
- `bias` 规则：从 `Bias 1 Value` 行读取，科学计数法规范化（`1.000E+02` → `"100"`）。`IDSS` 输出为 `IDSS100(nA)` 这类列名；当多个有效 `IDSS` 或 `RDON` 测试得到相同增强名时全部保留，并按源顺序在单位前加 `-1/-2`，例如 `RDON20-1(mR)`、`RDON20-2(mR)`。
- 杰群漏电命名：负偏置 `ISGS`（如 `-25`、`-20`、`-10`）保留为 `ISGS25/20/10`，正偏置 `ISGS` 改名为 `IGSS25/20/10`，输出顺序保持 `ISGS25, IGSS25, ISGS20, IGSS20`。

### 1.1 杰群输出格式化
- `factories/jiequn/formatting.py` 是杰群格式1的输出格式入口。
- `normalize_output_columns()` 会把内部 `周记` 列重命名为对外输出的 `批次`，并统一参数顺序。
- 如果后续新增参数，优先在 `PARAM_ORDER` 里补排序位置；不要在各 cleaner 里各自手写列顺序。
- 杰群格式2统一 CSV 使用 `preserve_source_order=True`，并在 `clean_unified._normalize_unified_columns()` 中只做 `周记` → `批次`，不重排参数列。

### 2. 子目录发现（杰群批次1）
- `Jiequn*Cleaner._get_*_subdir()` 使用 `Path(self.input_dir).rglob(sub)` 递归找类型目录（如 `DC`），返回首个含 CSV 的目录。fallback `<input_dir>/<sub>`。

### 3. 单位换算策略
**两个实现并存：**
- **`BaseCleaner._apply_unit_conversions`**（杰群批次1）：按 param 子串匹配列名，匹配则乘以 factor。
- **`clean_unified.apply_conv` / `unified_cleaner._apply_conv`**（批次2 + 备选）：硬编码 `dict[param: factor]`，子串匹配；格式2 DC/DVDS 都沿用杰群单位换算。

> ⚠️ 单位换算仍按列名子串识别参数，解析阶段已经避免 `VF/VFSDS` 误匹配。后续如新增名称重叠的参数，应同步检查 `UNIT_CONVERSIONS` 和 `clean_unified.NUM_CONV`；格式2 DC 还要同步检查 `DC_PARAMS` 白名单。

### 4. PAT 统计
- `Sigma = (Q3 - Q1) / 1.35`（IQR → σ 等价因子，针对正态数据）
- 控制限：±6·Sigma **围绕中位数**（非均值）—— 鲁棒 SPC 方法，中位数抗离群点。
- "更新前/后/是否更新" 字段是占位符，函数签名接受 `lsl`/`usl` 但未实际更新 limit，**待后续人工更新 limit 工作流**。

### 5. Auto-Engine 选择（ExcelOptimizer）
- calamine 使用条件：(a) pandas ≥ 2.2 + (b) `python_calamine` 可导入。
- 失败时按 openpyxl → xlrd → 裸 `pd.read_excel` 回退。
- 写入优先 xlsxwriter，回退 openpyxl。
- 据 `PERFORMANCE_OPTIMIZATION_REPORT.md`，DC 968→1916 rows/s（+98%）。

### 6. Lot-ID 提取
- **ASE**：`regex [A-Z0-9]{4}-[0-9]{4}`（如 `FA4Z-2484`、`FA53-4115`），fallback stem。
- **杰群**：`parts[1]` of `stem.split('_')`（依赖 4 段式文件名约定）。

### 7. 文件大小分流
- `write_excel_fast` 检测 `len(df) > 1,048,575`，按 1,048,575 行/块写到多个 sheet，sheet name 截断到 31 字符（Excel 硬限制）。

### 8. GUI 线程
- `CleanerWorker(QThread)` 后台运行 cleaner，**避免 GUI 长时间阻塞**。
- 进度/完成/错误信号 → slot 更新状态文本 + QMessageBox 通知。

### 9. ASE DC 相邻 ISGS 启发式
- 相邻两列都是 `ISGS<cond>` 且测试条件相同：左侧列重命名为 `IGSS<cond>`。
- **业务含义**：Jiequn 测试程序偶有 ISGS 重复（off-state + on-state at 同一 Vgs），车间惯例 off-state 标 IGSS。

### 10. 鲁棒性
- `scan_excel_files` / `scan_csv_files` 排除 `~$*.xlsx` 临时文件。
- `pd.to_numeric(errors='coerce')` 大量使用，非数值变 NaN 而非崩溃。
- `dropna(how='all', subset=val_cols)` 删空行。
- 所有 `process_all` 返回 `True/False` 并 `logging.exception(..., exc_info=True)`，异常不传到 GUI。

---

## 🛠️ 扩展点（迭代升级指南）

### 场景1：同一封装厂新增数据类型（如杰群"VTH2"或"BVDSS2"作为独立按钮）

1. **无需新解析器**（如果参数已在 `_PARAM_NAME_RULES`）。在 `factories/jiequn/` 下新建 cleaner 文件，调用 `parse_dta_csv` 配合需要的 `target_params` 和 `unique_only`。
2. 在 `gui/panels/jiequn_panel.py` 的 `data_types` 加新标签，`_get_cleaner_fn` 加分支。
3. 如需新单位处理，在 `factories/jiequn/config.py` 的 `UNIT_CONVERSIONS` 加规则。

### 场景2：新增批次格式（如杰群批次3 列布局不同）

1. 在 `factories/jiequn/` 下新建 cleaner，**继承 `BaseCleaner`**（或复用 `csv_parser.py` 的工具函数）。
2. 如 CSV 布局差异大，可扩展 `csv_parser.py` 的命名行锚点，或新建并行 parser 模块。
3. 在 `jiequn_panel.py` 加按钮。

### 场景3：新增封装厂（如"长电 JCET"）

1. `mkdir factories/jcet/`
2. 创建 `__init__.py`、`config.py`（结构参考 `factories/jiequn/config.py`：FACTORY_NAME、DATA_TYPES、FILE_EXT、INPUT_DIR、OUTPUT_DIR、UNIT_CONVERSIONS）。
3. 为每种数据类型建 cleaner。**建议继承 `BaseCleaner`**（仅杰群有示例，ASE 是历史遗留）。
4. 在 `gui/panels/jcet_panel.py` 子类化 `BasePanel`：
   - 设置 `factory_name`、`data_types`、`default_input`、`default_output`。
   - 实现 `_get_cleaner_fn(data_type)`。
5. 在 `gui/panels/__init__.py` 注册，并在 `gui/main_window.py` 的 `FACTORIES` 列表添加 `{"name": "长电 (JCET)", "panel": JcetPanel}`。

### 场景4：新增工具函数

- 加到 `shared/excel_utils.py`（或新建独立模块如 `shared/csv_utils.py`）。
- 建议同时加便捷函数和类方法。
- 通过 `from shared.excel_utils import my_helper` 导入。

### 场景5：替换/新增 Excel I/O 引擎

- 修改 `ExcelOptimizer._can_use_calamine()` 和 `read_excel_fast`/`write_excel_fast` 的 fallback 链。

### 场景6：新增 PAT 统计量

- 改 `pat_cleaner.py:compute_pat_stats()`，在 `PAT_HEADERS` 和返回 dict 中同步加列。

### ⚠️ 已知过时的扩展点

- `packaging/build_secure_pyz.py` 当前配置：
  - 入口点：`gui.ft_data_cleaner_gui:main`（**该文件已不存在**）
  - 打包列表：`['dc_processing', 'dvds_processing', 'rg_processing', 'gui']`（前 3 个旧模块已删除）
  - **需更新为**：`gui.main_window:main` 和 `['factories', 'shared', 'gui']`。

---

## ⚠️ Quirks & Gotchas（迭代前必读）

1. **两个并行的统一CSV实现**：`clean_unified.py`（GUI/CLI 实际使用）和 `unified_cleaner.py`（带 logger 的备选）。`_apply_conv` 逻辑被重复实现。
2. **PAT `build_pat` 只认 `mixed_*_JQ_*.xlsx`**，跳过 `mixed_*_JQ2_*.xlsx`（批次2）。批次2 输出的 PAT 分析需改前缀或加新函数。
3. **ASE DVDS panel 的 monkey-patch**：`DVDSCleaner` 内部用 `base_dir` 派生 `dvds_dir` / `output_dir`，panel 在构造后修改这两个属性。
4. **杰群输出列名约定**：内部解析仍会先生成 `周记`，最终输出通过 `formatting.normalize_output_columns()` 改为 `批次`。PAT 已跳过 `批次`，如果新增统计入口也要同步跳过。
5. **同函数不同入参**：`generate_lot_based_filename` 在 Jiequn 调 `zhouji_list`，ASE 调 `lot_ids`——参数名不同，**只关心值**。
6. **两处 log 文件位置**：`dc_cleaner.log` 等既在项目根也在 `gui/` 下。ASE cleaner 用 `logging.FileHandler('dc_cleaner.log', mode='w')`（相对 CWD），从 `gui/` 跑就在 `gui/`，从根跑就在根。
7. **xlsxwriter 硬依赖**：`requirements.txt` 锁定 `xlsxwriter>=3.0.0`，但 fallback 到 openpyxl 仍可工作。
8. **PAT 用 glob + mtime 取最新**：仅分析**最新**的 `mixed_*_JQ_*.xlsx`，同时存在两个批次时只分析新的。
9. **ASE RG 健全性过滤**：`0 < RG < 1000` 硬编码，对某些器件家族可能误删。
10. **`process_all_dc_files` 返回类型不对称**：返回 `bool` 但 `None` 也视为失败；`RGCleaner.run()` 可返回 `None` 或 path。
11. **Jiequn panel 不自动检测批次**：用户需手动指向 `data/杰群` 或 `data/杰群2/RAW`。
12. **`gui/README.md` 引用了不存在的 `ft_data_cleaner_gui.py`**：实际模块是 `gui/main_window.py`。
13. **`packaging/build_secure_pyz.py` 配置陈旧**：见上方"已知过时的扩展点"。
14. **DVDS 单位读取**：从 row 6 读单位。如果文件是 `V` 而非 `mV`，列名是 `DVDS(V)` 但值**不自动换算**——Jiequn 靠 `BaseCleaner._apply_unit_conversions` 补 V→mV；ASE 直接信任源文件单位。
15. **Excel 列数从 `Serial` 行推断**：避免首数据行字段少时误判列数。
16. **性能优化报告**：DC 968→1916 rows/s（+98%），DVDS 8960 rows/s，RG 8494 rows/s（calamine 引擎切换后）。
17. **大文件写入依赖 xlsxwriter**：`xlsxwriter` 缺失时会回退 `openpyxl`，可成功但 DC 90万行级写入会明显变慢。开发/部署前建议确认 `python -m pip show XlsxWriter`。
18. **迭代约定**：功能性调整完成并验证后，需要提交并推送到 GitHub 远端仓库；不要把 `output/`、`__pycache__/`、失败的临时 Excel 文件一并提交。

---

## 📚 核心类/函数索引

| 模块 | 类 / 函数 | 角色 |
|------|-----------|------|
| `factories/base/base_cleaner.py` | `BaseCleaner` (ABC) | 单位换算 + 抽象 `process_all` |
| `factories/jiequn/csv_parser.py` | `parse_dta_csv` | DTA CSV → 增强 DataFrame（**核心**） |
| `factories/jiequn/csv_parser.py` | `extract_zhouji` | 文件名 → 周记 |
| `factories/jiequn/csv_parser.py` | `_item_matches_param` | Item 精确/别名匹配，避免短名误匹配 |
| `factories/jiequn/csv_parser.py` | `_build_param_name` | 构建增强参数名（seq/bias/unit） |
| `factories/jiequn/formatting.py` | `normalize_output_columns`, `sort_param_columns` | 杰群输出列名和参数排序统一入口 |
| `factories/jiequn/dc_cleaner.py` | `JiequnDCCleaner` | DC cleaner (批次1) |
| `factories/jiequn/dvds_cleaner.py` | `JiequnDVDSCleaner` | DVDS cleaner (批次1) |
| `factories/jiequn/rg_cleaner.py` | `JiequnRGCleaner` | RG cleaner (批次1) |
| `factories/jiequn/clean_unified.py` | `run(input, output)` | 批次2 统一CSV runner（GUI 使用） |
| `factories/jiequn/unified_cleaner.py` | `process_unified` | 备选批次2 runner（历史/参考） |
| `factories/jiequn/pat_cleaner.py` | `build_pat`, `save_pat`, `compute_pat_stats` | PAT 统计聚合 |
| `factories/riyuexin/dc_cleaner.py` | `DCDataCleaner` | ASE DC cleaner（未继承 BaseCleaner） |
| `factories/riyuexin/dvds_cleaner.py` | `DVDSCleaner` | ASE DVDS cleaner |
| `factories/riyuexin/rg_cleaner.py` | `RGCleaner` | ASE RG cleaner |
| `shared/excel_utils.py` | `ExcelOptimizer` | calamine/xlsxwriter 引擎选择 |
| `shared/excel_utils.py` | `read_excel_fast` | 快速 Excel 读取 |
| `shared/excel_utils.py` | `write_excel_fast` | 快速 Excel 写入（>1M 行自动分 sheet） |
| `shared/excel_utils.py` | `extract_batch_id` | lot_ID 提取 |
| `shared/excel_utils.py` | `scan_excel_files` / `scan_csv_files` | 文件扫描 |
| `shared/excel_utils.py` | `generate_lot_based_filename` | 智能文件名生成 |
| `shared/excel_utils.py` | `performance_monitor` / `PerformanceStats` | 性能监控 |
| `gui/main_window.py` | `MainWindow`, `FACTORIES` | 侧边栏 + 堆叠切换器 |
| `gui/panels/base_panel.py` | `BasePanel`, `CleanerWorker` | UI 外壳 + QThread |
| `gui/panels/riyuexin_panel.py` | `RiyuexinPanel` | 3 按钮（DC/DVDS/RG） |
| `gui/panels/jiequn_panel.py` | `JiequnPanel` | 4 个清洗入口 + PAT 清洗后统计 |
| `packaging/build_secure_pyz.py` | `create_secure_archive` | ⚠️ 配置陈旧，需更新 |

---

**开发者**: cc  
**最后更新**: 2026-06-03
