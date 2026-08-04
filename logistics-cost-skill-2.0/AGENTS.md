# AGENTS.md — 物流成本核算 v2.2 (OUTPUT_CONTRACT 2026-08-04-v2)

## 模式门禁
两种模式：1. 利润核算 / 2. 仅头程。新对话第一次核算只输出模式菜单并停止。已选后后续商品沿用。禁止从local_user_preferences.json/MEMORY/历史对话读取模式。

## 利润模式参数门禁
模式1在图片理解前检查：exchange_rate / tail_fee_usd / target_profit_markup_percent / activity_reserve_percent。第一次缺参数时一次性询问全部缺失项并停止。参数保存在config/local_user_preferences.json（被Git忽略）。SHEIN补贴阈值属于项目规则，不要求用户输入。不得保存模式。

## 每商品快速路径
```
确认SKU和数量→一次图片理解→一次紧凑AI JSON→一次run.py --render-markdown调用→renderer直接输出
```
最多1次图片理解+1次计算。仅异常时允许1次重估。缺参数不阻断。

精确校准由 run.py 内部自动完成：Agent 只需在信封中提供 product_display.title / selected_sku / quantity，run.py 会自动查询 calibration_cases.jsonl 并覆盖 AI JSON 参数。Agent 不得手工读取 calibration_cases.jsonl 或改写参数。

## 证据优先级
用户明确说明>当前高亮SKU/数量>规格参数>validated档案>通用规则>AI推测。禁止用同页套包/其他颜色覆盖当前单包。

## AI JSON 字段要求
Agent 识图构建 AI JSON 时必须：

1. **dimension_scope**：必须区分 `display_size` / `product_size` / `shipping_package_size` / `unknown`
2. **material_family**：必须输出，不得写 "unknown"。常见值：pvc / tpu / pu / oxford / canvas / fabric / thin_textile / transparent_soft_plastic
3. **structure_evidence**：声称硬底/硬框/硬衬/原盒/整件保形时，必须在 `structure_evidence` 中给出来源和位置。`source` 取 `user_confirmed` / `merchant_text` / `image_visible` / `ai_inferred`
4. 拉链、提手、肩带和普通五金不能单独证明整体刚性
5. Agent 只识图一次并提交候选；不得为通过校验自行改分类或二次试算；候选修复由 `packaging_arbitrator.py` 完成

## 输出合同保护（最高优先级）
OUTPUT_CONTRACT.md、output_renderer.py 和黄金快照属于受保护文件。只有用户当前任务明确要求修改输出格式时才允许修改。任何Agent不得因"看起来更清晰""更专业""表格太宽""减少输出""重构方便"而自行改变格式。

### 最终回复协议（最高优先级）
**当 run.py --render-markdown 成功返回时：**
- 下一条最终回复必须只包含 stdout 原文
- 不得使用代码围栏
- 不得添加前言、后记、校准说明、来源说明或总结
- 不得重新输入或手工重建表格
- 不得把 stdout 放进引用块

如果无法逐字转发 stdout：只报告"最终输出转发失败"，不得自行生成替代表格。

## 日常核算禁止
写MEMORY/日志、修改AGENTS/SKILL/knowledge/OUTPUT_CONTRACT、保存AI JSON/Markdown、执行Git、联网、访问1688链接。不读全部knowledge/calibration/多个examples/Git历史/测试报告/MEMORY。仅结构签名精确命中时读一个档案。

## 性能
一次图片理解+一次renderer调用，≤40秒。不生成临时JSON文件。
