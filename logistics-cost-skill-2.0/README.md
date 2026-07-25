# 物流成本核算 (Logistics Cost Skill) — simple-v2.1

单件跨境物流头程成本核算工具。

## 使用

```powershell
# Codex AI JSON 模式
python run.py --ai-json examples/socks_ai.json --pretty

# 带可信重量 (65g)
python run.py --ai-json examples/socks_ai.json --weight-value 65 --weight-unit g --pretty

# 带 1688 链接 (仅保存, 不访问)
python run.py --ai-json examples/socks_ai.json --link https://detail.1688.com/offer/xxx.html --pretty
```

## 调用链

```
Codex Read (图片像素) → AI JSON → run.py → estimator → head cost
```

## 测试

```powershell
python -m pytest tests/ -v
```
