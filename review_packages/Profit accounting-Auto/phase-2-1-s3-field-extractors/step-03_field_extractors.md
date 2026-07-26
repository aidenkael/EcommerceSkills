# Phase 2.1 / S3 OCR 文本候选字段提取器 — 步骤说明

## 目标

从已返回的 OCR 文本行中提取价格、成本、运费、重量和尺寸候选。继续用合成文本测试，不接真实 PaddleOCR，不开发 GUI，不回填正式字段。

## 分支与完整 HEAD

| 项 | 值 |
|---|---|
| 仓库根 | `E:/EcommerceSkills` |
| 当前分支 | `codex/feature/phase-02-01-s3-field-extractors` |
| 基线 HEAD（S2 提交） | `6280111107dd810122725cf577b4f6f98b3016a4` |
| 是否合并 master | 否 |
| 工作区其他项目修改 | 原样保留未触碰 |

## 新增和修改文件

### 新增

| 文件 | 作用 |
|---|---|
| `image_intake/extractors/__init__.py` | 提取器集合，导出三个 extract 函数 |
| `image_intake/extractors/common.py` | 共用工具：parse_number / is_valid_amount / is_valid_measure / make_candidate / make_group_id / dedupe / normalize_weight / normalize_dim / sort_candidates |
| `image_intake/extractors/shein_price_extractor.py` | SHEIN 核价 → shein_price_usd |
| `image_intake/extractors/cost_shipping_extractor.py` | 1688 成本运费 → product_cost_rmb / domestic_shipping_rmb |
| `image_intake/extractors/dimension_extractor.py` | 尺寸重量 → weight_g / length_cm / width_cm / height_cm |
| `tests/test_extractors.py` | 37 个测试用例 |

### 修改

无。S1、S2 的 result_models.py / base_engine.py / intake_service.py / __init__.py 均保持不变，接口完全兼容。

## 三个提取器的输入输出接口

统一签名：

```python
def extract(lines: list[OcrTextLine], source_image: str = "") -> list[OcrCandidate]:
```

- **输入**：`list[OcrTextLine]`（主输入）+ `source_image`（辅助参数，来自 `OcrPageResult.image_id`，用于记录候选来源）
- **输出**：`list[OcrCandidate]`，已按"上下文明确优先 > 置信度高优先 > 出现顺序"排序，并去完全重复
- 三个提取器返回类型一致，均为 `list[OcrCandidate]`

说明：`OcrTextLine`（S1 定义）含 `text/confidence/bbox`，无 `source_image` 字段；候选的 `source_image` 通过辅助参数注入，未修改 `base_engine.py`。

## 支持的货币和计量单位

### 货币（SHEIN 提取器）

| 单位/标识 | 归一化 |
|---|---|
| `$` / `US$` / `USD` / `美元` | `usd`，normalized_value 保持美元数值（不换算汇率） |

人民币标识（`¥` `￥` `RMB` `CNY` `元`）不进入美元候选。

### 货币（成本运费提取器）

| 单位/标识 | 归一化 |
|---|---|
| `¥` / `￥` / `RMB` / `CNY` / `元` / `包邮` | `rmb` |

`包邮` 生成 0 元运费候选（unit_original="包邮"）。`运费0元` 也生成 0 元候选。

### 重量（尺寸提取器）

| 单位 | 归一化 |
|---|---|
| `g` / `gram` / `克` | `g`（原值） |
| `kg` / `kilogram` / `千克` / `公斤` | `g`（×1000） |

### 尺寸（尺寸提取器）

| 单位 | 归一化 |
|---|---|
| `cm` / `厘米` | `cm`（原值） |
| `mm` / `毫米` | `cm`（÷10） |

## measurement_group_id 生成与关联规则

`make_group_id(content)` 基于内容（表达式原文 + source_image）生成确定性 md5 短串：

1. **三元表达式**（`10×20×30cm`）：三个值（长/宽/高）共享同一 group_id（content = 表达式原文 + source_image）
2. **长宽高文字**（`长10cm 宽20cm 高30cm`）：三个值共享同一 group_id（content = 整行 + source_image）
3. **两维表达式**（`10×20cm`）：长/宽共享 group_id，不补高度
4. **四维及以上**：不生成完整三维，设 dim_handled 阻止后续误匹配
5. **单独重量**：独立 group_id（content 含 "w" 前缀 + 值）
6. **单独尺寸**：独立 group_id
7. **不同表达式/不同行**：content 不同 → group_id 不同
8. **完全相同重复行**：content 相同 → group_id 相同 → 去重

