# 电基 FT-ALL 清洗说明

## 1. 适用范围

本流程自动识别并处理四种已验证的电基 FT-ALL 文件：

- PowerTECH：使用 `.xls` 扩展名，实际是 GB18030 编码、Tab 分隔的文本报告；
- PowerTECH XLSX：使用原生 `.xlsx` 工作簿，数据位于唯一的 `Datalog` 工作表；
- STS8203：使用 `.csv` 扩展名，文件前部是测试元数据，后部是 UTF-8 CSV 记录；
- DP1205 TF：使用 GB18030 `.csv`，测试类型为 `SW+Trr`，严格输出 47 个带单位参数。

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
- dj6 真实数据另外验证了三种精确命名边界：制造批次和周记之间可以没有空格；
  制造批次片号后可带 `-A-A`；测试时间前可出现 `DC M08` 标签。程序只接受这些
  已验证形式，不把规则扩展到任意后缀或设备标签。
- 两种批次标识都统一转为大写并写入输出列 `批次`。
- 源参数单位已经是目标单位（mV、R、V、nA、mR）；只有未来源单位明确变化时才按配置换算。
- 数值 `9999/-9999` 是 PowerTECH 溢出或未测试占位，不作为真实参数值。

### 2.2 STS8203 CSV

- 第一行签名为 `STS8203 Station...`，头部包含 `Date`、`Program`、`Lot Id`
  和 `Beginning Time`。
- 文件名格式为
  `<产品>_Lot Id_<制造批次> <批次> [分段号]_ALL_<日期 时_分_秒>.csv`。
- 制造批次已验证两种主体长度：`M/R + 8位数字` 和 `M/R + 9位数字`，后接
  `-三位片号`；另兼容真实出现的 `-a` 片段后缀。批次后的可选分段号目前只接受
  已验证值 `2`，且必须与文件内 `Lot Id` 同时出现并一致。
- 文件名测试时间必须严格等于 `Beginning Time`；`Date` 是设备记录的测试结束日，
  必须等于 `Ending Time` 的日期，因此允许一批测试跨越午夜或跨多日。
- 数据区以 `SITE_NUM` 表头开始，后接 `Unit`、`LimitL`、`LimitU`，失效记录
  可能提前结束，所以数据行字段数不固定。
- 已验证产品 `NCEAP40T20AGU(M)-7E00` 使用末尾 `QC_*` 终测参数组；前部同名
  `DC_*` 参数不作为标准 FT 输出。
- STS8203 文件未提供可用于动态命名的 Bias 元数据，因此只对已逐项确认的产品启用
  显式映射；未知产品或列位置、单位变化会停止清洗。

### 2.3 PowerTECH 原生 XLSX（dj7）

- 当前只支持已验证产品 `NCE40ED120VT(LA)`，第一格签名为
  `PowerTECH Test System`，工作表必须唯一且名称为 `Datalog`。
- 第 1～18 行是设备元数据、Item、Bias、规格及单位；第 19 行起是测试记录。
- 已验证 34、35、38、39 项四种布局。35 项比 34 项多一个末尾 `DELAY`；
  38/39 项在 VF 后分别含 3/4 个 `SAME` 分档占位项，业务测试身份保持一致。
- 文件名、`DataFileName`、`Lot`、`TestFileName`、Station 和 Tester Serial 会交叉校验。
  当前支持真实出现的空标签、`ALL/M05/DC/rt`、批次后单下划线和机台号后 `ALL`。
  标签、机台号、尾部 `ALL` 与 34/35/38/39 项布局按真实组合登记，不做交叉放宽。
- 测量值 `over` 及 `9999/-9999` 作为无效占位写为空值；未知非数值标记会停止。

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

PowerTECH XLSX 使用独立的 21 参数契约：

```text
DVCE(mV), Rg(R), VTH1(V), VTH2(V),
BVDSS1(V), BVDSS2(V), BVDSS3(V), ICES1000(nA),
IGSS30-1(nA), ISGS30-1(nA),
VDSON40A-11V(V), VDSON40A-15V(V), VDSON160A-15V(V), VF40A(V),
ICES1200-1(nA), ICES1250(nA), ICES1200-2(nA),
IGSS30-2(nA), ISGS30-2(nA), DELTA BV, DELTA VTH
```

设备筛选或占位项 `CONT_TR/VF_EX/SAME/DVF_EX/TSD/CONT_LCR/CISS_EX/CONT/`
首个占位 VTH/DELAY 不进入输出。四种布局均按注册表中的明确 Item 身份恢复上述顺序。

### PowerTECH Item 映射

