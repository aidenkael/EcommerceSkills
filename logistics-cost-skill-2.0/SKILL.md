---
name: estimate-logistics-cost
description: 单件跨境物流头程成本核算。Codex 读取商品图片输出 AI JSON, Python 确定性计算头程运费。支持用户可信净重修正、软品展开尺寸保护。
---

# 物流成本核算 (simple-v2.1)

## 入口

CLI: `python run.py --ai-json <Codex AI JSON> [--weight-value N] [--link URL]`

Python: `from logistics_cost.ai_schema import estimate_from_ai_json`

## 流程

```
AI JSON → validate → to_estimate_inputs → estimator.estimate()
  → 证据仲裁 → 包装校验 → 软品检查 → 重量修正
  → 每家货代分别计算: 深圳 = 计费重 × 80 + 10, 义乌 = 计费重 × 100 + 6
  → 返回: provider_costs + recommended_provider + recommended_cost_rmb
```

## AI JSON 格式

```json
{
  "product_type": "mid_calf_socks",
  "quantity": 1,
  "quantity_source": "assumed",
  "category": "general",
  "rigidity": "soft",
  "foldability": "good",
  "compressibility": "good",
  "ai_net_weight_kg": 0.08,
  "ai_package_size_cm": [15, 10, 4],
  "ai_package_weight_kg": 0.09,
  "conservative_package_size_cm": [18, 12, 5],
  "conservative_package_weight_kg": 0.105,
  "confidence": "medium",
  "reasoning": "一句话判断理由"
}
```

## 规则

### 货代费率

| 货代 | 单价 | 固定服务费 |
|---|---|---|
| 深圳 | 80 元/kg | 10 元/单 |
| 义乌 | 100 元/kg | 6 元/单 |

- 体积重 = 长×宽×高 / 8000
- 计费重 = max(实重, 体积重)
- 每个包装档同时计算两家，推荐费用较低的货代
- 包类/非包类只作为商品属性，不影响费率
- **旧规则 "包类80/非包类100" 已作废 (2026-07-26)**，运行时不再读取

- 用户可信净重 → 净重 + 0.05kg
- 低可信/约值/未核实 → 回退 AI 估重
- 软品展开尺寸不得作为包装尺寸 (体积重>AI净重×3 自动忽略)
- 1688 链接只保存, 不访问网页

## 输出结构

```json
{
  "status": "calculated",
  "normal": {
    "chargeable_weight_kg": 0.12,
    "provider_costs": {
      "深圳货代": {"rate_per_kg_rmb": 80, "fixed_service_fee_rmb": 10, "total_cost_rmb": 19.6},
      "义乌货代": {"rate_per_kg_rmb": 100, "fixed_service_fee_rmb": 6, "total_cost_rmb": 18.0}
    },
    "recommended_provider": "义乌货代",
    "recommended_cost_rmb": 18.0
  },
  "conservative": { ... },
  "ai_meta": {...}
}
```
