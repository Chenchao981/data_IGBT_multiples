# 电基 FT-ALL 清洗说明

## 1. 适用范围

本流程自动识别并处理两种已验证的电基 FT-ALL 文件：

- PowerTECH：使用 `.xls` 扩展名，实际是 GB18030 编码、Tab 分隔的文本报告；
- STS8203：使用 `.csv` 扩展名，文件前部是测试元数据，后部是 UTF-8 CSV 记录。

GUI 入口：`电基 (Dianji) -> FT-ALL`

命令行入口：

```powershell
python -m factories.dianji.dc_cleaner <输入目录> <输出目录>
```

## 2. 已确认的源数据事实

### 2.1 PowerTECH

- 第一行签名为 `PowerTECH Test System`。
- 头部包含 `Item Name`、`Bias1`、`Bias2`、`Bias3` 和 `Serial#` 行。
- `Serial#` 下一行开始为测试记录；不同 Bin 会在失效项后提前结束，所以每行字段数不固定。
- 文件名制造批次支持 `M`/`R` 前缀；批次标识支持旧式 `C203133.03` 周记和
  已验证的新式 `FA65-5405` 批次。旧式周记的小数点兼容 `.`、`,`、`。` 并统一
  为 `.`。测试时间前可带 `ALL`/`DC` 标签，也兼容批次标识后直接连接 12 位时间。
- 两种批次标识都统一转为大写并写入输出列 `批次`。
- 源参数单位已经是目标单位（mV、R、V、nA、mR）；只有未来源单位明确变化时才按配置换算。
- 数值 `9999/-9999` 是 PowerTECH 溢出或未测试占位，不作为真实参数值。

### 2.2 STS8203 CSV

- 第一行签名为 `STS8203 Station...`，头部包含 `Date`、`Program`、`Lot Id`
  和 `Beginning Time`。
- 文件名格式为
  `<产品>_Lot Id_<制造批次> <批次>_ALL_<日期 时_分_秒>.csv`。
- 数据区以 `SITE_NUM` 表头开始，后接 `Unit`、`LimitL`、`LimitU`，失效记录
  可能提前结束，所以数据行字段数不固定。
- 已验证产品 `NCEAP40T20AGU(M)-7E00` 使用末尾 `QC_*` 终测参数组；前部同名
  `DC_*` 参数不作为标准 FT 输出。
- STS8203 文件未提供可用于动态命名的 Bias 元数据，因此只对已逐项确认的产品启用
  显式映射；未知产品或列位置、单位变化会停止清洗。

## 3. 输出契约

输出目录按产品主体和三位流水号创建，例如完整产品
`NCEAP016N85LL(M)-3E00` 第一次清洗进入 `NCEAP016N85LL(M)_001`，重复清洗进入
`NCEAP016N85LL(M)_002`。目录名只去掉末尾封装代码 `-3E00`，保留 `(M)`。
目录内输出文件名仍为 `<完整产品> DJ PAT.xlsx`，工作表固定为 `RAW`，不会覆盖历史结果。

输出列顺序：

```text
NUM, 批次, DVDS(mV), Rg(R), VTH1(V), VTH2(V),
BVDSS1(V), BVDSS2(V), IDSS<偏置>(nA),
IGSS25(nA), ISGS25(nA), IGSS20(nA), ISGS20(nA),
RDON<栅压>(mR), VFSD(V), ISGS10(nA), IGSS10(nA),
IDSS<第二偏置>(nA), VTH3(V), DELTA BV, DELTA VTH
```

PowerTECH 的偏置值从每个文件自己的 `Bias` 头部读取。例如不同产品可生成
`IDSS40(nA)/IDSS35(nA)` 或 `IDSS100(nA)/IDSS90(nA)`，程序不硬编码产品电压。
STS8203 当前已验证产品使用明确的 `IDSS40(nA)/IDSS35(nA)` 映射。

### PowerTECH Item 映射

| 输出 | 源 Item | 规则 |
| --- | ---: | --- |
| DVDS(mV) | 4 `DVDS_EX` | 作为保留记录的入口参数 |
| Rg(R) | 12 `LCR-RG` | 名称按参考模板写为 `Rg(R)` |
| VTH1/2/3 | 16 / 19 / 32 | Item 14 是程序占位 VTH，跳过 |
| BVDSS1/2 | 20 / 21 | 按源顺序编号 |
| IDSS | 22，以及 29 或 31 | 从 `VDS=` 动态生成条件名 |
| IGSS/ISGS | 23–26 / 30，以及 29 或 31 | 正 VGS 为 IGSS，负 VGS 为 ISGS |
| RDON | 27 | 从 `Bias2` 的 `VGS=` 生成条件名 |
| VFSD | 28 | 保留源 V 单位 |
| DELTA BV | 33 | 头部引用 BVDSS Item 20/21 |
| DELTA VTH | 34 | 头部引用 VTH Item 16/19 |

### STS8203 字段映射

