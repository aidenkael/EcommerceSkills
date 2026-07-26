@echo off
REM 步骤报告生成入口
REM 用法: run_step_report.bat [phase]
REM 示例: run_step_report.bat phase-2-1-s4
cd /d "%~dp0\.."
"Profit accounting-Auto\.venv-311\Scripts\python.exe" "tools\generate_step_report.py" %*
exit /b %errorlevel%
