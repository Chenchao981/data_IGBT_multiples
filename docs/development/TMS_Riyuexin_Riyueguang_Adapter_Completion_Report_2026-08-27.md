# TMS 日月新/日月光 FT Adapter 完成报告（2026-08-27）

## 1. 本次目标

在不重写既有 FT 清洗计算的前提下，为 TMS 正式入库建立日月新与日月光两个独立、严格、可审计的 DC Adapter，并发布可由 TMS Worker 调用的 FT Cleaner 包。

## 2. 已完成工作

1. 新增 `factories/tms_adapters`，把厂商身份、文件名规则和工作表布局校验放在 TMS 专用边界层。
2. 日月新支持已验收的两种文件名方向：`设备_产品_Lot_日期_时间` 与 `产品_Lot_设备_DC_时间`。
3. 日月光只接受已验收的 `设备_产品_Lot_日期_时间`，并严格要求 Item、Time、Unit、Test No. 位于对应行。
4. 日月光多出的 Time 行只在临时副本中删除；原始 XLSX 不修改。
5. 两家 Adapter 均复用成熟 `DCDataCleaner` 的参数命名、单位换算、规格读取和散点数据生成逻辑。
6. `Source_ID` 改为完整源文件 stem，代表唯一源文件 Run；物理测试机号仍可从文件名独立取得，避免同一测试机号的多次测试被错误合并。
7. GUI 中将“日月新 (ASE)”改为“日月新 (Riyuexin)”，日月光通过独立 TMS Adapter 提供，不再把 ASE 身份映射到日月新。
8. 发布包版本提升为 v2.16.0，并包含两个 TMS Adapter。

## 3. 真实样本验证

### 日月新

- 真实 DC 文件：6 个。
- 清洗结果：35,350 Unit、18 个参数。
- 全目录实测耗时：10.529 秒。
- 文件名、Product、Lot 与 Cleaner 输出完成交叉对账。

### 日月光

- 真实 DC 文件：7 个。
- 清洗结果：33,064 Unit、24 个参数。
- 全目录实测耗时：32.653 秒。
- 两个文件使用相同测试机号 `NCT6528073` 和 Lot `FA54-9815`，但 `HVBCES1/HVBCES2` 的 LSL 分别为 1.29 kV 与 1.27 kV；完整源文件 stem 能把两次测试和两套规格正确隔离。
- 清洗前后原始文件哈希一致。

## 4. 自动化与发布验证

- FT 项目全量测试：104 passed，52 warnings；warnings 均为既有 openpyxl `utcnow()` 弃用提示。
- 发布包：`packaging/release/ft_data_cleaner.pyz`。
- 发布包大小：133,415 bytes。
- SHA256：`2f052c54c559191b358951b10c691a0f81e49170efb5d8a72d529db87821124d`。
- 包内条目：71；TMS Adapter 文件齐全。
- 数据、输出、测试、缓存、日志、Markdown、Excel/CSV 条目：0。
- 私钥和常见硬编码凭据命中：0。
- 最新包单文件启动实测：日月光 3,900 Unit、24 个参数，Factory=`RIYUEGUANG`，Source_ID 为完整文件 stem，输入副本哈希不变。
- 离屏 GUI 启动已验证 4 个厂家面板可创建。

## 5. 做得较好的地方

- 没有复制或改写成熟 FT 清洗算法，TMS 差异被限制在 Adapter 和身份校验层。
- 用真实样本发现并处理了日月光 Time 行差异，而不是把相似格式直接当成日月新。
- Source_ID 与物理 tester 分离后，可以表达“同 tester、同 Lot、不同测试 Run、不同 Spec”的真实业务情况。
- 发布包在登记到 TMS 前完成了内容审计、真实文件运行和原始数据不变验证。

## 6. 仍存在的限制

- 日月光本阶段只承诺 DC XLSX；DVDS、RG、HTDC、TF 尚未作为 TMS 正式入库格式验收。
- 日月新和日月光当前源数据未提供可发布的 PASS/FAIL 或 Bin，因此 TMS 不计算 FT 良率。
- 电基、集佳、杰群虽有旧 Cleaner，但尚未完成各自独立的 TMS 正式 Route A 对账。
- 旧 Cleaner 的部分控制台中文日志受 Windows 代码页影响会乱码，不影响结果文件和 TMS 入库，但后续可统一日志编码。

## 7. 下一步建议

1. 按同一标准分别建设电基、集佳、杰群 TMS Adapter，逐厂使用真实样本验收。
2. 为每个厂商建立固定 Golden Manifest，持续校验行数、参数、单位、Lot、规格和源文件身份。
3. 新厂商或新格式继续采用“样本画像 → 人工批准 → Adapter → 真实包验证”的方式接入，未知格式保持失败关闭。
