# Step 05：冻结规则与编辑器二轮复审修复

## 目标

解除历史商品利润调整冻结副本与“启用且未归档”下拉映射的耦合；补齐利润规则编辑器的 dirty 防护、归档只读和中文列表显示。

## 修改文件

- `Profit accounting-Auto/ui/product_page.py`
- `Profit accounting-Auto/ui/main_window.py`
- `Profit accounting-Auto/tests/test_review_fixes.py`

## 具体修改

- ProductPage 保存独立的冻结规则副本和来源状态（`frozen`、`current`、`none`）。历史商品加载或首次快照还原后，使用保存时的完整副本，不再依赖当前下拉框映射。
- 用户在下拉框明确改选“无”或一条当前规则时，才丢弃冻结副本；“用当前规则重算”只在对应当前规则仍启用且未归档时采用它，否则显示提示并切换为无规则。
- 右侧调整说明在加载、还原和重算时显示规则来源、规则名称、判断结果、原币金额和人民币金额；新建/清空为“未选择规则”。
- ProfitRulesDialog 的程序化表单赋值使用 dirty 暂停标记；取消列表切换时按稳定 `rule_id` 恢复原选择。
- 归档规则的输入框、下拉框、启用开关、新增/保存/归档按钮统一禁用，只保留恢复和关闭；恢复后默认停用并重新可编辑。
- 列表字段全部使用中文映射，百分比规则显示基数。

## 测试与验证

```powershell
python -m pytest ".\Profit accounting-Auto\tests" -q
# 213 passed
python -m compileall ".\Profit accounting-Auto"
# 通过
git diff --check
# 通过
```

新增的 ProductPage 方法路径测试覆盖：加载历史冻结规则、不修改后保存、当前规则改价并归档后的冻结规则重算，以及历史提示文字。规则编辑器测试覆盖 dirty 暂停/放弃恢复、归档控件禁用和中文列表渲染。

## 当前结果

自动测试全部通过。未执行真实 Windows GUI 人工验收；未打包，未进入 OCR 或 Phase 2。

## 未解决问题与下一步

需要人工在 Windows GUI 中复核弹窗交互、Alt+F4 和归档只读视觉状态。本轮完成后停止，等待人工复审。
