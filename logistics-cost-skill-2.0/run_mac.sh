#!/usr/bin/env bash
# 物流2.0 Mac 快捷启动脚本
set -e

cd "$(dirname "$0")"

echo "===== 物流2.0 工具 ====="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 请先安装 Python 3.9+"
    echo "  brew install python3"
    exit 1
fi

# 首次运行环境检查
if [ ! -d ".venv" ] || [ ! -f ".bootstrapped" ]; then
    echo "首次运行，检查环境..."
    python3 tools/mac_bootstrap.py
    touch .bootstrapped
    echo ""
fi

# 启动模式选择
python3 agent_workflow.py prompt
