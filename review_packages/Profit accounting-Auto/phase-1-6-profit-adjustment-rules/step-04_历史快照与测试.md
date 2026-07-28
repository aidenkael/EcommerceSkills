# Step-04：历史快照与测试

目标：保存实际规则、条件输入、汇率、原始/人民币调整和前后利润，确保后续改名、停用、归档不改变历史。

修改：`ui/product_page.py`、`tests/test_profit_adjustments.py` 和既有 Schema 测试期望。

验证：`python -m pytest ".\\Profit accounting-Auto\\tests" -q` 为 `200 passed in 1.89s`；`compileall` 与 `git diff --check` 通过。

结果：当前商品和首次快照均保留规则副本；历史显示不依赖当前规则表。

未解决：未完成真实 GUI 人工验收。
