# Step 03 — 迁移验收与文档同步

## 目标

完成迁移后的结构与数据完整性验收，覆盖真实旧快照记录，并将运行说明同步到 Schema v3 和当前业务口径。

## 修改文件

- `Profit accounting-Auto/database/db_manager.py`
- `Profit accounting-Auto/tests/test_fix_06_database.py`
- `Profit accounting-Auto/docs/README.md`

## 具体修改

- 迁移连接启用外键检查。
- 旧 `products` 表存在但字段不完整时补齐可安全添加的业务字段。
- 对不可安全推断的关键标识字段直接终止迁移并恢复备份。
- 迁移提交前执行必需字段、`PRAGMA integrity_check` 和 `PRAGMA foreign_key_check`。
- 正常打开当前版本数据库时也执行结构和完整性检查。
- 新增带真实商品和快照行的极简 v0 迁移测试，覆盖所有规则列缺失的情况。
- 重写 README，修复乱码和旧设置说明，补充当前状态/首次快照、严格缺失、精度、迁移及已知边界。

## 测试/验证

- `python -m pytest tests -q`
- 结果：`151 passed in 0.72s`
- `python -c "import app; import ui.main_window; print('imports ok')"`
- 结果：`imports ok`
- `git diff --check`：通过。

## 当前结果

Schema v3 的新建、旧版迁移、失败恢复、当前状态保存和历史结果读取已经形成闭环；项目文档与当前实现一致。

## 未解决问题

- 未进行真实 GUI 人工点击验收。
- v2 已经形成且互相冲突的当前商品/首次快照记录无法无证据自动复原，迁移后需人工复核。
- 8 位商品 ID 和单一 `image_path` 字段仍是既有设计边界，本任务未扩大处理。
- 未接入 GitHub CI，本轮测试为本机 Python 3.13 执行结果。

## 下一步

生成 final_report，供合并前复审。
