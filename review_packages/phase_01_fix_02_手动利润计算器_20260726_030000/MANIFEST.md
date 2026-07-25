# MANIFEST.md — phase_01_fix_02 完整验收包

## 基本信息

| 项目 | 内容 |
|------|------|
| 阶段名称 | phase_01_fix_02（复审修复版） |
| 软件版本 | v0.1.2 |
| 生成时间 | 2026-07-26 03:00 |
| Git 提交 | `fa69607` |
| 前一提交 | `9fc254f`（fix_01） |
| 初始提交 | `072318b` |

## 验收包文件（18 项）

```
MANIFEST.md                           ← 本文件
fix_02修复对照表.md                    ← 复审问题逐项对照
测试报告.md                            ← 81项测试 + 分布
Git记录.txt                           ← 三次提交历史
当前规则与配置.md                       ← 生效规则
深圳与义乌货代规则说明.md               ← 线路处理说明
项目目录结构.txt                        ← 完整目录树
修改文件清单.md                        ← fix_02 变更文件
审查重点.md                            ← 建议审查的9个检查点
关键代码文件/                          ← 完整项目源码（保持目录结构）
test_db_samples/                      ← 旧数据库样本 + 迁移说明
sample_data/                          ← 虚拟测试数据（5条）
test_logs/                            ← （空）
screenshots/                          ← （空，Agent限制）
```

## 关键代码文件结构（可直接运行）

```
关键代码文件/
├── app.py
├── requirements.txt
├── calculation/
│   ├── __init__.py
│   ├── logistics.py
│   ├── profit.py          ← 新增 net_profit_amount / net_profit_rate
│   └── currency.py
├── database/
│   ├── __init__.py
│   └── db_manager.py       ← 含迁移机制
├── config/
│   ├── __init__.py
│   └── config_manager.py
├── ui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── product_page.py     ← fix_02 核心修复
│   └── history_page.py
├── tests/
│   ├── test_currency.py    (11)
│   ├── test_database.py    (10)
│   ├── test_history_product.py (6)  ← NEW
│   ├── test_logistics.py   (19)
│   ├── test_migration.py   (5)       ← NEW
│   ├── test_net_profit.py  (9)       ← NEW
│   └── test_profit.py      (21)
└── docs/
    └── README.md
```

## 测试：81 项全部通过

```
pytest tests/ -v → 81 passed in 0.37s
```

## 推荐阅读顺序

1. MANIFEST.md
2. fix_02修复对照表.md
3. 测试报告.md（81项分布）
4. 深圳与义乌货代规则说明.md
5. Git记录.txt
6. 审查重点.md
7. 关键代码文件/

## 已排除内容
- API 密钥、密��、Cookie
- .env 文件
- __pycache__、.pytest_cache
- 真实用户隐私数据