| 输出 | 源字段 |
| --- | --- |
| DVDS(mV) / Rg(R) | `DVDS` / `Zmu_RG2` |
| VTH1/2/3 | `QC_VTH` / `QC_VTH2` / `QC_VTH1` |
| BVDSS1/2 | `QC_BVDSS` / `QC_BVDSS1` |
| IDSS40/35 | `QC_IDSS` / `QC_IDSS1` |
| IGSS25/ISGS25 | `QC_IGSSF2` / `QC_IGSSR2` |
| IGSS20/ISGS20 | `QC_IGSSF` / `QC_IGSSR` |
| RDON10 / VFSD | `RDSON2` / `QC_VFSD` |
| IGSS10/ISGS10 | `QC_IGSSF1` / `QC_IGSSR1` |
| DELTA BV / DELTA VTH | `QC_DELTA_BVDSS` / `QC_DELTA_VTH` |

## 4. 行保留与空值规则

参考工作簿保留所有已经测到有效 `DVDS(mV)` 的记录。若记录在后续测试项失效并提前
结束，则该行继续保留，尚未测试的后续参数写为空值。尚未测到 DVDS 的早期失效记录
不进入输出。

程序不会按规格上下限删除真实测量值；仅将空字段、非数值和 `9999/-9999` 转为空值。
这样既保留失效分布，也避免溢出占位污染后续 PAT 统计。

## 5. 安全校验

清洗前会校验：

- `.xls/.csv` 内容签名确实属于已支持的 PowerTECH 或 STS8203 格式；
- 文件名制造主批/批次标识与头部 `Lot:` 元数据一致；若仅片号后缀（如 `-004`
  对 `-003`）未刷新，则输出 WARNING 并按文件名继续，制造主批或批次标识不同仍会停止；
- 必需 Item 编号、参数基名和数量符合当前已验证测试程序；
- Item 29–31 仅接受两种真实样本已验证布局：`IDSS/IGSS/IGSS` 或
  `IGSS/IGSS/IDSS`；程序按参数名与 VGS 正负条件恢复统一输出顺序；
- 同一次运行只包含一个产品；
- 多文件生成的输出列完全一致。

STS8203 还会严格校验文件名与 `Lot Id`、`Program`、`Date/Beginning Time`
元数据一致，并校验 63 列表头、目标字段位置和单位。

任一校验失败都会停止并给出文件名和原因，不会猜测列位置后继续清洗。

## 6. 当前限制

- 当前严格支持已验证的两种 34 项 PowerTECH FT-ALL 布局，以及
  `NCEAP40T20AGU(M)-7E00` 的 STS8203 63 列布局。
- 测试程序若调整 Item 编号或新增/删除目标参数，需要先用真实新样例更新配置和测试。
- 输出遵循用户提供的 `RAW` 数据模板；模板中遗留的图表对象不属于清洗契约，不复制。

## 7. FT 参数散点图

FT-ALL 清洗成功后，GUI 会启用“FT散点图”。清洗器直接利用内存中的 19 个参数和
PowerTECH `Min Limit`、`Max Limit`、`Bias1-3`、单位行生成散点数据包，不重复读取
原始 `.xls/.csv` 文件。每个源文件使用独立 `Source_ID`，因此不同测试程序规格会画在各自
记录区间内；颜色和图例按 `批次` 区分。

数据包与清洗 Excel 位于同一个 `<产品主体>_NNN` 流水目录，文件名前缀为
`<清洗文件名>_ft_scatter_`；重复运行时创建新的流水目录，不覆盖历史结果。
规格值执行与测量值相同的单位换算，并保留 PowerTECH 原始限值文本和 Bias 条件。

2026-07-22 真实验证：22 个源文件合并为 118,005 行，清洗 Excel 与散点数据行数一致；
19 个参数、4 个批次、22 个来源规格全部关联成功。

2026-07-31 真实验证：1 个 STS8203 文件含 34,608 条源记录，按有效 DVDS 规则保留
33,862 条，输出 21 列（`NUM + 批次 + 19参数`）；首行参数值、批次、规格和散点数据包
均与源 CSV 对齐。

## 8. PAT 参数分析

GUI 入口：`电基 (Dianji) -> PAT`。先完成 FT-ALL 清洗，再选择一个或多个含
`RAW` 工作表的清洗结果 Excel。若大文件拆成 `RAW_1/RAW_2/...`，程序会逐个
Sheet 读取，并在计算前合并同名参数的全部有效值。

电基 PAT 与日月新使用同一个统计函数和输出格式：

```text
Sigma = (Q3 - Q1) / 1.35
LCL = 中位数 - 6 × Sigma
UCL = 中位数 + 6 × Sigma
```

`NUM`、`批次` 等身份列不参与统计。输出位于顺序目录 `PAT_001/PAT_001.xlsx`，
重复生成会使用 `PAT_002`、`PAT_003`，不会覆盖历史报表。
