# Step 04 — 历史尾程与有限配置最小修正

## 目标

在不修改 Schema、不重构数据库或 ProductPage 的前提下，保持历史缺失尾程为空，并拒绝非有限设置值。

## 修改文件

- `Profit accounting-Auto/ui/product_page.py`
- `Profit accounting-Auto/ui/main_window.py`
- `Profit accounting-Auto/config/config_manager.py`
- `Profit accounting-Auto/tests/test_fix_06_minimal_corrections.py`
- `review_packages/Profit accounting-Auto/phase_01_fix_06/final_report.md`

## 具体修改

- `_load_data()` 不再把历史商品或首次快照中的空尾程替换为当前默认尾程。
- 新建/清空表单仍由既有 `clear_form()` 填入当前默认尾程。
- 历史缺尾程记录只修改备注后保存，尾程继续为 `None`。
- 设置窗口要求汇率和默认尾程均为有限数字，并保留原有正数/非负约束。
- `ConfigManager.get_float()` 遇到 NaN、Infinity 或 -Infinity 时返回调用方默认值。

## 测试/验证

- `python -m pytest tests -q`
- 结果：`171 passed in 0.78s`
- 新增覆盖：历史缺尾程加载、备注保存、首次快照还原、新建默认尾程、配置非有限回退、设置窗口所有无效输入和零尾程有效输入。

## 当前结果

历史缺失值不再被当前默认配置污染；只有用户主动填写尾程后才会形成完整物流成本。设置层和配置读取层均拒绝非有限值。

## 未解决问题

- 未执行真实 GUI 人工点击验收。
- phase_01_fix_06 原报告列出的既有范围外问题保持不变。

## 下一步

提交并推送当前分支，不合并 master。
