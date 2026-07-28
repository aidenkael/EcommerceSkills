# Phase 1.5 完成报告

## 完成情况

Phase 1.5 的代码开发与自动化验证已完成，未进入 OCR，也未合并 `master`。

本阶段从提交 `5f3cae8278b067638c7a22ab79c663de8b4c4ab4` 开始独立复审，完成：

1. 动态货代设置窗口修复与不限数量滚动展示；
2. 新增、编辑、启停、归档、删除、恢复 UI 闭环；
3. 真实 v4 旧货代键和历史 JSON 到 UUID 的安全迁移；
4. 默认货代稳定顺序与事务校验；
5. 整库备份、恢复前验证、恢复前安全副本和失败回滚；
6. PyInstaller 打包后的稳定 Windows 数据目录；
7. Windows 一键打包脚本与人工 GUI 验收清单。

## 关键修复

- 修复打开设置窗口即触发 `TypeError` 的阻断问题。
- 修复默认货代受随机 UUID 排序影响，导致原提交测试不稳定的问题。
- 修复真实 v2/v3 `forwarder` 旧键在 v5 迁移中可能丢失的问题。
- 原 v4 测试从 v5 数据库降版本，未覆盖真实 v4 结构；已改为直接构造真实 v4 表和历史数据。
- 恢复归档货代时默认保持停用，避免未经人工核对便重新参与新商品计算。
- 历史商品保存时的显示名称和冻结费用不被当前货代改名或费率修改覆盖。

## 主要修改文件

- `Profit accounting-Auto/database/db_manager.py`
- `Profit accounting-Auto/config/config_manager.py`
- `Profit accounting-Auto/config/forwarder_manager.py`
- `Profit accounting-Auto/ui/main_window.py`
- `Profit accounting-Auto/build_windows.bat`
- `Profit accounting-Auto/docs/README.md`
- `Profit accounting-Auto/docs/WINDOWS_ACCEPTANCE.md`
- `Profit accounting-Auto/tests/test_backup_restore.py`
- `Profit accounting-Auto/tests/test_unlimited_forwarders.py`
- `Profit accounting-Auto/tests/test_fix_06_minimal_corrections.py`

## 测试结果

- 完整测试：`188 passed in 1.23s`
- Python 编译检查：通过
- `git diff --check`：通过

复审前基线实测为 `178 passed, 2 failed`；修复并扩充测试后为 `188 passed`。

## 提交

- Step-01：`a64794f` — `Profit accounting-Auto：完成动态货代UI闭环`
- Step-02：`e569c5d` — `Profit accounting-Auto：增加备份恢复与Windows打包`

## 已知问题

- 当前执行环境不是 Windows，无法在本阶段内实际生成 Windows `.exe`。
- 当前执行环境没有图形显示服务，不能代替真实 Windows GUI 人工点击验收。
- Windows 验收步骤见 `Profit accounting-Auto/docs/WINDOWS_ACCEPTANCE.md`。

## 复审重点

1. 在真实 v4 数据库副本上启动后，商品货代和首次快照是否保持正确关联。
2. 归档已引用货代后，历史商品是否继续显示保存时名称和冻结费用。
3. 恢复备份失败时，当前数据库是否保持不变。
4. 打包版重启后，数据是否持续保存在 `%LOCALAPPDATA%\ProfitAccountingAuto`。

## 下一步

先完成 Windows GUI 人工验收。验收通过后，再单独建立分支启动 Phase 2.1 本地 OCR 原型。
