# MIGRATION_SOURCE_MANIFEST.md — 2.5 迁移来源清单

> 生成日期：2026-07-28  
> 冻结基线：`profit-legacy-freeze-20260728`  

本文件列出冻结基线中每个模块/文件的来源信息与 2.5 迁移建议。仅做来源清单，不创建 2.5 目录。

## 处理建议代号

| 代号 | 含义 |
|------|------|
| KEEP | 直接沿用（数据结构、配置格式不变） |
| ADAPT | 需适配 PySide6 / 新架构后使用 |
| REFERENCE_ONLY | 仅作逻辑参考，需重新实现 |
| DOCUMENT_ONLY | 仅文档价值，不迁移代码 |
| EXCLUDE | 旧实现，2.5 中由新方案替代 |

---

## 一、Profit accounting-Auto — 核心计算

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `calculation/profit.py` | 利润正算与反推核心 | ADAPT |
| `calculation/logistics.py` | 物流费用计算（双货代/多货代） | ADAPT |
| `calculation/profit_adjustments.py` | 利润调整规则引擎 | ADAPT |
| `calculation/rules.py` | 规则模型、冻结、生命周期 | ADAPT |
| `config/config_manager.py` | 配置读写 | ADAPT |
| `config/forwarder_manager.py` | 动态货代管理 | ADAPT |
| `config/profit_adjustment_manager.py` | 利润调整规则持久化 | ADAPT |
| `database/db_manager.py` | SQLite 数据库管理、Schema 迁移 v1→v6 | KEEP（数据格式） |
| `tests/test_profit.py` | 利润计算测试套件 | ADAPT |
| `tests/test_logistics.py` | 物流计算测试 | ADAPT |
| `tests/test_profit_adjustments.py` | 利润调整规则测试 | ADAPT |
| `tests/test_unlimited_forwarders.py` | 动态货代测试 | ADAPT |

## 二、Profit accounting-Auto — OCR 图片录入

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `image_intake/image_types.py` | 图片类型定义 | ADAPT |
| `image_intake/result_models.py` | OCR 候选字段模型 | ADAPT |
| `image_intake/intake_service.py` | 录入服务协调 | ADAPT |
| `image_intake/intake_controller.py` | 录入控制器 | REFERENCE_ONLY |
| `image_intake/extractors/common.py` | 提取器基类 | ADAPT |
| `image_intake/extractors/dimension_extractor.py` | 尺寸提取器 | ADAPT |
| `image_intake/extractors/shein_price_extractor.py` | SHEIN 价格提取器 | ADAPT |
| `image_intake/extractors/cost_shipping_extractor.py` | 成本运费提取器 | ADAPT |
| `ocr/base_engine.py` | OCR 引擎基类 | REFERENCE_ONLY |
| `adapters/fake_vision.py` | FakeAI 视觉适配器（测试用） | REFERENCE_ONLY |
| `ui/ocr_intake_dialog.py` | OCR 录入对话框（Tkinter） | REFERENCE_ONLY |
| `tests/test_extractors.py` | 提取器测试 | ADAPT |
| `tests/test_intake_service.py` | 录入服务测试 | ADAPT |
| `tests/test_result_models.py` | 结果模型测试 | ADAPT |
| `tests/test_base_engine.py` | OCR 引擎测试 | ADAPT |
| `tests/test_ocr_intake_dialog.py` | OCR 对话框测试 | REFERENCE_ONLY |

## 三、Profit accounting-Auto — UI

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `ui/main_window.py` | 主窗口布局（Tkinter） | REFERENCE_ONLY |
| `ui/product_page.py` | 商品页面（Tkinter，含 8 区布局） | REFERENCE_ONLY |
| `ui/history_page.py` | 历史页面（Tkinter） | REFERENCE_ONLY |
| `tests/test_road1_review.py` | ROAD-1 UI 交互测试 | REFERENCE_ONLY |
| `tests/test_road1_gui_smoke.py` | ROAD-1 GUI 冒烟测试 | REFERENCE_ONLY |

> **UI 冻结说明**：以上 Tkinter UI 作为 2.5 PySide6 的布局与交互参考，代码不直接迁移。

