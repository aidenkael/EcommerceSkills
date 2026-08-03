# Mac 使用说明

## 系统要求

- macOS 10.15+ 或 Linux
- Python 3.9+（推荐 3.11+）
- 终端（Terminal）

## 快速开始

**⚠️ 重要：不要双击 ZIP 解压，请用终端命令：**

```bash
# 1. 解压并验证
cd ~/Desktop
unzip logistics-cost-skill-2.0-macos-agent-v2.zip
cd logistics-cost-skill-2.0
bash extract_and_verify.sh

# 2. 首次安装时运行环境检查
python3 tools/mac_bootstrap.py
```

环境检查只在首次安装或用户主动排错时运行。新建Agent对话不重复运行。

日常使用：在支持Agent的工具中打开 `logistics-cost-skill-2.0` 目录，让Agent先读取 `START_HERE_FOR_AGENT.md`。

或使用快捷脚本：
```bash
bash run_mac.sh
```

## 首次测试

```bash
python3 -m pytest tests/ -q
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

- **模式1（利润核算）**：识别商品 → 两档四方案头程 + 总成本与利润表
- **模式2（仅头程）**：识别商品 → 两档四方案头程表

两个模式在同一对话中互斥。模式只在当前对话有效。
