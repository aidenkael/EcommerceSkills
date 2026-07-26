# 步骤报告工具

自动收集 Git 状态、文件变更和测试结果，生成 markdown 步骤报告。

## 用法

### 命令行

```bat
REM 在仓库根执行
tools\run_step_report.bat phase-2-1-s4
```

或直接用 Python：

```bat
"Profit accounting-Auto\.venv-311\Scripts\python.exe" tools\generate_step_report.py phase-2-1-s4
```

### 输出

默认输出到：

```
review_packages/Profit accounting-Auto/<phase>/step_report.md
```

`<phase>` 不指定时用 `report_config.json` 的 `default_phase`。

## 报告内容

- 生成时间
- 当前分支、HEAD、最近 5 条提交、工作区状态
- 暂存/未暂存/未跟踪文件
- 测试命令、状态（PASS/FAIL）、passed/failed/skipped 数量
- 测试输出末尾 2000 字符

## 配置

`report_config.json`：

| 字段 | 说明 |
|---|---|
| `project_name` | 项目名（用于输出路径） |
| `test_command` | 默认测试命令 |
| `default_phase` | 未指定 phase 时的默认阶段名 |

## 规则

- 测试失败仍生成报告，状态为 FAIL，不伪造结果
- 退出码：PASS=0，FAIL=1
- 不提交缓存、日志、真实数据库
