# fix_02 修复对照表

## 复审 8 项核心问题 → 全部修复

| # | 复审问题 | 根因 | 修复 | 测试验证 |
|---|---------|------|------|---------|
| 1 | 包装全空仍显示确定利润 | `chg_partial` 在全部包装字段为 None 时为 False | `head_partial = (head_cost is None)` 无条件检测 | 冒烟测试: head_partial=True |
| 2 | 费率变更后崩溃 | `StringVar.master` 不存在 | 用 `_results_frame.winfo_children()` 获取容器 | 导入测试通过 |
| 3 | 历史结果串用旧数据 | `load_product` 只更新输入框 | 新增 `_populate_results_from_product()` | test_history_product 6项 |
| 4 | 设置自动重算历史商品 | `_on_settings_saved` 无条件调用 recalculate | `recalculate()` 检查 `_historical_mode` 直接 return | 逻辑审查通过 |
| 5 | 重算按钮不应用全部费率 | `_force_recalc` 未更新 fixed_fee/tail_haul | 同步更新到当前配置值 | 代码审查通过 |
| 6 | 推广预留不扣利润 | 只有毛利公式，无净利公式 | 新增 `net_profit_amount()`/`net_profit_rate()` | test_net_profit 9项 |
| 7 | 历史利润率公式错误 | 只用 (售价-采购成本) | 改用完整总成本 + 净利润公式 | 代码审查通过 |
| 8 | 迁移不安全 | 每次都检测旧值覆盖 | 一次性迁移标记 `_config_migrated_v1` | test_migration 5项 |

## 其他问题修复

| 问题 | 修复 |
|------|------|
| USD 输入不反算 RMB | `_last_modified == "price_usd"` 时 `usd_to_rmb` 转换 |
| 还原快照不更新结果 | `restore_product` 调用 `_populate_results_from_product` |
| 测试报告数量不准确 | 本报告使用实际 pytest 计数（81项精确） |

## 修改的文件

| 文件 | 改动 |
|------|------|
| `calculation/profit.py` | +net_profit_amount, +net_profit_rate |
| `calculation/__init__.py` | 导出新函数 |
| `database/db_manager.py` | search_products 增加物流字段；迁移标记修复 |
| `ui/product_page.py` | 全面重写：10项修复 |
| `ui/history_page.py` | 完整总成本利润率 |
| `tests/test_net_profit.py` | 新增 9项 |
| `tests/test_history_product.py` | 新增 6项 |
| `tests/test_migration.py` | 新增 5项 |
