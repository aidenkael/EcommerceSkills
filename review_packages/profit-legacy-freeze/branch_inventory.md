# 分支盘点清单 — Profit Legacy Freeze 2026-07-28

> 盘点时间：2026-07-28 15:22 GMT+8
> 仓库：https://github.com/aidenkael/EcommerceSkills.git
> 当前分支：integration/logistics-calibration-v1

## 仓库状态

| 项目 | 状态 |
|------|------|
| 远程 | origin → https://github.com/aidenkael/EcommerceSkills.git |
| master HEAD | `1ac4e08` — chore: remove legacy logistics-cost-skill-1.8 |
| 当前分支 | `integration/logistics-calibration-v1` @ `3708506` (领先 master 1 commit) |
| 标签 | 无 |
| Stash | 无 |
| Worktree | 仅默认工作树 |
| 嵌套 Git | 无 |
| 未提交修改 | 4 个文件（详见下文） |
| 未跟踪文件 | 若干（详见下文） |

## 分支线性关系总览

```
master (1ac4e08)
│
├─ integration/logistics-calibration-v1 (3708506) [+1 commit]
│
└─ 2015b88 (fork point: repository-rules) ← 主开发链分叉点
   │
   ├─ fix/phase-01-fix-03 (7e15265) [+1]
   ├─ fix/phase-01-fix-04 (bf84f69) [+2] ⊃ fix-03
   ├─ fix/phase-01-fix-05 (27ea6fb) [+3] ⊃ fix-04
   ├─ codex/fix/phase-01-fix-06 (efd7c50) [+8] ⊃ fix-05
   ├─ codex/feature/configurable-forwarders-and-gram-weight (4f27f07) [+9] ⊃ fix-06
   ├─ codex/feature/unlimited-forwarders (5f3cae8) [+10] ⊃ config-forwarders
   ├─ codex/feature/phase-1-5-completion (10e2bdd) [+13] ⊃ unlimited-forwarders
   ├─ codex/fix/phase-1-5-review (a50108a) [+16] ⊃ phase-1-5-completion
   ├─ codex/feature/phase-1-6-profit-adjustment-rules (8b8b6a2) [+17] ⊃ phase-1-5-review
   ├─ codex/fix/phase-1-6-review (589c360) [+22] ⊃ phase-1-6-profit-adjustment
   ├─ codex/test/phase-1-6-windows-acceptance (9eae400) [+23] ⊃ phase-1-6-review
   ├─ codex/feature/phase-02-01-local-ocr-intake (9eae400) [+23] ⊃ phase-1-6-review (同 HEAD)
   ├─ codex/feature/phase-02-01-s1-foundation (15a9c6a) [+24] ⊃ phase-1-6-review
   ├─ codex/feature/phase-02-01-s2-intake-session (6280111) [+25] ⊃ s1
   ├─ codex/feature/phase-02-01-s3-field-extractors (5381a29) [+33] ⊃ s2  ← Phase 2.1 链顶
   ├─ codex/chore/full-progress-sync-20260728 (4396fc8) [+37] ⊃ s3
   ├─ codex/chore/road-0-spec-baseline (070aaea) [+41] ⊃ full-progress-sync
   ├─ codex/feature/road-1-main-page-ui (77a90d7) [+49] ⊃ road-0
   │   │
   │   ├─ data/calibration-round-01-51 (b53b257) [+49 +1 unique] (分叉于 02753ef)
   │   │
   │   └─ fix/calibration-round-01 (cadb176) [+54] ⊃ road-1
   │
   └─ (所有左列分支按 ⊃ 方向完全包含)
```

> ⊃ 表示右列分支的所有提交都是左列分支的祖先。

## 分支详细清单

### 利润计算 Phase 1.x 分支链（Profit accounting-Auto）

