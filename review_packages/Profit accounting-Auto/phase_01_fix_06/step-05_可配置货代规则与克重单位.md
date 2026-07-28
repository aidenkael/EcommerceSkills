# Step 05 — 可配置货代规则与克重单位

## 目标

将两个固定货代槽位改为稳定内部键与可修改显示名称，并将新商品重量输入统一为克。

## 修改文件

- `database/db_manager.py`
- `config/config_manager.py`
- `calculation/logistics.py`
- `calculation/__init__.py`
- `ui/main_window.py`
- `ui/product_page.py`
- `ui/history_page.py`
- `docs/README.md`
- `tests/test_configurable_forwarders.py` 及既有迁移断言

## 修改摘要

- Schema v4 支持 `route_key`、显示名、独立体积重除数和启用状态。
- 保留 `shenzhen`/`yiwu` 作为兼容内部键；显示名称可修改。
- 设置页原子保存全局设置和两个货代完整规则。
- 新商品重量按 g 输入，计算前转换为 kg；旧数据标记 `legacy_unknown`，不自动换算。
- 规则快照保存路由键、显示名称、独立费率、体积重除数和重量单位。

## 测试

- `python -m pytest tests -q`
- 结果：`176 passed in 1.05s`
- GUI 人工操作：未执行。

## 已知问题

- 旧重量 `legacy_unknown` 需要用户核对并重新填写；不会自动乘 1000。
- 当前仅维护两个固定货代槽位，不支持新增删除。
