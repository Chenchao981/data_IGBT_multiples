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

GUI 入口是 `gui.main_window:main`，版本为 2.6.1。

## 界面结构

- 左侧：日月新、杰群、电基三个封装厂。
- 右侧：当前封装厂的 FT 数据清洗、PAT 参数分析、封装良率分析。
- 输入/输出默认指向用户桌面，可手工输入或浏览选择。
- 长任务通过 `CleanerWorker(QThread)` 执行，日志实时显示，运行期间按钮禁用。

## 杰群 DC-AI

杰群面板默认选择 `DC-AI`，另保留 `DC-1`、`DC-统一CSV`、`DC-3` 三个手工
DC 入口以及 DVDS、RG 入口。

`DC-AI` 只读取目录结构和 DTA CSV 的 Item 头部：

| 类型 | 识别特征 | 清洗器 |
| --- | --- | --- |
| DC-1 | 存在名称严格等于 `DC` 的分类型目录 | `JiequnDCCleaner` |
| DC-统一CSV | Item 同时有 DC、DVDS、LCR-RG | `clean_unified.run` |
| DC-3 | 无 DC 子目录，Item 有 DC 且无 DVDS | `JiequnDCCleaner` |

选择的目录必须只有一种格式。混合目录、缺 Item、无 DC 参数或不完整统一CSV会在
清洗前报错。识别和分发逻辑位于 `factories/jiequn/dc_auto.py`，GUI 不包含业务规则。

## 其他操作

- 电基 FT-ALL：选择包含 PowerTECH 伪 `.xls` 文本文件的目录，输出一个产品级 `RAW` 工作簿。
- PAT：选择一个或多个清洗结果 `.xls/.xlsx`，支持读取 `DC_Data_1/2/3` 等编号 Sheet。
- SYL&SBL：选择一个工厂良率 `.xls/.xlsx` 文件，输出到单独目录。
- DC/DVDS/RG/DC-AI：输入为目录，输出为目录。

## 开发验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q gui factories shared packaging tests
python packaging/build_secure_pyz.py
```

发布前还需检查 PYZ 包内没有原始 CSV、Excel 输出、日志、缓存、测试或内部文档。
