# Step-02：Schema v6 与放弃修改恢复

## 目标

修复不严格 Schema v5 无法升级，以及设置窗口“放弃修改”未真正恢复界面的问题。

## 修改文件

- `Profit accounting-Auto/database/db_manager.py`
- `Profit accounting-Auto/ui/main_window.py`
- `Profit accounting-Auto/tests/test_database.py`
- `Profit accounting-Auto/tests/test_fix_05.py`
- `Profit accounting-Auto/tests/test_fix_06_database.py`
- `Profit accounting-Auto/tests/test_fix_06_minimal_corrections.py`
- `Profit accounting-Auto/tests/test_migration.py`
- `Profit accounting-Auto/tests/test_unlimited_forwarders.py`

## 具体修改

- Schema 升级至 v6。v4 和不严格 v5 均在既有迁移事务中重建 `route_config`；`route_id` 为 `PRIMARY KEY NOT NULL`，并拒绝空字符串和重复值。
- 保持旧路由数据、商品关联、当前规则快照、首次快照 UUID 与显示名称。v6 再次打开不重建路由或 UUID；重建异常继续使用已有备份恢复路径。
- “放弃修改并继续”现在回读数据库全局设置并重渲染货代列表；后续新增名称或归档确认即使取消，放弃的输入也不会重新出现。取消保护对话框仍保留输入。
- 删除归档确认中关于未保存费率会丢失的过时提示。

## 测试/验证

- `python -m pytest ".\\Profit accounting-Auto\\tests" -q`：`194 passed in 1.55s`。
- `python -m compileall -q ".\\Profit accounting-Auto"`：通过。
- `git diff --check`：通过。

## 当前结果

数据库已正式升级为 Schema v6；两类复审问题均有真实结构和界面流程的自动化覆盖。

## 未解决问题

- 未执行真实 GUI 或打包阶段；按任务要求未安装 PyInstaller。

## 下一步

提交并推送当前复审分支，等待人工复审。
