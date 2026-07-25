# AGENTS.md — 物流成本核算 Skill v2.1

## 项目目标
电商单件跨境物流头程成本核算 Skill。Codex 读取商品图片 → 输出 AI JSON → Python 确定性计算。

## 业务规则

- 物流公式和费率只从 `config/logistics_config.json` 读取，不写死任何数值。
- AI JSON 格式参照 `examples/socks_ai.json`，包装方案必须提供 normal 和 conservative 两档。
- Python 负责：证据仲裁、软品检查、重量修正、确定性头程计算。
- 软品展开尺寸不得作为包装尺寸；体积重 > AI 净重 ×3 时自动忽略。
- 用户可信净重使用净重 + 0.05kg；低可信重量不得进入可信流程。
- 1688 链接只保存，不访问网页。
- 参数修改必须显示原值和建议值并由用户确认。
- 保持实现简洁，只修改任务所需内容。

## 入口
```bash
python run.py --ai-json <Codex AI JSON> [--weight-value N] [--link URL]
```

## 测试
```bash
python -m pytest tests/ -v
```
