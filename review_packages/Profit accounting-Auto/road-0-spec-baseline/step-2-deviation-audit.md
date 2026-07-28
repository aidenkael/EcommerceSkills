# ROAD-0 Step 2 — 现状偏差审计（对照 Development rules-1.5.md）

**生成时间：** 2026-07-28  
**对照文档：** `Profit accounting-Auto/docs/Development rules-1.5.md`  
**审计范围：** `Profit accounting-Auto/` 与 `logistics-cost-skill-2.0/`

---

## 一、可复用内容（保留并迁移到新架构）

### Profit accounting-Auto

| 模块/组件 | 路径 | 说明 |
|---|---|---|
| `calculation/logistics.py` | calculation/logistics.py | 干净的体积重/计费重/头程/总物流公式函数，全部参数化，无硬编码货代 |
| `calculation/profit.py` | calculation/profit.py | 利润/净利/净利率/反推售价，公式独立，便于调用 |
| `calculation/currency.py` | calculation/currency.py | USD↔RMB 双向换算 |
| `config/forwarder_manager.py` | config/forwarder_manager.py | 动态货代 CRUD（LOG-005 符合），数据库为真源 |
| `config/config_manager.py` | config/config_manager.py | 运行时配置管理（汇率/尾程/货代规则封装） |
| `database/db_manager.py` | database/db_manager.py | SQLite Schema v7、迁移、备份恢复、货代/利润规则/产品快照 |
| `image_intake/intake_service.py` | image_intake/intake_service.py | 会话创建、图片复制、原子写入、旧会话清理 — 可迁移到新图片框 |
| `image_intake/intake_controller.py` | image_intake/intake_controller.py | 与 Tkinter 解耦的控制器（图片管理/OCR/选择编辑/确认） |
| `image_intake/extractors/*.py` | image_intake/extractors/ | 三个字段提取器（价格/成本运费/尺寸重量），逻辑与 UI 解耦 |
| `image_intake/result_models.py` | image_intake/result_models.py | 数据模型（部分如 MeasurementScope 可复用，OcrCandidate/FielSelection 可降级为后端模型） |
| 全部 26 个测试 | tests/ | 测试结构稳定，可继续覆盖新功能 |

### logistics-cost-skill-2.0

| 模块/组件 | 路径 | 说明 |
|---|---|---|
| `logistics_cost/ai_schema.py` | logistics_cost/ai_schema.py | AI JSON 契约（validate/to_estimate_inputs/estimate_from_ai_json）— 符合 LOG-002 |
| `logistics_cost/evidence_resolver.py` | logistics_cost/evidence_resolver.py | 多源证据仲裁（页面/用户/OCR/视觉）— 符合 LOG-002 |
| `logistics_cost/soft_goods_rules.py` | logistics_cost/soft_goods_rules.py | 软品体积重高估保护 |
| `logistics_cost/weight_rules.py` | logistics_cost/weight_rules.py | 用户重量信任级别与 +0.05kg 修正 |
| `logistics_cost/packaging_decision_ai.py` | logistics_cost/packaging_decision_ai.py | 包装方案校验（拒绝 AI 计算费用）— 符合 AI-003 |
| `logistics_cost/packing_engine.py` | logistics_cost/packing_engine.py | 基于 Fact + Profile 的确定性包装尺寸 |
| `logistics_cost/calculator.py:calc_freight_costs` | logistics_cost/calculator.py | 双货代对比计算 — 符合 LOG-002 |
| `archive/calibration/*.json` | archive/calibration/ | 79 项 CAL 样本可继续回归 |
| `examples/*.json` | examples/ | 9 个真实 AI JSON 估算样本 |

---

## 二、应停止扩展的旧 OCR 弹窗（按 APPENDIX A）

按 Development rules-1.5.md 附录 A + ROAD-1 要求，**以下内容不得再扩展或增加新功能**，仅作为历史代码与测试资产保留：

