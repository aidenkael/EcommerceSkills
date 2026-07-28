# Phase 2.1 / S1 基础骨架 — 步骤说明

## 目标

完成运行环境验证、基础数据结构和 OCR 接口骨架，不进入图片管理、正则提取、GUI、真实 PaddleOCR 或字段回填。

## 当前分支和完整 HEAD

| 项 | 值 |
|---|---|
| 仓库根 | `E:/EcommerceSkills` |
| 当前分支 | `codex/feature/phase-02-01-s1-foundation` |
| 基线 HEAD | `9eae4008bf80867f34d3a429dbc749e5d44f46ba` |
| 基线分支 | `codex/test/phase-1-6-windows-acceptance` |
| 是否合并 master | 否 |
| 工作区其他项目修改 | 原样保留未触碰（logistics-cost-skill-2.0 等） |

## Python 3.11 环境路径和版本

| 项 | 值 |
|---|---|
| venv 路径 | `E:\EcommerceSkills\Profit accounting-Auto\.venv-311` |
| Python 版本 | 3.11.9 |
| 创建命令 | `py -3.11 -m venv .venv-311` |
| 系统 Python 3.13.14 | 保留未删除、未覆盖 |
| git 忽略 | 已被项目级 `.gitignore` 忽略（`.venv-311/`） |
| 依赖安装 | `pip install -r requirements.txt`（pytest 9.1.1） |

从本步骤起，项目测试统一使用 `.venv-311\Scripts\python.exe -m pytest tests -q`。

## 修改及新增文件

### 新增文件

| 文件 | 作用 |
|---|---|
| `.gitignore`（项目级） | 忽略 `.venv-311/`，不污染仓库 |
| `image_intake/__init__.py` | 图片录入服务层包入口 |
| `image_intake/image_types.py` | 第一版 5 种人工指定图片类型枚举 + 中文名 |
| `image_intake/result_models.py` | OcrCandidate / FieldSelection / FieldCandidates / IntakeSession + MeasurementScope |
| `ocr/__init__.py` | OCR 引擎层包入口 |
| `ocr/base_engine.py` | BaseOcrEngine 抽象接口 + PlaceholderOcrEngine 占位 + EngineStatus / OcrTextLine / OcrPageResult |
| `requirements-ocr.txt` | OCR 依赖清单占位（只写注释，不安装、不锁定版本） |
| `tests/test_result_models.py` | 候选与确认结果数据结构测试（10 个用例） |
| `tests/test_base_engine.py` | 引擎接口与占位引擎测试（6 个用例） |

### 修改文件

