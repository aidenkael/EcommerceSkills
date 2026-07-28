# Phase 1.5 恢复、复审与修复报告

## 分支与来源

- 原始导入分支：`codex/feature/phase-1-5-completion`
- 原始最终提交：`10e2bddb82bfc751417c5a042fe438d68ecc38ca`
- 原始基础提交：`e569c5dbcd79c5e57577903e55d097ba6563346d`
- 原始分支已未修改推送至：`origin/codex/feature/phase-1-5-completion`
- 复审分支：`codex/fix/phase-1-5-review`
- 修复提交：`0c166d9880b1e59565aba812d24420c73c3ca51c`

## 完成情况

仅修复两项复审问题，没有重新开发 Phase 1.5，未进入 Phase 2.1，也未增加 OCR。

1. v4→v5 迁移现在真正重建 `route_config`，而非补加列。重建表的 `route_id` 为非空主键并有非空检查；旧规则、商品关联、当前快照和首次不可变快照的 UUID 映射均保留。操作位于既有迁移事务内，异常会走既有回滚/备份恢复；已迁移 v5 数据库再次打开不会重建。
2. 货代新增、归档/删除、恢复等会刷新设置窗口的操作，现在先检测未保存设置。用户可选择保存并继续、明确放弃、取消；默认取消，避免静默丢失修改。

## 修改文件

- `Profit accounting-Auto/database/db_manager.py`
- `Profit accounting-Auto/ui/main_window.py`
- `Profit accounting-Auto/tests/test_unlimited_forwarders.py`
- `Profit accounting-Auto/tests/test_fix_06_minimal_corrections.py`
- `review_packages/Profit accounting-Auto/phase-1-5-review/step-01_迁移主键与设置防丢失.md`

## 验证结果

- `git bundle verify phase-1-5-completion.bundle`：有效，含完整历史。
- `python -m pytest tests -q`：`190 passed in 1.45s`。
- `python -m compileall -q .`：通过。
- `git diff --check`：通过。
- `python -c "import app; import ui.main_window; print('imports ok')"`：通过。

## GUI 与打包状态

- 已静态检查 `build_windows.bat` 和 `docs/WINDOWS_ACCEPTANCE.md`。
- 未完成真实 GUI 验收。
- 当前 Python 环境未安装 PyInstaller，未执行实际 Windows 打包；没有伪造打包成功结果。

## 复审重点与已知边界

- 可用 `PRAGMA table_info(route_config)` 检查 `route_id` 的 PK 和 NOT NULL 标志；测试也验证重复 UUID 插入被拒绝。
- 设置防丢失逻辑仅覆盖会刷新货代表的新增、归档/删除与恢复；“取消”按钮本身不会刷新，不改变其原有语义。
- 工作区内其他项目的既有未提交修改未被暂存、删除或覆盖。

## 第二轮复审：Schema v6 与设置放弃恢复

- Schema 已从 v5 升级为 v6。新库直接创建严格 `route_id`；v4 可直迁 v6，旧版不严格 v5 也会在事务内重建 `route_config` 后升级。
- 迁移保留货代、商品关联、当前规则和首次快照中的 UUID 与显示名称；迁移异常走既有备份恢复，已完成 v6 的数据库重开保持幂等。
- 设置窗口选择“放弃修改并继续”会立即从数据库恢复全局值并重渲染货代；选择取消则不刷新、不保存、不继续。
- 新增测试覆盖真实 v4→v6、真实不严格 v5→v6、v6 幂等、v5 重建异常恢复、主键/NOT NULL/非空/重复约束，以及保存、保存失败、放弃、取消和后续操作取消路径。
- 验证：`python -m pytest ".\\Profit accounting-Auto\\tests" -q` 为 `194 passed in 1.55s`；`compileall` 与 `git diff --check` 通过。
- 未完成真实 GUI 验收；按本轮约束未安装 PyInstaller，未进入 GUI 打包阶段。
