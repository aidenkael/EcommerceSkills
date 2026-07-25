# API 说明

启动：

```bash
python run.py serve --host 127.0.0.1 --port 8765
```

## 健康检查
`GET /health`

## 结构化核算
`POST /v1/estimate`

请求示例：

```json
{
  "analysis": {
    "image_path": "input_images/example.png",
    "product_name": "金属卡夹",
    "keywords": ["卡夹", "金属"],
    "rigidity": "hard",
    "package_type": "气泡膜+小纸盒",
    "actual_weight_kg": 0.08,
    "dimensions_cm": [8, 5, 2],
    "confidence": "high",
    "evidence": "商品页标注 80g，尺寸 8×5×2cm"
  },
  "tail_cost_rmb": null
}
```

默认只返回头程。只有显式传入 `tail_cost_rmb` 时，才会计算 `optional_total_logistics_rmb`。

## 图片核算
`POST /v1/estimate-image`

```json
{
  "image_path": "input_images/example.png",
  "provider": "auto"
}
```

需要 `.env` 已配置视觉提供方。

## 追加反馈
`POST /v1/feedback`

```json
{
  "image_path": "input_images/example.png",
  "product_name": "金属卡夹",
  "actual_allocated_head_cost_rmb": 12,
  "actual_weight_kg": 0.08,
  "dimensions_cm": [8, 5, 2],
  "notes": "真实发货反馈"
}
```
