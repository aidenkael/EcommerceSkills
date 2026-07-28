# MIGRATION_SOURCE_MANIFEST.md -- 2.5 迁移来源清单

> 生成日期：2026-07-28（R2 修正）  
> 冻结基线：`profit-legacy-freeze-20260728-r2`  

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

## 一、Profit accounting-Auto -- 核心计算

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `calculation/profit.py` | 利润正算与反推核心 | ADAPT |
| `calculation/logistics.py` | 物流费用计算（多货代） | ADAPT |
| `calculation/profit_adjustments.py` | 利润调整规则引擎 | ADAPT |
| `calculation/rules.py` | 规则模型、冻结、生命周期 | ADAPT |
| `config/config_manager.py` | 配置读写 | ADAPT |
| `config/forwarder_manager.py` | 动态货代管理 | ADAPT |
| `config/profit_adjustment_manager.py` | 利润调整规则持久化 | ADAPT |
| `database/db_manager.py` | SQLite 数据库管理、Schema v1-v6 | KEEP（数据格式） |
| `tests/test_profit.py` | 利润计算测试 | ADAPT |
| `tests/test_logistics.py` | 物流计算测试 | ADAPT |
| `tests/test_profit_adjustments.py` | 利润调整规则测试 | ADAPT |
| `tests/test_unlimited_forwarders.py` | 动态货代测试 | ADAPT |

## 二、Profit accounting-Auto -- OCR 图片录入

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

## 三、Profit accounting-Auto -- UI（全部 REFERENCE_ONLY）

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `ui/main_window.py` | 主窗口布局（Tkinter） | REFERENCE_ONLY |
| `ui/product_page.py` | 商品页面（Tkinter，含 8 区布局） | REFERENCE_ONLY |
| `ui/history_page.py` | 历史页面（Tkinter） | REFERENCE_ONLY |

> UI 冻结说明：以上 Tkinter UI 作为 2.5 PySide6 的布局与交互参考，代码不直接迁移。

## 四、Profit accounting-Auto -- 文档

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `docs/Development rules-1.5.md` | 最高产品需求与开发总规 | KEEP（2.5 需求来源） |
| `docs/assets/development-rules-1.5-ui-baseline.png` | 1.5 冻结 UI 截图 | DOCUMENT_ONLY |
| `docs/WINDOWS_ACCEPTANCE.md` | Windows 验收清单 | DOCUMENT_ONLY |

> `Development rules-1.5.md` 标记为 2.5 需求来源。2.5 将生成新的 `Development rules-2.5.md`；2.5 总则生效后，1.5 仅作为历史和来源文档，不再作为新项目最高规则。

## 五、logistics-cost-skill-2.0 -- 计算引擎

| 原项目路径 | 功能说明 | 建议 |
|-----------|---------|------|
| `logistics_cost/calculator.py` | 头程运费确定性计算 | KEEP（算法核心） |
| `logistics_cost/estimator.py` | AI JSON -> 头程估算入口 | ADAPT |
| `logistics_cost/weight_rules.py` | 超轻品可信重量修正 | KEEP |
| `logistics_cost/ai_schema.py` | AI JSON Schema 校验 | ADAPT |
| `config/logistics_config.json` | 货代费率、体积重分母等配置 | KEEP（配置格式） |
| `tests/test_integration.py` | 集成测试（40 项） | ADAPT |
| `tests/test_replay_validation.py` | 校准回放验证测试 | ADAPT |

## 六、logistics-cost-skill-2.0 -- 校准系统

| 原项目路径 | 功能说明 | 数量 | 建议 |
|-----------|---------|------|------|
| `archive/calibration/calibration_samples.json` | Round 01 校准样本 | 51 | KEEP |
| `archive/calibration/calibration_samples_cleaned_v1.json` | 清洗后校准样本 | 51 | KEEP |
| `archive/calibration/calibration_samples_round_02.json` | Round 02 校准样本 | 14 | KEEP |
| `archive/calibration/calibration_round_01_replay_report.md` | Round 01 回放报告 | -- | DOCUMENT_ONLY |
| `archive/calibration/calibration_validation_report.md` | 校准验证报告 | -- | DOCUMENT_ONLY |
| `scripts/phase5_replay.py` | 校准全量回放脚本 | -- | ADAPT |
| `scripts/phase1_clean_data.py` | 数据清洗脚本 | -- | ADAPT |
| `docs/NEXT_CALIBRATION_SESSION.md` | 下一轮校准指导 | -- | DOCUMENT_ONLY |
| `data/head_cost_feedback.csv` | 头程费用反馈表 | -- | DOCUMENT_ONLY |

## 七、logistics-cost-skill-2.0 -- AI JSON 示例

| 原项目路径 | 商品 | 来源 | 建议 |
|-----------|------|------|------|
| `examples/socks_ai.json` | 分趾袜（标准样例） | 已跟踪 | KEEP |
| `examples/aroma_diffuser_ai.json` | 车载香薰机 | R2 新增 | KEEP |
| `examples/arm_sleeves_ai.json` | UV 防晒臂套 | R2 新增 | KEEP |
| `examples/brush_set_ai.json` | 双头化妆刷套装 | R2 新增 | KEEP |
| `examples/camera_strap_ai.json` | 快拆相机腕带 | R2 新增 | KEEP |
| `examples/dual_head_makeup_brush_set_F4E6_ai.json` | 双头化妆刷 F4E6（含中文品名） | R2 新增 | KEEP |
| `examples/gaia_figurine_ai.json` | 大地女神树脂工艺像 | R2 新增 | KEEP |
| `examples/ganesha_ai.json` | 象神树脂像 | R2 新增 | KEEP |
| `examples/greca_belt_ai.json` | 希腊回纹金属腰带 v1 | R2 新增 | KEEP |
| `examples/greca_belt_v2.json` | 金属腰链 v2 | R2 新增 | KEEP |
| `examples/painthandle_ai.json` | 喷漆助力手柄 | R2 新增 | KEEP |
| `examples/split_toe_socks_ai.json` | 26 款韩系分趾袜 | R2 新增 | KEEP |
| `examples/*.json` | 其他 55+ AI JSON 示例 | 已跟踪 | KEEP |

> R2 新增 11 个 AI JSON 示例，全部通过 schema 验证和 estimator 管道。

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

## 排除文件

| 路径 | 原因 |
|------|------|
| `Profit accounting-Auto/.venv-311/` | 虚拟环境（56MB，.gitignore 已排除） |
| `Profit accounting-Auto/test_sessions/` | 测试临时数据（.gitignore 已排除） |
| `review_packages/phase-1-5-import/` | 3.2MB bundle（归档参考，不提交） |
| `Image Search/` 未提交修改 | v6.1 修改（独立项目，不纳入冻结） |
| `.workbuddy/` | Agent 工作目录（.gitignore 已排除） |

---

## 汇总统计

| 处理建议 | 数量 |
|---------|------|
| KEEP | 22 |
| ADAPT | 24 |
| REFERENCE_ONLY | 12 |
| DOCUMENT_ONLY | 16 |
| EXCLUDE | 1 |
| **总计** | **75** |

> 2.5 迁移时以此清单为索引，按模块逐步提取即可。物流核心算法（logistics-cost-skill-2.0）作为唯一上游独立维护，2.5 不得自行维护另一套物流算法。
