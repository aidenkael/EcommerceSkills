# AGENTS.md — 物流成本核算 v2.2

## 模式与参数
首次核算：信封无 mode 且本地无保存模式时，run.py 返回 mode_required 错误；Agent 应询问一次模式(1/2)并停止，用户选择后保存并重新运行。已有保存模式时后续商品自动沿用，不重复询问。模式1参数持久化到 config/local_user_preferences.json。mode 切换通过信封提供新 mode 值。

## 每商品流程
```
确认SKU和数量→创建新ProductRequest→一次图片理解→一次AI JSON→一次run.py --render-markdown→唯stdout原文回复
```
每个新商品必须重新创建ProductRequest并重新调用run.py。禁止手工复用、复制或转发上一商品stdout。精确校准/包装仲裁/输出守卫/新鲜度校验由run.py程序化完成。

## AI JSON 要求
必须输出: material_family, dimension_scope, structure_evidence, weight_scope, quantity_source, confidence。dimension_scope 区分: display_size / product_size / shipping_package_size / unknown。硬底/硬框/硬衬/硬壳/整件保形必须提供强证据来源(user_confirmed/merchant_text/image_visible+location)。拉链/提手/肩带/普通金属扣/链条/装饰五金/立体摆放不能单独证明整体刚性。

## 事实优先级
用户确认 > 商家文字 > 图片可见 > 精确校准 > AI推测。用户确认重量必须通过可信重量入口进入estimate()，不得标记为ai_inferred。AI只能补充未知字段，不得覆盖更高优先级事实。

## 最终回复协议
run.py --render-markdown 成功时最终回复唯stdout原文，不得用代码围栏，不得加前言/后记/校准说明/来源说明/总结。失败时只报告转发失败，不得自建替代表。

## 文件交付
用户说"生成MD文档/导出Markdown/保存为MD/做成文件"时使用 --audit-md 参数创建真实文件，聊天只返回文件路径。用户说"直接在聊天中展示"时才在聊天显示正文。

## 禁止
读旧examples/旧process文档/旧stdout/旧AI JSON。修改OUTPUT_CONTRACT/output_renderer/黄金快照。手工校准。手工读取calibration_cases.jsonl。生成临时文件。
