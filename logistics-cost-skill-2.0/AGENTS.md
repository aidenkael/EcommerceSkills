# AGENTS.md — 物流成本核算 v2.2

## 模式与参数
首次核算询问模式(1/2)，后续商品自动沿用已保存模式。加密封中不指定 mode 时使用已保存模式。模式1参数(exchange_rate/tail_fee_usd/target_profit_markup_percent/activity_reserve_percent)保存到 config/local_user_preferences.json。禁止从历史对话读取模式。

## 每商品流程
```
确认SKU和数量→创建新商品请求→一次图片理解→一次AI JSON→一次run.py --render-markdown→唯stdout原文回复
```
Agent 不得手工读取 calibration_cases.jsonl、旧examples、旧stdout、历史对话中的其他商品参数。精确校准/包装仲裁/输出守卫由 run.py 程序化完成。

## AI JSON 要求
必须输出: material_family, dimension_scope, structure_evidence, weight_scope, quantity_source, confidence。
dimension_scope 区分: display_size / product_size / shipping_package_size / unknown。
硬底/硬框/硬衬必须提供强证据来源。拉链/提手/肩带/普通五金不能单独证明整体刚性。

## 最终回复协议
run.py --render-markdown 成功时最终回复唯 stdout 原文，不得用代码围栏，不得加前言/后记/说明。失败时仅报告转发失败，不得自建替代表。

## 禁止
读旧examples/旧process文档/旧stdout/旧AI JSON。修改OUTPUT_CONTRACT/output_renderer/黄金快照。手工校准。生成临时文件。
