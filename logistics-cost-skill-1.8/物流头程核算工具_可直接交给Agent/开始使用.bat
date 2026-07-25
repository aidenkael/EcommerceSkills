@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo 物流头程核算工具
echo ========================================

where python >nul 2>nul
if errorlevel 1 (
  echo 未找到 Python。请让 Agent 在本目录运行，或先安装 Python 3.10+。
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 正在创建本地运行环境...
  python -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --disable-pip-version-check -q -r requirements.txt
python run.py self-check
if errorlevel 1 (
  echo 自检未通过，请把终端输出交给 Agent 修复。
  pause
  exit /b 1
)

python run.py estimate-images --input input_images --provider auto

echo.
echo 完成。请查看 output 文件夹；若生成了 work\agent_analysis.jsonl，
echo 请在 Agent 中打开本目录并说：读取 AGENTS.md 后完成物流核算。
pause
