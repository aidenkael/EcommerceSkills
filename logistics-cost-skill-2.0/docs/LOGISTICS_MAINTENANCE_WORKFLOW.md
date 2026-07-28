# 物流成本核算长期维护规范

> 生效日期：2026-07-28  
> 项目路径：`logistics-cost-skill-2.0/`  

---

## 1. 唯一上游

`logistics-cost-skill-2.0` 是物流算法、校准数据和物流版本发布的**唯一开发源**。

- 2.5 不得自行维护另一套不同的物流核心算法
- 物流相关修改统一在本项目完成，再通过版本包分发给下游

---

## 2. 校准分支

长期稳定分支（建议）：

```
calibration/logistics-active
```

每轮校准使用独立分支：

```
calibration/logistics-round-03
calibration/logistics-round-04
```

> 当前未建立 `calibration/logistics-active`，待 2.5 迁移完成后单独建立。

---

## 3. 发布类型

### 仅校准数据更新

命名：`logistics-calibration-YYYY.MM-v{N}.zip`

示例：`logistics-calibration-2026.08-v1.zip`

适用场景：
- 新增校准样本
- 更新品类参数
- 调整经验阈值
- 不改变输入输出 Schema

### 算法引擎更新

命名：`logistics-engine-v{X}.{Y}.{Z}.zip`

示例：`logistics-engine-v2.1.0.zip`

适用场景：
- 修改物流算法
- 修改证据仲裁规则
- 修改包装估算流程
- 修改输入输出 Schema
- 修改核心计算行为

---

## 4. 版本同步流程

任一修改的流程：

```
原物流项目校准或修改
  -> 全量回放（Round 01 + Round 02）
  -> 全量测试（40 项集成测试 + replay 验证）
  -> 生成正式版本包
  -> 2.5 兼容测试
  -> 2.5 启用
```

**禁止：**
- 直接复制几个 .py 文件到 2.5
- 两边分别继续修改物流算法

---

## 5. 版本包元数据

未来物流版本包应记录：

```json
{
  "source_repository": "https://github.com/aidenkael/EcommerceSkills",
  "source_commit": "<完整 SHA>",
  "engine_version": "2.1.0",
  "calibration_version": "2026.07",
  "schema_version": "v2.1",
  "compatible_app_versions": ["2.5"],
  "test_summary": {
    "integration": "40 passed",
    "replay_round_01": "48/48",
    "replay_round_02": "14/14"
  },
  "generated_at": "2026-07-28T15:00:00+08:00"
}
```

> 本任务只建立维护规范，不开发完整版本打包器。

---

## 6. 当前项目结构

```
logistics-cost-skill-2.0/
  config/              -- 货代费率、体积重分母等配置
  logistics_cost/      -- 核心计算引擎（calculator/estimator/weight_rules/ai_schema）
  archive/calibration/ -- 校准样本与回放报告
  examples/            -- AI JSON 输入示例（67+）
  scripts/             -- 校准与回放脚本
  tests/               -- 集成测试与验证测试
  docs/                -- 本规范及其他文档
```

---

## 7. 运行入口

```bash
# 标准化 AI JSON 输入
python logistics-cost-skill-2.0/logistics_cost/ai_schema.py

# 全量测试
python -m pytest logistics-cost-skill-2.0/tests/ -v

# Round 01 回放
python logistics-cost-skill-2.0/scripts/phase5_replay.py
```

---

*本规范与项目共存。算法修改、校准更新均需通过本文档定义的标准流程。*
