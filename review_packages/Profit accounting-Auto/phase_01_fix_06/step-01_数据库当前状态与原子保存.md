# Step 01 — 数据库当前状态与原子保存

## 目标

建立首次快照与当前保存状态分离的数据模型，修复首次保存的跨事务风险，并补齐旧数据库迁移入口。

## 修改文件

- `Profit accounting-Auto/database/db_manager.py`
- `Profit accounting-Auto/tests/test_database.py`
- `Profit accounting-Auto/tests/test_fix_05.py`
- `Profit accounting-Auto/tests/test_migration.py`
- `Profit accounting-Auto/tests/test_fix_06_database.py`

## 具体修改

- Schema 升级到 v3，`products` 增加当前规则、当前计算结果、计算结构版本和计算时间。
- 新增 `save_product_state()`，新商品、当前状态和首次快照在同一事务内保存。
- 首次快照继续保持不可变；已有商品保存只更新当前状态。
- 迁移补建 `products`，补齐旧快照的全部规则字段，并回填可恢复的当前状态。
- 迁移时补写当前业务规则版本；高于程序支持版本的数据库拒绝打开。
- 迁移失败时回滚并从迁移前备份恢复。

## 测试/验证

- `python -m pytest tests -q`
- 结果：`145 passed in 0.75s`
- 新增验证：当前状态更新/首次快照不变、首次保存失败原子回滚、无 products 的 v0、旧业务规则版本升级、未来版本拒绝、强制迁移失败恢复。
- `git diff --check`：通过。

## 当前结果

数据库层已经能同时表达“首次还原点”和“当前保存状态”，并提供 UI 后续接入所需的原子接口。

## 未解决问题

- UI 仍使用旧的 `create_product()` / `update_product()` 保存路径，下一步切换到原子接口。
- 当前计算结果仍需统一字段名并在历史加载时优先使用。
- v2 时代已经形成的规则混合记录无法无证据自动复原；迁移仅回填可靠存在的快照数据。

## 下一步

修正规则上下文来源、历史结果冻结、动态体积重除数和历史列表展示。
