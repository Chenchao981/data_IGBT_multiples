# TMS FT Lot 人工补录 Adapter 完成报告（2026-08-27）

## 1. 本阶段完成内容

1. 为日月新、日月光 TMS FT DC Adapter 增加显式 `lot_overrides` 输入。
2. 只有文件名符合已批准的 Source、Product、日期、时间和方向，且唯一缺少 Lot 时，Adapter 才抛出 `LotOverrideRequired`。
3. 人工 Lot 只能填补空值；文件名已识别出 Lot 时，人工值必须与其一致，否则停止处理。
4. 人工 Lot 同步写入 `DC_Data`、散点数据、Spec 和 Manifest；原始 XLSX 不修改。
5. 未知厂家名、未知文件名方向、未知 Workbook 行布局继续失败关闭，不会被误判为“只缺 Lot”。
6. FT 发布版本更新为 `2.17.0`，重建安全 PYZ。

7. 增加多文件完整覆盖校验：已登记的每个源文件都必须同时出现在 Manifest 与逐来源 Spec 中，避免成熟 Cleaner 跳过空文件后仍返回部分成功。

## 2. 验证结果

- FT 全量测试：`109 passed`（unittest）。
- 发布包归档：71 个条目；必需 Adapter、GUI 模块齐全；禁止目录、日志、Markdown、缓存文件为 0。
- 发布包离屏 GUI：4 个厂家面板均可实例化。
- 发布包人工 Lot Smoke：2 行数据全部为 `FA54-9744`，Manifest Lot 一致，原始 XLSX SHA256 前后一致。
- 发布包：`packaging/release/ft_data_cleaner.pyz`
- SHA256：`42F0A0C275E2A251E82844ED1D644BF94BFFA25DA9CAAC32E11DFBAFA2AE339F`
- 大小：135,401 bytes。
- TMS 真实浏览器闭环：真实日月新 DC 样本仅从副本文件名移除 Lot，经前端补录 `FA53-4115` 后由本发布包完成清洗；4,962 个 Unit、89,316 条 Measurement 正式发布，源文件 SHA256 前后均为 `C0894974020EB652815051FADCF01D3757DFC60FC25542B157E85A6D95D74529`。
- TMS 日月光真实浏览器闭环：3,919 行 × 41 列真实 DC 文件仅从副本文件名移除 Lot，经前端补录 `FA54-9744` 后形成 3,900 个 Unit、93,600 条 Measurement；原件与副本 SHA256 均为 `C36A3E064FF980818A78868295B1410387E5EF5F6C3724B81CBBA4AE23157D92`。

## 3. 完成较好的部分

- 没有放宽现有完整文件名的严格解析规则，而是单独登记“仅缺 Lot”的批准轮廓。
- 人工值不会覆盖 Cleaner 已识别事实，冲突能够确定性阻断。
- 日月光继续只在临时副本中处理 Time 行，人工补录也不触碰原始文件。
- 补录后的 Lot 在明细、规格和便携图表包中保持一致，避免 Lot 与 Spec 串用。
- 多文件批次不再接受“部分源文件被静默跳过”的成功结果。

## 4. 不确定性和限制

- 当前人工补录轮廓只覆盖已批准的日月新/日月光 DC 文件名方向，不代表任意未知文件名都能补 Lot 后清洗。
- 当前两家已批准 Lot 形态仍为 `AAAA-9999`；其他厂家或其他 Lot 结构必须在对应厂家 Adapter 中单独批准和验证。
- 电基、集佳、杰群尚未接入 TMS 正式 Route A，本阶段未为它们增加 TMS Lot override。

## 5. TMS 集成状态与下一步

1. TMS Worker 已将 `LotOverrideRequired` 转为结构化 `NEEDS_INPUT`，不会归入普通失败。
2. 前端已在待补录批次行提供文件级 Lot 补录；保存审计后创建同 Cleaner release 的子 Job。
3. 真实 SQL Server 与浏览器“缺 Lot → 补录 → 重跑 → Dataset Current → FT 图表”闭环已经完成。
4. 后续接入其他厂家时，继续按厂家独立批准“仅缺 Lot”文件名轮廓；不得把未知格式纳入通用补录。
