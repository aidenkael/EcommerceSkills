#!/usr/bin/env python3
"""
generate_step_report.py — 自动生成步骤报告

用法：
    python tools/generate_step_report.py [--project <项目名>] [--step <步骤名>]

输出：
    review_packages/<项目名>/<任务名>/step-NN_<步骤名>.md
    自动编号，若已存在则递增。

脚本负责收集 Git 状态、分支、Commit、修改文件和测试结果。
Agent 只补充实现内容、关键设计、真实风险和遗留问题。
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run(cmd, cwd=REPO_ROOT):
    """Run a command and return stdout string."""
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=str(cwd), capture_output=True, text=True, timeout=30
        )
        return r.stdout.strip()
    except Exception as e:
        return f"[error: {e}]"


def git_branch():
    return run("git rev-parse --abbrev-ref HEAD")


def git_commit():
    return run("git rev-parse --short HEAD")


def git_status():
    return run("git status --short")


def git_diff_stat():
    return run("git diff --stat HEAD~1 HEAD") or run("git diff --cached --stat")


def git_remote():
    return run("git remote get-url origin")


def find_test_dirs():
    """Find all tests/ directories with Python test files."""
    test_dirs = []
    for item in REPO_ROOT.iterdir():
        if item.is_dir() and not item.name.startswith(".") and item.name != ".git":
            test_dir = item / "tests"
            if test_dir.is_dir() and any(test_dir.glob("test_*.py")):
                test_dirs.append(item.name)
    return test_dirs


def run_tests(project_names):
    """Run pytest for each project that has tests."""
    python_exe = sys.executable or "python"
    results = []
    for name in project_names:
        test_path = REPO_ROOT / name / "tests"
        if not test_path.is_dir():
            continue
        r = subprocess.run(
            f'"{python_exe}" -m pytest "{test_path}" -v --tb=short',
            shell=True,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = r.stdout + r.stderr
        passed = len(re.findall(r"\bPASSED\b", output))
        failed = len(re.findall(r"\bFAILED\b", output))
        errors = len(re.findall(r"\bERROR\b", output))
        results.append({
            "project": name,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "status": "PASS" if failed == 0 and errors == 0 else "FAIL",
        })
    return results


def next_step_number(report_dir):
    """Find the next step number in the report directory."""
    if not report_dir.exists():
        return 1
    existing = list(report_dir.glob("step-NN_*.md"))
    # Also check numbered ones
    pattern = re.compile(r"step-(\d+)_")
    max_num = 0
    for f in report_dir.glob("step-*.md"):
        m = pattern.match(f.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num + 1


def generate_report(project, step_name, implementation, design, risks, issues):
    """Generate the step report markdown."""
    # Determine report directory
    report_base = REPO_ROOT / "review_packages" / project
    # If step_name looks like a task name, use it as subdirectory
    task_dir = report_base / step_name if step_name else report_base

    step_num = next_step_number(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)

    filename = f"step-{step_num:02d}_{step_name or 'update'}.md"
    report_path = task_dir / filename

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    branch = git_branch()
    commit = git_commit()
    remote = git_remote()
    status = git_status()
    diff_stat = git_diff_stat()

    test_results = run_tests(find_test_dirs())

    # Build test summary
    test_lines = []
    total_pass = total_fail = 0
    for t in test_results:
        test_lines.append(
            f"- {t['project']}: {t['passed']} passed, {t['failed']} failed, {t['errors']} errors [{t['status']}]"
        )
        total_pass += t["passed"]
        total_fail += t["failed"]
    test_summary = "\n".join(test_lines) if test_lines else "- (无测试目录)"

    # Build modified files list
    modified_files = status if status else "(无未提交修改)"

    content = f"""# 步骤报告：{step_name or 'update'}

> 自动生成于 {now}

## Git 状态

| 项目 | 值 |
|------|-----|
| 分支 | `{branch}` |
| Commit | `{commit}` |
| 远程 | `{remote}` |
| 工作区 | { "clean" if not status else "有修改" } |

## 修改文件

```
{modified_files}
```

## Diff 统计

```
{diff_stat or "(无差异)"}
```

## 测试结果

{test_summary}

**汇总**：{total_pass} passed, {total_fail} failed

## 实现内容

{implementation or '(待 Agent 填写)'}

## 关键设计

{design or '(待 Agent 填写)'}

## 真实风险

{risks or '(待 Agent 填写)'}

## 遗留问题

{issues or '(待 Agent 填写)'}

## 下一步

(待 Agent 填写)
"""

    report_path.write_text(content, encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="生成步骤报告")
    parser.add_argument("--project", default="repository-rules", help="项目名称")
    parser.add_argument("--step", default="update", help="步骤名称")
    parser.add_argument("--impl", default="", help="实现内容")
    parser.add_argument("--design", default="", help="关键设计")
    parser.add_argument("--risks", default="", help="真实风险")
    parser.add_argument("--issues", default="", help="遗留问题")
    args = parser.parse_args()

    report_path = generate_report(
        args.project, args.step, args.impl, args.design, args.risks, args.issues
    )

    rel_path = report_path.relative_to(REPO_ROOT)
    print(f"报告已生成：{rel_path}")
    print(f"完整路径：{report_path}")


if __name__ == "__main__":
    main()
