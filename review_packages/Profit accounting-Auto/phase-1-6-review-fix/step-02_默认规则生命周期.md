# Step 02: 默认规则生命周期

## 目标
默认规则只在首次建库/迁移时种子一次，用户改名/停用/归档/删除后重启不重复创建。

## 修改文件
- `database/db_manager.py`

## 具体修改

### 1. `_seed_current_data()` 移除利润规则种子
修改前：每次启动（新DB和已有v7 DB）都调用 `_seed_profit_adjustment_rules(conn)`。
修改后：完全移除该调用。`_seed_current_data` 只负责版本号、配置和货代。

### 2. 新增 `_seed_profit_adjustment_rules_first_time()`
仅在 `__init__` 的新数据库分支调用。逻辑：检查 `profit_adjustment_rules` 表是否为空，空则插入默认规则。不依赖 `display_name` 存在性检查，避免改名后重复创建。

## 测试/验证
- `test_review_fixes.py::TestDefaultRuleLifecycle` 4项通过：
  - 改名后重启不新增第二条
  - 修改金额后重启不还原
  - 停用后重启仍停用
  - UUID 重启不变

## 当前结果
- 新数据库：包含 1 条默认规则（SHEIN 29美元以下运费补贴）
- 已有 v7 数据库：不重复种子
- 用户改名/停用/归档后重启：保持用户状态

## 未解决问题
无

## 下一步
Step 03: 规则设置界面
