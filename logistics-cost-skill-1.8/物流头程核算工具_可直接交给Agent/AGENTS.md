# AGENTS.md — 物流头程核算工具 v1.8

## 项目目标
读取 `input_images/` 中的商品图片，Agent 视觉判断 → 项目代码完成校准、计费、区间估算和复核标记。

## 业务规则

1. 货代规则只读取 `config/freight_rules.json`。
2. **禁止使用旧的"包类 80 元/kg、非包类 100 元/kg"规则**，历史包类字段仅用于找相似商品。
3. 图片无尺寸或重量标注时不得编造精确值，填 `null`。
4. 缺少信息仍可给出校准区间，但必须保留 `needs_review` 与原因。
5. 不改写 `data/source/` 和 `data/calibration_records.jsonl`。真实新反馈只追加到 `data/feedback.jsonl`。

## 标准执行流程

1. 阅读 `config/vision_prompt.txt` 和 `schemas/product_analysis.schema.json`
2. 枚举 `input_images/` 中所有图片
3. 逐张分析，写入 `work/agent_analysis.jsonl`（必填：image_path、product_name、rigidity、package_type、confidence、evidence）
4. 能确认重量/尺寸时填 `actual_weight_kg`、`dimensions_cm`，否则保持 `null`
5. 执行：`python run.py estimate-agent --analysis work/agent_analysis.jsonl`
6. 检查输出：`output/estimates.csv`、`output/estimates.jsonl`

## 用户说"根据图片核算"时
直接按上述流程处理，信息不足标记需复核，不要反复提问。

## 真实反馈录入
```bash
python run.py add-feedback --image input_images/示例.png --actual-cost 12 --product-name "商品名"
```
有真实重量或尺寸时一并传入。

## 测试
```bash
python -m pytest tests/ -v
```

---

> 本项目 v1.8 是独立版本，与 v2.0 采用不同架构（src/logistics_tool/ 包结构 + 校准图片）。
> 二者共存，各自维护各自的 AGENTS.md 和业务规则。
