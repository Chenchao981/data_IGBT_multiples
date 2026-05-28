@echo off
echo.
echo ==========================================
echo    FT Data Cleaner Tool - Dependencies Installer
echo ==========================================
echo.

cd /d "%~dp0"

echo Checking Python environment...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo Python environment not found, please ensure Anaconda is properly installed
    echo    Suggestion: Open Anaconda Prompt and run this script
    pause
    exit /b 1
)

echo.
echo Checking pip tool...
python -m pip --version
if %ERRORLEVEL% NEQ 0 (
    echo pip tool not found
    pause
    exit /b 1
)

echo.
echo Installing dependencies...
echo    This may take a few minutes, please wait...
echo.

python -m pip install -r requirements.txt

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Dependencies installed successfully!
    echo Now you can run FT Data Cleaner Tool
    echo.
    echo Tip: Double-click "startup_program.bat" to start the program
) else (
    echo.
    echo Dependencies installation failed
    echo Suggestion: Check network connection, or try this command:
    echo    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
)

echo.
echo Press any key to exit...
pause > nul 
