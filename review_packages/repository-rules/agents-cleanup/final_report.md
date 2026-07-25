# AGENTS 规则体系整理报告

## 执行摘要

创建仓库根目录 AGENTS.md，精简两个子项目 AGENTS.md。三层规则无冲突。

## 修改的文件

| 文件 | 操作 | 行数变化 |
|------|------|---------|
| `AGENTS.md`（根目录） | **新建** | 0 → 40 行 |
| `logistics-cost-skill-2.0/AGENTS.md` | 精简 | 33 → 25 行 |
| `logistics-cost-skill-1.8/.../AGENTS.md` | 精简 | 41 → 40 行 |

## 各文件详细变化

### 根目录 AGENTS.md（新建）

从零创建，只写仓库通用规则：
- 仓库结构（一级子文件夹 = 独立项目）
- 分步骤开发与记录（`review_packages/<项目>/<任务>/step-NN_名称.md`）
- 步骤定义：有实际代码/配置变化的阶段，非每次工具调用
- Git 提交规则（单步单提交、禁止强制推送、格式要求）
- 完成反馈格式

**不包含**：任何物流公式、费率、利润规则、具体运行命令。

### logistics-cost-skill-2.0/AGENTS.md（33→25 行）

**删除的重复内容：**
- 整节「GitHub 提交与复审规则」（19 行，与根目录重复）
- 「使用 Git 管理」（1 处）
- 冗余的「参数修改必须显示原值…由用户确认」

**保留的项目特有规则：**
- 物流公式/费率从 `config/logistics_config.json` 读取
- AI JSON 格式参照 `examples/socks_ai.json`
- 两档包装方案（normal + conservative）
- 软品展开尺寸保护、重量修正逻辑
- 1688 链接只保存不访问
- 入口命令和测试命令

### logistics-cost-skill-1.8/.../AGENTS.md（41→40 行）

**删除：**
- 「每次任务结束时报告处理图片数…」（由根目录反馈格式覆盖）
- 小幅精简冗余措辞

**保留的全部业务规则：**
- 货代规则来源（`config/freight_rules.json`）
- 禁止使用旧包类/非包类规则
- null 规则（无信息不编造）
- needs_review 和复核标记
- 数据保护规则（不改写 source/calibration）
- 完整 Agent 执行流程（6 步）
- "根据图片核算"快捷处理
- feedback 录入命令
- 测试命令

**新增底部说明：** 明确 v1.8 是独立版本（`src/logistics_tool/` 包 + 校准图片），与 v2.0 共存。

## 关于 logistics-cost-skill-1.8 的评估

- **路径**：`logistics-cost-skill-1.8/物流头程核算工具_可直接交给Agent/`
- **状态**：**独立完整项目**，非历史备份或无效果副本
- **证据**：拥有 `run.py`、完整的 `src/logistics_tool/` 包结构、`tests/`、79 张校准图片、独立配置和数据
- **与 v2.0 的关系**：二者架构不同（v1.8 是传统 Python 包 + 图片校准，v2.0 是 Codex Skill 模式），非上下游关系，各自独立运行
- **建议**：保留并继续维护其 AGENTS.md

## 规则层级关系（无冲突确认）

```
根目录 AGENTS.md（仓库结构 + 步骤记录 + Git 规则 + 反馈格式）
  │
  ├── logistics-cost-skill-2.0/AGENTS.md（物流业务规则 + 入口 + 测试）
  │
  └── logistics-cost-skill-1.8/.../AGENTS.md（视觉判断流程 + 校准规则 + 入口 + 测试）

Profit accounting-Auto/  暂无 AGENTS.md（后续按需创建）
```

每个子项目 AGENTS.md **不重复**根目录的 Git/提交/报告规则。

## 建议后续人工确认

1. `Profit accounting-Auto/` 暂无 AGENTS.md — 如有需要可按同样模式创建
2. `Image Search/` 暂无 AGENTS.md — 该项目较简单，暂不需要

## 当前分支
`master`
