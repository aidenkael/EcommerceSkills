# AGENTS.md — 物流成本核算 v2.2

## 模式与参数
首次核算：信封无 mode 且本地无保存模式时，run.py 返回 mode_required 错误；Agent 询问一次模式(1/2)并停止，用户选择后保存重新运行。已有模式时后续商品沿用。利润模式缺失参数时返回 profit_parameters_required 及缺失字段列表，Agent 一次性询问全部缺失项。模式/参数持久化到 config/local_user_preferences.json。

## 每商品流程
确认SKU和数量→创建新ProductRequest→一次图片理解→一次AI JSON→一次run.py --render-markdown→唯stdout原文回复。每个新商品必须重新创建ProductRequest并重新调用run.py。禁止手工复用旧stdout。

## AI JSON 要求
必须输出：material_family, dimension_scope, structure_evidence。dimension_scope 区分：display_size / product_size / shipping_package_size / unknown。硬底/硬框/硬衬/硬壳/整件保形必须提供强证据。拉链/提手/肩带/普通五金不能单独证明整体刚性。

## 事实来源契约
用户确认 > 商家文字 > 图片可见 > 精确校准 > AI推测。AI候选默认 ai_inferred。product_size/display_size 进入包装仲裁，由仲裁生成运输候选。AI尺寸 field 必须与 dimension_scope 一致。shipping_package_size 属高优先级事实，保守档默认保持事实值不机械放大。用户确认重量走可信重量入口。审计文件包含本次真实 Renderer 输出。

## 最终回复
run.py --render-markdown 成功时唯stdout原文。禁止代码围栏/前言/后记/校准说明/来源说明/总结。

## 文件交付
生成MD文档/导出Markdown/保存为MD/做成文件 → 使用 --audit-md 创建真实文件，聊天只返回文件路径。直接在聊天中展示 → 才在聊天显示正文。

## 禁止
读旧examples/旧process文档/旧stdout/旧AI JSON。修改OUTPUT_CONTRACT/output_renderer/黄金快照。手工校准。手工读取calibration_cases.jsonl。
