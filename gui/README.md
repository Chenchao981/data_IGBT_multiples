# FT 数据清洗工具 GUI

## 启动

在项目根目录运行：

```powershell
python gui/main_window.py
```

发布版运行：

```powershell
python packaging/release/ft_data_cleaner.pyz
```

GUI 入口是 `gui.main_window:main`，版本为 2.22.2。

## 界面结构

- 左侧：日月新、杰群、电基、集佳四个封装厂。
- 右侧：当前封装厂的 FT 数据清洗、PAT 参数分析、封装良率分析。
- 输入/输出默认指向用户桌面，可手工输入或浏览选择。
- 长任务通过 `CleanerWorker(QThread)` 执行，日志实时显示，运行期间按钮禁用。

## FT 参数散点图与箱体图

- 支持日月新 `DC`、杰群 `DC-AI`、电基 `FT-ALL`。
- 先完成对应清洗；成功生成图表数据包后才启用“散点图 / 箱体图”按钮。
- 清洗器利用内存中的清洗数据生成可移动数据包，不改变原始数据、Bin、良率或 PAT。
- 页面首次打开只显示筛选；点击“绘制图形”后逐参数生成白底静态 PNG，并可单张下载。
- FT 分组契约固定为：完整 `lot_ID` 是批次及箱体分组，`NUM` 只维持批次内样本顺序，`Source_ID` 只做来源追溯和规格绑定；不生成 `Wafer_ID`。
- 散点图全量绘制所有有限有效值，不抽样、不把空值或无穷值补成零；箱体图每批一个箱体，使用全部有限值及 1.5 IQR 箱须，不叠加离群散点。
- 散点图和箱体图分别提供“完整纵轴范围”开关；默认按各批次主体范围聚焦，只改变视窗，不改变数据与统计。
- 参数默认不选，支持“全选”和自由多选。每个参数图上方直接显示单行 Y 轴操作栏：最小值、最大值、右侧“应用自定义并绘制”和“恢复自动范围”；无自定义复选框，输入后应用即生效。两类图独立设置，下载 PNG 使用相同范围。
- 颜色按 `lot_ID` 批次区分；不同来源规格继续按 `Source_ID` 适用区间显示。
- 规格不同的来源文件按各自区间画线；杰群和电基的规格值会执行与清洗结果相同的单位换算。
- 杰群 P 型程序的反向 Min/Max 会保留原始文本，并按数值上下界用于 LSL/USL 与超限判断。
- Streamlit 使用本机 `8502` 端口。发布包旁必须保留 `frontend/ft_scatter_app.py`。

## 杰群 DC-AI

杰群面板保留 `DC-AI`、`DVDS`、`RG` 三个清洗入口。三个手工 DC 格式按钮已隐藏；
格式识别和产品根目录中的 DVDS/RG 配对由后端完成，纯 DVDS/RG 目录使用专用按钮。

`DC-AI` 只读取目录结构和 DTA CSV 的 Item 头部：

| 类型 | 识别特征 | 清洗器 |
| --- | --- | --- |
| DC-1 | 存在名称严格等于 `DC` 的分类型目录 | 依次调用既有 DC、可配对 DVDS、可配对 RG 清洗器 |
| DC-统一CSV | Item 同时有 DC、DVDS、LCR-RG | `clean_unified.run` |
| DC-3 | 无 DC 子目录，Item 有 DC 且无 DVDS | `JiequnDCCleaner` |

选择的目录必须只有一种格式。分目录格式建议选择同时包含 `DC/DVDS/RG` 的产品根目录，
也可直接选择 `DC` 目录；程序只处理实际发现的附加目录。多个可配对目录、混合格式、
缺 Item、无 DC 参数或不完整统一CSV会在清洗前报错。识别和分发逻辑位于
`factories/jiequn/dc_auto.py`，GUI 不包含业务规则。

## 其他操作

- 集佳 FT-ALL：选择包含 `NCE15TD120BT_<C批次>_<测试批次>_DC_<时间>.csv` 的目录；
  程序按 GB18030 读取 STS8203 数据，严格校验 123 列字段和单位，输出日月新风格
  `NUM + lot_ID + 117参数` 的 `DC_Data` 工作表，不输出 `PASSFG/SOFT_BIN`，也不删除 FAIL 行。
- 电基 FT-ALL：选择包含 PowerTECH 伪 `.xls`、原生 `.xlsx`、STS8203 `.csv` 或 DP1205 TF `.csv` 文件的目录；
  程序通过格式注册表自动识别并调用对应解析模块，创建 `<产品主体>_NNN` 流水目录，并把产品级 `RAW`
  工作簿和散点数据包一起放入该目录。PowerTECH 已兼容 dj6 实际出现的紧凑 32 项程序、
  `-A-A` 制造批次后缀、制造批次/周记紧连及 `DC M08` 测试标签。
  原生 XLSX 当前严格支持 `NCE40ED120VT(LA)` 的 dj7 四种已验证布局。
- 杰群 PAT：预览并选择原始 DTA CSV 目录，点击“计算 PAT”；程序逐文件提取参数、
  低内存汇总后直接输出 PAT，不需要先生成清洗明细 Excel。
- 日月新/电基 PAT：仍选择各自已验证的清洗结果 Excel；日月新读取
  `DC_Data_1/2/3`，电基读取 `RAW/RAW_1/RAW_2`。
- SYL&SBL：选择一个工厂良率 `.xls/.xlsx` 文件，输出到单独目录。
- 杰群 DC-AI：输入为目录，输出为目录；自动处理实际存在的 DC/DVDS/RG。
- 杰群 DVDS/RG：输入为对应专用目录或包含该子目录的单产品目录，输出为目录。
- 若 DVDS/RG 输入已经是包含唯一合法结果工作簿的输出目录，程序返回现成结果并跳过重复清洗。

## 开发验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q gui factories shared frontend packaging tests
python packaging/build_secure_pyz.py
```

发布前还需检查 PYZ 包内没有原始 CSV、Excel 输出、日志、缓存、测试或内部文档。
