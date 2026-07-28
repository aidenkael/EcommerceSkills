# Step 06：保存冻结与规则编辑器同步修复

## 目标

修复商品保存后仍引用数据库当前利润规则的问题，并收敛规则编辑器保存切换、创建新规则和零值显示状态。

## 修改

- 商品保存成功后立即把实际保存的利润调整规则副本设为 `frozen`；无规则则设为 `none`。
- 当前规则不可用时，“用当前规则重算”弹出警告，并保留无规则的原因说明。
- 规则列表切换以稳定 `rule_id` 为目标；新增时清除旧列表选择。
- 规则表单和列表保留合法数值 `0`；保存异常返回失败并阻止后续操作。

## 验证

- `python -m pytest ".\Profit accounting-Auto\tests" -q`：216 passed。
- `python -m compileall ".\Profit accounting-Auto"`：通过。
- `git diff --check`：通过。

## 人工验证

未执行真实 GUI 验收；未打包、未进入 OCR 或 Phase 2。
