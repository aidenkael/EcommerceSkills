# Step-02：备份恢复与 Windows 打包

## 目标

完成 Phase 1.5 的数据安全与 Windows 交付能力：整库备份、安全恢复、打包后稳定数据目录和一键打包入口。

## 修改文件

- `Profit accounting-Auto/database/db_manager.py`
- `Profit accounting-Auto/ui/main_window.py`
- `Profit accounting-Auto/build_windows.bat`
- `Profit accounting-Auto/tests/test_backup_restore.py`
- `Profit accounting-Auto/docs/README.md`
- `Profit accounting-Auto/docs/WINDOWS_ACCEPTANCE.md`

## 具体修改

- 使用 SQLite 在线备份接口创建一致性备份，写入临时文件并通过完整性检查后原子替换目标。
- 恢复前检查 SQLite 文件头，将所选备份复制到候选文件中验证；旧 Schema 先在候选副本上迁移，不修改用户选择的原备份。
- 替换当前数据库前自动生成 `before_restore` 安全备份；替换后再次验证，失败时回滚到恢复前数据库。
- “设置”菜单新增“备份全部数据”和“从备份恢复”入口；恢复成功后刷新商品页、货代选项和历史列表。
- PyInstaller 单文件打包状态下，正式数据库固定保存到 `%LOCALAPPDATA%\ProfitAccountingAuto`。
- 新增 `build_windows.bat`，自动检查/安装 PyInstaller 并生成 `dist\ProfitAccountingAuto.exe`。
- 新增 Windows GUI 人工验收清单，覆盖设置、滚动、归档/删除/恢复、备份恢复和打包版重启。

## 测试/验证

- `PYTHONPATH=/tmp/profit_pytest python -m pytest tests -q`：`188 passed in 1.23s`
- `python -m compileall -q .`：通过
- `git diff --check`：通过
- 新增测试覆盖备份恢复往返、恢复前安全副本、无效文件拒绝、禁止覆盖活动数据库、打包数据目录。

## 当前结果

Phase 1.5 已具备本地数据安全闭环和 Windows 打包入口。源码运行继续使用项目 `data` 目录；打包版使用当前 Windows 用户的本地应用数据目录。

## 未解决问题

- 当前执行环境不是 Windows，无法实际生成 Windows `.exe`，也不能替代用户在 Windows 上进行真实鼠标点击验收。
- `docs/WINDOWS_ACCEPTANCE.md` 已列出完整人工验收步骤。

## 下一步

提交并推送本步骤；完成 Windows 人工验收后，才进入 Phase 2.1 本地 OCR 原型。
