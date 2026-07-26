# Agent 高效稳定开发准则（通用执行文件）

适用于 EcommerceSkills 仓库所有项目。本文件是 `tools/` 报告工具的使用规范。

## 开发节奏

1. **中等粒度开发**：每个步骤是有实际代码/配置变化的阶段，纯分析不计入独立步骤。
2. **按风险决定测试强度**：核心计算/数据迁移/字段回填必须全量回归；UI/工具可只跑相关测试，完成前再跑全量。
3. **完成后运行报告脚本**：每个有效步骤完成后，运行 `tools/run_step_report.bat <phase>` 生成报告。
4. **聊天只输出摘要和报告路径**：不在聊天里贴大段代码或完整报告正文。

## 步骤报告

运行：

```bat
tools\run_step_report.bat phase-2-1-s4
```

输出：`review_packages/Profit accounting-Auto/<phase>/step_report.md`

报告自动包含：分支、HEAD、工作区状态、文件变更、测试 passed/failed/skipped、测试输出末尾。

测试失败仍生成报告（状态 FAIL），不伪造结果。

## Git 提交

- 一个 commit 只含一个明确步骤或紧密相关的小修改
- 提交信息格式：`<类型>: <简述>` 或 `<项目名称>：<步骤简述>`
- 推送前检查 `git diff`、测试结果、敏感信息
- 不提交缓存、日志、临时文件、真实数据库、Token、Cookie

## 测试

- 默认命令：`"Profit accounting-Auto/.venv-311/Scripts/python.exe" -m pytest "Profit accounting-Auto/tests" -q`
- 不修改现有测试来迁就错误实现
- 自动测试只证明流程可运行，真实识别精度需人工验证

## 报告工具扩展

如需支持其他项目，修改 `tools/report_config.json` 的 `project_name` 和 `test_command`，或在 `generate()` 调用时传入 `phase` 和 `output_path`。
