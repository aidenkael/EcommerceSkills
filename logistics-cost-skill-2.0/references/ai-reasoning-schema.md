# Accuracy-first AI推理输入契约

新入口允许AI提出包装方案，但Python保留证据硬拒绝、包装不变量校验和全部费用计算权。旧 `visual` 入口仍遵守 `visual-facts-schema.md`，不得包含包装结果。

## 顶层结构

```json
{
  "input_type": "image",
  "image_path": "C:/path/product.png",
  "product_summary": {},
  "raw_extracted_evidence": [],
  "ai_evidence_review": {},
  "packaging_scenarios": {},
  "self_review": {},
  "warnings": []
}
```

`input_type` 支持 `image`、`screenshot`、`page_text`、`mixed`。没有真实AI Adapter时，先由外部模型按此契约生成JSON，再交给CLI。

## 第一轮：商品事实与原始证据

### `product_summary`

```json
{
  "product_type": "soft_headband",
  "category_type": "general",
  "material": "textile",
  "rigidity": "soft",
  "foldability": "good",
  "compression": "good",
  "fragility": "low",
  "has_rigid_parts": false,
  "requires_shape_retention": false,
  "includes_gift_box": false,
  "quantity": 1,
  "confidence": "medium"
}
```

### `raw_extracted_evidence`

每条证据尽量保留原文、单位和来源：

```json
{
  "evidence_type": "dimension",
  "raw_text": "Unfolded size: 80 x 8 x 1 cm",
  "value": [80, 8, 1],
  "unit": "cm",
  "source": "page_text",
  "interpreted_as": "unfolded_flat_size",
  "sku_scope": "selected",
  "quantity_basis": 1,
  "confidence": "high"
}
```

尺寸语义：

- `packaged_size`
- `product_body_size`
- `unfolded_flat_size`
- `wearing_size`
- `size_chart`
- `carton_size`
- `variant_max_size`
- `unknown_context`

重量语义：

- `gross_weight`
- `net_weight`
- `shipping_weight`
- `carton_weight`
- `variant_max_weight`
- `unknown_context`

来源：`user_provided`、`page_text`、`ocr`、`image_visual`、`unknown`。

## 第二轮：AI证据复核

`value`必须有明确且不冲突的单位；只有字段本身为`value_cm/value_kg`时可省略单位。销售数量大于1时，每条将被采用的尺寸和重量证据都必须提供与销售数量一致的`quantity_basis`。页面低置信度数据只作辅助，`shipping_weight`不能代替包装毛重。

当前选定变体必须在商品摘要与尺寸、重量证据中一致；混合SKU或最大变体数据直接拒绝。


AI可以指出需要拒绝的证据索引：

```json
{
  "rejected_evidence_indices": [2],
  "reasoning": "第2条为整箱箱规"
}
```

Python仍会独立检查单位、整箱关键词、SKU范围、商品类别异常和图文冲突。AI不能让Python硬拒绝的数据恢复为可信数据。

## 第三轮：包装方案

必须同时提供正常和保守两档：

```json
{
  "normal": {
    "packaged_size_cm": [18, 12, 3],
    "packaged_weight_kg": 0.08,
    "method": "OPP袋",
    "folding_action": "常规折叠",
    "compression_action": "轻度压缩",
    "requires_box": false,
    "requires_bubble_wrap": false,
    "used_evidence_indices": [0, 1],
    "reason": "页面为展开尺寸，软商品可折叠后装袋",
    "confidence": "medium"
  },
  "conservative": {
    "packaged_size_cm": [22, 15, 4],
    "packaged_weight_kg": 0.11,
    "method": "稍大外袋",
    "folding_action": "较少折叠",
    "compression_action": "弱压缩",
    "requires_box": false,
    "requires_bubble_wrap": false,
    "used_evidence_indices": [0, 1],
    "reason": "增加合理厚度和包材余量，但不复用展开外廓",
    "confidence": "medium"
  }
}
```

`used_evidence_indices`必须是非空整数数组，并同时引用Python已采用的尺寸/折叠依据和重量证据；引用已拒绝、降权或不存在的索引会阻断计算。

所有AI轮次都禁止夹带：头程费用、费率、体积除数、体积重、计费重量、尾程、服务费、汇率或总成本；包装方案还不得另行指定分类。

## 第四轮：自我复核

```json
{
  "needs_review": true,
  "review_reasons": [
    "页面只有展开尺寸，折叠后的厚度仍依赖视觉判断"
  ]
}
```

AI复核只能增加风险，不能清除Python已经产生的复核标记，也不能修改Python计算结果。

## Python硬拒绝示例

- 原文包含 `carton`、`outer box`、`case pack`、`整箱`、`箱规`、`装箱数`；
- `size_chart`、`carton_size`、`variant_max_size/weight`；
- 多个SKU混合但没有选择当前变体；
- 小饰品重量或体积重超过配置阈值；
- 软袋候选体积重异常；
- 页面与图片尺度严重冲突；
- 毛重小于净重；
- AI包装直接复用已拒绝尺寸；
- 硬质或需保形商品被强折，硬质商品被压缩；
- 保守档体积或重量小于正常档。

## 离线运行

```powershell
python calc_logistics.py estimate --head-only --input sample.json --pretty
```

图片配合外部AI JSON：

```powershell
python calc_logistics.py estimate --head-only --input product.png --ai-json product_ai.json --pretty
```

未来真实模型接入需实现 `ReasoningAdapter.run_round(round_name, payload)`，四轮名称为：`visual_extraction`、`evidence_arbitration`、`packaging_decision`、`self_review`。