| 输出 | 标准 34 项源 Item | 紧凑 32 项源 Item | 规则 |
| --- | ---: | ---: | --- |
| DVDS(mV) | 4 `DVDS_EX` | 4 `DVDS_EX` | 作为保留记录的入口参数 |
| Rg(R) | 12 `LCR-RG` | 12 `LCR-RG` | 名称按参考模板写为 `Rg(R)` |
| VTH1/2/3 | 16 / 19 / 32 | 16 / 17 / 30 | Item 14 是程序占位 VTH，跳过 |
| BVDSS1/2 | 20 / 21 | 18 / 19 | 按源顺序编号 |
| IDSS | 22，以及 29 或 31 | 20 / 29 | 从 `VDS=` 动态生成条件名 |
| IGSS/ISGS | 23–26 / 30，以及 29 或 31 | 21–24 / 27–28 | 正 VGS 为 IGSS，负 VGS 为 ISGS |
| RDON | 27 | 25 | 从 `Bias2` 的 `VGS=` 生成条件名 |
| VFSD | 28 | 26 | 保留源 V 单位 |
| DELTA BV | 33 | 31 | 头部引用对应的两项 BVDSS |
| DELTA VTH | 34 | 32 | 头部引用对应的 VTH1/2 |

紧凑 32 项程序是标准程序删除两个 `SAME` 占位项后的明确布局，并没有删除 19 个业务
输出参数。程序按布局注册表恢复同一 RAW 列顺序；不能匹配上述任一布局时停止清洗。

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
- 必需 Item 编号、参数基名和数量符合当前已验证的标准 34 项或紧凑 32 项程序；
- 标准 34 项的 Item 29–31 仅接受两种真实样本已验证布局：`IDSS/IGSS/IGSS` 或
  `IGSS/IGSS/IDSS`；紧凑 32 项的 Item 27–29 只接受已验证的
  `IGSS/IGSS/IDSS`；程序按参数名与 VGS 正负条件恢复统一输出顺序；
- 同一次运行只包含一个产品；
- 多文件生成的输出列完全一致。

PowerTECH XLSX 还会严格校验唯一 `Datalog` 工作表、产品白名单、四种完整 Item
序列、目标 Item 单位和 Bias 条件，以及文件名与工作簿内 DataFile/Lot/程序/机台身份。

STS8203 还会严格校验文件名与 `Lot Id`、`Program`、`Beginning Time` 一致，
并校验 `Date` 与 `Ending Time` 的日期、63 列表头、目标字段位置和单位。

### 模块化格式识别

`source_registry.py` 是电基格式注册表。清洗器只调用统一入口，注册表先按扩展名和
文件内容签名识别格式，再分发给独立模块：

- `PowerTECH Test System` → `powertech_parser.py`；
- 原生 XLSX `PowerTECH Test System` Datalog → `powertech_xlsx_parser.py`；
- `STS8203 Station...` → `sts8203_parser.py`。
- `设备名称,DP1205` → `tf_csv_parser.py`。

三种解析器共享 `models.py` 中的身份和解析结果契约，但各自维护文件名、元数据、
表头、单位和参数映射。以后新增格式时新增解析模块并注册，不在 GUI 或现有解析器中
堆叠跨格式条件；未知签名、混合格式和识别不唯一仍会停止。

任一校验失败都会停止并给出文件名和原因，不会猜测列位置后继续清洗。

## 6. 当前限制

- 当前严格支持伪 `.xls` 的两种 34 项和一种紧凑 32 项 PowerTECH 布局、原生
  `.xlsx` 的 `NCE40ED120VT(LA)` 34/35/38/39 项布局，以及
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

2026-08-03 真实验证：`dj5/DC` 47 个 STS8203 文件全部通过身份、时间、63 列布局和
单位校验；802,377 条源记录保留 793,010 条，剔除 9,367 条 DVDS 前失效记录，输出
13 个批次、21 列。完整 Excel、散点数据、规格和清单均生成在
`NCEAP40T20AGU(M)_001` 流水目录内。

2026-08-05 真实验证：`dj6/DC` 92 个 PowerTECH 文件均为 GB18030 Tab 文本，其中
89 个为标准 34 项、3 个为紧凑 32 项；465,562 条源记录按有效 DVDS 规则保留
460,595 条，15 个批次统一输出 21 列。文件名覆盖 2 个 `DC M08`、1 个无空格、
2 个 `-A-A` 样本；另有 2 个既有片号未刷新告警，均保持制造主批与周记严格一致。

2026-08-13 真实验证：`dj7/NCE40ED120VT Old PR FT data/DC` 14 个 PowerTECH
原生 XLSX 文件全部通过签名、身份、四种布局、单位和 Bias 校验；103,689 条源记录
按有效 `DVCE(mV)` 保留 103,282 条，覆盖 7 个批次，统一输出 23 列
（`NUM + 批次 + 21参数`），同时生成 103,282 条散点记录和 294 条来源规格。

2026-08-13 真实验证：`dj7/NCE40ED120VT Old PR FT data/TF` 6 个 DP1205
`SW+Trr` 文件共 23,594 条源记录，按有效 `Udc(V)` 保留 22,581 条，覆盖
`FA5Y-9298/9413/9718` 三个批次；47 个参数逐项对账通过，并保留两套真实
`Eoff2(mJ)` 限值（11.5–17.5、13–20）。

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
