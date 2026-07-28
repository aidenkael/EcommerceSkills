# 仓库进度快照 — 2026-07-28

## 1. 仓库地址
https://github.com/aidenkael/EcommerceSkills

## 2. 同步日期
2026-07-28 03:09 GMT+8

## 3. 同步分支
`codex/chore/full-progress-sync-20260728`

## 4. 同步分支完整HEAD
`a17dd744721bb08588bda17530dedf51b97d2a91`

## 5. master完整HEAD
`3704c0c537e5eaec99063a8e9974ba2f67376500`（同步前）
cherry-pick 1.8删除后更新。

## 6. 当前各一级项目状态

| 项目 | 状态 | 说明 |
|------|------|------|
| Profit accounting-Auto | 活跃开发 | Phase 2.1 OCR intake，289+测试 |
| logistics-cost-skill-2.0 | 活跃开发 | CAL校准数据纳入，存在路径相关测试失败 |
| logistics-cost-skill-1.8 | **已删除** | 用户已备份并授权删除 |
| Image Search | 稳定 | 无修改 |
| Information extraction | 空目录占位 | 无修改 |
| review_packages | 活跃 | 新增 phase-1-5-import |
| docs | 稳定 | AGENT_WORKFLOW.md |
| tools | 稳定 | generate_step_report.py |

## 7. 每个项目最新Commit

| 项目 | 最新Commit | 说明 |
|------|-----------|------|
| logistics-cost-skill-1.8 | `9e27edd` | chore: remove legacy |
| logistics-cost-skill-2.0 | `5026d75` | feat: sync calibration progress |
| Profit accounting-Auto | `a17dd74` | feat: sync current progress |
| 仓库规则 | `3704c0c`（master） | repository-rules: AGENTS工作流重构 |

## 8. 本次新增Commit清单

| # | SHA | 信息 |
|---|-----|------|
| 1 | `9e27edd` | chore: remove legacy logistics-cost-skill-1.8 |
| 2 | `5026d75` | feat: sync logistics 2.0 calibration progress |
| 3 | `a17dd74` | feat: sync current Profit accounting-Auto progress |
| 4 | （本报告） | docs: add repository progress snapshot |

## 9. 已推送分支清单
- `codex/chore/full-progress-sync-20260728`（本次同步分支）
- `codex/feature/phase-02-01-local-ocr-intake`
- `codex/feature/phase-02-01-s1-foundation`
- `codex/feature/phase-02-01-s2-intake-session`
- `codex/feature/phase-02-01-s3-field-extractors`

## 10. 未推送或未处理分支及原因

| 分支 | 状态 | 原因 |
|------|------|------|
| `codex/fix/phase-1-6-review` | 远程已存在 | 本地与远程可能一致，需核对 |
| `codex/test/phase-1-6-windows-acceptance` | 远程已存在 | 本地与远程可能一致 |
| `fix/phase-01-fix-03/04/05` | 远程已存在 | 旧修复分支，无新提交 |

## 11. Profit accounting-Auto测试结果
- **通过**：349
- **跳过**：3
- **xpassed**：1
- **错误**：1（test_ocr_intake_interactions — Tcl/Tk环境问题，非代码缺陷）
- **失败**：0
- 环境：Python 3.11 (.venv-311)

## 12. logistics-cost-skill-2.0测试结果
- **通过**：9
- **失败**：8
- **跳过**：0
- 环境：Python 3.13.12
- 失败原因：全部为 `test_integration.py` 中的路径问题（测试从仓库根运行时找不到 `examples/socks_ai.json` 和 `run.py`）。这是**原有问题**，非本次修改引入。
- 失败用例：test_both_modes_have_provider_costs, test_estimate_from_ai_json, test_estimate_from_ai_json_with_weight, test_socks_no_user_weight, test_socks_trusted_weight, test_socks_untrusted_weight, test_link_no_network, test_e2e_socks

## 13. 其他项目测试结果
- Image Search：无自动测试（仅GUI工具）
- Information extraction：空目录

## 14. logistics 2.0 CAL字段和对应文件清单

