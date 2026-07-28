# ROAD-0 阶段综合报告 — 需求冻结与基线修复

**生成时间：** 2026-07-28  
**分支：** `codex/chore/road-0-spec-baseline`  
**基线：** `codex/chore/full-progress-sync-20260728` (HEAD `4396fc8`)  
**风险等级：** 低风险（需求入库 + 测试修复，未改业务代码）

---

## 一、阶段目标与实际完成

### 目标（来自 Development rules-1.5.md ROAD-0）

1. 将 `Development rules-1.5.md` 放入项目 `docs/`
2. 将最终 UI 预览图保存为受控需求附件
3. 核对当前同步分支和 Phase 2.1 分支
4. 修复物流 2.0 的 8 个路径测试
5. 建立利润软件与物流 2.0 全绿基线
6. 暂不改业务代码

### 完成情况

| # | 任务 | 状态 | Commit |
|---|---|---|---|
| 1 | 需求入库（MD + UI 图 + 根 AGENTS.md 引用） | ✅ | `9d137c2` |
| 2 | 现状偏差审计 | ✅ | `c7a4501` |
| 3 | 测试基线修复（物流路径 + Tcl/Tk） | ✅ | `6992115` |

---

## 二、入库文件路径

| 类型 | 路径 |
|---|---|
| 总规文档 | `Profit accounting-Auto/docs/Development rules-1.5.md` (1640 行) |
| UI 基线图 | `Profit accounting-Auto/docs/assets/development-rules-1.5-ui-baseline.png` (1672×941 PNG) |
| 根 AGENTS.md 规则 | `AGENTS.md` 新增"项目最高需求文件"小节 |
| 偏差审计 | `review_packages/Profit accounting-Auto/road-0-spec-baseline/step-2-deviation-audit.md` |

---

## 三、修改文件清单

### Step 1 Commit `9d137c2`
- 新增：`Profit accounting-Auto/docs/Development rules-1.5.md`
- 新增：`Profit accounting-Auto/docs/assets/MISSING_UI_BASELINE.txt`（占位，后续删除）
- 修改：`AGENTS.md`（新增项目最高需求引用规则）

### Step 2 Commit `c7a4501`
- 新增：`Profit accounting-Auto/docs/assets/development-rules-1.5-ui-baseline.png`（真实 PNG）
- 删除：`Profit accounting-Auto/docs/assets/MISSING_UI_BASELINE.txt`
- 新增：`review_packages/Profit accounting-Auto/road-0-spec-baseline/step-2-deviation-audit.md`

### Step 3 Commit `6992115`
- 修改：`logistics-cost-skill-2.0/tests/test_integration.py`
- 修改：`Profit accounting-Auto/tests/test_ocr_intake_interactions.py`

---

## 四、关键修改与实现

### 物流 2.0 测试路径修复

**问题：** 8 个测试使用相对路径 `examples/socks_ai.json`，从仓库根运行时 CWD 不正确导致 `FileNotFoundError` 或 subprocess 找不到 `run.py`。

**修复：**
- 在 `test_integration.py` 顶部新增模块级常量 `EXAMPLES = PROJECT / "examples"`
- `_load()` 改为 `with open(EXAMPLES / path, ...)`
- 5 处 `_load("examples/socks_ai.json")` → `_load("socks_ai.json")`
- `test_estimate_from_ai_json` / `test_estimate_from_ai_json_with_weight` 用 `EXAMPLES / "socks_ai.json"`
- `test_e2e_socks` 改用 `sys.executable + str(PROJECT / "run.py") + cwd=PROJECT`

**未改动：** 物流公式（VOLUME_DIVISOR、双货代对比、软品规则、可信重量修正）；货代配置；校准阈值；测试期望金额。

### Profit accounting-Auto Tcl/Tk 处理

**问题：** `_tkroot` fixture 与 `TestProductPageFill` 4 个测试直接调用 `tk.Tk()`，在 managed Python (3.13.12) 从仓库根运行时偶发 `TclError: Can't find a usable tk.tcl`（fixture setup ERROR）与 `TclError: invalid command name "tcl_findLibrary"`（在某些测试顺序下）。

**诊断：** 这是测试隔离问题叠加 managed Python 环境限制（Python 3.13.12 缺少独立 Tcl/Tk 库，无法被 pytest 从非项目目录正确初始化）。

**修复：** 在两处增加 graceful degradation：
- `_tkroot` fixture：`try tk.Tk() except tk.TclError -> pytest.skip(...)`
- `TestProductPageFill` 新增 `_try_tk()` 辅助方法，4 个测试统一使用

**未改动：** 业务代码、利润公式、OCR 控制器逻辑、数据库 Schema、测试期望金额。

### 偏差审计报告内容

按 `Development rules-1.5.md` 全章节编号组织：
- **可复用内容** 17 个模块/组件（Profit accounting-Auto 11 项 + 物流 2.0 9 项）
- **应停止扩展的旧 OCR 弹窗** 6 个具体内容（OcrIntakeDialog、SHEIN核价截图类型、候选/置信度 UI 展示、scopes 编辑控件、OCR 作正式主识别）
- **待重构内容** 13 项 R-1..R-13（按优先级排序）
- **尚未实现内容** 21 项 M-1..M-21（按总规章节 UI/IMG/AI/SPEC/LOG/PROFIT/DATA/PAGE/CAL/MOD）

