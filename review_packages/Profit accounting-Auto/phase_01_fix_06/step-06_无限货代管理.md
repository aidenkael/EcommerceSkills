# Step-06：无限货代管理

## 目标

将固定双货代槽位升级为动态货代集合；保留历史商品和首次快照的稳定关联与保存时名称，不进入 phase_02。

## 修改文件

- `Profit accounting-Auto/database/db_manager.py`
- `Profit accounting-Auto/config/forwarder_manager.py`
- `Profit accounting-Auto/config/config_manager.py`
- `Profit accounting-Auto/ui/main_window.py`
- `Profit accounting-Auto/ui/product_page.py`
- `Profit accounting-Auto/docs/README.md`
- `Profit accounting-Auto/tests/test_unlimited_forwarders.py` 及既有迁移测试

## 具体修改

- Schema 升级为 v5。`route_config` 以不可变 UUID `route_id` 关联商品，保存显示名称、独立费率、固定服务费、体积重除数、启用/归档状态及时间戳。
- v4 的 `shenzhen`/`yiwu` 关联迁移到 UUID，并同步更新商品当前规则、首次规则和首次快照 JSON 的内部关联；历史显示名不改写。
- 新增 `ForwarderManager`，提供创建、更新、启停和“被引用则归档、未引用则删除”的原子操作。名称和全部数值均校验。
- 新商品仅可选启用且未归档货代；快照中保存 `route_id` 与 `route_display_name`。
- 保持克重输入、内部 g÷1000 换算 kg、`legacy_unknown` 不自动换算，以及 SHEIN 美元参考值不参与利润。

## 测试/验证

- `python -m pytest tests -q`：`180 passed in 1.22s`。
- 新增路径包括 20 个动态货代、不同体积重除数、名称重复拒绝、停用隐藏、引用后归档、未引用删除、UUID、克重 500g=0.5kg。
- `git diff --check`：通过。

## 当前结果

动态货代不再依赖深圳/义乌的写死业务键；默认首次数据库仍创建深圳（80、10、8000）和义乌（100、6、8000）两条记录。

## 未解决问题

- 未执行真实 GUI 人工操作；本步骤只做无窗口业务自动化验证。
- 当前设置窗口新增货代采用默认规则后再编辑；归档/删除的完整交互入口仍可由服务层调用，后续 UI 体验可单独完善。

## 下一步

提交并推送本步骤分支，不合并 master。
