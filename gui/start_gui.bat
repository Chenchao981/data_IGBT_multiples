@echo off
cd /d "%~dp0.."
echo ========================================
echo   FT 数据清洗工具 - 多封装厂
echo ========================================
echo.
echo 支持的封装厂: 日月新(ASE) / 杰群(Jiequn)
echo.
python -m gui.main_window
if %errorlevel% neq 0 (
    echo.
    echo 启动失败，请检查:
    echo 1. Python 是否已安装
    echo 2. 依赖: pip install -r requirements.txt
    pause
)
