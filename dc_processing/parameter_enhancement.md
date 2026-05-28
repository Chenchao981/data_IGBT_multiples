# DC数据清洗 - 参数名称增强功能文档

## 📖 功能概述

参数名称增强功能用于在DC数据清洗过程中，将特定参数的测试条件信息添加到参数名称中，使输出数据更具可读性和识别性。

### 🎯 目标

- 将 `IDSS` 参数改为 `IDSS40.0` 格式
- 将 `ISGS` 参数改为 `ISGS25.0` 格式
- 将 `LRDON` 参数改为 `LRDON10.0` 格式
- 自动从Excel源文件中提取测试条件数值

## 📊 当前实现状态

### ✅ 已支持参数

| 参数名 | 增强示例 | 测试条件来源 | 状态 |
|--------|----------|--------------|------|
| IDSS   | IDSS40.0(nA) | 第5行对应列 | ✅ 已实现 |
| ISGS   | ISGS25.0(nA) | 第5行对应列 | ✅ 已实现 |
| LRDON  | LRDON10.0(V) | 第6行对应列 | ✅ 已实现 |

### 📋 实际处理结果

```
原始参数 → 增强后参数
IDSS → IDSS40.0(nA), IDSS35.0(nA)
ISGS → ISGS25.01(nA), ISGS25.02(nA), ISGS20.01(nA), ISGS20.02(nA), ISGS10.01(nA), ISGS10.02(nA)
LRDON → LRDON10.0(V)
```

## 🔧 技术实现细节

### 文件位置

- **主文件**: `dc_processing/dc_cleaner.py`
- **核心类**: `DCDataCleaner`
- **关键方法**: `extract_test_condition_value()`, `extract_dc_data()`

### 实现逻辑

#### 1. 测试条件提取方法

```python
def extract_test_condition_value(self, df: pd.DataFrame, param_col: int) -> Optional[str]:
    """
    提取IDSS/ISGS参数的测试条件数值
    
    Args:
        df: Excel数据表
        param_col: 参数所在列索引
        
    Returns:
        测试条件数值字符串，如"40.0"，失败返回None
    """
```

**关键逻辑:**

- 从第5行（索引4）提取测试条件
- 使用正则表达式 `r'(\d+\.?\d*)'` 提取数值部分
- 支持格式：`(VDS)40.0V`、`40.0V`、`25.0` 等

#### 2. 参数名称增强逻辑

```python
# 特殊处理IDSS和ISGS参数：添加测试条件
if param.upper() in ['IDSS', 'ISGS']:
    test_condition = self.extract_test_condition_value(df, col)
    if test_condition:
        enhanced_param = f"{param}{test_condition}"
        logger.info(f"{param}参数增强: {param} -> {enhanced_param}")
```

### 数据流程图

```
Excel源文件
    ↓
第2行: 参数名 (IDSS, ISGS)
    ↓
第5行: 测试条件 ((VDS)40.0V)
    ↓
正则提取: 40.0
    ↓
参数增强: IDSS40.0
    ↓
最终输出: IDSS40.0(nA)
```

## 🚀 使用方法

### 自动触发

参数名称增强功能已集成到DC数据清洗主流程中，无需额外操作：

```bash
cd dc_processing
python dc_cleaner.py
```

### 日志输出示例

```
2025-06-18 17:31:54,862 - INFO - IDSS参数增强: IDSS -> IDSS40.0
2025-06-18 17:31:54,863 - INFO - ISGS参数增强: ISGS -> ISGS25.0
```

## 📈 扩展指南

### 🔄 添加新参数支持

当需要为新参数（如VTH、BVDSS等）添加增强功能时：

#### 方法1：直接修改（当前方案）

在 `extract_dc_data()` 方法中修改条件判断：

```python
# 修改前
if param.upper() in ['IDSS', 'ISGS']:

# 修改后
if param.upper() in ['IDSS', 'ISGS', 'VTH', 'BVDSS']:
```

#### 方法2：配置化重构（推荐重构方案）

```python
class ParameterEnhancer:
    """参数名称增强器"""
    
    ENHANCE_CONFIG = {
        'IDSS': {'row_index': 4, 'pattern': r'(\d+\.?\d*)'},
        'ISGS': {'row_index': 4, 'pattern': r'(\d+\.?\d*)'},
        'VTH': {'row_index': 4, 'pattern': r'(\d+\.?\d*)'},
        'BVDSS': {'row_index': 6, 'pattern': r'(\d+\.?\d*)'},  # 不同行位置
    }
```

### 🎯 重构触发条件

建议在以下情况下进行模块化重构：

1. **参数数量**: 需要增强的参数超过4个
2. **规则复杂化**: 不同参数需要不同的提取规则
3. **其他模块需要**: DVDS或RG处理器需要类似功能
4. **测试需求**: 需要对增强逻辑进行独立测试

## 🐛 问题排查

### 常见问题

#### 1. 参数未被增强

**可能原因:**

- 参数名大小写不匹配
- 第5行测试条件为空或格式不正确
- 正则表达式匹配失败

**排查方法:**

```python
# 检查日志中是否有警告信息
logger.warning(f"无法为{param}参数提取测试条件，保持原名: {param}")
```

#### 2. 提取的数值不正确

**可能原因:**

- 源文件格式变化
- 测试条件格式不符合预期

**调试方法:**

```python
# 在extract_test_condition_value中添加调试日志
logger.debug(f"测试条件原始值: '{condition_str}'")
logger.debug(f"提取到数值: '{numeric_value}'")
```

### 调试技巧

1. 启用DEBUG级别日志：`logging.basicConfig(level=logging.DEBUG)`
2. 检查Excel文件第5行对应列的值
3. 测试正则表达式：`re.search(r'(\d+\.?\d*)', test_string)`

## 📋 测试用例

### 输入测试数据

```
第2行: IDSS, ISGS, VTH
第5行: (VDS)40.0V, (VGS)25.0V, 空值
```

### 预期输出

```
IDSS → IDSS40.0
ISGS → ISGS25.0  
VTH → VTH (保持原名)
```

## 🔄 版本历史

| 版本 | 日期 | 更新内容 | 作者 |
|------|------|----------|------|
| 1.0 | 2025-06-18 | 实现IDSS参数增强功能 | cc |
| 1.1 | 2025-06-18 | 添加ISGS参数增强功能 | cc |
| 1.2 | 2025-06-18 | 创建功能文档 | cc |
| 1.3 | 2025-06-18 | 添加LRDON参数增强功能 | cc |

## 🎯 后续规划

### 短期目标

- [ ] 监控现有功能稳定性
- [ ] 收集用户反馈
- [ ] 完善错误处理

### 中期目标（触发条件达成时）

- [ ] 模块化重构
- [ ] 配置文件支持
- [ ] 单元测试覆盖

### 长期目标

- [ ] 支持自定义增强规则
- [ ] 图形化配置界面
- [ ] 跨处理器复用

## 📞 联系方式

如有问题或建议，请联系：

- 开发者：cc
- 项目位置：`D:\data_IGBT\dc_processing\`
- 文档更新：请同步更新此文档

---

*最后更新：2025-06-18*
*文档版本：1.0*
