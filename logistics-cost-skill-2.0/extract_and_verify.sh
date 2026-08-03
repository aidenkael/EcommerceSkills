#!/usr/bin/env bash
# 物流2.0 Mac 解压与验证脚本
# 用法: bash extract_and_verify.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ZIP_FILE="$SCRIPT_DIR/logistics-cost-skill-2.0-macos-agent-v2.zip"
EXTRACT_DIR="$SCRIPT_DIR/logistics-cost-skill-2.0"

echo "===== 物流2.0 Mac 解压与验证 ====="
echo ""

# 1. 检查 ZIP 是否存在
if [ ! -f "$ZIP_FILE" ]; then
    echo "错误: 找不到 $ZIP_FILE"
    echo "请确保 ZIP 文件与本脚本在同一目录"
    exit 1
fi

# 2. 解压（使用 -o 覆盖，-q 静默）
echo "解压中..."
if [ -d "$EXTRACT_DIR" ]; then
    echo "  已存在 $EXTRACT_DIR，覆盖更新..."
fi
unzip -o -q "$ZIP_FILE" -d "$SCRIPT_DIR"

# 3. 验证关键目录和文件
echo "验证文件完整性..."
ERRORS=0

check_dir() {
    if [ -d "$EXTRACT_DIR/$1" ]; then
        echo "  ✓ $1/"
    else
        echo "  ✗ $1/ 缺失！"
        ERRORS=$((ERRORS + 1))
    fi
}

check_file() {
    if [ -f "$EXTRACT_DIR/$1" ]; then
        echo "  ✓ $1"
    else
        echo "  ✗ $1 缺失！"
        ERRORS=$((ERRORS + 1))
    fi
}

echo "核心目录:"
check_dir "logistics_cost"
check_dir "workflows"
check_dir "tools"
check_dir "templates"
check_dir "calibration"
check_dir "scripts"
check_dir "tests"
check_dir "examples"

echo "入口文件:"
check_file "agent_workflow.py"
check_file "run.py"
check_file "AGENTS.md"
check_file "START_HERE_FOR_AGENT.md"
check_file "MAC使用说明.md"
check_file "requirements.txt"
check_file "run_mac.sh"

echo ""
echo "Python 文件数: $(find "$EXTRACT_DIR" -name '*.py' -not -path '*__pycache__*' | wc -l | tr -d ' ')"

if [ $ERRORS -eq 0 ]; then
    echo ""
    echo "===== 验证通过 ====="
    echo ""
    echo "下一步:"
    echo "  cd logistics-cost-skill-2.0"
    echo "  python3 tools/mac_bootstrap.py"
    echo "  python3 agent_workflow.py prompt"
else
    echo ""
    echo "===== 发现 $ERRORS 个缺失项 ====="
    echo "请重新下载 ZIP 文件或联系发送者"
    exit 1
fi
