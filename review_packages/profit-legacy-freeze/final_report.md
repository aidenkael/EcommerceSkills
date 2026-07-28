# 旧项目冻结 R2 收口 -- 最终报告

> 任务：EcommerceSkills 冻结 R2 收口与物流长期维护基线  
> 完成日期：2026-07-28  
> 仓库：https://github.com/aidenkael/EcommerceSkills.git  

---

## 完成内容

1. **补交有效校准资料**：提交 Round 02 追加校准样本（CAL-055 ~ CAL-065）和 11 个 AI JSON 示例，全部通过 schema 验证和 estimator 管道
2. **修复测试收集错误**：重写 `test_step_report.py` 以适配当前正式报告工具 API，10/10 通过，全量 393 passed / 0 collection errors
3. **纠正冻结边界**：修正 LEGACY_FREEZE.md、BRANCH_MERGE_MANIFEST.md、MIGRATION_SOURCE_MANIFEST.md 的冻结范围、分支统计、标签引用
4. **建立物流维护规范**：新增 LOGISTICS_MAINTENANCE_WORKFLOW.md，明确唯一上游、校准分支、发布类型、版本同步流程
5. **R2 标签**：创建 profit-legacy-freeze-20260728-r2，合并到 master

---

## 修正分支

`chore/profit-legacy-freeze-r2`

## master 最终 SHA

`（最终合并后确认）`

## R2 冻结标签

`profit-legacy-freeze-20260728-r2`

## 原冻结标签状态

`profit-legacy-freeze-20260728` -- 保留，不移动、不覆盖

---

## 冻结项目

### Profit accounting-Auto
- **状态**：功能开发已冻结
- **允许修改**：仅限修复影响迁移取证的严重错误、补充迁移说明、文档修正
- **禁止**：旧 UI、旧 OCR、新 AI 功能、新业务模块

## 持续维护项目

### logistics-cost-skill-2.0
- **状态**：活跃维护
- **允许**：校准样本新增、算法修复、配置升级、回放测试、版本发布
- **2.5 约束**：不得自行维护另一套物流算法，必须通过本项目版本包分发

---

## 新增校准文件

| 路径 | 样本数量 | Schema 验证 | 回放结果 |
|------|---------|------------|---------|
| `logistics-cost-skill-2.0/archive/calibration/calibration_samples_round_02.json` | 14（CAL-052 ~ CAL-065） | 通过 | 全量 valid |
| `logistics-cost-skill-2.0/examples/` 新增 AI JSON | 11 个 | 11/11 通过 | 11/11 通过 estimator 管道 |

## 排除的未提交文件

| 路径 | 原因 |
|------|------|
| `Image Search/` 未提交修改（README.md, app.py, CHANGELOG.md） | 独立项目，不纳入本次冻结 |
| `.workbuddy/memory/2026-07-26.md` | Agent 工作目录，.gitignore 已排除 |
| `review_packages/phase-1-5-import/` | 归档 bundle 参考，不提交 |

---

## 分支统计

| 分类 | 数量 |
|------|------|
| 本地分支 | 24 |
| 远程分支 | 23 |
| 去重后唯一分支 | 24 |
| MERGE（已 --no-ff 合并） | 7 |
| DUPLICATE（已被包含） | 14 |
| 基线/整合/R2 分支 | 3（master, integration/profit-legacy-freeze-20260728, chore/profit-legacy-freeze-r2） |

---

## 测试结果

| 测试项 | 通过 | 跳过 | 失败 | collection errors |
|--------|------|------|------|-------------------|
| Profit accounting-Auto 全量 | 393 | 6 | 0 | 0 |
| logistics-cost-skill-2.0 全量 | 40 | 0 | 0 | 0 |
| Round 01 回放 | 48/48 | -- | 0 | -- |
| Round 02 回放 | -- | -- | -- | 样本已通过 schema + estimator 验证 |
| 仓库工具（test_step_report） | 10 | 0 | 0 | 0 |
| **collection errors** | **0** | -- | -- | -- |

### 环境跳过

- 6 个 Profit 测试因 `tkinterdnd2` 未安装在测试环境被跳过（GUI 拖放功能）
- Tcl/Tk 在无头环境中部分功能不可用

---

## 修正文档

| 文件 | 修正内容 |
|------|---------|
| `docs/LEGACY_FREEZE.md` | 明确区分冻结项目（Profit）和持续维护项目（logistics）；标签改为 R2 权威；修正未完成功能分类；修正历史数据说明 |
| `docs/BRANCH_MERGE_MANIFEST.md` | 修正分支统计（24/23/24 本地/远程/去重、7 MERGE、14 DUPLICATE）；标签引用更新 |
| `docs/MIGRATION_SOURCE_MANIFEST.md` | 新增 R2 校准文件真实路径和数量；Development rules-1.5.md 标记为需求来源；2.5 将生成新 2.5.md |
| `logistics-cost-skill-2.0/docs/LOGISTICS_MAINTENANCE_WORKFLOW.md` | 新增：唯一上游、校准分支、发布类型、版本同步流程 |

---

## 物流维护规范

路径：`logistics-cost-skill-2.0/docs/LOGISTICS_MAINTENANCE_WORKFLOW.md`

核心规则：
- logistics-cost-skill-2.0 是物流算法唯一上游
- 修改 -> 全量回放 -> 全量测试 -> 版本包 -> 2.5 兼容测试 -> 2.5 启用
- 禁止两边分别修改或直接复制文件

---

## 已提交报告

```
review_packages/profit-legacy-freeze/
  branch_inventory.md
  final_report.md
  final/step-01_final.md
```

---

## 敏感信息检查

R2 新增文件（12 个校准 + 文档）已扫描：无 API Key、Token、Cookie、密码发现。

---

## 推送状态

- 整合分支：待完成合并后推送
- master：待合并后推送
- 标签：profit-legacy-freeze-20260728-r2 待创建和推送

---

## 真实风险/遗留问题

1. **原标签保留**：`profit-legacy-freeze-20260728` 指向初次冻结基线（commit `04bc08b`），核心内容已被 R2 标签取代但历史完整性保留
2. **物流长期分支未创建**：`calibration/logistics-active` 待 2.5 迁移完成后单独建立
3. **tkinterdnd2 环境依赖**：6 个测试在无头环境跳过的现象无法在本任务解决，不影响功能
4. **版本打包器未开发**：物流维护规范已建立，但完整的自动版本打包工具属于 2.5 范围

---

## 下一步

等待 ChatGPT 以 `profit-legacy-freeze-20260728-r2` 标签为迁移来源，生成 Development rules-2.5.md 并建立新项目迁移基线。原仓库中的 logistics-cost-skill-2.0 继续独立校准。
