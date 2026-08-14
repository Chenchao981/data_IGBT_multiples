# FT数据清洗工具 - 安全打包

## 概述

本目录包含FT数据清洗工具的安全打包脚本，可以创建不包含敏感信息的发布版本。

## 主要文件

### 主要脚本
- `build_secure_pyz.py` - 主要的安全打包脚本（推荐使用）

### 配置文件
- `requirements_minimal.txt` - 最小依赖列表

### 备份文件
- `build_secure.bat.bak` - 批处理启动脚本（备份）
- `build_all.bat.bak` - 一键打包脚本（备份）
- `build_config.py.bak` - PyInstaller构建配置（备份）

## 使用方法

### 直接运行Python脚本（推荐）
```bash
cd packaging
python build_secure_pyz.py
```

### 可选：使用批处理文件
```batch
# 如需要，可以将备份文件恢复：
# ren build_secure.bat.bak build_secure.bat
# 然后双击运行 build_secure.bat
```

## 安全特性

### 自动排除的内容
- ✅ 所有.md文档文件
- ✅ 日志文件 (*.log)
- ✅ 计划和TODO文档
- ✅ 测试数据目录 (ASEData/, sample/)
- ✅ 构建缓存文件
- ✅ Git相关文件

### 保留的内容
- ✅ 核心业务逻辑代码
- ✅ GUI界面代码
- ✅ 必要的依赖文件
- ✅ requirements.txt
- ✅ Plotly/Streamlit 散点图逻辑和独立前端入口

## 输出

### 生成文件
- `release/ft_data_cleaner.pyz` - 主程序包
- `release/USAGE.txt` - 使用说明
- `release/frontend/ft_scatter_app.py` - Streamlit 物理启动入口

### 运行方式
```bash
# 安装依赖
python -m pip install -r requirements.txt

# 运行程序
python ft_data_cleaner.pyz
```

## 注意事项

1. 确保Python环境正确配置
2. 生成的.pyz文件可安全分发
3. 接收方需要安装Python和依赖包
4. 所有敏感信息已被自动过滤

## 版本信息

- 版本：2.12.0
- 作者：cc
- 创建时间：2025-01-20 