### Python代码中的CAL字段
| 字段名 | 文件 | 说明 |
|--------|------|------|
| `actual_head_cost` | calculator.py, feedback.py | 真实头程费用 |
| `estimated_head_cost` | calculator.py, feedback.py | 估算头程费用 |
| `conservative_head_cost` | feedback.py | 保守档头程费用 |
| `actual_weight_kg` | calculator.py | 真实重量 |
| `estimated_actual_weight_kg` | feedback.py | 估算实际重量 |
| `estimated_volume_weight_kg` | feedback.py | 估算体积重 |
| `estimated_chargeable_weight` | calculator.py, feedback.py | 估算计费重 |
| `implied_actual_chargeable_weight` | calculator.py | 反推实际计费重 |
| `error_amount` | feedback.py | 误差金额 |
| `error_percent` | feedback.py | 误差百分比 |
| `error_direction` | feedback.py | 误差方向 |
| `correction_threshold` | config.py, calculator.py | 校正阈值 |

### JSON/数据文件中的CAL字段
| 文件 | 跟踪状态 | 说明 |
|------|---------|------|
| `archive/calibration/calibration_samples.json` | ✅ 本次纳入 | CAL-001~CAL-N 样本 |
| `archive/calibration/79_items_original.json` | ✅ 已跟踪 | 79条原始校准 |
| `archive/calibration/79_items_verified.json` | ✅ 已跟踪 | 79条已验证 |
| `archive/calibration/79_items_visual_estimates.json` | ✅ 已跟踪 | 79条视觉估算 |
| `data/head_cost_feedback.csv` | ✅ 本次纳入 | 真实头程反馈记录 |
| `examples/*_ai.json`（35个） | ✅ 本次纳入 | AI JSON校准样本 |
| `config/logistics_config.json` | ✅ 已跟踪（本次修改） | 费率与阈值配置 |

## 15. 被.gitignore排除的CAL文件处理结果
- **无CAL文件被.gitignore误伤**
- `data/head_cost_feedback.csv` 和 `calibration_samples.json` 均未被忽略，只是之前未 `git add`
- 已全部纳入版本控制

## 16. logistics-cost-skill-1.8删除确认
- **本地删除**：✅ 已确认（用户自行删除，118个文件显示为 `D` 状态）
- **Git提交**：✅ Commit `9e27edd` — `chore: remove legacy logistics-cost-skill-1.8`
- **历史保留**：v1.8 的所有历史commit仍保留在Git历史中

## 17. 未提交或被排除文件清单

| 文件/目录 | 原因 |
|----------|------|
| `Profit accounting-Auto/test_sessions/` | 测试运行输出，不应纳入版本控制 |
| `Profit accounting-Auto/.venv-311/` | Python虚拟环境 |
| `.workbuddy/` | Agent工作目录（.gitignore排除） |
| `review_packages/phase-1-5-import/` | git bundle文件，需用户确认是否纳入 |

## 18. 已知失败和风险

1. **logistics-cost-skill-2.0 集成测试失败（8项）**：路径问题，需修复测试以支持从仓库根运行
2. **Profit accounting-Auto OCR测试错误（1项）**：Tcl/Tk环境问题，非代码缺陷
3. **review_packages/phase-1-5-import/phase-1-5-completion.bundle**：未提交，需确认
4. **多个分支无远程跟踪**：旧分支可能需要清理或设置跟踪

## 19. 后续建议复审顺序

1. **logistics-cost-skill-2.0 CAL数据**：验证 `calibration_samples.json` 和 `head_cost_feedback.csv` 的数据完整性
2. **logistics-cost-skill-2.0 测试路径问题**：修复 `test_integration.py` 支持从仓库根运行
3. **Profit accounting-Auto Phase 2.1**：OCR intake 功能的完整性和验收
4. **1.8 删除影响**：确认无其他文件引用 1.8 路径
5. **分支清理**：评估旧 fix/ 分支是否可归档

## 20. 最终工作区状态
- 分支：`codex/chore/full-progress-sync-20260728`
- HEAD：`a17dd74`（报告提交后更新）
- 工作区：除 test_sessions/.venv-311/.workbuddy 外 clean
- 远程同步：同步分支已推送
