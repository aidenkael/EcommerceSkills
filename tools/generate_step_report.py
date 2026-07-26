"""自动生成步骤报告。

收集 git 状态、文件变更、测试结果，生成 markdown 报告。
测试失败仍生成报告并返回失败状态，不伪造结果。

用法：
    python tools/generate_step_report.py [phase]
    python tools/generate_step_report.py phase-2-1-s4
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "report_config.json"


def load_config():
    """读取报告配置。"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_git(args):
    """执行 git 命令，返回 (stdout, stderr, returncode)。"""
    result = subprocess.run(
        ["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def collect_git_info():
    """收集分支、HEAD、工作区状态、最近提交。"""
    branch, _, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    head, _, _ = run_git(["rev-parse", "HEAD"])
    status, _, _ = run_git(["status", "--short"])
    log, _, _ = run_git(["log", "--oneline", "-5"])
    return {"branch": branch, "head": head, "status": status, "log": log}


def collect_file_changes():
    """收集暂存/未暂存/未跟踪文件。"""
    staged, _, _ = run_git(["diff", "--cached", "--name-status"])
    unstaged, _, _ = run_git(["diff", "--name-status"])
    untracked, _, _ = run_git(["ls-files", "--others", "--exclude-standard"])
    return {"staged": staged, "unstaged": unstaged, "untracked": untracked}


def run_tests(test_cmd):
    """执行测试命令，返回 (output, returncode)。

    test_cmd 中的 {python} 占位符替换为 sys.executable（加引号），避免硬编码虚拟环境路径。
    """
    py = f'"{sys.executable}"'
    cmd = test_cmd.replace("{python}", py)
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, shell=True, capture_output=True, text=True, encoding="utf-8"
    )
    out = (result.stdout or "") + (result.stderr or "")
    return out, result.returncode


def parse_test_summary(output):
    """从 pytest 输出解析 passed/failed/skipped 数量。"""
    def _find(pattern):
        m = re.search(pattern, output)
        return int(m.group(1)) if m else 0
    return {
        "passed": _find(r"(\d+)\s+passed"),
        "failed": _find(r"(\d+)\s+failed"),
        "skipped": _find(r"(\d+)\s+skipped"),
    }


def generate(phase=None, output_path=None, test_runner=None):
    """生成步骤报告。

    test_runner 可注入（测试用），默认为 run_tests。
    返回 {"path": ..., "status": "PASS"/"FAIL", "summary": {...}}。
    """
    config = load_config()
    test_cmd = config.get("test_command", 'python -m pytest "Profit accounting-Auto/tests" -q')
    runner = test_runner or run_tests
    git_info = collect_git_info()
    changes = collect_file_changes()
    test_output, test_rc = runner(test_cmd)
    summary = parse_test_summary(test_output)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    phase = phase or config.get("default_phase", "current")
    if output_path is None:
        output_path = REPO_ROOT / "review_packages" / "Profit accounting-Auto" / phase / "step_report.md"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    status = "PASS" if test_rc == 0 else "FAIL"

    md = f"""# 步骤报告

生成时间：{now}
Python：`{sys.executable}`

## Git 信息

- 分支：`{git_info['branch']}`
- HEAD：`{git_info['head']}`
- 最近提交：
```
{git_info['log']}
```
- 工作区状态：
```
{git_info['status'] or '(干净)'}
```

## 文件变更

暂存（staged）：
```
{changes['staged'] or '(无)'}
```

未暂存（unstaged）：
```
{changes['unstaged'] or '(无)'}
```

未跟踪（untracked）：
```
{changes['untracked'] or '(无)'}
```

## 测试

- 命令：`{test_cmd}`
- 状态：**{status}**
- passed：{summary['passed']}
- failed：{summary['failed']}
- skipped：{summary['skipped']}

测试输出（末尾 2000 字符）：
```
{test_output[-2000:]}
```
"""
    output_path.write_text(md, encoding="utf-8")
    return {"path": str(output_path), "status": status, "summary": summary}


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else None
    result = generate(phase=phase)
    print(f"报告状态：{result['status']}")
    print(f"报告路径：{result['path']}")
    print(f"测试：passed={result['summary']['passed']} failed={result['summary']['failed']} skipped={result['summary']['skipped']}")
    sys.exit(0 if result["status"] == "PASS" else 1)
