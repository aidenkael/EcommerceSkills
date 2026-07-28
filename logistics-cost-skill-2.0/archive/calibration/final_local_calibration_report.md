# logistics-cost-skill-2.0 最终本地规则校准报告

> 日期：2026-07-28
> 基线提交：`0ff62604282a0a471bd28cde7e4d0519389fadc5`
> 数据：`archive/calibration/calibration_all_cleaned_v3.json`

## 1. 修改文件

- 配置：`config/packaging_calibration_profile_v1.json`
- Schema 与链路：`logistics_cost/ai_schema.py`、`logistics_cost/estimator.py`
- 校准层：`logistics_cost/packaging_calibration.py`
- 安全校验：`logistics_cost/evidence_resolver.py`、`logistics_cost/packaging_decision_ai.py`
- 回放：`scripts/final_calibration_replay.py`
- 测试：`tests/test_final_calibration.py`
- 回放夹具：9 个既有代表 CAL 的 JSON 补充结构字段；CAL-055/059 仅依据现有 CAL 记录补齐缺失夹具

## 2. 校准配置结构

配置包含 `schema_version`、`profile_version`、`generated_at`、`source_commit`、`enabled`、适用范围、五种 `supported_packaging_states`、`active_rules`、`tentative_rules`、`observation_rules`、`safety_limits` 和 `evidence_refs`。

每条规则均为“结构化条件 + 比例区间 + 禁止条件 + CAL 证据”，没有使用商品名称或 CAL 编号作为生产判断分支。配置损坏、缺字段或 schema 不合法时使用内置安全默认：不自动压缩、继续核心计算、输出明确警告并要求复核。

## 3. 正式启用规则

| 规则 | 条件摘要 | 区间/作用 | 支持与反例 |
|---|---|---|---|
| `structure_safety_guard` | 硬底、硬背板、框架、定型衬、保形、零售盒任一为真或关键状态未知 | 禁止激进压缩 | 反例 CAL-045/064/075 |
| `thin_soft_fabric_fold` | 薄/蕾丝/冰丝标记与 fabric/knit/lace 等面料族同时成立，且明确无硬卡 | 正常厚度比 0.55–0.75，保守 0.8–1.0；重量规则与体积规则分离 | CAL-032/049/055/059 |
| `full_flat_fold` | `packaging_state=full_flat_fold` 且所有硬结构字段明确为 false | 正常档按原候选比例折叠；保守档只按强压缩；不使用固定尺寸模板 | CAL-068；边界 CAL-075 |
| `strong_compression` | `packaging_state=strong_compression` 且所有硬结构字段明确为 false | 正常厚度比 0.4–0.6，保守 0.65–0.8 | CAL-076；反例 CAL-045/064 |

## 4. 暂定规则

| 规则 | 状态 | 原因 |
|---|---|---|
| `moderate_compression` | tentative、条件满足时可运行并强制留痕 | CAL-065 支持，但 CAL-045/064 证明定型、硬衬、盒装必须排除 |
| `soft_flattened_protrusion` | tentative、与 moderate/strong 状态组合 | CAL-047 单一独立样本；历史约 2cm 未写成固定厚度 |

## 5. 观察规则

`thin_soft_fabric_weight` 保留为 observation，不自动改重。CAL-004/014/016/018/024/028 只支持重量观察；多件装应为单件重量乘数量并单独加入共同包材、纸卡、吊牌和挂钩，未与 CAL-055/059 的体积修正混为一组。

## 6. Schema、作用域与保护

新增可选字段保持旧 JSON 兼容：`dimension_scope`、`weight_scope`、`packaging_state`、硬底/背板/框架/定型衬、保形、零售盒、硬卡、突出部件可压平、`packaging_method`、`proposal_source`、`reasoning_summary`、`confidence`、`needs_review`、`default_fields_used`。

- 未知硬结构字段使用 `null`，不等价于 false。
- `shipping_package_size` 映射为 `packaged_size`，不会被软品体积忽略，也不会被本地校准改写。
- `display_size`/`product_size` 只映射为商品本体上下文，不冒充包装尺寸。
- `packaged_weight` 进入毛重路径；`net_weight` 只进入净重路径；`unknown` 不被当成包装重量。
- 旧 `user_weight_kg` 会进入重量规则；未附可信状态时按“未核实”并要求复核。
- 兼容默认 50g、60g、15×10×4cm 等仍可计算，但会写入 `default_fields_used`、降低为 low confidence，并设置 `needs_review=true`。
- `proposal_source=external_ai/vision_api` 时，本地规则不静默覆盖候选；冲突输出原始值、拟调整值、冲突原因和复核标记。

## 7. 回放口径

- 源文件共 77 条。
- 71 条标记为可用于准确率评估。
- 6 条按原清洗口径排除：CAL-009/029/054/057/062/070，没有新增排除。
- 基线提交实际可回放 65 条；CAL-052/053/055/056/058/059 的 AI JSON 缺失。
- 本次仅补齐任务明确要求的 CAL-055/059 回放夹具，最终可回放 67 条。
- CAL-052/053/056/058 仍缺夹具；没有把它们计为成功或用零值代替。
- 回放 blocked/异常为 0。

## 8. 总体前后指标

