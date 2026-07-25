# 物流头程核算工具：Agent 项目守则

## 项目目标
读取 `input_images/` 中的商品图片，先由 Agent 进行谨慎的视觉判断，再调用本项目代码完成校准、计费、区间估算和复核标记。

## 必须遵守
1. 当前货代规则只读取 `config/freight_rules.json`。
2. **禁止使用旧的“包类 80 元/kg、非包类 100 元/kg”规则。** 历史包类字段仅用于找相似商品。
3. 图片没有尺寸或重量标注时，不得编造精确尺寸或重量，必须填 `null`。
4. 缺少信息时仍可给出校准区间，但必须保留 `needs_review` 与原因。
5. 不要改写 `data/source/` 和 `data/calibration_records.jsonl`。真实新反馈只追加到 `data/feedback.jsonl`。
6. 每次任务结束时，报告处理图片数、输出文件、需复核数量。

## Agent 标准执行流程
1. 阅读 `config/vision_prompt.txt` 和 `schemas/product_analysis.schema.json`。
2. 枚举 `input_images/` 中所有图片。
3. 逐张看图，将分析写入 `work/agent_analysis.jsonl`，每行一个 JSON。
4. 必须填写：`image_path`、`product_name`、`rigidity`、`package_type`、`confidence`、`evidence`。
5. 能确认重量/尺寸时再填 `actual_weight_kg`、`dimensions_cm`；不能确认就保持 `null`。
6. 执行：

```bash
python run.py estimate-agent --analysis work/agent_analysis.jsonl
```

7. 检查：
- `output/estimates.csv`
- `output/estimates.jsonl`

## 用户只说“根据图片核算”时
不要反复提问。直接按上述流程处理；信息不足的商品标记需复核。

## 真实反馈录入
用户提供真实头程费用后执行：

```bash
python run.py add-feedback --image input_images/示例.png --actual-cost 12 --product-name "商品名"
```

有真实重量或尺寸时一并传入。
