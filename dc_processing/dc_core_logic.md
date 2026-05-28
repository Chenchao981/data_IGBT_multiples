# DC数据定位逻辑核心说明

## 数据结构分析结果

基于对 `NCT5450009_NCEAP40PT15D(M)-2B00_FA4Z-2484_20241222_162324.xlsx` 文件的详细分析：

### 文件基本信息

- 文件形状：(6258, 34)
- 测试参数数量：18个（去除SAME列后）
- 数据起始行：第19行（索引18的下一行）

### 关键行位置

1. **第1行 (索引1)** - 参数名行
   - CONT列位置：第7列（索引7）
   - 参数列范围：第8-33列（索引8-33）
   - SAME列位置：9, 11, 13, 15, 22, 24, 26, 31

2. **第6行 (索引6)** - 单位行
   - Unit标识：第6列（索引6）
   - 单位数据：对应参数列位置

3. **第18行 (索引18)** - Test No.行
   - 数据起始：第19行（索引19）

## 参数提取算法

### 1. 定位CONT列

```python
# 在第1行找到CONT列位置
cont_col = None
for i, val in enumerate(row1):
    if not pd.isna(val) and str(val).strip() == 'CONT':
        cont_col = i
        break
```

### 2. 提取参数列表（跳过SAME）

```python
# 从CONT右边开始提取参数，跳过SAME
test_params = []
for i in range(cont_col + 1, len(row1)):
    val = row1.iloc[i]
    if not pd.isna(val) and str(val).strip() != '' and str(val).strip() != 'SAME':
        param_name = str(val).strip()
        test_params.append((i, param_name))
```

### 3. 获取参数单位并进行参数名称增强

```python
# 从第6行获取对应位置的单位
param_unit_pairs = []
for col, param in test_params:
    unit_val = row6.iloc[col] if col < len(row6) else None
    unit_name = str(unit_val).strip() if not pd.isna(unit_val) else 'N/A'
    
    # 特殊处理IDSS和ISGS参数：添加测试条件
    if param.upper() in ['IDSS', 'ISGS']:
        test_condition = self.extract_test_condition_value(df, col)
        if test_condition:
            # 将IDSS/ISGS改为IDSS/ISGS+测试条件，如IDSS40.0, ISGS25.0
            enhanced_param = f"{param}{test_condition}"
            param_unit_pairs.append((col, enhanced_param, unit_name))
        else:
            param_unit_pairs.append((col, param, unit_name))
    else:
        param_unit_pairs.append((col, param, unit_name))
```

#### 3.1 参数名称增强功能

对于IDSS和ISGS参数，系统会自动从第5行（索引4）提取测试条件数值：

```python
def extract_test_condition_value(self, df: pd.DataFrame, param_col: int) -> Optional[str]:
    """
    提取IDSS/ISGS参数的测试条件数值
    从第5行对应列中提取数值部分，如从"(VDS)40.0V"中提取"40.0"
    """
    row5 = df.iloc[4, :]  # 第5行（索引4）
    condition_value = row5.iloc[param_col]
    
    # 使用正则表达式提取数值部分
    pattern = r'(\d+\.?\d*)'
    match = re.search(pattern, str(condition_value))
    
    if match:
        return match.group(1)  # 返回提取的数值
    return None
```

**增强效果：**

- `IDSS` → `IDSS40.0` (测试条件40.0V)
- `ISGS` → `ISGS25.0` (测试条件25.0V)

### 4. 重复参数编号

```python
# 对重复参数进行编号
param_counters = {}
final_params = []

for col, param, unit in param_unit_pairs:
    if param in param_counters:
        param_counters[param] += 1
        numbered_param = f"{param}{param_counters[param]}"
    else:
        param_counters[param] = 1
        if param_counts[param] > 1:  # 如果该参数出现多次
            numbered_param = f"{param}1"
        else:
            numbered_param = param
    
    final_param_name = f"{numbered_param}({unit})"
    final_params.append((col, final_param_name))
```

## 实际提取结果

基于当前文件，最终参数列表为（含参数名称增强）：

