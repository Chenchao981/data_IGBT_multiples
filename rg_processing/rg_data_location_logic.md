# RG数据关键元素定位逻辑规划

## 概述

基于对源数据文件的详细分析，制定RG数据中3个关键元素的精确定位逻辑：

1. **RG标识定位**：确定"RG"文字标识的位置
2. **R单位定位**：确定"R"单位标识的位置  
3. **RG数值定位**：确定RG测量数值的位置

## 源数据结构分析结果

### 文件基本信息

- **文件格式**：Excel (.xlsx)
- **总行数**：6256行
- **总列数**：11列
- **文件示例**：`ST1_NCEAP40PT15D(M)-2B00_1-0_FA4Z-2482_NCT5452009_P_001_20250102152204.xlsx`

### 关键区域分布

```
行1   : 表头区域      [None | 'Item Status' | 'Color' | ... | 'Test' | 'T1' | 'T2' | 'T3' | 'T4']
行2   : 测试项目行    [None | 'Fail' | None | ... | 'Item' | 'CONT' | 'OPEN' | 'SHORT' | 'RG']
行3-4 : 限制值行      [None | 'Alarm' | None | ... | 'Low Limit' | ... | '4.600 R']
行5-18: 其他设置行    
行19  : 数据标识行    ['Test No.' | ...]
行20+ : 数据内容行    ['0001' | None | '1' | ... | 'PASS' | 'PASS' | 'PASS' | 'PASS' | 5.387]
```

## 三个关键元素定位策略

### 1. RG标识定位 ("RG"文字)

**定位结果**：

- **位置**：第2行，列数动态寻找
- **实际发现**：第2行，第11列 `(2, 11)`

**定位逻辑**：

```python
def locate_rg_header(df):
    """定位RG标识的位置 - 在第2行中动态寻找RG列"""
    target_row = 1  # 第2行（0-based索引）
    
    # 在第2行中寻找"RG"标识
    if target_row < len(df):
        for j in range(len(df.columns)):
            cell_value = str(df.iloc[target_row, j]).strip()
            if cell_value.upper() == "RG":  # 不区分大小写
                return (target_row, j)  # 返回0-based索引
    
    # 容错：如果第2行没找到，在前5行中寻找
    for i in range(min(5, len(df))):
        for j in range(len(df.columns)):
            cell_value = str(df.iloc[i, j]).strip()
            if cell_value.upper() == "RG":
                return (i, j)
    
    return None
```

**容错机制**：

- 优先在第2行寻找RG标识
- 如果第2行没找到，在前5行范围内搜索
- 不区分大小写匹配
- 返回第一个找到的位置

### 2. R单位标识定位 ("R"单位)

**定位结果**：

- **位置**：第7行与RG列的交叉位置 `(7, RG_col)`
- **实际发现**：第7行，第11列 `(7, 11)`
- **完整内容**：`"4.600 R"` (作为下限值显示)

**定位逻辑**：

```python
def locate_r_unit(df, rg_col):
    """基于RG列位置定位R单位标识 - 在unit行（第7行）与RG列交叉位置查找"""
    unit_row = 6  # 第7行（0-based索引）
    
    # 首先在第7行与RG列交叉位置查找
    if unit_row < len(df) and rg_col < len(df.columns):
        cell_value = str(df.iloc[unit_row, rg_col]).strip()
        # 匹配包含数值+空格+R的格式，或包含"R"的内容
        if re.search(r'\bR\b', cell_value) or re.match(r'^\d+\.\d+\s+R$', cell_value):
            return (unit_row, rg_col)
    
    # 容错：在RG列的前10行中查找包含R单位的内容
    for i in range(min(10, len(df))):
        cell_value = str(df.iloc[i, rg_col]).strip()
        if re.match(r'^\d+\.\d+\s+R$', cell_value):
            return (i, rg_col)
    
    return None
```

**识别特征**：

- 位置：第7行（unit行）与RG列的交叉位置
- 格式：包含"R"单位标识的内容
- 常见格式：`数值 + 空格 + "R"`（如"4.600 R"）
- 通常表示测量限制值或单位说明

### 3. RG数值定位 (测量数据)

**定位结果**：

- **数据起始行**：第20行 (基于"Test No."定位)
- **数据列**：第11列 (基于RG标识定位)
- **样本数据**：`[5.387, 5.407, 5.39, 5.051, 5.054, ...]`

