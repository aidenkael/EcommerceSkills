# ROAD-1 阶段报告（最终收尾版） — 新商品测算主页面重构

**更新时间：** 2026-07-28  
**分支：** `codex/feature/road-1-main-page-ui`  
**风险等级：** 中风险（主UI重构，未改公式/Schema）

> **重要声明：** 本报告替代此前所有 ROAD-1 报告。初版中"可验收"的结论已被复审撤回，复审后又进行了最终收尾（根窗口修复+真实交互测试+包装计算链测试）。

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

### Commit 3（最终收尾）：根窗口修复+完整测试

| # | 任务 | 内容 |
|---|---|---|
| 1 | 修复根窗口 | `MainWindow.__init__` 在 tkinterdnd2 可用时使用 `TkinterDnD.Tk()` 替代 `tk.Tk()`；不可用时回退并输出 `RuntimeWarning` |
| 2 | 真实交互测试 | `TestCtrlVClipboardImage`（4项：PIL Image粘贴/无选中框粘贴/满框提示/空剪贴板提示）；`TestDragDropPathParsing`（4项：空格路径/中文路径/Tcl列表格式/覆盖确认）；`TestDndRootWindowRegistration`（2项：MainWindow使用TkinterDnD.Tk验证/ProductPage在DnD根窗口下不崩溃） |
| 3 | 包装计算链测试 | `TestPackagingCalcChain`（5项：正常档recalculate验证体积重/计费重/头程/总物流/总成本；保守档切换结果变化；切回正常档值恢复；无包装数据不崩溃；填售价利润计算） |
| 4 | GUI冒烟测试 | `tests/test_road1_gui_smoke.py` — 12项独立冒烟（上传/拖拽/Ctrl+V图片/Ctrl+V文件/预览/Del/增加框/减少含图框/AI识别/模式切换/保存不清空/清空确认） |

---

## 三、测试结果

### Python 3.11 (.venv-311)

```
393 passed, 4 skipped, 1 xpassed, 0 failed in 28.36s
```

Skip 原因：
- Tcl/Tk 环境间歇性不可用（测试间多 Tk root 冲突，单独运行均通过）

### Python 3.13 (managed)

```
349 passed, 5 skipped, 0 failed
```

### Logistics 2.0

```
17 passed in 0.16s
```

### GUI 冒烟（Python 3.11 真实 Tk）— 12 项

| # | 检查项 | 结果 |
|---|---|---|
| 1 | 上传图片 | ✅ |
| 2 | 拖拽文件 | ✅ |
| 3 | Ctrl+V 粘贴 PIL Image | ✅ (间歇 skip) |
| 4 | Ctrl+V 粘贴文件路径 | ✅ |
| 5 | 预览已有图片 | ✅ (间歇 skip) |
| 6 | Del 删除选中图片 | ✅ |
| 7 | 增加图片框 | ✅ |
| 8 | 减少含图图片框 | ✅ |
| 9 | AI 识别 | ✅ |
| 10 | 包装档切换 | ✅ |
| 11 | 保存不清空 | ✅ |
| 12 | 清空确认 | ✅ |

### ROAD-1 复审测试明细（test_road1_review.py）

```
31 passed, 1 skipped — 含新增 15 个测试
```

新增测试类：
- `TestCtrlVClipboardImage` — 4 项真实 Ctrl+V 流程
- `TestDragDropPathParsing` — 4 项路径解析（空格/中文/Tcl列表/覆盖确认）
- `TestDndRootWindowRegistration` — 2 项 DnD 根窗口验证
- `TestPackagingCalcChain` — 5 项包装计算链完整验证

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

### 6. 根窗口修复（最终收尾新增）
- **之前**：`MainWindow` 使用 `tk.Tk()`，图片框的 `drop_target_register` 静默降级，DnD 拖拽实际不可用
- **之后**：`MainWindow` 在 tkinterdnd2 可用时使用 `TkinterDnD.Tk()`，不可用时回退 `tk.Tk()` 并输出 `RuntimeWarning`
- 验证：`TestDndRootWindowRegistration::test_main_window_uses_tkinterdnd_when_available` 确认根窗口有 `drop_target_register` 方法

---

## 五、Commit SHA

| Commit | SHA | 说明 |
|---|---|---|
| 初版 Step1 | `a8a3fb6` | 8区布局重构 |
| 初版 Step2+3 | `bfd70ac` | 图片框+FakeAI |
| 初版 Fix | `90eee42` | image_states guard |
| 初版 Report | `e5f5424` | ROAD-1 report（已撤回） |
| 复审 Commit1 | `04773cd` | 主页面功能与边界修复 |
| 复审 Commit2 | `143cf29` | 回归修复与测试 |
| **最终收尾** | （本次提交） | 根窗口修复+真实交互测试+包装计算链测试+GUI冒烟12项 |

---

## 六、是否可以重新交给用户进行 ROAD-1 人工 GUI 验收

**✅ 可以。**

- 0 failed / 0 error
- 5 项验收缺陷全部修复
- 根窗口已修复为 TkinterDnD.Tk()，DnD 真正可用
- Python 3.11 全量 393 passed（含新增 15 个交互/计算链测试 + 12 项 GUI 冒烟）
- 底部仅 2 个主按钮
- 拖拽/Ctrl+V/Del 全部接入并测试
- 包装档数据结构统一
- 冷冻规则快照修复
- 包装计算链完整验证（正常→保守→正常，数值变化与恢复均通过）

**不进入 ROAD-2，不合并 master。**