| # | 分支名 | 本地/远程 | HEAD SHA | 基于 | 新增提交数 | 建议处理 |
|---|--------|----------|----------|------|-----------|---------|
| 1 | `fix/phase-01-fix-03` | 本地+远程 | `7e15265` | master | 1 | DUPLICATE |
| 2 | `fix/phase-01-fix-04` | 本地+远程 | `bf84f69` | fix-03 | 2 | DUPLICATE |
| 3 | `fix/phase-01-fix-05` | 本地+远程 | `27ea6fb` | fix-04 | 3 | DUPLICATE |
| 4 | `codex/fix/phase-01-fix-06` | 本地+远程 | `efd7c50` | fix-05 | 8 | DUPLICATE |
| 5 | `codex/feature/configurable-forwarders-and-gram-weight` | 本地+远程 | `4f27f07` | fix-06 | 9 | DUPLICATE |
| 6 | `codex/feature/unlimited-forwarders` | 本地+远程 | `5f3cae8` | config-forwarders | 10 | DUPLICATE |
| 7 | `codex/feature/phase-1-5-completion` | 本地+远程 | `10e2bdd` | unlimited-forwarders | 13 | DUPLICATE |
| 8 | `codex/fix/phase-1-5-review` | 本地+远程 | `a50108a` | phase-1-5-completion | 16 | DUPLICATE |
| 9 | `codex/feature/phase-1-6-profit-adjustment-rules` | 本地+远程 | `8b8b6a2` | phase-1-5-review | 17 | DUPLICATE |
| 10 | `codex/fix/phase-1-6-review` | 本地+远程 | `589c360` | phase-1-6-profit | 22 | DUPLICATE |
| 11 | `codex/test/phase-1-6-windows-acceptance` | 本地+远程 | `9eae400` | phase-1-6-review | 23 | DUPLICATE |

**说明**：Phase 1.x 全部 11 个分支通过完全线性包含关系最终全部进入 Phase 2.1 s3 分支。无需单独合并，均标记为 DUPLICATE。

### Phase 2.1 图片录入分支链（Profit accounting-Auto + OCR）

| # | 分支名 | 本地/远程 | HEAD SHA | 基于 | 新增提交数 | 主要功能 | 建议处理 |
|---|--------|----------|----------|------|-----------|---------|---------|
| 12 | `codex/feature/phase-02-01-local-ocr-intake` | 本地+远程 | `9eae400` | phase-1-6-review | 23 | Windows 验收 .venv 打包修复 + EXE 测试 | DUPLICATE (同 test 分支 HEAD) |
| 13 | `codex/feature/phase-02-01-s1-foundation` | 本地+远程 | `15a9c6a` | phase-1-6-review | 24 | OCR intake 基础框架 | DUPLICATE |
| 14 | `codex/feature/phase-02-01-s2-intake-session` | 本地+远程 | `6280111` | s1 | 25 | OCR intake 会话管理 | DUPLICATE |
| 15 | `codex/feature/phase-02-01-s3-field-extractors` | 本地+远程 | `5381a29` | s2 | 33 | 字段提取器 + OCR 交互闭环 | **MERGE** |

**说明**：Phase 2.1 四个分支中前三个被 s3 完全包含。s3（`5381a29`）是 Phase 2.1 的最终累积分支，包含全部字段提取器、OCR 交互和集成。**合并 s3 即可获得 Phase 1.5→1.6→2.1 全部有效成果。**

### 全仓同步与路线图分支

| # | 分支名 | 本地/远程 | HEAD SHA | 基于 | 新增提交数 | 主要功能 | 建议处理 |
|---|--------|----------|----------|------|-----------|---------|---------|
| 16 | `codex/chore/full-progress-sync-20260728` | 本地+远程 | `4396fc8` | s3 | 37 | 仓库进度快照、Profit-Auto 同步、物流 2.0 校准同步 | **MERGE** |
| 17 | `codex/chore/road-0-spec-baseline` | 本地+远程 | `070aaea` | full-progress-sync | 41 | ROAD-0 需求入库、UI 偏差审计、测试基线修复 | **MERGE** |
| 18 | `codex/feature/road-1-main-page-ui` | 本地+远程 | `77a90d7` | road-0 | 49 | ROAD-1 主页面 8 区布局、图片框联动、GUI 冒烟 12 项 | **MERGE** |

**说明**：三者线性包含（road-1 ⊃ road-0 ⊃ full-progress-sync）。road-1 包含最终冻结 UI 布局和需求。按粒度分别合并以保留里程碑记录。

### 物流校准分支（logistics-cost-skill-2.0）

| # | 分支名 | 本地/远程 | HEAD SHA | 基于 | 新增提交数 | 主要功能 | 建议处理 |
|---|--------|----------|----------|------|-----------|---------|---------|
| 19 | `data/calibration-round-01-51` | 本地+远程 | `b53b257` | road-1 (02753ef) | 49+1 unique | 51 个校准样本数据 | **MERGE** |
| 20 | `fix/calibration-round-01` | 本地+远程 | `cadb176` | road-1 (77a90d7) | 54 | 校准回放完全可重现、超轻品可信重量、29 样本验证 | **MERGE** |
| 21 | `integration/logistics-calibration-v1` | 本地+远程 (当前) | `3708506` | master (1ac4e08) | 1 | round 02 校准工作区准备 | **MERGE** |

