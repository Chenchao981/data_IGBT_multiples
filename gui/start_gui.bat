@echo off
cd /d "%~dp0"
echo 启动FT数据清洗工具...
python ft_data_cleaner_gui.py
if %errorlevel% neq 0 (
    echo.
    echo 程序运行出错，请检查：
    echo 1. 是否已安装Python
    echo 2. 是否已安装依赖包：pip install -r ../requirements.txt
    echo 3. 检查错误日志信息
    pause
) 