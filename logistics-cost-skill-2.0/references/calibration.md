# 实际头程金额校准

## 能校准什么

按 `category_type` 费率用实际头程金额反推实际计费重量。它可以校准：

- 商品/结构是否路由到正确包装行为；
- 正常—保守计费重量区间是否覆盖实际；
- 折叠、压缩、包材余量是否长期偏乐观或偏保守；
- bag/general、数量和页面参数含义是否识别错误。

实际金额不能证明真实长度、宽度、高度或重量，也不能单独区分体积重和实重原因。

## 原因判断顺序

1. 检查实际是否位于正常—保守费用区间；落入时优先视为合理操作波动。
2. 检查数量、bag/general、裸品/包装、净重/毛重含义。
3. 检查原估算由体积重还是包装后重量主导。
4. 体积重主导时复查形状、折叠、硬件、保护空间和最大外廓范围。
5. 实重主导时复查数量、配件、礼盒、包材和视觉重量范围。
6. 无原估算上下文时只记录低置信度原因，不编造尺寸结论。

## 聚合规则

- 金额误差不超过5元且比例不超过10%：记录为正常波动。
- 超过任一阈值：标记关注并生成原因诊断。
- 同一画像连续2次低估：提示复查保护空间、硬件和不可压缩部位。
- 同一画像与尺寸级别少于5条只监测；达到5条可给出初步审查，建议达到5—10条再稳定修改。
- 报告使用反推计费重量 P25/P50/P75/P90 和正常—保守区间覆盖率，不使用统一乘数。
- 不以单条异常修改画像，不根据金额反推真实尺寸。
- 参数建议只修改路由或包装行为；应用前显示原值和建议值并等待 Y/N。

## 操作

逐条录入：

```powershell
python feedback_correction.py add
```

批量导入：

```powershell
python feedback_correction.py import --file input_feedback.csv
```

刷新原因和报告：

```powershell
python feedback_correction.py rebuild-diagnoses
python feedback_correction.py report
```

人工复核原图、路由和聚合报告后，把建议的行为参数写成JSON，再确认应用：

```powershell
python feedback_correction.py apply-suggestion --profile-key <画像键> --proposal <建议.json>
```
