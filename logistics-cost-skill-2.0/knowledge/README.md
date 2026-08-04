# knowledge/ — 本地包装经验库

## physical_packaging_rules.json

保存跨品类通用物理包装规则，可随工具打包。

包含 15 种结构类型的：刚性主体识别、可折/可拆部件处理、压缩策略、嵌套判断、保护方式、正常档与保守档生成原则、禁止假设和复核触发条件。

**不包含**具体商品固定尺寸、重量或费用。

## calibration_cases.jsonl

保存实际反馈案例。每行一个案例。

状态：
- `validated`：有实际重量、尺寸或可靠物流证据 → 可参考数值范围
- `pending`：实际信息不足 → 只能提醒检查 SKU/折叠/压缩/嵌套/包装方式，禁止反推尺寸或费用
- `deprecated`：不再使用

**精确案例命中规则（日常核算）：**
- `validated` 精确商品案例（`usage_scope=exact_product_sku_only`）可在日常核算中通过一次精确键查询使用
- 精确案例不得模糊匹配；只有标题标识、SKU和数量同时一致才命中
- 实际纯头程已确认但货代未知时，可用两家费率推导计费重区间；该区间只用于当前商品，不得推广为通用品类规则
- 未命中时不扫描其他案例
- `pending` 禁止数值参与
- `validated_packaging_profiles` 至少5样本才可建立通用档案

## 与 local_user_preferences.json 的区别

`config/local_user_preferences.json` 属于用户个人参数（汇率/利润率等），不属于知识库。模式（active_mode）不保存在该文件中，模式仅在当前对话有效。

## 打包规则

打包给别人时：
- 包含：`physical_packaging_rules.json`、`calibration_cases.jsonl` 中的 `validated` 通用案例
- 不包含：`local_user_preferences.json`、原始商品图片、供应商身份、个人利润参数、运行日志、未经确认的私人案例
