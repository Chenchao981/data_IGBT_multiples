# FT 全厂 PAT 扩展完成报告（2026-09-02）

## 做了什么

- 将已确认的 FT PAT 业务口径固化为全厂统一统计合同：`Sigma=(Q3-Q1)/1.35`，`LCL/UCL=Median±6×Sigma`。
- 新增集佳原始 STS8203 CSV PAT Adapter，复用既有严格文件名、内容签名、123 列、单位和参数解析规则。
- 新增日月光原始目录 PAT Adapter。DC 复用独立的 `RiyueguangTmsDCCleaner`；DVDS/RG 按真实 EBR 表头动态定位 `Test/Item/Unit`，排除 `CONT/OPEN/SHORT` 控制项，并严格校验参数结构和数值。
- 两家均复用 `shared/pat_engine.py` 的逐文件解析、临时 float64 流和精确四分位数计算，没有复制 PAT 统计公式。
- FT 发布版本升级为 `v2.20.0`，发布包包含两个新 Adapter。

## 已验证

- FT 全量自动化测试：129 passed。
- 发布包：74 个条目、145,242 bytes；新 Adapter、统一 PAT 引擎和 GUI 主入口均可从 PYZ 导入；数据、输出、日志、缓存和 Excel/CSV 源文件为 0。
- 集佳真实目录：5 个 CSV、97,287 解析行、112 个有数值的参数，约 8.930 秒生成 PAT。
- 日月光真实目录：DC 7 个、DVDS 6 个、RG 6 个，共 19 个 XLSX；99,782 解析行、32 个参数，约 21.023 秒生成 PAT。
- 日月光真实样本包含两种 EBR 系统列宽，`Test` 标记位置不同；最终 Adapter 动态定位该列，并保持业务参数结构严格一致。
- 发布包 SHA-256：`21a81a8ae83f927983c520dd5350ca6847e14bf78b42e6cad25fec8989f4b6ac`。

## 确定的结论

- 杰群、日月新、日月光、电基、集佳使用相同 PAT 统计合同。
- 厂商差异只保留在原始文件识别和参数解析 Adapter 中，不再作为是否能执行 PAT 的限制条件。
- PAT 是结果型快速分析，不要求先生成巨型清洗 Excel，也不要求写入 TMS 正式明细事实表。

## 限制和下一步

- 本轮日月光原始目录覆盖已验证的 DC/DVDS/RG；同目录的 TF、HTDC、HTTF 仍需各自原始格式 Adapter，不能按扩展名猜测解析。
- 集佳当前严格支持已验证的 `NCE15TD120BT` STS8203 123 列布局；新产品或新列结构继续保持失败关闭，取得真实样本后扩展。
- 下一步由 TMS Cleaner Registry 固定 `v2.20.0` 包和 SHA，并在快速分析页面开放日月光、集佳入口。