无。本步骤未修改任何现有文件（app.py、ui/*、database/*、calculation/*、config/*、现有测试、requirements.txt 均保持不变）。

## 数据结构说明

### image_intake/image_types.py

5 种图片类型枚举（第一版不自动判断，由用户上传时手动选择）：

| 枚举值 | 中文显示 |
|---|---|
| `PRODUCT_MAIN_IMAGE` | 商品主图 |
| `SHEIN_PRICING` | SHEIN 核价截图 |
| `SUPPLIER_COST_SHIPPING` | 1688 成本及运费截图 |
| `DIMENSIONS_WEIGHT` | 尺寸和重量截图 |
| `SUPPLEMENTARY` | 补充截图 |

### image_intake/result_models.py

**OcrCandidate（frozen，不可变）** — OCR 原始候选：

| 字段 | 类型 | 说明 |
|---|---|---|
| `candidate_id` | str | 自动生成 UUID |
| `field_name` | str | 字段名（shein_price_usd / product_cost_rmb / ...） |
| `parsed_value` | float \| None | OCR 解析出的数字（无单位也保留不丢） |
| `normalized_value` | float \| None | 单位明确后的标准值（无单位为 None） |
| `unit_original` | str \| None | 原始单位 |
| `unit_normalized` | str \| None | 归一化单位 |
| `selectable` | bool | 是否可选中（无单位默认 False） |
| `source_image` | str | 来源图片 ID |
| `raw_text` | str | OCR 原文片段 |
| `confidence` | float | OCR 置信度 0-1 |
| `measurement_group_id` | str \| None | 关联同组长宽高重量；非尺寸类为 None |

**FieldSelection（可变）** — 用户最终确认结果：

| 字段 | 类型 | 说明 |
|---|---|---|
| `field_name` | str | 字段名 |
| `source_candidate_id` | str | 来源候选 ID |
| `confirmed_value` | float \| None | 确认值 |
| `confirmed_unit` | str \| None | 确认单位 |
| `measurement_scope` | MeasurementScope | bare / packaged / unknown / not_applicable |
| `user_modified` | bool | 用户是否修改过（默认 False） |

**MeasurementScope 枚举**：
- `BARE` 裸件
- `PACKAGED` 包装
- `UNKNOWN` 无法确认
- `NOT_APPLICABLE` 非尺寸类（价格/成本/运费）

**FieldCandidates** — 一个字段的全部候选，不自动选最低价，不删重复来源。
**IntakeSession** — 一次录入会话（session_id / created_at / session_dir / images / field_candidates / selections / engine_name），本步骤只定义结构不实现读写。

### ocr/base_engine.py

- `EngineStatus`：READY / UNAVAILABLE
- `OcrTextLine`：单行 OCR 文本（text / confidence / bbox）
- `OcrPageResult`：单张图片 OCR 结果（image_id / lines / success / error）
- `BaseOcrEngine`：抽象接口（status / recognize / name），字段提取器只依赖此接口
- `PlaceholderOcrEngine`：占位实现，status=UNAVAILABLE，recognize 返回空结果不抛异常

本步骤禁止 import paddleocr / paddlepaddle / cv2，禁止下载模型、联网、接真实 OCR。

## 测试数量和结果

| 类别 | 数量 | 结果 |
|---|---|---|
| 原有测试 | 216 | 全部通过 |
| 新增 test_result_models.py | 10 | 全部通过 |
| 新增 test_base_engine.py | 6 | 全部通过 |
| **合计** | **232** | **232 passed in 3.47s** |

执行命令：
```
.venv-311\Scripts\python.exe -m pytest tests -q
```

测试覆盖（test_result_models.py）：
1. 有单位候选可以保存归一化值 ✓
2. 无单位候选保留 parsed_value 但 selectable=False ✓
3. OCR 候选与用户确认结果相互独立 ✓
4. 用户修改确认值不会改变原始候选（frozen 校验） ✓
5. measurement_group_id 可以关联同组尺寸 ✓
6. 价格字段 scope 可以使用 not_applicable ✓
7. 尺寸字段支持 bare、packaged 和 unknown ✓
8. FieldCandidates 保留全部候选、不自动选最低价、不删重复来源 ✓
9. IntakeSession 基本结构 ✓

测试覆盖（test_base_engine.py）：
1. PlaceholderOcrEngine 可以实例化 ✓
2. 返回空 OCR 结果 ✓
3. OCR 不可用不会影响程序继续运行 ✓
4. 接口返回类型稳定 ✓
5. OcrTextLine 默认值与带 bbox 构造 ✓

## 未完成事项（本步骤明确不做）

- 图片上传和保存
- LOCALAPPDATA 会话目录 + session.json 读写
- 正则字段提取器（shein_price / cost_shipping / dimension）
- OCR 录入对话框（GUI）
- 真实 PaddleOCR 接入（paddle_engine.py）
- OpenCV 预处理（preprocessing.py）
- 正式字段回填到 ProductPage
- EXE 打包
- requirements-ocr.txt 依赖锁定（S6 验证后）
- Phase 2.2

## 下一步 S2 的前置条件

1. S1 全部测试通过（已满足，232 passed）
2. 用户确认进入 S2
3. S2 计划实现 `image_intake/intake_service.py`：
   - 图片管理（上传时 UUID 重命名）
   - 会话目录（默认 `%LOCALAPPDATA%\ProfitAccountingAuto\ocr_sessions\`，支持注入自定义目录）
   - session.json 读写
   - 调度占位引擎生成空候选
   - 清理工具函数
4. S2 测试用 pytest tmp_path 注入临时目录，不污染用户 LOCALAPPDATA

## 审查重点

- OcrCandidate 是否真的 frozen（用户修改不覆盖原始数据）
- 无单位候选 parsed_value 是否保留且 selectable=False
- FieldSelection 与 OcrCandidate 是否完全独立
- PlaceholderOcrEngine 不可用时是否不抛异常（主窗口能启动）
- 是否误改了现有文件或数据库 Schema（应为否）
- 是否误 import 了 paddleocr/paddlepaddle/cv2（应为否）
