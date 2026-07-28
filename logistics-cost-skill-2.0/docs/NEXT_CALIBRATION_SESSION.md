# 下一轮校准会话

## 当前基线

- **Commit**: `cadb176387d5aa1382b03ed3e5eac294962c3574`
- **分支**: `integration/logistics-calibration-v1`
- **内容**: CAL-001 至 CAL-051 原始数据、清洗和回放报告、超轻重量规则、全部 AI JSON 和校准脚本

## 下一条起始编号

**CAL-052**

## 校准流程

1. **每测试一个新商品，只追加一条 CAL 记录和对应 AI JSON。**
2. 每条 CAL 记录必须包含：
   - 实际运费（头程）
   - 货代来源
   - 商品重量
   - 包装尺寸
   - 误差原因
   - 证据来源（evidence_level）
3. **不得修改旧 CAL 记录**（CAL-001 至 CAL-051 保持不变）。
4. 不要每增加一条就调整算法。
5. 等我明确说「本批数据完成」后，再统一清洗、回放和最终校准。

## 数据文件

- 原始数据追加到: `archive/calibration/calibration_samples_round_02.json`
- AI JSON 保存到: `examples/` 目录

## 接入 Profit accounting-Auto

最终校准通过后，才接入 Profit accounting-Auto。
在此之前两个项目独立运行。