| 旧内容 | 路径 | 说明 |
|---|---|---|
| `OcrIntakeDialog` 主弹窗 | `Profit accounting-Auto/ui/ocr_intake_dialog.py`（530行） | 完整独立 GUI：上传/拖拽/粘贴/预览/OCR/候选编辑/确认回填。规则要求最终用户入口为"主页面图片框"，不再跳转此弹窗 |
| SHEIN核价 截图识别 | `image_intake/image_types.py` 的 `SHEIN核价` 类型 | IMG-002 已取消该类型，SHEIN核价完全手动录入（PROFIT-001） |
| `OcrCandidate` / `FieldSelection` / `FieldCandidates` / `MeasurementScope` 在 UI 展示 | `ui/ocr_intake_dialog.py` 的 Treeview 候选表 | FLOW-003 + AI-004 要求候选/置信度/坐标/证据索引只在后台保存，不暴露给普通用户 |
| `_open_ocr_intake()` / `_apply_ocr_selections()` 主流程入口 | `ui/product_page.py` | 应被主页面图片框的"AI识图"取代 |
| `scopes` 编辑控件（裸件/包装/无法确认） | `ui/ocr_intake_dialog.py` SCOPE_LABELS | 不暴露给普通用户（FLOW-003） |
| PR 规则：OCR 作为正式主识别 | `image_intake/*` 全套 | AI-001 明确正式方案使用外部视觉 API，本地 OCR 仅作实验/离线辅助 |

---

## 三、待重构内容（高优先级，按 LOG-002/LOG-003/MOD-001）

### logistics-cost-skill-2.0

| 编号 | 问题 | 位置 | 对应规则 |
|---|---|---|---|
| R-1 | `FREIGHT_FORWARDERS` 在 `calculator.py` 硬编码（深圳80+10/义乌100+6） | `logistics_cost/calculator.py:26-29` | LOG-003.2 货代配置应由利润软件注入，不能继续硬编码 |
| R-2 | `get_freight_rate()` / `_category()` / `calc_head_cost(category_type)` 残留旧"包类/非包类"签名 | `logistics_cost/calculator.py:94-123` | LOG-003.3 废弃旧费率分流 |
| R-3 | `config/logistics_config.json` 仍保留 `categories` 字段（已 _deprecated） | config/logistics_config.json:34-47 | LOG-003.3 同上 |
| R-4 | `calc_total_cost(category_type)` 参数未使用 | `logistics_cost/calculator.py:135-146` | LOG-003.7 统一字段与签名 |
| R-5 | 经验规则/阈值（`evidence_quality`、`correction_threshold`）散落在 config.json 而非版本化校准包 | config/logistics_config.json:48-72 | LOG-003.5 + CAL-001 应通过校准包分发 |
| R-6 | `estimator.py:_safe_float()` 默认值 0.0 可能掩盖缺失数据 | `logistics_cost/estimator.py:40-44` | AI-007 缺失数据不得静默填充假值 |
| R-7 | `calc_logistics()` 返回结构含 `first_leg_rate`/`first_leg_cost` 命名但没有显式拆分 `head_freight`/`fixed_fee`/`tail_fee`/`total` | `logistics_cost/calculator.py:209-230` | LOG-003.4 输出需拆分 |

### Profit accounting-Auto

| 编号 | 问题 | 位置 | 对应规则 |
|---|---|---|---|
| R-8 | 主流程仍把 OCR 弹窗作为图片录入主入口 | `ui/product_page.py:_open_ocr_intake` | ROAD-1 主页面重构 |
| R-9 | `calculation/logistics.py:VOLUME_DIVISOR=8000` 常量化 | `calculation/logistics.py:13` | LOG-004 体积重除数应可配置 |
| R-10 | 利润公式散落在 `product_page.py` 与 `profit.py`，未确认是否所有 UI 计算均经过 profit_engine 单一入口 | `ui/product_page.py` 多处 | PROFIT-005 统一计算引擎 |
| R-11 | 利润区暂未实现"最后修改字段决定方向"的双向反推机制 | `ui/product_page.py` | PROFIT-003 + 防止字段循环更新 |
| R-12 | 历史记录页未显示图片，仅显示文字 | `ui/history_page.py` | DATA-005 历史页必须直接显示图片 |
| R-13 | 货代配置界面（SettingsDialog）尚未实现 `forwarder_manager` 的 UI 接入 | `ui/main_window.py:SettingsDialog` | LOG-005 设置中可修改货代参数 |

