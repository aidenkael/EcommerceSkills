# Final Report — Phase 1.6 Review Fix

**项目**：Profit accounting-Auto  
**分支**：`codex/fix/phase-1-6-review`  
**基准提交**：`8b8b6a2`（Phase 1.6 利润调整规则实现）  
**生成时间**：2026-07-26 12:27  
**Schema**：v7（未修改）

---

## 一、修改文件

| 文件 | 修改 | 原因 |
|------|------|------|
| `ui/product_page.py` | 3处修改 | ① `_populate_results_from_saved` 恢复利润调整字段到 `_computed`；② `_apply_profit_adjustment` 优先使用冻结规则副本；③ `new_product`/`clear_form` 重置利润调整提示 |
| `ui/main_window.py` | ProfitRulesDialog 重写 | 中文映射下拉框、字段联动、description字段、防丢失保护、归档保护 |
| `database/db_manager.py` | 2处修改 | ① `_seed_current_data` 移除利润规则种子；② 新增 `_seed_profit_adjustment_rules_first_time` 仅新库种子 |
| `tests/test_review_fixes.py` | 新增 | 13项复审修复测试 |

---

## 二、历史规则如何冻结

1. **保存时**：`_apply_profit_adjustment` 在计算时将完整规则 dict 放入 `_computed["profit_adjustment"]["rule"]`（冻结副本），再随快照保存。
2. **加载时**：`_populate_results_from_saved` 从 `_calculation_results` 读取 `profit_adjustment` 和 `profit_before_adjustment`，恢复至 `_computed`。
3. **重算时**：`_apply_profit_adjustment` 优先从 `_saved_rule_context` 中查找冻结副本，找不到才读 DB。
4. **保存后**：`_computed` 保持冻结值，再次保存不会清空。

---

## 三、用户如何明确切换规则

仅以下操作切换规则：
1. 用户在利润规则下拉框中选择另一条规则（`_set_profit_rule_id`）
2. 用户点击"用当前规则重算"（`_force_recalc`）

编辑成本、运费、售价、备注等普通字段不改变 `_saved_rule_context`。

---

## 四、默认规则如何避免重复

- `_seed_profit_adjustment_rules_first_time()` 仅在新数据库 `__init__` 时调用
- 检查 `profit_adjustment_rules` 表是否为空，空则插入
- 不依赖 `display_name` 存在性（避免改名后重复创建）
- 已有 v7 数据库启动时不执行种子

---

## 五、设置界面中文映射

6 个枚举字段全部使用中文 Combobox：

| 字段 | 中文值 | 内部值 |
|------|--------|--------|
| 条件字段 | 无条件/最终售价（美元）/最终售价（人民币）/商品成本（人民币）/物流成本（人民币） | None/final_price_usd/final_price_rmb/product_cost_rmb/logistics_cost_rmb |
| 比较方式 | 小于/小于等于/大于/大于等于/等于 | </<=/>/>=/== |
| 调整方向 | 增加收入/增加成本 | income/cost |
| 调整类型 | 固定金额/百分比 | fixed/percent |
| 币种 | 美元/人民币 | USD/RMB |
| 百分比基数 | 最终售价人民币/商品成本人民币/物流成本人民币 | final_price_rmb/product_cost_rmb/logistics_cost_rmb |

---

## 六、新增测试

`tests/test_review_fixes.py` — 13项：

| 类 | 测试 | 验证 |
|----|------|------|
| TestHistoricalRuleFrozen | test_load_then_save_preserves_adjustment_snapshot | 加载后保存不改变利润调整快照 |
| TestHistoricalRuleFrozen | test_snapshot_contains_profit_before_adjustment | 快照含 profit_before_adjustment |
| TestDefaultRuleLifecycle | test_rename_no_duplicate_on_restart | 改名后重启不新增 |
| TestDefaultRuleLifecycle | test_modify_value_no_reset | 修改金额后重启不还原 |
| TestDefaultRuleLifecycle | test_disable_stays_disabled | 停用后重启仍停用 |
| TestDefaultRuleLifecycle | test_uuid_preserved_across_restarts | UUID 重启不变 |
| TestArchiveProtection | test_archive_then_restore_is_disabled | 恢复后默认停用 |
| TestFrozenRuleEvaluation | test_evaluate_with_frozen_rule | 冻结规则求值正确 |

