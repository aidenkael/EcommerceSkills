# Step-01：规则模型与数据库

目标：将 Schema v6 安全迁移至 v7，新增受限的利润调整规则表和默认 SHEIN 补贴规则。

修改：`database/db_manager.py`、`config/profit_adjustment_manager.py`、`calculation/profit_adjustments.py`。

验证：新库 v7、v6→v7、失败恢复、重复打开、UUID、归档/删除/恢复均由自动测试覆盖。

结果：规则为 UUID、名称在未归档记录中不区分大小写唯一；引用规则归档，未引用规则删除。

未解决：无真实 GUI 验收。

下一步：接入计算和商品快照。
