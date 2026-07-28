# Step 02 — 规则上下文与历史结果冻结

## 目标

让商品下次打开使用最近一次保存的规则和结果，让“还原”只使用首次快照，并消除历史列表的重复计算口径。

## 修改文件

- `Profit accounting-Auto/calculation/__init__.py`
- `Profit accounting-Auto/calculation/logistics.py`
- `Profit accounting-Auto/calculation/rules.py`
- `Profit accounting-Auto/ui/product_page.py`
- `Profit accounting-Auto/ui/history_page.py`
- `Profit accounting-Auto/tests/test_fix_06_state_flow.py`

## 具体修改

- 分离当前商品规则上下文和首次快照规则上下文，不再混合两个时间点的货代与费率。
- UI 保存切换到数据库原子接口，每次保存同步更新当前规则和当前结果。
- 统一保存结果字段名，包括体积重、计费重、头程、总成本、净利润和建议售价。
- 打开商品优先展示保存的当前计算结果；还原优先展示首次快照结果。
- `volumetric_weight()` 接收规则中的体积重除数，历史除数真正参与公式。
- 规则差异比较提取为纯函数，并识别 `None` 与已有值之间的变化。
- 历史列表优先读取保存净利率；兼容旧记录时仅在全部成本完整后调用统一计算模块。

## 测试/验证

- `python -m pytest tests -q`
- 结果：`150 passed in 0.78s`
- 新增验证：义乌保存后切换深圳并重新读取、首次还原规则不变、冻结结果不重新计算、动态体积重除数、缺失规则差异、历史列表不把缺失成本当零。
- `git diff --check`：通过。

## 当前结果

当前保存状态与首次还原点已经在数据库层和 UI 层贯通；历史列表与商品页面共用保存结果和统一计算函数。

## 未解决问题

- 尚未在真实图形界面中进行人工点击验收。
- v2 时代已经形成且首次快照与当前商品冲突的记录无法无证据恢复真实费率，迁移后应人工复核。
- README 仍描述旧设置项和旧数据模型，下一步同步。

## 下一步

补齐边界测试和迁移验收，更新 README，生成 final_report。