**说明**：
- `data/calibration-round-01-51` 在 road-1 中间点分叉，仅新增 1 个数据提交。需在 road-1 合并后单独合并。
- `fix/calibration-round-01` 在 road-1 顶部继续。校准修复链：包含回放可重现、超轻品处理等。
- `integration/logistics-calibration-v1` 独立于主开发链，仅含 round 02 准备提交。直接基于 master。

## 工作区未提交变更

| 文件 | 类型 | 内容 | 处理建议 |
|------|------|------|---------|
| `.workbuddy/memory/2026-07-26.md` | 已修改 | 工作空间记忆 | 不提交（.gitignore 已排除） |
| `Image Search/README.md` | 已修改 | v6.1 文档更新 | 本次任务不涉及（独立项目） |
| `Image Search/app.py` | 已修改 | v6.1 代码更新 | 本次任务不涉及（独立项目） |
| `logistics-cost-skill-2.0/archive/calibration/calibration_samples_round_02.json` | 已修改 | round 02 校准样本（从空数组 → 159 行实际数据） | 提交到 integration/logistics-calibration-v1 |

## 工作区未跟踪文件

| 路径 | 大小 | 内容 | 处理建议 |
|------|------|------|---------|
| `Image Search/CHANGELOG.md` | — | 变更日志 | 本次任务不涉及 |
| `Image Search/接入主软件方案.md` | — | 方案文档 | 本次任务不涉及 |
| `Profit accounting-Auto/.venv-311/` | 56MB | Python venv | 排除（.gitignore） |
| `Profit accounting-Auto/test_sessions/` | — | 测试会话数据 | 排除（临时数据） |
| `logistics-cost-skill-2.0/examples/*.json` (6 files) | — | AI JSON 示例 | 有价值，建议添加 |
| `review_packages/phase-1-5-import/` | 3.2MB | phase-1-5 bundle | 归档参考，不提交 |

## 已知提交验证

| 短 SHA | 完整 SHA | 提交信息 | 所在分支 |
|--------|---------|---------|---------|
| `1ac4e08` | `1ac4e0864b9729be902a43358fb25b9d3b92c410` | chore: remove legacy logistics-cost-skill-1.8 | master |
| `a17dd74` | `a17dd744...` | feat: sync current Profit accounting-Auto progress | full-progress-sync+ |
| `5381a29` | `5381a2976edffdc08335242de2f20b0a4294e68b` | fix: complete OCR image intake interactions | s3+ |
| `3708506` | `3708506b37df1e4adfc453eac5759f1047ac5476` | chore: prepare round 02 calibration workspace | integration/logistics-calibration-v1 |

全部已知提交已定位，均属于主开发链或校准分支。

## 敏感信息检查

扫描范围：所有 `.py` `.json` `.txt` `.md` 文件（排除 `.git` `__pycache__` `.venv` `.venv-311` `node_modules`）。

结果：无 API Key、Token、Cookie、Authorization、Bearer、真实密码发现。所有命中为库代码变量名或文档说明。

## 合并策略总结

### 有效合并目标（5 个分支 + 当前分支提交）

按建议顺序：

1. `codex/feature/phase-02-01-s3-field-extractors` → Profit accounting Phase 1.5/1.6 + Phase 2.1 全部
2. `codex/chore/full-progress-sync-20260728` → 仓库进度同步文档
3. `codex/chore/road-0-spec-baseline` → ROAD-0 需求基线
4. `codex/feature/road-1-main-page-ui` → ROAD-1 最终冻结 UI
5. `data/calibration-round-01-51` → 51 样本校准数据
6. `fix/calibration-round-01` → 校准回放修复
7. `integration/logistics-calibration-v1` → round 02 准备（含当前未提交校准样本）

### 标记为 DUPLICATE 的分支（16 个）

所有 Phase 1.x 及 Phase 2.1 中间分支均被最终分支完全包含，无需单独合并：
- `fix/phase-01-fix-03` ~ `fix/phase-01-fix-05`
- `codex/fix/phase-01-fix-06`
- `codex/feature/configurable-forwarders-and-gram-weight`
- `codex/feature/unlimited-forwarders`
- `codex/feature/phase-1-5-completion`
- `codex/fix/phase-1-5-review`
- `codex/feature/phase-1-6-profit-adjustment-rules`
- `codex/fix/phase-1-6-review`
- `codex/test/phase-1-6-windows-acceptance`
- `codex/feature/phase-02-01-local-ocr-intake`
- `codex/feature/phase-02-01-s1-foundation`
- `codex/feature/phase-02-01-s2-intake-session`