| 列索引 | 原参数名 | 增强后参数名 | 编号后参数名 | 单位 | 最终列名 |
|--------|----------|-------------|--------------|------|----------|
| 8      | VTH      | VTH         | VTH1         | V    | VTH1(V)  |
| 10     | VTH      | VTH         | VTH2         | V    | VTH2(V)  |
| 12     | BVDSS    | BVDSS       | BVDSS1       | V    | BVDSS1(V) |
| 14     | BVDSS    | BVDSS       | BVDSS2       | V    | BVDSS2(V) |
| 16     | IDSS     | IDSS40.0    | IDSS40.0     | nA   | IDSS40.0(nA) |
| 17     | ISGS     | ISGS25.0    | ISGS25.01    | nA   | ISGS25.01(nA) |
| 18     | ISGS     | ISGS25.0    | ISGS25.02    | nA   | ISGS25.02(nA) |
| 19     | ISGS     | ISGS20.0    | ISGS20.01    | nA   | ISGS20.01(nA) |
| 20     | ISGS     | ISGS20.0    | ISGS20.02    | nA   | ISGS20.02(nA) |
| 21     | LRDON    | LRDON       | LRDON1       | mR   | LRDON1(mR) |
| 23     | LRDON    | LRDON       | LRDON2       | mR   | LRDON2(mR) |
| 25     | HVFSD+   | HVFSD+      | HVFSD+       | V    | HVFSD+(V) |
| 27     | IDSS     | IDSS35.0    | IDSS35.0     | nA   | IDSS35.0(nA) |
| 28     | ISGS     | ISGS10.0    | ISGS10.01    | nA   | ISGS10.01(nA) |
| 29     | ISGS     | ISGS10.0    | ISGS10.02    | nA   | ISGS10.02(nA) |
| 30     | VTH      | VTH         | VTH3         | V    | VTH3(V)  |
| 32     | ABSDEL   | ABSDEL      | ABSDEL1      | N/A  | ABSDEL1 |
| 33     | ABSDEL   | ABSDEL      | ABSDEL2      | N/A  | ABSDEL2 |

**注意：**

- IDSS和ISGS参数经过名称增强，添加了测试条件数值
- 增强后的参数名在重复参数编号时仍然有效
- 其他参数保持原有处理方式

## 数据提取流程

### 1. 定位数据起始行

```python
# 查找Test No.行
test_no_row = None
for i in range(df.shape[0]):
    for j in range(df.shape[1]):
        if not pd.isna(df.iloc[i, j]) and "Test No" in str(df.iloc[i, j]):
            test_no_row = i
            break

# 数据从Test No.行的下一行开始
data_start_row = test_no_row + 1
```

### 2. 提取测试数据

```python
# 提取所有测试数据行
test_data = []
for row_idx in range(data_start_row, df.shape[0]):
    row_data = {}
    
    # 提取每个参数列的数据
    for col, param_name in final_params:
        value = df.iloc[row_idx, col]
        row_data[param_name] = value
    
    test_data.append(row_data)
```

## 输出格式

最终输出DataFrame结构：

```
NUM | lot_ID | VTH1(V) | VTH2(V) | BVDSS1(V) | ... | ABSDEL2(N/A)
1   | 文件名  | 1.8437  | 1.9535  | 45.8035   | ... | 数值
2   | 文件名  | ...     | ...     | ...       | ... | ...
```

## 关键注意事项

1. **SAME列跳过**：第1行中值为"SAME"的列不参与数据提取
2. **单位匹配**：第6行Unit列右边对应位置获取单位信息
3. **参数名称增强**：IDSS和ISGS参数会自动添加测试条件数值（如IDSS40.0）
4. **重复参数编号**：按出现顺序编号（VTH1, VTH2, VTH3），增强后的参数同样适用
5. **数据起始精确定位**：Test No.行的下一行即为数据开始
6. **批次信息**：使用正则表达式提取（如FA4Z-2484）或文件名
7. **列名格式**：参数名(单位)，如VTH1(V)、IDSS40.0(nA)

## 边界情况处理

1. **缺失单位**：显示为N/A
2. **空数据值**：保持pandas的NaN
3. **异常行**：跳过非数值行
4. **文件格式错误**：记录错误并跳过该文件
