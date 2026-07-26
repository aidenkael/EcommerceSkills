@echo off
setlocal
cd /d "%~dp0"

set VENV="%~dp0..\Profit accounting-Auto.venv\Scripts\python.exe"
set VENV_DIR="%~dp0..\Profit accounting-Auto.venv"

if not exist %VENV% (
    echo Virtual environment not found at %VENV_DIR%.
    echo Creating .venv...
    where py >nul 2>&1
    if errorlevel 1 (
        echo Python launcher "py" was not found. Install Python 3.10+.
        pause
        exit /b 1
    )
    py -3 -m venv %VENV_DIR%
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

%VENV% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller in .venv...
    %VENV% -m pip install "pyinstaller>=6.0,<7.0"
    if errorlevel 1 (
        echo PyInstaller installation failed.
        pause
        exit /b 1
    )
)

echo Building ProfitAccountingAuto.exe...
%VENV% -m PyInstaller ^
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
