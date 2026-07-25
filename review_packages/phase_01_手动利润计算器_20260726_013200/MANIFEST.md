# MANIFEST.md — 阶段验收包清单

## 基本信息

| 项目 | 内容 |
|------|------|
| 阶段名称 | phase_01_手动利润计算器 |
| 软件版本 | v0.1 |
| 生成时间 | 2026-07-26 01:32 |
| Git 提交编号 | 072318b356f72f72659d80e708cecf6dd3482fd8 |
| 分支 | master（初始提交） |

## 验收包包含的全部文件

```
MANIFEST.md                     ← 本文件（建议最先阅读）
阶段完成总结.md                  ← 阶段目标与完成情况
测试报告.md                      ← 59项测试结果
本阶段修改文件清单.md             ← 逐文件说明
项目目录结构.txt                  ← 完整目录树
运行说明.md                      ← 面向用户的启动指南
当前规则与配置.md                 ← 生效的计算规则和配置
Git记录.txt                     ← Git 日志与状态
审查重点.md                      ← 建议审查者重点检查的内容
关键代码文件/                    ← 核心源代码副本
    app.py                      程序入口
    calculation/__init__.py
    calculation/logistics.py    物流计算
    calculation/profit.py       利润计算
    calculation/currency.py     货币换算
    database/__init__.py
    database/db_manager.py      SQLite管理
    config/__init__.py
    config/config_manager.py    配置管理
    ui/__init__.py
    ui/main_window.py           主窗口
    ui/product_page.py          测算页面
    ui/history_page.py          历史页面
    tests/test_logistics.py     物流测试
    tests/test_profit.py        利润测试
    tests/test_currency.py      货币测试
    tests/test_database.py      数据库测试
    requirements.txt            依赖声明
    docs/README.md              说明文档
screenshots/                    （空，Agent无法截取GUI屏幕）
sample_data/
    完整商品记录.json            示例：完整数据
    部分缺失记录.json            示例：部分字段为空
    修改后记录.json              示例：保存后修改
logs/                           （空，首次运行暂无日志）
```

## 推荐阅读顺序

1. **MANIFEST.md**（本文件）
2. **阶段完成总结.md** — 快速了解全局
3. **测试报告.md** — 验证计算正确性
4. **本阶段修改文件清单.md** — 了解每个文件
5. **项目目录结构.txt** — 了解代码组织
6. **当前规则与配置.md** — 确认业务规则
7. **审查重点.md** — 告诉审查者看什么
8. **关键代码文件/** — 审查源代码

## 已删除或脱敏的内容

- 无 API 密钥
- 无 .env 文件
- 无密码或 Cookie
- 无真实客户数据
- 无浏览器账号数据
- SQLite 数据库未放入验收包（sample_data 使用 JSON 虚拟数据替代）

## 是否适合直接上传给第三方AI审查

**是**。本验收包不含任何隐私信息，所有文件内容均可公开审查。
