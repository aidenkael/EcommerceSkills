# Step 02: EXE启动与隔离数据库

## 测试环境

```
$env:LOCALAPPDATA = "E:\EcommerceSkills\temp_acceptance\phase-1-6\localappdata"
```

## 自动验证项目

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | EXE 可以启动 | ✅ PID 47288，运行8秒未崩溃 |
| 2 | 不会立即退出或崩溃 | ✅ 进程持续运行 |
| 3 | 创建 `ProfitAccountingAuto\profit_accounting.db` | ✅ 路径：`temp_acceptance\phase-1-6\localappdata\ProfitAccountingAuto\profit_accounting.db` |
| 4 | Schema 版本 = 7 | ✅ |
| 5 | 默认存在 SHEIN 29美元以下运费补贴 | ✅ 启用状态，income/fixed 2.99 USD |
| 6 | 默认规则启用 | ✅ is_enabled=1 |
| 7 | EXE 不依赖源码目录数据库 | ✅ 数据库创建在 LOCALAPPDATA 下 |
| 8 | 无缺失模块/Tkinter 错误 | ✅ 进程正常运行无崩溃 |
| 9 | 无预置测试数据库 | ✅ 新创建的空白数据库 |

## 待用户人工验收

| # | 检查项 | 说明 |
|---|--------|------|
| 10 | 关闭软件后再次启动，数据库和设置仍能读取 | 需 GUI 操作 |
| 11 | 商品页面默认选择"无" | 需 GUI 视觉确认 |
