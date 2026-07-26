# Final Report — Phase 1.6 Windows 验收

**项目**：Profit accounting-Auto  
**分支**：`codex/test/phase-1-6-windows-acceptance`  
**提交**：待提交  
**生成时间**：2026-07-26 13:18

---

## 一、环境

| 项目 | 值 |
|------|-----|
| Python | 3.13.14 |
| PyInstaller | 6.21.0 |
| venv | `Profit accounting-Auto.venv` |

## 二、测试结果

```
.venv\Scripts\python.exe -m pytest tests -q
→ 216 passed in 3.60s
```

## 三、EXE 信息

| 项目 | 值 |
|------|-----|
| 路径 | `dist\ProfitAccountingAuto.exe` |
| 大小 | 12.7 MB |
| 构建命令 | `.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name ProfitAccountingAuto app.py` |
| 是否真实启动 | ✅ 是（PID 47288，8秒未崩溃） |

## 四、隔离测试环境

```
$env:LOCALAPPDATA = "E:\EcommerceSkills\temp_acceptance\phase-1-6\localappdata"
```

- 数据库路径：`temp_acceptance\phase-1-6\localappdata\ProfitAccountingAuto\profit_accounting.db`
- Schema：v7 ✅
- 默认规则：SHEIN 29美元以下运费补贴 ✅

## 五、自动通过项目（9/10）

| # | 项目 | 状态 |
|---|------|------|
| 1 | EXE 启动 | ✅ |
| 2 | 不崩溃 | ✅ |
| 3 | 创建隔离数据库 | ✅ |
| 4 | Schema v7 | ✅ |
| 5 | 默认规则存在 | ✅ |
| 6 | 不依赖源码DB | ✅ |
| 7 | 无预置测试DB | ✅ |
| 8 | 无缺失模块错误 | ✅ |
| 9 | 无 Tkinter 错误 | ✅ |

## 六、待用户人工点击项目（38项）

详见 `step-03_GUI验收清单.md`，分为四类：
- 全局和货代：9项（修改设置、新增/修改/停用/归档货代）
- 利润调整规则：12项（默认规则、中文界面、联动、生命周期）
- 商品利润计算：13项（规则冻结、额度触发、历史保持、快照）
- 数据安全：4项（备份、恢复、容错）

## 七、代码修改

仅 `build_windows.bat` — 改为使用项目 `.venv`。无业务代码修改。

## 八、Git

| 项目 | 值 |
|------|-----|
| 分支 | `codex/test/phase-1-6-windows-acceptance` |
| 推送 | 待执行 |
| 合并 master | 否 |

## 九、建议

38 项 GUI 验收需在真实 Windows 桌面环境中逐项操作验证。自动测试层面已全部通过，无阻塞性问题。
