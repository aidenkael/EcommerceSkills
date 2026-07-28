# BRANCH_MERGE_MANIFEST.md -- 分支合并清单

> 生成日期：2026-07-28（R2 修正）  
> 整合分支：`integration/profit-legacy-freeze-20260728`  
> R2 分支：`chore/profit-legacy-freeze-r2`  

## 分支统计

| 分类 | 数量 |
|------|------|
| 本地分支 | 24 |
| 远程分支 | 23 |
| 去重后唯一分支 | 24 |
| 基线分支（master） | 1 |
| 整合与 R2 分支 | 2 |
| MERGE（已合并） | 7 |
| DUPLICATE（已被包含） | 14 |

## 合并操作汇总

| # | 分支名 | 原 HEAD SHA | 处理方式 | 合并 Commit | 冲突处理 |
|---|--------|------------|---------|-------------|---------|
| 1 | `codex/feature/phase-02-01-s3-field-extractors` | `5381a29` | MERGE (--no-ff) | `0607962` | AGENTS.md x2, AGENT_WORKFLOW.md, generate_step_report.py（保留 HEAD） |
| 2 | `codex/chore/full-progress-sync-20260728` | `4396fc8` | MERGE (--no-ff) | `5cfa061` | 无 |
| 3 | `codex/chore/road-0-spec-baseline` | `070aaea` | MERGE (--no-ff) | `05d9012` | AGENTS.md（保留 HEAD） |
| 4 | `codex/feature/road-1-main-page-ui` | `77a90d7` | MERGE (--no-ff) | `a8dc4d8` | 无 |
| 5 | `data/calibration-round-01-51` | `b53b257` | MERGE (--no-ff) | `f079f05` | 无 |
| 6 | `fix/calibration-round-01` | `cadb176` | MERGE (--no-ff) | `fcb6e63` | 无 |
| 7 | `integration/logistics-calibration-v1` | `3708506` + `1017048` | MERGE (--no-ff) | `29ab07b` | 无 |

## DUPLICATE 分支（14 个，已被上述合并完全包含）

| # | 分支名 | 原 HEAD SHA | 包含关系 |
|---|--------|------------|---------|
| 1 | `fix/phase-01-fix-03` | `7e15265` | ⊂ fix-04 ⊂ ... ⊂ s3 |
| 2 | `fix/phase-01-fix-04` | `bf84f69` | ⊂ fix-05 ⊂ ... ⊂ s3 |
| 3 | `fix/phase-01-fix-05` | `27ea6fb` | ⊂ fix-06 ⊂ ... ⊂ s3 |
| 4 | `codex/fix/phase-01-fix-06` | `efd7c50` | ⊂ config-forwarders ⊂ ... ⊂ s3 |
| 5 | `codex/feature/configurable-forwarders-and-gram-weight` | `4f27f07` | ⊂ unlimited-forwarders ⊂ ... ⊂ s3 |
| 6 | `codex/feature/unlimited-forwarders` | `5f3cae8` | ⊂ phase-1-5 ⊂ ... ⊂ s3 |
| 7 | `codex/feature/phase-1-5-completion` | `10e2bdd` | ⊂ phase-1-6 ⊂ ... ⊂ s3 |
| 8 | `codex/fix/phase-1-5-review` | `a50108a` | ⊂ phase-1-6 ⊂ ... ⊂ s3 |
| 9 | `codex/feature/phase-1-6-profit-adjustment-rules` | `8b8b6a2` | ⊂ phase-1-6-review ⊂ ... ⊂ s3 |
| 10 | `codex/fix/phase-1-6-review` | `589c360` | ⊂ s1 ⊂ s2 ⊂ s3 |
| 11 | `codex/test/phase-1-6-windows-acceptance` | `9eae400` | ⊂ s1 ⊂ s2 ⊂ s3（同 local-ocr-intake HEAD） |
| 12 | `codex/feature/phase-02-01-local-ocr-intake` | `9eae400` | ⊂ s1 ⊂ s2 ⊂ s3（同 windows-acceptance HEAD） |
| 13 | `codex/feature/phase-02-01-s1-foundation` | `15a9c6a` | ⊂ s2 ⊂ s3 |
| 14 | `codex/feature/phase-02-01-s2-intake-session` | `6280111` | ⊂ s3 |

> `codex/feature/road-1-main-page-ui` 在本地 HEAD (`77a90d7`) 领先远程 (`02753ef`)，已在整合分支中合并完整版本。

## 合并详情

### 1. Phase 2.1 s3 -- Profit Phase 1.5/1.6 + Phase 2.1 全部

包含：完整利润计算、动态货代、利润调整规则、OCR 图片录入、字段提取器、ROAD-1 UI

### 2-4. 全仓同步与路线图

包含：仓库进度快照、ROAD-0 需求基线、ROAD-1 主页面 8 区布局

### 5-6. 物流校准

包含：51 校准样本、校准回放完全可重现、超轻品修正

### 7. Round 02 校准

包含：Round 02 工作区准备、校准样本数据

## R2 修正内容

| 修正项 | 内容 |
|--------|------|
| 分支数量 | 本地 24（原报告 22，因未计入 master 和整合分支）、远程 23、去重 24 |
| DUPLICATE 数量 | 14（原报告 16，经重新核查修正） |
| 冻结范围 | 明确区分已冻结项目（Profit）和持续维护项目（logistics） |
| 标签引用 | 改为以 `profit-legacy-freeze-20260728-r2` 为唯一权威 |
| 校准数据 | 补充 Round 02 最终提交统计 |
| 测试 | 补充 collection errors = 0 验证结果 |

## 旧分支处理

- 不删除本地或远程分支
- 不改写历史
- 所有旧分支保留，待 2.5 迁移完成后另行决定清理
- 通过 `git merge --no-ff` 保留分支名作为合并记录
