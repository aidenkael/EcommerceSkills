# 校准数据验证报告 v1

> 日期: 2026-07-28
> 原始文件: `archive/calibration/calibration_samples.json`
> 清洗文件: `archive/calibration/calibration_samples_cleaned_v1.json`

## 一、概览

| 指标 | 值 |
|------|-----|
| 记录总数 | 29 (CAL-001 ~ CAL-029) |
| 排除出数值校准 | 3 条 (CAL-009, CAL-026, CAL-029) |
| 计入数值校准 | 26 条 |
| 原始文件是否修改 | 否 (仅生成清洗副本) |

**注意**: Agent 指令预期 51 条，实际文件为 29 条。指令中引用的 CAL-030~CAL-051 不存在。本报告以实际数据为准。

## 二、已知问题处理

### 已修正 (1 条)

| 样本 | 问题 | 修正 |
|------|------|------|
| CAL-017 | `error_direction` 错误标记为 `overestimate` | 更正为 `underestimate` (估6.05元 < 实际12.35元) |

### 已排除 (3 条)

| 样本 | 原因 | evidence_level |
|------|------|---------------|
| CAL-009 | 数据冲突: actual_head_freight(18.9)与 actual_chargeable_weight(0.189)与 notes 中的 0.236kg 不一致 | manual_review_required |
| CAL-026 | 需复核: 根因名称 `EXACT_MATCH_VIA_CONSERVATIVE` 与说明中正常档/保守档结论不一致 | manual_review_required |
| CAL-029 | 货代不确定: 深圳或义乌无法确定 | forwarder_uncertain |

## 三、字段拼写修正

以下记录的 `1638_display_size_cm/volume_cm3/listed_weight_g` 统一修正为 `1688_*`:

- CAL-001: 1638_display_size_cm, 1638_display_volume_cm3, 1638_listed_weight_g
- CAL-005: 1638_display_size_cm
- CAL-007: 1638_display_size_cm, 1638_listed_weight_g

## 四、数据质量分级

### evidence_level 分布

| 等级 | 数量 | 含�� |
|------|------|------|
| actual_package_measured | 2 | 有实际打包尺寸+重量+计费重 |
| actual_measured | 2 | 有实际尺寸或重量 |
| freight_inferred | 22 | 仅有头程运费反推 |
| forwarder_uncertain | 1 | 货代不确定 (CAL-029) |
| manual_review_required | 2 | 需人工复核 (CAL-009, CAL-026) |

### data_quality_status 分布

| 状态 | 数量 |
|------|------|
| ok | 25 |
| conflict | 1 (CAL-009) |
| needs_review | 3 (CAL-026, CAL-029) |

## 五、自动检查结果

### error_direction 一致性

无新增异常 (除 CAL-017 已手动修正外)。

### 费用与计费重一致性

所有样本的 actual_head_freight_rmb 与 actual_chargeable_weight_kg × 货代费率偏差均在 0.5 元以内，无异常。

### 单位检查

无单位异常 (所有 _g 字段均 < 50000)。

### 区间值样本

- CAL-003: actual_head_freight_range_rmb, actual_chargeable_weight_range_kg
- CAL-011: actual_head_freight_range_rmb
- CAL-016: actual_head_freight_range_rmb, actual_chargeable_weight_range_kg

以上区间值已保留原样，未误当单点值。

## 六、新增字段说明

| 字段 | 说明 |
|------|------|
| data_quality_status | ok / conflict / needs_review |
| data_quality_issues | 问题列表 |
| exclude_from_numeric_calibration | true=排除出精确数值校准 |
| evidence_level | actual_package_measured / actual_measured / freight_inferred / range_inferred / forwarder_uncertain / manual_review_required |
