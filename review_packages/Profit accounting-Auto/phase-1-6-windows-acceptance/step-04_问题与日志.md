# Step 04: 问题与日志

## 问题

**无阻塞性问题**。EXE 构建成功，隔离启动测试通过，216 项测试全部通过。

## 日志位置

- PyInstaller 构建日志：`Profit accounting-Auto\build\ProfitAccountingAuto\warn-ProfitAccountingAuto.txt`
- PyInstaller 交叉引用：`Profit accounting-Auto\build\ProfitAccountingAuto\xref-ProfitAccountingAuto.html`

## 警告摘要

仅标准跨平台模块缺失警告，不影响 Windows 运行：
- `grp` / `pwd` — Unix 用户/组模块
- 无业务代码缺失

## 代码修改

仅 `build_windows.bat` — 改为使用项目 `.venv`。无业务代码修改。
