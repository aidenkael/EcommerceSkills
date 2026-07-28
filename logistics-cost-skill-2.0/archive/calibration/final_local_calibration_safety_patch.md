# 最终本地校准安全补丁报告

> 复审基线：`15ce7ddd2fc3a9879bd919eb972319905e75604b`

## 1. 复审发现的三个问题

1. `tentative_rules` 中的规则参与尺寸调整后，没有稳定地把正常档、保守档和最终结果标记为需要人工复核。
2. `soft_flattened_protrusion` 只检查 `protrusion_flattenable=true`，没有同时执行规则配置中的 `conditions.packaging_states`。
3. 外部 AI 候选与本地规则冲突时虽然没有静默覆盖 AI，但审计元数据只记录冲突文本，没有保存本地原拟调整方案和触发规则。

## 2. 修改文件

- `logistics_cost/packaging_calibration.py`
- `logistics_cost/estimator.py`
- `tests/test_final_calibration.py`
- `archive/calibration/final_local_calibration_safety_patch.md`

`estimator.py` 只增加场景 `needs_review` 标记的输出传播，使正常档和保守档能显式展示包装规则复核状态；没有改变尺寸、重量、计费重或费用计算。

## 3. 暂定规则复核机制

规则查找现在返回 `(rule, rule_group)`，可区分 `active`、`tentative` 和 `observation`。生产调整只搜索 active 与 tentative；observation 不参与候选尺寸生成。

任意 tentative 规则实际参与本地尺寸调整时：

- 正常档与保守档的 `needs_review` 均设为 `true`；
- 最终结果 `needs_review=true`；
- `review_reasons` 加入包含规则 ID 的明确暂定提示；
- `packaging_calibration.applied_rule_details` 记录 `rule_id`、`rule_group=tentative`、触发原因和 `evidence_refs`；
- `packaging_calibration.needs_review=true`。

active 规则不会仅因为所属 active 组而自动产生“暂定规则”提示。

## 4. 柔软突出部件状态限制

`soft_flattened_protrusion` 现在同时要求：

- `protrusion_flattenable=true`；
- 当前 `packaging_state` 位于规则自身 `conditions.packaging_states`。

当前配置只允许 `strong_compression` 和 `moderate_compression`。因此 `full_flat_fold`、`shape_retained` 和 `unknown` 不会触发突出部件规则。原有全结构字段必须明确为 false 的安全门仍在规则匹配之前执行，突出规则不能绕过硬底、硬背板、框架、硬质内衬、保形、零售盒、硬卡或未知结构保护。

## 5. 外部 AI 冲突审计

当 `proposal_source=external_ai` 或 `vision_api` 且本地候选与 AI 候选不同：

- `original_scenarios` 保存 AI 原始正常档和保守档；
- `local_proposed_scenarios` 保存本地规则拟调整后的完整两档方案；
- `adjusted_scenarios` 继续等于 AI 原始方案；
- `conflicts` 保存冲突原因；
- `proposed_rule_ids` 保存导致候选变化的规则 ID；
- `proposed_rule_details` 保存规则组、触发原因和证据引用；
- `needs_review=true`。

本地拟调整方案只进入审计元数据，没有进入物流费用计算。

## 6. 新增专项测试

新增覆盖：

- moderate tentative 两档与最终复核标记；
- soft protrusion 在允许状态参与并要求复核；
- soft protrusion 在 `full_flat_fold` 下不参与；
- `shape_retained` 禁止突出规则且不改尺寸；
- external AI 同时保留原始、本地拟调整和最终方案；
- active strong compression 不被误标 tentative；
- CAL-045/064/068/075/076 金额回归保护。

专项测试结果：`21 passed`。

## 7. 完整测试

- 修改前基线：`50 passed`
- 修改后项目全量：`61 passed`

## 8. 回放金额一致性

两套回放均与 `15ce7ddd` 完全一致：

- 全部可用回放：67 条，blocked 0；
- 相同可比样本：65 条，blocked 0；
- missing fixtures：CAL-052、CAL-053、CAL-056、CAL-058；
- 67 条正常档 MAE `2.4163`，保守档 MAE `4.9648`；
- 65 条正常档 MAE `2.4829`，保守档 MAE `5.0180`；
- 58 条非软品正常档与保守档所有指标不变；
- 代表软品所有金额不变。

## 9. 代表 CAL 回归结果

| CAL | 正常档 | 保守档 | 结果 |
|---|---:|---:|---|
| CAL-045 | 39.60 | 48.00 | 不变 |
| CAL-064 | 52.00 | 60.00 | 不变 |
| CAL-068 | 10.00 | 35.09 | 不变 |
| CAL-075 | 16.00 | 22.26 | 不变 |
| CAL-076 | 78.00 | 130.50 | 不变 |

## 10. 明确边界

- 未调整任何校准比例、区间或配置。
- 未修改任何代表 CAL 夹具和原始校准记录。
- 未修改 `config/logistics_config.json` 或 `logistics_cost/calculator.py`。
- 深圳/义乌费率、服务费、体积重除数、计费重取高和最低纯头程费用均不变。
- 未接入 `Profit-Accounting-2.6`、`Profit accounting-Auto` 或 `Development rules-2.6`。