---

## 七、测试总数

**216 passed in 2.37s**

```
python -m pytest tests/ -v
```

---

## 八、Git 信息

| 项目 | 值 |
|------|-----|
| 分支 | `codex/fix/phase-1-6-review` |
| 本轮代码提交 | `f0b3389113cea20bf524da07f741a0deb3452106` |
| 合并 master | 否 |
| GitHub | `https://github.com/aidenkael/EcommerceSkills.git` |

---

## 九、复审重点建议

1. `ui/product_page.py` `_populate_results_from_saved` 是否正确恢复利润调整字段
2. `ui/product_page.py` `_apply_profit_adjustment` 冻结副本查找逻辑
3. `database/db_manager.py` `_seed_current_data` 是否还有残留种子调用
4. `ui/main_window.py` `_values()` 是否正确传递 `is_archived` 状态
5. `tests/test_review_fixes.py` 测试路径是否真实

---

## 十、仍需人工验证

- ProfitRulesDialog 中文下拉框联动（无条件/固定金额/百分比）
- 未保存修改弹窗（切换规则/新增/关闭时）
- 归档规则保存按钮拦截提示
- 归档规则恢复后默认为停用状态

---

## 十一、第二轮复审修复（2026-07-26）

- 冻结利润规则现在保存为 ProductPage 独立副本；加载历史商品或还原首次快照后，不依赖启用规则下拉映射。即使当前规则改名、改金额、停用或归档，商品字段变化触发重算仍使用保存时副本。
- 历史提示统一显示“历史冻结规则”、保存时名称、判断结果、原币调整金额与折合人民币；新商品/清空显示“未选择规则”，无规则历史商品显示“无规则”。
- 用户明确选择“无”会冻结无规则；明确选择当前规则会保存其新副本。“用当前规则重算”遇到停用、归档或删除的对应规则会提示并切换为无规则。
- 利润规则编辑器增加程序化赋值 dirty 保护、取消列表切换时按 `rule_id` 恢复选择、关闭窗口（含 `WM_DELETE_WINDOW` / Alt+F4）保护、归档/恢复保护，以及归档规则的完整只读控件状态。
- 规则列表不再显示内部代码；条件、比较方式、调整方向、类型、币种和百分比基数均为中文。

### 本轮新增测试和结果

- ProductPage 方法路径：冻结副本在当前规则改价并归档后仍以 2.99 USD 计算；真实加载后不修改直接保存时快照不变。
- ProfitRulesDialog 方法路径：程序赋值不产生假 dirty、放弃修改会载入数据库值、归档时编辑控件禁用、恢复后重新可编辑、列表只显示中文。
- `python -m pytest ".\\Profit accounting-Auto\\tests" -q`：**213 passed**。
- `python -m compileall ".\\Profit accounting-Auto"`：通过。
- `git diff --check`：通过。

### GUI 与打包状态

- **未完成真实 GUI 验收**；未将命令行测试表述为 GUI 通过。
- 未打包；未安装 PyInstaller；未进入 OCR、Phase 2 或 master。

---

## 十二、最终小范围修复（2026-07-26）

- 商品保存成功后立即从本次规则快照冻结利润调整规则；后续数据库改价、改名、停用或归档不会影响已保存商品的普通字段重算。
- 冻结规则的当前版本不可用时，强制重算会弹出警告，切换为无规则后右侧保留“原冻结规则当前已停用、归档或不存在”的原因。
- 规则 A 保存并切换到规则 B 使用稳定 `rule_id` 重新定位，新增规则会清除旧列表选择。
- 条件阈值和调整金额为 `0` 时不再被转换为空值；保存异常会显示“保存失败”并停止后续动作。
- 本轮新增保存即冻结、冻结规则不可用提示、零值回填测试；全部测试总数为 **216 passed**。
- 本轮代码提交：`6522f3fba8f51ff79b3016666d387a23070b3a37`。
- 未完成真实 GUI 验收；未打包、未合并 master、未进入 OCR。
