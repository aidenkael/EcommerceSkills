---
name: estimate-logistics-cost
description: 单件跨境物流头程成本核算。Codex 读取商品图片输出 AI JSON，Python 确定性计算头程运费和利润。
---

# 物流成本核算 v2.2 (OUTPUT_CONTRACT 2026-08-04-v1)

## 交互模式

两种互斥模式：1. 利润核算 / 2. 仅头程。模式仅当前对话有效。新对话第一次核算只输出模式菜单并停止；已选后后续商品直接沿用。利润模式缺参数时一次性询问全部缺失项并停止。

SHEIN 补贴阈值（<$29 补 $2.99）属于项目规则，不要求用户每次输入。

## 紧凑物理结构签名

每商品选择一个最匹配的基础形态（9 选 1）：soft_flat / soft_bulky / flexible_long / flexible_chain / semi_structured_hollow / hard_flat / hard_3d / mixed / unknown。4 个修饰符：nestable / articulated / fragile / hollow。

## 组件级字段

`rigid_body_size_cm`：运输时不可缩小的主体最小外廓。`shape_retention_scope`：body（主体保型）/ whole（整件不可折）/ none。`foldable_parts` / `detachable_parts`：可折/可拆部件列表。

半结构化包可：主体保型 + 把手折叠 + 肩带收纳 + 防尘袋 + 局部五金保护，不强制硬纸盒。

## 正常档与保守档

**正常档：** 最可能普通代发包装。合理折叠/收纳/压缩。把手折叠、肩带收纳、主体适度保持、袋装或局部保护。

**保守档：** 合理偏高成本场景。仍合理折叠把手、较少压缩、增加局部五金保护。只调整不确定因素，不机械放大。

## 货代费率与公式

| 货代 | 单价 | 固定费 |
|---|---|---|
| 深圳 | 80 元/kg | 10 元 |
| 义乌 | 100 元/kg | 6 元 |

```
体积重 = 长×宽×高(cm) ÷ 8000
计费重 = max(包装后重量, 体积重)
总头程 = 计费重 × 单价 + 固定费
```

四行方案固定顺序：义乌正常 / 义乌保守 / 深圳正常 / 深圳保守。

## 双售价利润模型 (模式1)

```
国内成本 = 采购价 + 国内运费
核算成本 C = 国内成本 + 最低总头程 + 尾程RMB
无活动售价USD = (C × (1+利润率)) ÷ 汇率
活动后售价USD = 无活动售价USD × (1-活动预留率)
补贴：售价<$29 时 +$2.99（按未舍入值判断）
利润 = 售价USD×汇率 + 补贴USD×汇率 - C
```

## 精确校准键查询（轻量快速路径）

日常核算中，在图片理解之后、AI JSON 构建之前，执行一次精确校准键查询：

1. 只查询 `knowledge/calibration_cases.jsonl`
2. 查询键：`normalized_title + selected_sku + quantity`
3. 命中条件：`status=validated` + `usage_scope=exact_product_sku_only` + 标题关键标识一致 + selected_sku完全一致 + quantity完全一致
4. 命中后直接使用该案例的 `calibrated_estimate_normal/conservative` 包装参数填入AI JSON
5. 结构字段按案例中 `runtime_overall_form` / `runtime_modifiers` / `shape_retention_scope` / `foldability` / `compressibility` / `requires_shape_retention` 等填入
6. 不得因运行时形态（如 `soft_bulky`）覆盖精确校准参数
7. 未命中立即继续现有AI快速估算，不做模糊搜索，不扫描其他案例

## AI JSON 格式

```json
{
  "product_type": "...", "quantity": 1,
  "overall_form": "semi_structured_hollow",
  "rigid_body_size_cm": [21, 28.5, 12],
  "foldable_parts": [{"name": "把手", "action": "折叠", ...}],
  "detachable_parts": [{"name": "肩带", "action": "拆卸收纳", ...}],
  "ai_net_weight_kg": 0.4, "ai_package_size_cm": [22, 30, 13],
  "ai_package_weight_kg": 0.43,
  "conservative_package_size_cm": [23, 31, 14],
  "conservative_package_weight_kg": 0.48,
  "confidence": "medium", "reasoning": "..."
}
```

`ai_package_size_cm` / `conservative_package_size_cm` = 已完成折叠/收纳/压缩/包装后的运输外廓。

## 输出格式

完整输出合同见 `OUTPUT_CONTRACT.md`，程序模板见 `logistics_cost/output_renderer.py`。

- 仅头程：商品摘要 → 四行七列表 → 推算句
- 利润核算：商品摘要 → 四行七列表 → 参数摘要 → 一行七列表 → 推算句
- 禁止：小结 / 临界点 / 案例引用 / 模式说明 / MEMORY 提示 / 风险段落 / 内部过程

## 日常运行限制

- 不读 knowledge/全部规则、不扫描案例库
- 不生成临时 AI JSON 文件、不写 MEMORY/日志、不执行 Git
- 默认读取：AGENTS.md / SKILL.md
- 日常最终回复 = `output_renderer` 返回值，Agent 不手工拼接表格

## CLI

```bash
python run.py --ai-json PATH [--compact]
echo '$JSON' | python run.py --stdin [--compact] [--render-markdown]
echo '$ENVELOPE' | python run.py --stdin --render-markdown
```
