@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
    echo Python launcher "py" was not found.
    echo Install Python 3.10 or newer, then run this file again.
    pause
    exit /b 1
)

py -3 -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    py -3 -m pip install "pyinstaller>=6.0,<7.0"
    if errorlevel 1 (
        echo PyInstaller installation failed.
        pause
        exit /b 1
    )
)

echo Building ProfitAccountingAuto.exe...
py -3 -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name ProfitAccountingAuto ^
    app.py

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build completed:
echo %CD%\dist\ProfitAccountingAuto.exe
echo User data will be stored under %%LOCALAPPDATA%%\ProfitAccountingAuto
pause