为避免通过增加夹具改变统计口径，主前后比较使用相同的 65 条可比样本。

| 档位/指标 | 修改前 | 修改后 |
|---|---:|---:|
| 正常档 MAE | 4.37 元 | 2.48 元 |
| 正常档中位绝对误差 | 1.75 元 | 1.75 元 |
| 正常档平均百分比误差 | 33.04% | 23.07% |
| 正常档中位百分比误差 | 20.00% | 20.00% |
| 正常档 ≤5元 | 55/65 | 59/65 |
| 正常档 高估/低估/命中 | 24/33/8 | 20/37/8 |
| 保守档 MAE | 6.68 元 | 5.02 元 |
| 保守档中位绝对误差 | 2.95 元 | 2.95 元 |
| 保守档平均百分比误差 | 51.06% | 44.66% |
| 保守档中位百分比误差 | 30.86% | 30.43% |
| 保守档 ≤5元 | 48/65 | 49/65 |
| 保守档 高估/低估/命中 | 47/12/6 | 47/12/6 |

最终 67 条全可用回放：正常档 MAE 2.42 元、中位绝对误差 1.40 元、平均百分比误差 22.53%、中位百分比误差 20.00%、≤5元 61 条、高估/低估/命中 21/37/9；保守档 MAE 4.96 元、中位绝对误差 2.95 元、平均百分比误差 45.26%、中位百分比误差 30.86%、≤5元 51 条、高估/低估/命中 49/12/6。

## 9. 软品与非软品表现

相同 7 条软品可比样本的正常档：MAE `21.07 → 3.50 元`，中位绝对误差 `7.50 → 3.00 元`，平均百分比误差 `114.56% → 22.01%`。保守档 MAE `32.19 → 16.74 元`，仍明显偏保守，符合风险上界定位但不是准确点估计。

最终 9 条软品正常档：MAE 2.78 元、中位绝对误差 2.00 元、平均百分比误差 18.23%、中位百分比误差 12.50%、≤5元 8 条。58 条非软品正常档前后完全相同：MAE 2.36 元、中位绝对误差 1.33 元、平均百分比误差 23.20%；说明本轮没有通过牺牲非软品提高软品成绩。

## 10. 代表 CAL 前后结果

数值为纯头程费用“正常档 / 保守档 / 实际”，单位元。

| CAL | 修改前 | 修改后 | 结论 |
|---|---:|---:|---|
| CAL-032 | 11.55 / 17.25 / 9.00 | 7.00 / 15.52 / 9.00 | 正常档绝对误差 2.55→2.00，改善 |
| CAL-047 | 18.48 / 26.68 / 12.00 | 16.00 / 24.02 / 12.00 | 柔软突出部件压平，改善；规则仍 tentative |
| CAL-049 | 11.55 / 17.25 / 8.00 | 7.00 / 12.51 / 8.00 | 正常档误差 3.55→1.00，改善 |
| CAL-055 | 7.50 / 不可回放 / 5.00 | 5.50 / 6.75 / 5.00 | 补齐现有记录夹具后可回放，正常档改善 |
| CAL-059 | 6.00 / 不可回放 / 5.00 | 5.00 / 9.72 / 5.00 | 补齐现有记录夹具后正常档命中 |
| CAL-065 | 71.82 / 107.52 / 57.00 | 52.00 / 71.28 / 57.00 | 正常档误差 14.82→5.00，改善 |
| CAL-068 | 43.56 / 48.40 / 7.00 | 10.00 / 35.09 / 7.00 | 严重高估明显下降；未使用 10×10×3 固定模板 |
| CAL-075 | 16.00 / 22.26 / 23.50 | 16.00 / 22.26 / 23.50 | 有底厚款 PVC 未套全折叠，边界保持 |
| CAL-076 | 156.00 / 180.00 / 80.00 | 78.00 / 130.50 / 80.00 | 正常档严重高估下降，误差 76→2 |

反例 CAL-045 保持 `39.60 / 48.00 / 39.00`，CAL-064 保持 `52.00 / 60.00 / 53.00`，均未被软品规则压缩。

## 11. 未解决问题

- CAL-052/053/056/058 缺少既有 `ai_json_path` 所指向的文件，未自行补录未知事实，因此最终回放数为 67 而非 71。
- 软品保守档仍偏高，尤其 CAL-068/076；它代表少压缩风险上界，不应替代正常档点估计。继续收紧需要新的独立证据，本次没有为提高成绩强改。
- `moderate_compression` 与 `soft_flattened_protrusion` 证据独立组数仍少，保留 tentative。

## 12. 费用公式与系统边界

本次没有修改 `config/logistics_config.json` 或 `logistics_cost/calculator.py`，核心规则保持：

- 深圳货代 80 元/kg + 10 元固定服务费；
- 义乌货代 100 元/kg + 6 元固定服务费；
- 体积重 = 长×宽×高÷8000；
- 计费重取实际重量与体积重较大值；
- 最低纯头程费用 3 元。

最终费用仍只由 Python 确定性计算层产生。未接入外部 AI API、HTTP、数据库、UI、1688 采集、尾程、利润公式，也未接入 `Profit-Accounting-2.6` 或 `Profit accounting-Auto`。
