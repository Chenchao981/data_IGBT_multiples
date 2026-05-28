# DC数据处理模块

## 📚 文档索引

### 核心文档

- **[dc_core_logic.md](dc_core_logic.md)** - DC数据定位和提取的核心逻辑说明
- **[parameter_enhancement.md](parameter_enhancement.md)** - 参数名称增强功能详细文档
- **[todo_DC.md](todo_DC.md)** - 待办事项和开发计划

### 主要文件

- **[dc_cleaner.py](dc_cleaner.py)** - DC数据清洗主程序
- **[dc_cleaner.log](dc_cleaner.log)** - 运行日志文件

## 🚀 快速开始

### 运行数据清洗

```bash
cd dc_processing
python dc_cleaner.py
```

### 输入数据位置

- 源文件目录：`../ASEData/DC/`
- 支持格式：`.xlsx` 文件
- 自动排除：以 `~$` 开头的临时文件

### 输出结果

- 输出目录：`../output/`
- 文件命名：`DC_YYYYMMDD_HHMMSS.xlsx`
- 数据格式：标准化的测试参数表

## ✨ 主要功能

### 1. 数据提取

- 自动识别Excel文件结构
- 提取所有测试参数和对应数值数据
- 支持重复参数自动编号

### 2. 参数名称增强 🆕

- **IDSS参数**：自动添加测试条件 (如 `IDSS` → `IDSS40.0`)
- **ISGS参数**：自动添加测试条件 (如 `ISGS` → `ISGS25.0`)
- 从Excel第5行提取测试条件数值

### 3. 数据清洗

- 统一数据格式
- 生成连续编号（NUM列）
- 提取批次信息（lot_ID列）

## 📊 输出数据结构

```
NUM | lot_ID | VTH1(V) | VTH2(V) | IDSS40.0(nA) | ISGS25.01(nA) | ...
1   | FA4Z-2484 | 1.8437 | 1.9535 | 12.5 | 8.3 | ...
2   | FA4Z-2484 | 1.8512 | 1.9601 | 11.8 | 7.9 | ...
```

## 🔧 技术特性

- **自适应结构识别**：自动定位关键行和列
- **错误处理**：完善的异常处理和日志记录
- **批量处理**：支持多文件同时处理
- **参数增强**：智能参数名称增强功能

## 📈 扩展计划

查看 [parameter_enhancement.md](parameter_enhancement.md) 了解：

- 如何添加新的参数增强支持
- 模块化重构建议
- 扩展触发条件

## 🐛 问题排查

### 常见问题

1. **文件读取失败**：检查文件路径和权限
2. **参数未增强**：查看日志中的警告信息
3. **数据格式异常**：验证Excel文件结构

### 调试方法

```python
# 启用详细日志
logging.basicConfig(level=logging.DEBUG)
```

## 👥 贡献

- 开发者：cc
- 创建时间：2025-06-18
- 最后更新：2025-06-18

---

💡 **提示**：参数名称增强功能已集成到主流程中，无需额外配置即可使用。
