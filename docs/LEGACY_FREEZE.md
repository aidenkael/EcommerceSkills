# LEGACY_FREEZE.md — 旧项目冻结声明

> 冻结日期：2026-07-28  
> 仓库地址：https://github.com/aidenkael/EcommerceSkills.git  

## 冻结基线

| 项目 | 值 |
|------|-----|
| master 最终 Commit SHA | `29ab07b`（整合分支合并后） |
| 冻结标签 | `profit-legacy-freeze-20260728` |
| 预整合基线标签 | `profit-legacy-premerge-20260728` |
| 整合分支 | `integration/profit-legacy-freeze-20260728` |

## 当前项目范围

- **Profit accounting-Auto**（微智能利润管理软件 v1.x）：手动利润计算、多货代管理、OCR 图片录入、字段提取、Phase 1.5/1.6 利润调整规则、ROAD-1 主页面 UI 布局
- **logistics-cost-skill-2.0**：AI JSON → 确定性头程成本核算、多货代、校准系统（Round 01 + Round 02）、超轻品重量修正

## 已完成功能

### Profit accounting-Auto
- 手动利润正算 / 反推
- 汇率实时查询与手动输入
- 推广预留（百分比）
- SHEIN 运费补贴（可配置）
- 动态货代管理（不限数量、独立规则、克重输入）
- 历史保存与快照（原子迁移、Schema v6）
- 利润调整规则系统（规则编辑器、冻结、归档、恢复）
- Phase 2.1 OCR 图片录入：图片框管理、拖放/Ctrl+V 粘贴、FakeAI 联动
- Phase 2.1 字段提取器：尺寸、价格、成本运费候选提取
- ROAD-1 主页面 8 区布局、图片框与计算联动、GUI 冒烟 12 项

### logistics-cost-skill-2.0
- 双档包装估算（normal / conservative）
- 软品识别与展开尺寸修正
- 计费重计算（实重 vs 体积重 ÷ 8000）
- 超轻品可信重量修正（+0.05kg or MAX(AI, 1688, img)）
- 多货代费率支持（深圳：80 RMB/kg + 10，义乌：100 RMB/kg + 6）
- Round 01 校准：51 样本、完全可重现回放
- Round 02 校准：10+ 样本（腰带、刷具、香薰机、袜子等）
- AI JSON 标准化入口（product_type、material、rigidity 等新字段）
- 校准验证与偏差分析

## 未完成功能

- 2.5 PySide6 新版 UI（仅保留 ROAD-1 Tkinter 布局为冻结 UI 参考）
- 真实 AI 视觉识别（当前使用 FakeAI）
- 自动核价决策系统
- 批量商品管理

## 测试结果（冻结时）

| 项目 | 通过 | 跳过 | 失败 | 错误 |
|------|------|------|------|------|
| Profit accounting-Auto | 382 | 7 | 0 | 1* |
| logistics-cost-skill-2.0 | 40 | 0 | 0 | 0 |

> *1 个 collection error：`test_step_report.py` 依赖旧版 `tools/generate_step_report.py` 的 `load_config` 函数，当前 HEAD 版本已重构为 argparse 架构。这是已知集成问题，不影响核心业务功能。

## 已知环境问题

- 7 个测试因 `tkinterdnd2` 未安装在测试环境中而被跳过（GUI 拖放功能依赖）
- Tcl/Tk 在无头测试环境中部分功能不可用
- `Profit accounting-Auto/.venv-311/` 不在仓库中（由用户本地管理）

## 旧项目规则

### 允许继续维护的范围

1. 修复影响迁移取证的严重错误
2. 继续进行独立物流成本核算校准（添加校准样本、更新货代费率）
3. 补充不会改变旧软件功能的校准数据

### 禁止继续开发的范围

- Profit accounting-Auto 旧 UI 新功能开发
- 历史页面、OCR 交互新功能
- 新业务功能
- 2.5 迁移前的新模块

### 2.5 迁移原则

1. 从冻结基线读取源代码、测试和校准数据
2. 使用 `Development rules-1.5.md` 作为最高需求依据
3. 参考 ROAD-1 最终冻结 UI 布局设计新版 PySide6 界面
4. 物流核算从 `logistics-cost-skill-2.0` 独立移植
5. 校准样本和规则作为迁移验收基准
6. 历史数据不要求兼容（旧 Tkinter 数据库独立冻结）

---

*本文件为旧项目冻结声明。冻结后任何功能变更需在 2.5 新项目中实现。*
