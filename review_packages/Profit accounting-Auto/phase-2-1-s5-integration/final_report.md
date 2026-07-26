# Phase 2.1 S4修正 + S5 综合报告

## 1. 当前分支和完整 HEAD

- 分支：`codex/feature/phase-02-01-s3-field-extractors`
- HEAD：`990ed29984d81cc09298eb810c44cae3539cb282`
- 未合并 master

## 2. 两个 Commit SHA

| 步骤 | Commit | 信息 |
|---|---|---|
| A（S4修正） | `ec9831ac0fb892bca3c3f53b9850eb8a85b74da7` | fix: complete OCR manual candidate confirmation |
| B（S5接入） | `990ed29984d81cc09298eb810c44cae3539cb282` | feat: connect OCR intake to product page |

## 3. S4 人工确认规则

- 原始 OcrCandidate 不可变（frozen），用户编辑不覆盖原候选
- 无单位候选（selectable=False）：用户手动输入 confirmed_value/confirmed_unit 后生成 FieldSelection，user_modified=True，可确认
- can_confirm：selectable 候选直接可确认；不可选候选需 user_modified 且 confirmed_value 非 None
- 确认只返回 dict[field_name, FieldSelection]，不写 db/ProductPage

## 4. 单位归一化规则

| 字段 | 接受单位 | 归一化 |
|---|---|---|
| shein_price_usd | usd/$/美元/US$ | usd，值不变 |
| product_cost_rmb | rmb/cny/元/¥/￥ | rmb，值不变 |
| domestic_shipping_rmb | rmb/cny/元/¥/￥ | rmb，值不变 |
| weight_g | g/gram/克 | g，值不变 |
| weight_g | kg/kilogram/千克/公斤 | g，×1000 |
| length_cm/width_cm/height_cm | cm/厘米 | cm，值不变 |
| length_cm/width_cm/height_cm | mm/毫米 | cm，÷10 |

数值验证：价格/运费 ≥0；重量/尺寸 >0；拒绝空值/NaN/Infinity/非法字符串；不用 eval。

measurement_scope：价格/成本/运费强制 not_applicable；尺寸/重量支持 bare/packaged/unknown，不允许 not_applicable。

## 5. 报告工具环境无关修正

- `report_config.json` 的 test_command 改为 `{python} -m pytest ...`
- `generate_step_report.py` 的 run_tests 把 `{python}` 替换为 `sys.executable`（加引号）
- 不再硬编码 `.venv-311\Scripts\python.exe`
- 报告中记录实际 Python 路径
- 测试不依赖真实虚拟环境名称

## 6. ProductPage 字段映射

| FieldSelection.field_name | ProductPage._entry_vars |
|---|---|
| shein_price_usd | shein |
| product_cost_rmb | cost |
| domestic_shipping_rmb | domestic |
| weight_g | net_w（仅 bare） |
| length_cm | net_l（仅 bare） |
| width_cm | net_wi（仅 bare） |
| height_cm | net_h（仅 bare） |

已核对 product_page.py 真实变量名（第 120/121/134-137/149 行），与映射一致。

## 7. bare/packaged/unknown 回填差异

| scope | 价格/成本/运费 | 尺寸/重量 |
|---|---|---|
| not_applicable | 直接回填 | 不适用（不允许） |
| bare | 不适用（价格不用 scope） | 回填 net_* |
| packaged | 不适用 | 不回填 net_*，保留会话 |
| unknown | 不适用 | 不回填 net_*，保留会话 |

未确认字段不清空原有输入；user_modified=True 用 confirmed_value。

## 8. 自动测试结果

- 全量：**343 passed, 1 skipped in 7.94s**
- 步骤A新增：test_ocr_intake_dialog +12（人工确认规则）、test_step_report +2（{python} 替换）
- 步骤B新增：test_product_page_ocr +16（回填规则、不写db、FakeDialog）
- 现有测试全部保持通过，未修改旧测试

## 9. GUI 冒烟测试结果

自动测试已覆盖冒烟逻辑：多图添加/删除/替换、类型切换、候选勾选、无单位编辑、scope 设置(bare/packaged/unknown)、确认回填、价格/bare尺寸回填、packaged/unknown不回填、重新计算触发、不写db、取消不变。

**真实人工 GUI 点击未执行**（Agent 无法操作桌面 GUI）。建议用户人工验证：启动软件→点OCR录入→添加图片→改类型→选候选→编辑无单位→设scope→确认→核对回填→核对不保存。

## 10. 确认未写数据库、未修改历史快照

- _apply_ocr_selections 只调 _entry_vars.set 和 recalculate，不调 save_product/db
- 测试 test_no_db_save / test_no_snapshot_created 验证 products 和 product_snapshots 表回填后仍为空
- 未修改 db_manager.py、calculation/*、config/*、利润公式、物流规则、历史快照逻辑

## 11. 已知限制

1. 真实 OCR 精度待 S6 用真实截图验证（当前用 FakeEngine）
2. GUI 仅最小实现，图片预览/拖拽/多候选同字段勾选交互待完善
3. 真实人工 GUI 点击未执行
4. 回填后需用户主动点"保存"才进数据库
5. 1 个 skipped 测试（Tkinter 环境相关，不影响核心逻辑）

## 12. S6 前置条件

1. 全量测试通过（已满足，343 passed）
2. 用户确认进入 S6
3. S6 计划：创建 Python 3.11 venv 真实 PaddleOCR 接入（paddle_engine.py + preprocessing.py），锁定 requirements-ocr.txt 版本，用真实截图验证识别精度
4. S6 前需用户提供真实截图样本（SHEIN核价/1688成本运费/尺寸重量等）
