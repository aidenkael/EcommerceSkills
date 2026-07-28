# Step-01：迁移主键与设置防丢失

## 目标

基于导入且已推送保存的 Phase 1.5 原始分支，只修复 v4→v5 `route_config` 约束缺陷，以及设置窗口刷新操作导致未保存修改丢失的问题。

## 修改文件

- `Profit accounting-Auto/database/db_manager.py`
- `Profit accounting-Auto/ui/main_window.py`
- `Profit accounting-Auto/tests/test_unlimited_forwarders.py`
- `Profit accounting-Auto/tests/test_fix_06_minimal_corrections.py`

## 具体修改

- 迁移不再用 `ALTER TABLE` 补列。SQLite 在同一迁移事务中建立替代表、复制 v4 路由数据、替换旧表，使 `route_id` 成为 `NOT NULL` 的真实主键，并加非空检查。
- 保留旧货代字段、商品 `freight_forwarder` 和当前/首次快照 JSON 的 UUID 映射；已完成 v5 迁移再次打开不重建。
- 设置窗口在新增、归档/删除、恢复前检测未保存的全局和货代字段。对话框提供保存并继续、明确放弃、取消；默认取消，不会静默丢失输入。

## 测试/验证

- `python -m pytest tests -q`：`190 passed in 1.45s`。
- `python -m compileall -q .`：通过。
- `git diff --check`：通过。
- 新增断言验证迁移后 `route_id` 的 `PRAGMA table_info` 主键和 NOT NULL 标志、重复 UUID 插入失败、迁移后重开仍保留关联；新增设置保护的取消、保存继续、明确放弃测试。

## 当前结果

两项复审问题均有自动化回归覆盖，未修改 Phase 1.5 的其他业务功能。

## 未解决问题

- 未完成真实 GUI 验收。
- `PyInstaller` 当前环境未安装，因此仅检查了 `build_windows.bat` 和 Windows 验收清单，未执行实际打包。

## 下一步

提交实现，生成最终复审报告并推送 `codex/fix/phase-1-5-review`；不合并 master。
