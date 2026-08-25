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

GUI 入口是 `gui.main_window:main`，版本为 2.14.0。

## 界面结构

- 左侧：日月新、杰群、电基、集佳四个封装厂。
- 右侧：当前封装厂的 FT 数据清洗、PAT 参数分析、封装良率分析。
- 输入/输出默认指向用户桌面，可手工输入或浏览选择。
- 长任务通过 `CleanerWorker(QThread)` 执行，日志实时显示，运行期间按钮禁用。

## FT 参数散点图

- 支持日月新 `DC`、杰群 `DC-AI`、电基 `FT-ALL`。
- 先完成对应清洗；成功生成散点数据包后才启用“FT 散点图”按钮。
- 操作按钮按业务顺序排列：左侧“开始清洗”，右侧“FT 散点图”。
- 清洗器利用内存中的清洗数据生成散点图数据包，不重复读取原始文件。
- 页面一次展示全部参数图；参数名称位于坐标轴上方，Y 轴左侧不再重复参数名。
- 颜色按 `lot_ID` 批次区分，批次图例显示在图形右侧。
- 页面采用亮色背景，散点、参数标题、坐标数字、批次图例及上下限标签均已放大。
- 规格内重复值按批次分层压缩，每个有效批次保留代表点，全部超限点保留，以缩短页面打开时间。
- 规格不同的来源文件按各自区间画线；杰群和电基的规格值会执行与清洗结果相同的单位换算。
- 杰群 P 型程序的反向 Min/Max 会保留原始文本，并按数值上下界用于 LSL/USL 与超限判断。
- Streamlit 使用本机 `8502` 端口。发布包旁必须保留 `frontend/ft_scatter_app.py`。

## 杰群 DC-AI

杰群面板只保留 `DC-AI` 一个清洗入口。格式识别和分目录的 DVDS/RG 配对均由后端完成。

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

## 开发验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q gui factories shared frontend packaging tests
python packaging/build_secure_pyz.py
```

发布前还需检查 PYZ 包内没有原始 CSV、Excel 输出、日志、缓存、测试或内部文档。