**定位逻辑**：

```python
def locate_rg_data(df):
    """定位RG测量数据区域"""
    # 1. 找到"Test No."行作为数据起始标识
    test_no_row = None
    for i in range(len(df)):
        for j in range(len(df.columns)):
            cell_value = str(df.iloc[i, j]).strip()
            if "Test No" in cell_value:
                test_no_row = i
                break
        if test_no_row is not None:
            break
    
    # 2. 找到RG列
    rg_col = locate_rg_header(df)[1] if locate_rg_header(df) else None
    
    # 3. 数据区域从Test No.行的下一行开始
    if test_no_row is not None and rg_col is not None:
        data_start_row = test_no_row + 1
        return (data_start_row, rg_col)
    
    return None
```

**数据提取规则**：

- 起始行：`"Test No."行 + 1`
- 数据列：`RG标识所在列`
- 有效数据：数值型且不为空
- 数据过滤：跳过非数值和异常值

## lot_ID提取逻辑

**文件名分析结果**：

```
完整文件名: ST1_NCEAP40PT15D(M)-2B00_1-0_FA4Z-2482_NCT5452009_P_001_20250102152204
lot_ID: ST1_NCEAP40PT15D(M)-2B00_1-0_FA4Z-2482_NCT5452009_P_001_20250102152204
```

**提取逻辑**：

```python
def extract_lot_id(filename):
    """直接使用完整文件名作为lot_ID"""
    # 移除文件扩展名，保留完整的文件名作为lot_ID
    from pathlib import Path
    return Path(filename).stem
```

## 综合定位流程

### 完整定位算法

```python
def locate_all_rg_elements(df, filename):
    """综合定位所有RG关键元素"""
    result = {
        'rg_header_pos': None,
        'r_unit_pos': None, 
        'data_start_pos': None,
        'rg_data_col': None,
        'lot_id': None
    }
    
    # 1. 定位RG标识
    rg_pos = locate_rg_header(df)
    if rg_pos:
        result['rg_header_pos'] = rg_pos
        result['rg_data_col'] = rg_pos[1]
        
        # 2. 基于RG列定位R单位
        r_unit_pos = locate_r_unit(df, rg_pos[1])
        result['r_unit_pos'] = r_unit_pos
    
    # 3. 定位数据起始位置
    data_pos = locate_rg_data(df)
    if data_pos:
        result['data_start_pos'] = data_pos
    
    # 4. 提取lot_ID（直接使用文件名）
    result['lot_id'] = extract_lot_id(filename)
    
    return result
```

## 容错和异常处理

### 常见异常情况

1. **RG标识缺失**：搜索"RG"、"Rg"、"rg"等变体
2. **Test No.标识变化**：搜索包含"Test"和"No"的组合
3. **数据列位置偏移**：动态搜索而非固定列号
4. **文件名处理**：直接使用完整文件名作为lot_ID

### 验证机制

```python
def validate_rg_extraction(positions, sample_data):
    """验证定位结果的有效性"""
    checks = {
        'rg_header_found': positions['rg_header_pos'] is not None,
        'data_start_found': positions['data_start_pos'] is not None,
        'sample_data_valid': len(sample_data) > 0,
        'data_is_numeric': all(isinstance(x, (int, float)) for x in sample_data[:5]),
        'lot_id_extracted': positions['lot_id'] is not None
    }
    
    return all(checks.values()), checks
```

## 实施优先级

### Phase 1: 核心定位 (高优先级)

- [x] RG标识定位算法
- [x] Test No.行定位算法  
- [x] 数据起始位置确定
- [x] lot_ID提取规则

### Phase 2: 增强容错 (中优先级)  

- [ ] 多变体搜索算法
- [ ] 位置验证机制
- [ ] 异常情况处理

### Phase 3: 性能优化 (低优先级)

- [ ] 搜索范围优化
- [ ] 缓存机制
- [ ] 批量处理优化

## 测试用例设计

### 基础测试

- 正常文件的完整定位流程
- 多个RG文件的批量定位
- 定位结果的数据有效性验证

### 边界测试  

- RG标识缺失的文件
- Test No.标识变化的文件
- 文件名格式异常的情况
- 数据区域为空的情况

### 性能测试

- 大文件的定位速度
- 批量文件处理性能
- 内存使用情况

这个定位逻辑规划是否符合您的要求？需要我补充或调整哪些部分？
