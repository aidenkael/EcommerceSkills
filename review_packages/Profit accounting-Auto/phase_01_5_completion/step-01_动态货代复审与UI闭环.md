# Step-01：动态货代复审与 UI 闭环

## 目标

独立复审提交 `5f3cae8278b067638c7a22ab79c663de8b4c4ab4`，修复阻断真实使用的问题，并完成动态货代的归档、删除、恢复 UI 闭环；不进入 OCR。

## 复审发现

1. `SettingsDialog` 调用 `ConfigManager.get_all_routes(include_archived=False)`，但管理器原方法不接收该参数，打开设置窗口会直接触发 `TypeError`。
2. 两条默认货代使用完全相同的 `created_at`，随后按随机 UUID 排序，导致原提交自报的 `180 passed` 无法稳定复现；本次基线实测为 `178 passed, 2 failed`。
3. v5 迁移先补建空 `route_key`，再固定读取该列，真实 v2/v3 `forwarder` 旧键可能丢失；原 v4 测试是从 v5 数据库降版本，未覆盖真实 v4 表结构。
4. 设置窗口没有归档、删除和恢复入口，且不限数量货代没有滚动容器。

## 修改文件

- `Profit accounting-Auto/config/config_manager.py`
- `Profit accounting-Auto/config/forwarder_manager.py`
- `Profit accounting-Auto/database/db_manager.py`
- `Profit accounting-Auto/ui/main_window.py`
- `Profit accounting-Auto/tests/test_configurable_forwarders.py`
- `Profit accounting-Auto/tests/test_fix_06_minimal_corrections.py`
- `Profit accounting-Auto/tests/test_unlimited_forwarders.py`
- `Profit accounting-Auto/docs/README.md`

## 具体修改

- 补齐 `include_archived` 透传，修复设置窗口启动错误。
- 设置页改为可滚动的“使用中的货代 / 已归档”双页管理。
- 未引用货代可确认后永久删除；已引用货代自动停用并归档；归档货代可恢复，恢复后保持停用。
- 新增、归档、删除和恢复后立即刷新新商品货代选项。
- 默认货代和迁移货代使用稳定的创建顺序，不再受随机 UUID 排序影响。
- 修复真实旧 `forwarder` / `route_key` 到 UUID 的迁移，并同步迁移商品、当前规则、首次规则和首次快照中的关联，不改写历史显示名称。
- 统一动态货代数值和重复名称校验；全局设置与货代修改继续保持事务原子性。
- 补充真实 v4 表结构迁移、恢复后停用、UI 操作回调、重复名称回滚等回归测试。

## 测试/验证

- `PYTHONPATH=/tmp/profit_pytest python -m pytest tests -q`：`184 passed in 0.81s`
- `python -m compileall -q .`：通过
- `git diff --check`：通过

## 当前结果

动态货代的业务层、迁移层和设置 UI 已形成新增、编辑、启停、归档、删除、恢复闭环。历史商品继续使用保存时的 UUID、显示名称和冻结规则。

## 未解决问题

- 当前 Linux 执行环境没有图形显示服务，无法替代真实 Windows 鼠标点击和窗口尺寸验收；已通过无窗口 UI 回调测试覆盖关键动作。
- 数据备份/恢复和 Windows 打包入口留到 Step-02。

## 下一步

实现本地数据备份/恢复、打包后的稳定数据目录和 Windows 一键打包入口。
