# Phase 1.6：可配置利润调整规则

## 完成情况

- Schema 已升级至 v7；新数据库和 v6 迁移后均建立 `profit_adjustment_rules`。
- 默认规则为“`SHEIN 29美元以下运费补贴`”：最终售价 USD `< 29` 时增加收入 `2.99 USD`，默认启用但不会自动选中。
- 支持最终售价 USD/RMB、商品成本 RMB、物流成本 RMB、无条件；支持五种比较、收入/成本、固定金额/百分比、USD/RMB。百分比基数显式保存且仅限三个 RMB 基数。
- 商品每次保存均冻结实际规则副本、条件输入、是否满足、汇率、原始金额、人民币调整和利润前后结果；首次快照不更新。

## 修改文件

数据库、计算、配置服务、设置/商品界面及 `tests/test_profit_adjustments.py`，详见四份步骤说明。

## 验证

- `python -m pytest ".\\Profit accounting-Auto\\tests" -q`：`200 passed in 1.89s`。
- `python -m compileall ".\\Profit accounting-Auto"`：通过。
- `git diff --check`：通过。

## 边界

未执行 Windows 打包、真实 GUI 人工验收或 OCR；未合并 master。当前仅支持每商品一条由用户明确选择的规则。
