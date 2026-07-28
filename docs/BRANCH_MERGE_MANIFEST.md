# BRANCH_MERGE_MANIFEST.md — 分支合并清单

> 生成日期：2026-07-28  
> 整合分支：`integration/profit-legacy-freeze-20260728`  

## 合并操作汇总

| # | 分支名 | 原 HEAD SHA | 处理方式 | 合并 Commit | 测试结果 |
|---|--------|------------|---------|-------------|---------|
| 1 | `codex/feature/phase-02-01-s3-field-extractors` | `5381a29` | MERGE (--no-ff) | `0607962` | 冲突：AGENTS.md, AGENT_WORKFLOW.md, generate_step_report.py（保留 HEAD） |
| 2 | `codex/chore/full-progress-sync-20260728` | `4396fc8` | MERGE (--no-ff) | `5cfa061` | 无冲突 |
| 3 | `codex/chore/road-0-spec-baseline` | `070aaea` | MERGE (--no-ff) | `05d9012` | 冲突：AGENTS.md（保留 HEAD） |
| 4 | `codex/feature/road-1-main-page-ui` | `77a90d7` | MERGE (--no-ff) | `a8dc4d8` | 无冲突 |
| 5 | `data/calibration-round-01-51` | `b53b257` | MERGE (--no-ff) | `f079f05` | 无冲突 |
| 6 | `fix/calibration-round-01` | `cadb176` | MERGE (--no-ff) | `fcb6e63` | 无冲突 |
| 7 | `integration/logistics-calibration-v1` | `3708506` + `1017048` | MERGE (--no-ff) | `29ab07b` | 无冲突 |

## 合并详情

### 1. Phase 2.1 s3 — 全部 Profit + Phase 2.1

- **分支**：`codex/feature/phase-02-01-s3-field-extractors`
- **原 HEAD**：`5381a2976edffdc08335242de2f20b0a4294e68b`
- **包含内容**：
  - Phase 1.x 完整修复链（fix-03 → fix-06）
  - 动态货代（`configurable-forwarders`, `unlimited-forwarders`）
  - Phase 1.5 完成与复审
  - Phase 1.6 利润调整规则与复审
  - Phase 2.1 OCR 基础、会话、字段提取器
  - 所有利润计算核心代码与测试
- **冲突**：
  - `AGENTS.md`：s3 包含旧版冗长规则，保留 HEAD 精炼版
  - `docs/AGENT_WORKFLOW.md`：双方均有新增，保留 HEAD 精炼版
  - `tools/generate_step_report.py`：s3 为 json-config 版，HEAD 为 argparse 版，保留 HEAD
- **未合入**：旧版 generate_step_report.py 的 `load_config`/`parse_test_summary`/`generate` API

### 2. 全仓进度同步

- **分支**：`codex/chore/full-progress-sync-20260728`
- **原 HEAD**：`4396fc8b6bf9918f0876b9fae540b94a632612ab`
- **包含内容**：
  - `docs/REPOSITORY_PROGRESS_SNAPSHOT_20260728.md`
  - `Profit accounting-Auto/ProfitAccountingAuto.spec`（Windows 打包配置）
  - logistics 2.0 示例、配置和校准数据同步
- **无冲突**

### 3. ROAD-0 需求基线

- **分支**：`codex/chore/road-0-spec-baseline`
- **原 HEAD**：`070aaea8dfe046f1f43ad36859657dba9286a5db`
- **包含内容**：ROAD-0 需求入库、UI 偏差审计、测试基线修复报告
- **冲突**：`AGENTS.md`（保留 HEAD）

### 4. ROAD-1 主页面 UI

- **分支**：`codex/feature/road-1-main-page-ui`
- **原 HEAD**：`77a90d7e0264db5eba63d54d0bf04dcc0a06ef85`
- **包含内容**：
  - 主页面 8 区布局重构
  - 图片框与 FakeAI 联动
  - GUI 冒烟 12 项测试
  - ROAD-1 最终复审报告
- **无冲突**

### 5. 校准样本数据

- **分支**：`data/calibration-round-01-51`
- **原 HEAD**：`b53b257a538d4414445059bc7a9dc1533f561bdd`
- **分叉点**：`02753ef`（ROAD-1 中间点）
- **唯一新增提交**：`b53b257` — 51 个校准样本 JSON 数据
- **无冲突**

### 6. 校准回放修复

- **分支**：`fix/calibration-round-01`
- **原 HEAD**：`cadb176387d5aa1382b03ed3e5eac294962c3574`
- **包含内容**：
  - 校准回放完全可重现（51 样本全量回放）
  - 超轻品可信重量细化（15g/36g/50g 边界）
  - 29 样本数据验证与清洗
  - replay 脚本与验证测试
- **无冲突**

### 7. Round 02 校准工作区

- **分支**：`integration/logistics-calibration-v1`
- **原 HEAD**：`3708506b37df1e4adfc453eac5759f1047ac5476`（+ `1017048` 校准数据提交）
- **包含内容**：
  - Round 02 校准样本（腰带、刷具、香薰机、分趾袜等 10+ 样本）
  - `.gitignore` 模式补充
  - `NEXT_CALIBRATION_SESSION.md`
- **无冲突**

## DUPLICATE 分支（16 个，已完全包含）

以下分支的所有提交已通过上述合并进入冻结基线，标记为 DUPLICATE：

| 分支名 | 被包含于 |
|--------|---------|
| `fix/phase-01-fix-03` | s3 (→ fix-04 → ...) |
| `fix/phase-01-fix-04` | s3 (→ fix-05 → ...) |
| `fix/phase-01-fix-05` | s3 (→ fix-06 → ...) |
| `codex/fix/phase-01-fix-06` | s3 |
| `codex/feature/configurable-forwarders-and-gram-weight` | s3 |
| `codex/feature/unlimited-forwarders` | s3 |
| `codex/feature/phase-1-5-completion` | s3 |
| `codex/fix/phase-1-5-review` | s3 |
| `codex/feature/phase-1-6-profit-adjustment-rules` | s3 |
| `codex/fix/phase-1-6-review` | s3 |
| `codex/test/phase-1-6-windows-acceptance` | s3 |
| `codex/feature/phase-02-01-local-ocr-intake` | s3 |
| `codex/feature/phase-02-01-s1-foundation` | s3 |
| `codex/feature/phase-02-01-s2-intake-session` | s3 |

## 旧分支处理

- **不删除本地或远程分支**
- **不改写历史**
- 所有旧分支保留，待 2.5 迁移完成后另行决定清理
- 通过 `git merge --no-ff` 保留分支名作为合并记录
