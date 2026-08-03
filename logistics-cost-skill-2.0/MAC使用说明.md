# Mac 使用说明

## 系统要求

- macOS 10.15+ 或 Linux
- Python 3.9+（推荐 3.11+）
- 终端（Terminal）

## 快速开始

**⚠️ 重要：不要双击 ZIP 解压，请用终端命令：**

```bash
# 1. 解压并验证（替换 YOUR_ZIP 为实际文件名）
cd ~/Desktop
unzip logistics-cost-skill-2.0-macos-agent-v2.zip
cd logistics-cost-skill-2.0
bash extract_and_verify.sh

# 2. 运行环境检查（首次）
python3 tools/mac_bootstrap.py

# 3. 启动模式选择
python3 agent_workflow.py prompt
```

或使用快捷脚本：

```bash
bash run_mac.sh
```

## 首次测试

```bash
python3 -m pytest tests/ -q
python3 scripts/validate_active_rules.py
python3 scripts/replay_active_rules.py
```

## 常见问题

| 问题 | 解决 |
|------|------|
| `python3: command not found` | 安装 Python 3.9+：`brew install python3` 或从 python.org 下载 |
| `ModuleNotFoundError: No module named 'logistics_cost'` | ZIP 解压不完整，用终端 `unzip` 重新解压并运行 `bash extract_and_verify.sh` |
| `ModuleNotFoundError: No module named 'xxx'` | 运行 `pip3 install -r requirements.txt` |
| 中文显示乱码 | 终端设置 UTF-8：`export LANG=zh_CN.UTF-8` |
| `Permission denied` | 给脚本执行权限：`chmod +x run_mac.sh` |
| 目录或文件缺失 | 运行 `bash extract_and_verify.sh` 检查完整性 |

## 两个模式

- **模式1（仅校准头程）**：上传商品图片 → AI 识别 → CAL 校准 → 深圳/义乌头程计算 → 简表输出
- **模式2（完整物流与利润）**：先一次性配置汇率/利润率/佣金等参数 → 后续每个商品自动计算建议标价和预计利润

两个模式在同一对话中互斥，选定后不得切换。
