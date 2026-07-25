---
name: estimate-logistics-cost
description: 单件跨境物流头程成本核算。Codex 读取商品图片输出 AI JSON, Python 确定性计算头程运费。支持用户可信净重修正、软品展开尺寸保护。
---

# 物流成本核算 (simple-v2.1)

## 入口

`python run.py --ai-json <Codex AI JSON> [--weight-value N] [--link URL]`

## 流程

```
Codex multimodal Read (读取商品图片像素)
  → AI JSON (product_type, ai_net_weight_kg, ai_package_size_cm, confidence...)
  → run.py 加载 + 校验
  → estimator.estimate()
    → 证据仲裁 → 软品检查 → 重量修正 → 确定性头程
  → 输出正常档/保守档/复核标记
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

必填: product_type, ai_net_weight_kg, ai_package_size_cm, ai_package_weight_kg, conservative_package_size_cm, conservative_package_weight_kg, confidence

`quantity_source` 三选一: user_confirmed / ai_inferred / assumed; 默认 assumed (暂按 1 件试算)。

## 规则

### 货代费率 (2026-07-26 生效)

| 货代 | 单价 | 固定服务费 |
|---|---|---|
| 深圳 (sz) | 80 元/kg | 10 元/单 |
| 义乌 (yw) | 100 元/kg | 6 元/单 |

- 体积重 = 长×宽×高 / 8000
- 计费重 = max(实重, 体积重)
- 包类/非包类只作为商品属性，不影响费率
- 默认货代: 当前未设定，需用户选择 (`config/default_freight_forwarder`, 设为 null)
- **旧规则 "包类80元/kg、非包类100元/kg" 已作废 (2026-07-26)**，仍在 config 中保留为 `categories._deprecated`

- 用户可信净重 → 净重 + 0.05kg
- 低可信/约值/未核实 → 回退 AI 估重
- 软品展开尺寸不得作为包装尺寸 (体积重>AI净重×3 自动忽略)
- 1688 链接只保存, 不访问网页

## 输出

成功: `{"status":"calculated","normal":{...},"conservative":{...},"ai_meta":{...}}`

受阻: `{"status":"blocked","review_reasons":[...]}`
