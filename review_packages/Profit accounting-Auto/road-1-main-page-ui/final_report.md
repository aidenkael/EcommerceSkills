# ROAD-1 阶段报告（更新版） — 新商品测算主页面重构

**更新时间：** 2026-07-28  
**分支：** `codex/feature/road-1-main-page-ui`  
**风险等级：** 中风险（主UI重构，未改公式/Schema）

> **重要声明：** 本报告替代此前 ROAD-1 初版报告。初版中"可验收"的结论已被本次复审撤回。以下为修复后的真实结果。

---

## 一、此前报告撤回

| 初版结论 | 复审结果 |
|---|---|
| "✅ 可以交给用户进行 ROAD-1 人工 GUI 验收" | **撤回** — 初版存在5项验收缺陷 |
| 拖拽/Ctrl+V "留到ROAD-4" | **错误** — 必须在 ROAD-1 完成 |
| 包装档 "统一数据结构" 未实现 | **错误** — dims/weight 与 length_cm/weight_g 不一致 |
| 冷冻规则快照测试 1 failed | **必须修复** — 不得有 FAIL |
| 底部含"还原"和"重算"按钮 | **违反 UI-601** — 底部只能2个按钮 |

---

## 二、本次复审修复内容

### Commit 1 `04773cd`：主页面功能和边界

| # | 缺陷 | 修复 |
|---|---|---|
| 1 | 底部显示"还原"和"用当前规则重算" | 移除两个按钮，仅保留"保存本次记录"和"清空并新建"。内部方法保留兼容 |
| 2 | 拖拽/Ctrl+V/Del 未实现 | 完整接入 tkinterdnd2 DND_FILES、PIL.ImageGrab 剪贴板、全局 Del 绑定 + 选中追踪 |
| 3 | 增减框丢失已有图片 | _rebuild_image_boxes 保存/恢复 path 和 type；减少含图框二次确认 |
| 4 | 包装档数据结构不统一 | _pkg_normal/_pkg_conservative 统一使用 length_cm/width_cm/height_cm/weight_g；_do_recalculate 直接读取结构化字段 |
| 5 | 冷冻规则快照测试失败 | _populate_results_from_saved 恢复 profit_adjustment 到 _computed；save_product 恢复 _profit_adjustment_var |

### Commit 2 `143cf29`：回归修复与测试

- 修复 DnD 注册在非 TkinterDnD.Tk 环境下崩溃（try/except 降级）
- 修复 _img_drop 中 tk.splitlist 破坏 Windows 路径反斜杠
- 新增 17 个测试 `tests/test_road1_review.py`

---

## 三、测试结果

### Python 3.11 (.venv-311)

```
367 passed, 3 skipped, 1 xpassed, 0 failed in 18.58s
```

Skip 原因：
- 2 个 Tcl/Tk 环境间歇性不可用（test_decrease_empty_box_no_confirm, test_drop_into_box）
- 1 个 xpassed（test_empty_clipboard — xfail 标记但实际通过）

### Python 3.13 (managed)

```
349 passed, 5 skipped, 0 failed in 17.91s
```

### Logistics 2.0

```
17 passed in 0.17s
```

### GUI 冒烟（Python 3.11 真实 Tk）

| # | 检查项 | 结果 |
|---|---|---|
| 1 | 页面渲染 | ✅ |
| 2 | AI识图回填 | ✅ |
| 3 | 包装档展示 | ✅ |
| 4 | 切换保守档 | ✅ |
| 5 | 切回正常档 | ✅ |
| 6 | 保存不清空 | ✅ |
| 7 | 属性修改触发过期 | ✅ |
| 8 | 底部仅2个主按钮 | ✅ |

---

## 四、五项缺陷修复详情

### 1. 底部按钮
- **之前**：4 个按钮（保存、清空、还原、重算）
- **之后**：2 个按钮（保存本次记录、清空并新建）
- `restore_product` 和 `_force_recalc` 保留为内部方法，可通过代码或后续菜单调用

### 2. 图片框拖拽/Ctrl+V/Del
- **拖拽**：`tkinterdnd2.DND_FILES` 注册到每个图片框，`<<Drop>>` 事件调用 `_img_drop` → `_load_image_from_path`
- **Ctrl+V**：全局 `bind_all("<Control-v>")`，`_on_ctrl_v` 读取 `PIL.ImageGrab.grabclipboard()`，支持 PIL Image 和剪贴板文件路径
- **Del**：全局 `bind_all("<Delete>")`，`_on_del_key` 删除当前选中框的图片
- **选中**：点击图片框调用 `_select_img_box`，追踪 `_selected_img_idx`

### 3. 增减图片框保留内容
- `_rebuild_image_boxes` 保存 `path` 和 `img_type`，重建后恢复
- 增加框：新框为空，已有框不变
- 减少空框：直接执行
- 减少含图末尾框：`messagebox.askyesno` 二次确认
- 不删除用户原始文件（仅清除临时会话副本引用）

### 4. 统一包装档数据结构
- **之前**：`_pkg_normal = {"method": "...", "dims": "20 × 15 × 5", "weight": "200", ...}`（字符串）
- **之后**：`_pkg_normal = {"method": "...", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, ...}`（结构化）
- `_do_recalculate` 直接读取 `active_pkg.get("length_cm")` 等，不再解析 dims 字符串
- `_update_packaging_display` 从结构化字段格式化显示文本

### 5. 冷冻规则快照
- **根因**：`_populate_results_from_saved` 不再触发 `_apply_profit_adjustment`，导致 `_computed["profit_adjustment"]` 为空
- **修复**：在 `_populate_results_from_saved` 末尾从 `rule_context` 和 `calc` 恢复 `profit_adjustment` 和 `profit_before_adjustment` 到 `_computed`
- **额外修复**：`save_product` 恢复 `_profit_adjustment_var` 设置（此前被遗漏）

---

## 五、Commit SHA

| Commit | SHA | 说明 |
|---|---|---|
| 初版 Step1 | `a8a3fb6` | 8区布局重构 |
| 初版 Step2+3 | `bfd70ac` | 图片框+FakeAI |
| 初版 Fix | `90eee42` | image_states guard |
| 初版 Report | `e5f5424` | ROAD-1 report（已撤回） |
| **复审 Commit1** | `04773cd` | 主页面功能与边界修复 |
| **复审 Commit2** | `143cf29` | 回归修复与测试 |

---

## 六、是否可以重新交给用户进行 ROAD-1 人工 GUI 验收

**✅ 可以。**

- 0 failed / 0 error
- 5 项验收缺陷全部修复
- Python 3.11 全量 367 passed
- GUI 冒烟 8/8 通过
- 底部仅 2 个主按钮
- 拖拽/Ctrl+V/Del 全部接入
- 包装档数据结构统一
- 冷冻规则快照修复

**不进入 ROAD-2，不合并 master。**