## 四、Profit accounting-Auto — 文档

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `docs/Development rules-1.5.md` | 最高产品需求与开发总规 | KEEP（2.5 继续引用） |
| `docs/assets/development-rules-1.5-ui-baseline.png` | 1.5 冻结 UI 截图 | DOCUMENT_ONLY |
| `docs/WINDOWS_ACCEPTANCE.md` | Windows 验收清单 | DOCUMENT_ONLY |
| `review_packages/Profit accounting-Auto/` | 全部阶段报告（30+ 份） | DOCUMENT_ONLY |
| `ProfitAccountingAuto.spec` | PyInstaller 打包配置 | EXCLUDE |

## 五、logistics-cost-skill-2.0 — 计算引擎

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `logistics_cost/calculator.py` | 头程运费确定性计算 | KEEP（算法核心） |
| `logistics_cost/estimator.py` | AI JSON → 头程估算入口 | ADAPT |
| `logistics_cost/weight_rules.py` | 超轻品可信重量修正 | KEEP |
| `logistics_cost/ai_schema.py` | AI JSON Schema 校验 | ADAPT |
| `config/logistics_config.json` | 货代费率、体积重分母等配置 | KEEP（配置格式） |
| `tests/test_integration.py` | 集成测试（40 项） | ADAPT |
| `tests/test_replay_validation.py` | 校准回放验证测试 | ADAPT |

## 六、logistics-cost-skill-2.0 — 校准系统

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `archive/calibration/calibration_samples.json` | Round 01 校准样本（51 个） | KEEP |
| `archive/calibration/calibration_samples_cleaned_v1.json` | 清洗后校准样本 | KEEP |
| `archive/calibration/calibration_samples_round_02.json` | Round 02 校准样本（10+ 个） | KEEP |
| `archive/calibration/calibration_round_01_replay_report.md` | Round 01 回放报告 | DOCUMENT_ONLY |
| `archive/calibration/calibration_validation_report.md` | 校准验证报告 | DOCUMENT_ONLY |
| `scripts/phase5_replay.py` | 校准全量回放脚本 | ADAPT |
| `scripts/phase1_clean_data.py` | 数据清洗脚本 | ADAPT |
| `docs/NEXT_CALIBRATION_SESSION.md` | 下一轮校准指导 | DOCUMENT_ONLY |
| `data/head_cost_feedback.csv` | 头程费用反馈表 | DOCUMENT_ONLY |

## 七、logistics-cost-skill-2.0 — AI JSON 示例

| 原项目路径 | 商品 | 建议 |
|-----------|------|------|
| `examples/socks_ai.json` | 分趾袜（标准样例） | KEEP |
| `examples/aroma_diffuser_ai.json` | 香薰机（未跟踪） | KEEP |
| `examples/brush_set_ai.json` | 刷具套装（未跟踪） | KEEP |
| `examples/greca_belt_ai.json` | 腰带 v1（未跟踪） | KEEP |
| `examples/greca_belt_v2.json` | 腰带 v2（未跟踪） | KEEP |
| `examples/split_toe_socks_ai.json` | 分趾袜（未跟踪） | KEEP |
| `examples/dual_head_makeup_brush_set_F4E6_ai.json` | 双头化妆刷（未跟踪） | KEEP |
| `examples/*.json` | 其他 50+ AI JSON 示例 | KEEP |

> 未跟踪文件（`??`）作为有效校准样本，建议在 2.5 中正式入库。

## 八、仓库级别

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `AGENTS.md` | 仓库根规则 | KEEP |
| `docs/AGENT_WORKFLOW.md` | Agent 工作流规范 | KEEP |
| `docs/LEGACY_FREEZE.md` | 冻结声明 | KEEP |
| `docs/BRANCH_MERGE_MANIFEST.md` | 合并清单 | DOCUMENT_ONLY |
| `docs/MIGRATION_SOURCE_MANIFEST.md` | 本文件 | DOCUMENT_ONLY |
| `docs/REPOSITORY_PROGRESS_SNAPSHOT_20260728.md` | 仓库进度快照 | DOCUMENT_ONLY |
| `tools/generate_step_report.py` | 自动报告脚本 | KEEP |
| `tools/report_config.json` | 报告配置 | KEEP |
| `tools/run_step_report.bat` | Windows 报告批处理 | KEEP |
| `.gitignore` | Git 忽略规则 | KEEP |

---

## 汇总统计

| 处理建议 | 数量 |
|---------|------|
| KEEP | 20 |
| ADAPT | 25 |
| REFERENCE_ONLY | 12 |
| DOCUMENT_ONLY | 15 |
| EXCLUDE | 1 |

> 总计 73 个模块/文件。2.5 迁移时以此清单为索引，按模块逐步提取即可。
