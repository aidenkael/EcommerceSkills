# Step 01: 历史规则冻结修复

## 目标
确保历史商品加载后再次保存不丢失利润调整规则快照。

## 修改文件
- `ui/product_page.py`

## 具体修改

### 1. `_populate_results_from_saved()` 恢复利润调整字段
在重建 `_computed` 字典时，新增两行：
```python
_, profit_before_adj = self._saved_result(calc, "profit_before_adjustment")
_, profit_adjustment = self._saved_result(calc, "profit_adjustment")
```
并将这两个值放入 `_computed`，确保加载后再次保存时 `_build_rule_snapshot()` 和 `_build_calculation_snapshot()` 能读取到正确的冻结值，而不是 `None`。

### 2. `_apply_profit_adjustment()` 优先使用冻结规则
修改前：每次调用都从 `self._cfg.get_profit_adjustment_rule(rule_id)` 实时读取 DB。
修改后：先检查 `self._saved_rule_context` 中是否有匹配的冻结规则副本，如果有则直接使用，不读 DB。

### 3. `new_product()` / `clear_form()` 重置利润调整提示
增加 `_reset_profit_adjustment_display()` 方法，在新建和清空时将提示恢复为"未选择规则"。
使用 `hasattr()` 保护，兼容 mock 测试。

## 测试/验证
- `test_review_fixes.py::TestHistoricalRuleFrozen` 2项通过
- 200项现有测试不受影响

## 当前结果
历史商品加载后 `_computed` 完整包含 `profit_adjustment` 和 `profit_before_adjustment`，再次保存不会丢失。

## 未解决问题
无

## 下一步
Step 02: 默认规则生命周期
