#!/usr/bin/env python3
"""Mac/POSIX 环境自举脚本。

检查环境、创建虚拟环境、安装依赖、运行测试和 CAL 验证。
不修改业务配置、CAL 数据或写入用户个人目录。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
VENV = ROOT / ".venv"

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True, check=False)


def check_env() -> None:
    """检查 POSIX 环境和 Python 版本。"""
    if sys.platform.startswith("win"):
        print(f"{FAIL} 本脚本仅用于 macOS/Linux。Windows 请直接运行 run.py。")
        sys.exit(1)

    v = sys.version_info
    if v < (3, 9):
        print(f"{FAIL} Python 3.9+ 必需，当前: {sys.version}")
        sys.exit(1)
    print(f"{PASS} Python {v.major}.{v.minor}.{v.micro}")


def check_files() -> None:
    """检查必要文件是否存在。"""
    required = [
        "run.py", "agent_workflow.py", "config/logistics_config.json",
        "calibration/active_rules.json", "workflows/SESSION_ROUTER.md",
    ]
    for f in required:
        if (ROOT / f).is_file():
            print(f"{PASS} 找到: {f}")
        else:
            print(f"{FAIL} 缺失: {f}")
            sys.exit(1)


def setup_venv() -> None:
    """如果不存在，创建虚拟环境。"""
    if VENV.is_dir():
        print(f"{PASS} .venv 已存在，跳过创建。")
    else:
        r = run([sys.executable, "-m", "venv", str(VENV)])
        if r.returncode != 0:
            print(f"{FAIL} 创建 .venv 失败: {r.stderr}")
            sys.exit(1)
        print(f"{PASS} .venv 创建完成。")


def pip_bin() -> str:
    pip = VENV / "bin" / "pip3"
    if pip.is_file():
        return str(pip)
    pip = VENV / "bin" / "pip"
    if pip.is_file():
        return str(pip)
    print(f"{FAIL} 找不到 pip。")
    sys.exit(1)


def install_deps() -> None:
    """安装依赖（如有 requirements.txt）。"""
    if REQUIREMENTS.is_file():
        pip = pip_bin()
        r = run([pip, "install", "-r", str(REQUIREMENTS)])
        if r.returncode != 0:
            print(f"{FAIL} 安装依赖失败: {r.stderr[-200:]}")
            sys.exit(1)
    print(f"{PASS} 依赖就绪。")


def python_bin() -> str:
    py = VENV / "bin" / "python3"
    if py.is_file():
        return str(py)
    py = VENV / "bin" / "python"
    if py.is_file():
        return str(py)
    return sys.executable


def run_tests() -> None:
    """运行全量测试。"""
    py = python_bin()
    r = run([py, "-m", "pytest", "tests/", "-q"])
    if r.returncode != 0:
        # 如果 pytest 未安装在 venv 中，尝试直接用系统 Python 运行
        r2 = run([sys.executable, "-m", "pytest", "tests/", "-q"])
        if r2.returncode != 0:
            print(f"{FAIL} 测试失败。\n{r2.stdout[-500:]}\n{r2.stderr[-500:]}")
            sys.exit(1)
            return
        print(f"{PASS} 所有测试通过（系统 Python）。")
    else:
        print(f"{PASS} 所有测试通过。")


def run_validate() -> None:
    """运行 CAL 注册表验证。"""
    py = python_bin()
    r = run([py, "scripts/validate_active_rules.py"])
    if r.returncode != 0:
        r = run([sys.executable, "scripts/validate_active_rules.py"])
    if r.returncode != 0:
        print(f"{FAIL} CAL 验证失败: {r.stderr[-200:]}")
        sys.exit(1)
    print(f"{PASS} CAL 注册表验证通过。")


def run_replay() -> None:
    """运行 CAL 夹具回放。"""
    py = python_bin()
    r = run([py, "scripts/replay_active_rules.py"])
    if r.returncode != 0:
        r = run([sys.executable, "scripts/replay_active_rules.py"])
    if r.returncode != 0:
        print(f"{FAIL} CAL 回放失败: {r.stderr[-200:]}")
        sys.exit(1)
    print(f"{PASS} CAL 夹具回放通过。")


def main() -> int:
    print("===== 物流2.0 Mac 环境检查 =====")
    check_env()
    check_files()
    if REQUIREMENTS.is_file():
        setup_venv()
        install_deps()
    run_tests()
    run_validate()
    run_replay()
    print(f"\n{PASS} 全部检查通过。可以启动：python3 agent_workflow.py prompt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