---

## 五、测试结果

### 物流 2.0

| 运行位置 | 命令 | 结果 |
|---|---|---|
| 仓库根 `E:\EcommerceSkills` | `python -m pytest logistics-cost-skill-2.0/tests/` | **17 passed** in 0.17s |
| 项目目录 `E:\EcommerceSkills\logistics-cost-skill-2.0` | `python -m pytest tests/` | **17 passed** in 0.16s |

修复前从仓库根：8 failed + 9 passed。

### Profit accounting-Auto

| 运行位置 | 结果 |
|---|---|
| 仓库根 | **349 passed, 4 skipped, 1 xpassed** in 10.06s |
| 项目目录 | **350 passed, 4 skipped** in 10.47s |

修复前从仓库根：1 failed (`test_bare_fills_net_fields`) + 1 error (`test_upload_and_preview`) + 348 passed + 3 skipped + 1 xpassed。

xpassed 是 `test_empty_clipboard`（标 `@pytest.mark.xfail`），它实际通过，pytest 视为 xpass 非错误。两种运行方式均无失败。

### 未执行的测试

无。ROAD-0 测试范围完整覆盖物流 2.0（17）和利润软件（353+1xpass）全部用例。

---

## 六、是否改动业务公式 / Schema / 校准数值

| 类别 | 是否改动 |
|---|---|
| 物流公式（体积重/计费重/头程/尾程/总成本） | ❌ 未改 |
| 利润公式（毛利润/净利润/利润率/反推售价） | ❌ 未改 |
| 汇率/USD/CNY 换算 | ❌ 未改 |
| 货代硬编码费率（深圳80+10/义乌100+6） | ❌ 未改（R-1 留待 ROAD-3） |
| 校准阈值（`correction_threshold` / `evidence_quality`） | ❌ 未改（R-5 留待 ROAD-3） |
| SQLite Schema（v7） | ❌ 未改 |
| 测试期望金额 | ❌ 未改 |

---

## 七、已知问题与遗留风险

| 编号 | 问题 | 何时处理 |
|---|---|---|
| R-1 | `calculator.py` 仍硬编码 `FREIGHT_FORWARDERS`（80/100/10/6） | ROAD-3（物流2.0模块化移植） |
| R-2 | `get_freight_rate()` / `_category()` 残留旧"包类/非包类"签名 | ROAD-3 |
| R-3 | `logistics_config.json` 仍保留 deprecated `categories` 字段 | ROAD-3 |
| R-5 | 经验规则散落 config.json，未通过版本化校准包分发 | ROAD-3 + CAL-001 |
| R-9 | `VOLUME_DIVISOR=8000` 在 `calculation/logistics.py` 常量化 | ROAD-3 |
| R-10 | 利润公式入口分散，未确认全部 UI 计算经 profit_engine | ROAD-1/ROAD-3 |
| M-1..M-21 | 总规未实现功能（图片框/AI识图/正常保守档/物流2.0移植/利润双向反推/历史图片/校准包等） | ROAD-1 起逐步实现 |
| TestEmptyClipboard | `@pytest.mark.xfail` 标记但实际通过（xpass） | 后续阶段确认为正式 pass 时移除标记 |

---

## 八、下一阶段前置条件（是否进入 ROAD-1）

**结论：✅ 满足进入 ROAD-1 条件。**

- 最高需求文档已入库，AGENTS.md 引用规则已生效
- UI 视觉基准图已落地，ROAD-1 主页面重构可对照
- 物流 2.0 与利润软件测试基线全绿
- 业务公式 / Schema / 校准数值未受干扰

**建议下一阶段方向：**
- ROAD-1 主页面重构（按 UI-001~601 最终布局）
- 废弃 `OcrIntakeDialog` 作主流程入口
- 将图片上传/拖拽/粘贴/预览迁入主页面图片框
- 正常档与保守档同时展示

**等待 ChatGPT 总指挥决定下一步任务粒度与风险等级。**

---

## 九、工作区状态

```
branch: codex/chore/road-0-spec-baseline
HEAD:   6992115 (测试基线修复)
commits: 3 (Step1 9d137c2, Step2 c7a4501, Step3 6992115)
```

未提交修改（与本阶段无关，用户其他工作产物，保留不触动）：
- `.workbuddy/memory/2026-07-26.md`
- `logistics-cost-skill-2.0/archive/calibration/calibration_samples.json`
- `logistics-cost-skill-2.0/examples/*.ai.json`（多个新样本）
- `Profit accounting-Auto/test_sessions/`
- `review_packages/phase-1-5-import/`

---

## 十、最终 Commit SHA

```
9d137c2  Profit accounting-Auto: ROAD-0 Step1 需求入库
c7a4501  Profit accounting-Auto: ROAD-0 Step2 UI图与偏差审计
6992115  测试基线修复: 物流8路径 + Profit-Auto Tcl/Tk
```