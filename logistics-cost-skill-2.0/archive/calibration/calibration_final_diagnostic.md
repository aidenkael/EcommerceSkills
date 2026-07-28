# CALIBRATION FINAL DIAGNOSTIC (v2 修正)

## 数据概览
- 总记录数: 77 (CAL-001 ~ CAL-077)
- 首次估算样本: 58
- 修正后样本: 15
- 排除样本: 19
- 独立商品组: 56

## 首次估算准确率（仅真正首轮估算）
- 命中(match): 5 (8.6%)
- 高估(overestimate): 20 (34.5%)
- 低估(underestimate): 33 (56.9%)
- 平均误差: 29.9%
- 中位误差: 20.0%

## 排除样本详情
- CAL-001: 非首次估算
- CAL-002: 非首次估算
- CAL-003: 无实际运费
- CAL-007: 非首次估算
- CAL-009: 非首次估算; 无实际运费
- CAL-016: 无实际运费
- CAL-021: 非首次估算
- CAL-026: 非首次估算
- CAL-031: 非首次估算
- CAL-033: 非首次估算
- CAL-037: 非首次估算
- CAL-038: 非首次估算
- CAL-041: 非首次估算
- CAL-044: 非首次估算
- CAL-047: 非首次估算
- CAL-054: 修正后命中, 不参与首次估算统计
- CAL-057: 修正后命中, 不参与首次估算统计
- CAL-062: 修正后命中, 不参与首次估算统计
- CAL-070: 实际尺寸已忘记; 方向未知

## 修正后样本
- CAL-001: est=55.0, act=44.2, dir=overestimate
- CAL-002: est=38.4, act=18.05, dir=overestimate
- CAL-007: est=73.9, act=18.5, dir=overestimate
- CAL-009: est=9.0, act=0, dir=underestimate
- CAL-021: est=0, act=4.75, dir=underestimate
- CAL-026: est=12.0, act=12.0, dir=match
- CAL-031: est=12.0, act=12.0, dir=match
- CAL-033: est=0, act=6.0, dir=underestimate
- CAL-037: est=10.0, act=12.0, dir=underestimate
- CAL-041: est=0, act=3.0, dir=underestimate
- CAL-044: est=17.3, act=19.0, dir=underestimate
- CAL-047: est=18.48, act=12.0, dir=overestimate
- CAL-054: est=8.0, act=8.0, dir=match
- CAL-057: est=14.0, act=14.0, dir=match
- CAL-062: est=10.0, act=10.0, dir=match

## 候选修正规则 (≥2独立组支持)
### 1. thin_soft_fabric_volume_correction
- 薄款针织/弹性面料(袜/袖套): 折叠后体积重偏高40-50%, 建议ai_package_size_cm厚度从4cm→3cm
- 支持条目: CAL-028, CAL-055, CAL-059, CAL-068, CAL-075
- 独立组数: 5
- ⚠️ 当前soft_volume_ignore阈值=×3(提高数值=更少忽略; 降低数值=更多忽略)。本建议只调ai_package_size_cm, 不修改阈值。

### 2. bag_three_tier_compression
- 包袋品类三档压缩: 皮包×0.65 / PVC全折叠3cm模板 / 布包×0.4
- 支持条目: CAL-065, CAL-068, CAL-076
- 独立组数: 3

### 3. rigid_protrusion_packaging
- 手柄/夹扣类硬质突出: 包装厚度≥本体+2cm, 配件重量额外计入
- 支持条目: CAL-047, CAL-054, CAL-056
- 独立组数: 3

## 方向判定方法
- 方向优先按 estimated vs actual 对比, 不按误差百分比正负号
- 原始 error_direction 不一致时以 est vs act 为准
- act=0 或无实际运费 → unknown

## 已排除/不修改
- Round 01 原始校准文件不变
- Round 02 原始校准文件不变
- 物流算法、配置、CAL 原始数据均未修改