# DVDS数据清洗 - 核心代码逻辑说明

## 概述

本文档详细说明DVDS数据清洗项目的核心代码逻辑，帮助理解各个模块的实现原理和关键算法。

## 1. 文件扫描模块 (scan_dvds_files)

### 功能说明

扫描指定目录下的所有Excel文件，排除临时文件和无效文件。

### 核心逻辑

```python
def scan_dvds_files(directory_path):
    """
    扫描DVDS目录下的所有xlsx文件
    
    Args:
        directory_path (str): 目录路径
    
    Returns:
        list: 有效文件路径列表
    """
    # 逻辑步骤：
    # 1. 使用os.listdir()或pathlib.Path().glob()遍历目录
    # 2. 过滤条件：
    #    - 文件扩展名为.xlsx
    #    - 不以~$开头（排除Excel临时文件）
    #    - 文件大小大于0
    # 3. 返回完整文件路径列表
```

### 关键技术点

- **文件过滤**：使用正则表达式或字符串方法过滤文件名
- **路径处理**：使用os.path.join()或pathlib处理路径拼接
- **异常处理**：目录不存在、权限不足等情况

## 2. 数据定位与提取模块 (extract_dvds_data)

这是整个项目的**核心模块**，负责从Excel文件中精确定位和提取DVDS数据。

### 功能说明

从单个Excel文件中定位"Test No."行，并从该行下一行开始提取DVDS列的数值数据。

### 核心算法流程

#### 步骤1：加载Excel文件

```python
def extract_dvds_data(file_path):
    """
    从Excel文件中提取DVDS数据
    
    Args:
        file_path (str): Excel文件路径
    
    Returns:
        pd.DataFrame: 包含DVDS数据和文件名的DataFrame
    """
    # 使用pandas读取Excel文件
    df = pd.read_excel(file_path, sheet_name=0, header=None)
```

#### 步骤2：定位"Test No."行

```python
    # 在所有单元格中查找"Test No."
    test_no_row = None
    for row_idx, row in df.iterrows():
        for col_idx, cell_value in enumerate(row):
            if str(cell_value).strip() == "Test No.":
                test_no_row = row_idx
                break
        if test_no_row is not None:
            break
```

#### 步骤3：定位DVDS列

```python
    # 在"Test No."行中查找DVDS列
    dvds_col = None
    if test_no_row is not None:
        header_row = df.iloc[test_no_row]
        for col_idx, cell_value in enumerate(header_row):
            if str(cell_value).strip() == "DVDS":
                dvds_col = col_idx
                break
```

#### 步骤4：提取数据

```python
    # 从下一行开始提取DVDS列数据
    data_start_row = test_no_row + 1
    dvds_values = []
    
    for row_idx in range(data_start_row, len(df)):
        cell_value = df.iloc[row_idx, dvds_col]
        # 只提取数值数据，跳过"PASS"等文本
        if pd.isna(cell_value):
            break  # 遇到空值停止
        if isinstance(cell_value, (int, float)):
            dvds_values.append(cell_value)
        elif isinstance(cell_value, str):
            try:
                # 尝试转换为数值
                numeric_value = float(cell_value)
                dvds_values.append(numeric_value)
            except ValueError:
                # 跳过非数值数据
                continue
```

### 关键技术点

- **动态定位**：不依赖固定行列位置，通过搜索关键字定位
- **数据类型处理**：区分数值和文本，只提取有效数值
- **异常处理**：文件格式异常、关键字找不到等情况
- **内存优化**：逐行处理，避免加载整个文件到内存

## 3. 数据汇总模块 (merge_all_data)

### 功能说明

将多个文件提取的数据合并为统一的DataFrame，并生成连续编号。

### 核心逻辑

```python
def merge_all_data(data_list):
    """
    合并所有文件的数据
    
    Args:
        data_list (list): 包含各文件数据的DataFrame列表
    
    Returns:
        pd.DataFrame: 合并后的统一数据
    """
    # 1. 合并所有DataFrame
    merged_df = pd.concat(data_list, ignore_index=True)
    
    # 2. 生成连续NUM编号
    merged_df['NUM'] = range(1, len(merged_df) + 1)
    
    # 3. 调整列顺序
    merged_df = merged_df[['NUM', 'lot_ID', 'DVDS(mV)']]
    
    return merged_df
```

### 关键技术点

- **DataFrame合并**：使用pd.concat()实现高效合并
- **索引重置**：ignore_index=True确保连续索引
- **列重排序**：确保输出格式符合要求

## 4. 数据清洗模块 (clean_and_format)

### 功能说明

对合并后的数据进行最终清洗和格式化。

### 核心逻辑

```python
def clean_and_format(df):
    """
    数据清洗和格式化
    
    Args:
        df (pd.DataFrame): 原始合并数据
    
    Returns:
        pd.DataFrame: 清洗后的数据
    """
    # 1. 删除空值行
    df_clean = df.dropna(subset=['DVDS(mV)'])
    
    # 2. 数据类型转换
    df_clean['DVDS(mV)'] = pd.to_numeric(df_clean['DVDS(mV)'], errors='coerce')
    
    # 3. 删除转换失败的行
    df_clean = df_clean.dropna(subset=['DVDS(mV)'])
    
    # 4. 重新生成连续编号
    df_clean['NUM'] = range(1, len(df_clean) + 1)
    
    return df_clean
```

## 5. 输出模块 (save_result)

### 功能说明

将清洗后的数据保存为Excel文件，使用时间戳命名。

### 核心逻辑

```python
def save_result(df, output_dir):
    """
    保存结果到Excel文件
    
    Args:
        df (pd.DataFrame): 清洗后的数据
        output_dir (str): 输出目录
    
    Returns:
        str: 输出文件路径
    """
    # 1. 生成时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 2. 构造文件名
    filename = f"DVDS_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)
    
    # 3. 保存到Excel
    df.to_excel(filepath, index=False, engine='openpyxl')
    
    return filepath
```

## 错误处理策略

### 1. 文件级错误

- 文件不存在：记录错误，跳过该文件
- 文件格式错误：记录错误，跳过该文件
- 权限不足：记录错误，跳过该文件

### 2. 数据级错误

- "Test No."找不到：记录警告，跳过该文件
- DVDS列找不到：记录警告，跳过该文件  
- 数据为空：记录警告，跳过该文件

### 3. 系统级错误

- 内存不足：分批处理文件
- 磁盘空间不足：提前检查，警告用户

## 性能优化策略

### 1. 内存优化

- 使用chunking逐块读取大文件
- 及时释放不需要的DataFrame
- 使用适当的数据类型（int32 vs int64）

### 2. 处理速度优化

- 使用向量化操作替代循环
- 合理使用pandas的内置函数
- 避免重复的文件I/O操作

### 3. 并行处理

- 考虑使用multiprocessing处理多个文件
- 使用concurrent.futures简化并行代码

## 调试和测试建议

### 1. 单元测试

- 每个函数单独测试
- 准备不同格式的测试文件
- 测试边界情况

### 2. 集成测试

- 完整流程测试
- 大量文件处理测试
- 异常情况测试

### 3. 调试技巧

- 使用logging记录关键步骤
- 保存中间结果用于调试
- 使用pandas的info()和describe()检查数据