---

## 四、尚未实现内容（按 GOV/UI/SPEC/LOG/AI/PROFIT/CAL/PAGE 编号）

| 编号 | 章节 | 待实现项 |
|---|---|---|
| M-1 | UI-001/002 | 最终主页面布局：左侧导航（以图搜图/新商品测算/历史记录管理/数据导入导出/模型校准反馈/设置） |
| M-2 | UI-002 | 底部：当前数据目录/更改目录/USD↔CNY汇率/软件版本 |
| M-3 | IMG-001/002 | 默认 5 张图片框、最少 3、最多 6，类型仅 3 种：主图/商品信息/尺寸/重量 |
| M-4 | IMG-003 | 点击上传/拖拽/Ctrl+V 粘贴/预览/放大/删除/Del 删除/修改类型 |
| M-5 | IMG-004 | 图片框配置保存（数量、顺序、默认类型） |
| M-6 | IMG-005 | 多角度主图（最多 3 主图 + 1 信息 + 1 尺寸） |
| M-7 | AI-001~006 | AI识图摘要 + 重新估算规格 + AI原始/人工值双轨保存 |
| M-8 | AI-007 | 缺失数据留空 + 标记需确认 + 不生成虚假完整利润 |
| M-9 | SPEC-002/003 | 正常档与保守档包装规格同时显示（含两档包装方式/包装后尺寸/重量/说明） |
| M-10 | SPEC-004 | 上游字段修改后旧包装估算失效提示 |
| M-11 | LOG-001~003 | 物流 2.0 模块化移植（接口稳定、配置注入、费用拆分、校准外置、影子对比） |
| M-12 | LOG-005 | 普通用户设置界面可改货代参数 |
| M-13 | LOG-006 | 每个货代卡片显示计费重/头程/固定费/尾程/总费用 |
| M-14 | LOG-007 | "当前系统总成本"只读区域 |
| M-15 | PROFIT-001~004 | SHEIN核价手动录入 + USD/RMB 联动 + 最后修改字段决定方向 + 防止循环 |
| M-16 | PROFIT-005 | 利润引擎版本化（推广预留/29 USD 以下 2.99 USD 补贴/汇率） |
| M-17 | UI-601~603 | 底部仅"保存本次记录"+"清空并新建"；保存不自动清空；清空有未保存确认 |
| M-18 | DATA-001~006 | 图片正式持久化到 `<data_root>/products/<product_id>/images/`；首次保存不可变快照；历史可恢复图片/AI值/人工值；可迁移完整数据目录 |
| M-19 | PAGE-001~004 | 以图搜图/数据导入导出/模型校准反馈/设置四个页面 |
| M-20 | CAL-001~003 | 校准包导入/验证/备份/启用/回滚 |
| M-21 | MOD-001~005 | 模块化分层（ui/application/domain/engines/adapters/calibration/storage）；解压即用文件夹版交付；不过度插件化 |

---

## 五、审计结论

1. **现有 Phase 2.1 图片能力（上传/拖拽/粘贴/预览/会话/提取器/OCR控制器）大部分可复用**，但必须从独立 OCR 弹窗迁入主页面图片框（ROAD-1）。
2. **物流 2.0 核心能力符合 1.5 规则**（双货代对比/AI JSON 契约/证据仲裁/软品保护/可信重量/包装校验），但**R-1 硬编码货代费率** 与 **R-5 校准规则散落 config** 是阻塞点（需在 ROAD-3 处理）。
3. **业务公式 / Schema / 金额规则本阶段均未改动**，符合 ROAD-0 "暂不改业务代码" 原则。
4. **Tcl/Tk 与 OCR 弹窗均不涉及公式**，本阶段测试基线修复属环境隔离问题，未触碰计算引擎。