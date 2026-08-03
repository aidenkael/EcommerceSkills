---
name: estimate-logistics-cost
description: 单件跨境物流头程成本核算。Codex 读取商品图片输出 AI JSON, Python 确定性计算头程运费。支持用户可信净重修正、软品展开尺寸保护。
---

# 物流成本核算 (simple-v2.1)

## 交互模式

### 正常核算模式

图片 → 生成 AI JSON → 运行 run.py → 输出简明结果

聊天窗口只显示：

```
商品名称：
识别置信度：
正常档：尺寸、包装重、计费重
保守档：尺寸、包装重、计费重
深圳纯头程：
义乌纯头程：
推荐货代：
需要复核：
```

**不得默认显示：**
- 完整 JSON
- 完整推算过程
- 每条规则匹配过程
- 全部证据对象
- 命令执行过程
- 长篇商品介绍
- 开发报告

完整 JSON 只有用户明确要求时才显示。

### 仅校准头程模式

如果用户没有提供以下信息，先询问：
- 实际纯头程金额
- 实际使用的货代
- 数量是否为单件

信息齐全后再执行：

图片识别 → 正常核算 → 与实际纯头程对比 → 判断偏高、偏低或接近 → 输出误差来源摘要

聊天窗口只显示：

```
估算纯头程：
实际纯头程：
绝对误差：
误差比例：
主要误差来源：
本案例是否适合进入校准资料：
建议：
```

详细推算过程不得默认贴入聊天。

### 统一简洁输出要求

- 不逐步汇报"正在读取文件""正在运行脚本"等过程
- 开始时最多一句"正在核算"
- 完成后直接给结果
- 正常结果控制在一个屏幕以内
- 只给简短判断依据，不输出隐藏推理过程
- 发生阻断时，只说明缺少什么以及用户需要补充什么

## 入口

CLI: `python run.py --ai-json <Codex AI JSON> [--weight-value N] [--link URL]`

Python: `from logistics_cost.ai_schema import estimate_from_ai_json`

## 流程

```
AI JSON → validate → to_estimate_inputs → estimator.estimate()
  → 证据仲裁 → 包装校验 → 统一软品策略 → 重量修正
  → 每家货代分别计算: 深圳 = 计费重 × 80 + 10, 义乌 = 计费重 × 100 + 6
  → 单调性保护: 保守档费用不得低于正常档
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
  "overall_form": "soft_flat",
  "ai_net_weight_kg": 0.08,
  "ai_package_size_cm": [15, 10, 4],
  "ai_package_weight_kg": 0.09,
  "conservative_package_size_cm": [15, 10, 5],
  "conservative_package_weight_kg": 0.10,
  "conservative_risk_basis": "thickness_uncertainty",
  "confidence": "medium",
  "reasoning": "一句话判断理由"
}
```

## 正常档与保守档语义 (v2)

### 正常档
根据当前证据，**最可能实际发生的单件运输包装场景**。

优先采用顺序：商家明确运输包装 > 用户确认包装 > 有可靠依据的AI包装估算 > 结构经验回退。

正常档不是"最小可能包装"，不得为了降低费用而过度压缩。

### 保守档
在证据不确定范围内，**合理但偏高成本的场景**。

保守档**不是**所有尺寸统一增加，**不是**重量固定增加，**不是**最坏极端情况。

生成原则：
1. 先估正常档 → 说明不确定因素 → 只调整真正不确定的因素形成保守档
2. 有商家明确包装时两档**可以相同** (`conservative_risk_basis = known_package_no_uncertainty`)
3. 保守档**不是固定放大**，不得机械增加每个轴
4. 若保守档成本低于正常档，必须视为**规则冲突**，不得解释为合理结果
5. 填写 `overall_form` 和 `conservative_risk_basis`

### overall_form 取值

| 值 | 说明 | 两档示例 |
|----|------|---------|
| `soft_flat` | 柔软片状(袜/手套/丝巾) | 正常15×10×3, 保守15×10×4(仅增厚度) |
| `soft_bulky` | 柔软蓬松(玩偶/毛衣) | 正常20×15×8, 保守20×15×11(少压缩) |
| `flexible_chain` | 柔性链状(腰链/项链) | 正常15×10×3, 保守15×10×3(仅增重量) |
| `hard_flat` | 硬质扁平(卡/镜) | 正常15×10×2, 保守15×10×3(仅增缓冲) |
| `hard_3d` | 硬质立体(杯/摆件) | 有缓冲空间, 保护面增加 |
| `mixed` | 混合(软体+硬底) | 软部分定压缩, 硬部分定外廓 |
| `unknown` | 未分类 | 两档相同, 标记复核 |

### conservative_risk_basis 取值

| 值 | 含义 |
|----|------|
| `known_package_no_uncertainty` | 明确包装, 两档相同 |
| `weight_uncertainty` | 重量不确定 |
| `thickness_uncertainty` | 折叠/压缩厚度不确定 |
| `compression_uncertainty` | 压缩程度不确定 |
| `protection_uncertainty` | 保护空间不确定 |
| `quantity_uncertainty` | 数量不确定 |
| `mixed_uncertainty` | 多种不确定 |
| `unknown` | 未指定

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
