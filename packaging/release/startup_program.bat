@echo off
echo.
echo ==========================================
echo    FT Data Cleaner Tool - Startup Script
echo ==========================================
echo.

cd /d "%~dp0"

echo Starting FT Data Cleaner Tool...
echo.

python ft_data_cleaner.pyz

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Program startup failed
    echo Possible reasons:
    echo    1. Dependencies not installed, please run "install_dependencies.bat" first
    echo    2. Python environment not configured, please ensure Anaconda is properly installed
    echo.
    echo Press any key to exit...
    pause > nul
) 