设计原则：第一版宁可分开关联，也不错误拼组；measurement_scope 不在 OcrCandidate 中自动判断为 bare/packaged。

## 无单位候选处理

当数字有字段上下文但单位无法确认时：

- `parsed_value` 保留（不丢）
- `normalized_value = None`
- `unit_original = None`
- `unit_normalized = None`
- `selectable = False`

适用场景：
- SHEIN：有"核价/定价/售价/价格"上下文但无 `$`/`USD`/`美元`
- 成本：有"单价/价格"上下文但无 `¥`/`元`/`RMB`
- 尺寸：有"长/宽/高/尺寸"上下文但无 `cm`/`mm`

不把无单位数字强行解释为元、美元、克或厘米。

## 多候选保留和去重规则

### 保留

- 一张截图多个金额/尺寸全部保留
- 多档阶梯价全部保留
- 不同图片的相同值全部保留
- 不自动选最低价、最高置信度
- 不自动设置 FieldSelection

### 去重（仅完全相同）

必须同时满足才去重：相同 `field_name` + `normalized_value` + `source_image` + `raw_text` + `measurement_group_id`。

### 误识别防护

不当作价格/尺寸的情况：百分比、页码（EXCLUDE_MARK）；无货币符号且无成本/运费上下文的数字；起订量/库存/销量（无货币符号不匹配 RMB 正则）；满减门槛/优惠券（EXCLUDE_MARK）。零或负尺寸/重量不生成可用候选（is_valid_measure 要求 >0）。

## 新增测试数量

| 测试文件 | 用例数 |
|---|---|
| `tests/test_extractors.py` | 37 |

覆盖：SHEIN 核价(7)、成本运费(10)、尺寸重量(16)、接口回归(4)。

## 全部测试结果

| 类别 | 数量 | 结果 |
|---|---|---|
| S1 + S2 基线 | 252 | 全部通过 |
| S3 新增 | 37 | 全部通过 |
| **合计** | **289** | **289 passed in 3.38s** |

未修改任何现有测试。

## 已知限制

1. **单位归一化精度**：合成文本验证流程，真实平台识别精度需 S6 用真实截图验证
2. **上下文判断保守**：无货币符号且无上下文词的金额不生成候选（宁可不生成），可能遗漏部分真实价格
3. **同行多表达式**：同一行既有尺寸又有重量时，尺寸用 MULTI_EXPR 处理后 handled=True，同行的单独尺寸不再提取（重量仍独立提取）
4. **长宽高顺序**：三元表达式默认按"长×宽×高"映射（第一版约定），不依赖额外上下文
5. **EXCLUDE_MARK 简化**：只排除百分比/满减/券/页码，依赖上下文词和无货币符号判断起订量/销量，避免误杀阶梯价
6. **不自动判断 scope**：毛重/净重/包装尺寸等文字只保留在 raw_text，measurement_scope 由用户在确认阶段指定

## S4 前置条件

1. S3 全部测试通过（已满足，289 passed）
2. 用户确认进入 S4
3. S4 计划实现 `ui/ocr_intake_dialog.py`：多图上传 + 类型下拉 + 候选列表 + 勾选 + measurement_scope 选择（裸件/包装/无法确认）+ 确认；引擎用占位
4. S4 不接真实 OCR，不回填正式字段（回填在 S5）

## 审查重点

- 三个提取器是否真的统一 `extract(lines, source_image) -> list[OcrCandidate]`
- 无单位候选是否保留 parsed_value 且 selectable=False
- 多候选是否全部保留（不自动选最低价）
- measurement_group_id 是否同组共享、不同组不同
- 两维是否不补高度、四维是否不生成完整三维
- 零/负尺寸重量是否被拒
- 完全相同重复是否去重、不同来源同值是否保留
- 是否误改 S1/S2 文件或现有测试（应为否）
- 是否引入 PaddleOCR/OpenCV/联网（应为否）
