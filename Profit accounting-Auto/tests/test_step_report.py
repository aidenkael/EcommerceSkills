"""步骤报告工具测试。

覆盖当前正式 tools/generate_step_report.py 的真实接口。
"""
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.generate_step_report import (
    run,
    run_tests,
    find_test_dirs,
    next_step_number,
    generate_report,
)


class TestRun:
    def test_echo_returns_output(self):
        result = run("echo hello", cwd=REPO_ROOT)
        assert "hello" in result

    def test_empty_command_returns_degraded_result(self):
        """空命令或无输出命令应优雅降级，不抛异常。"""
        result = run("echo -n", cwd=REPO_ROOT)
        # 结果可能为空字符串或包含 error 前缀的降级信息，但不应抛异常
        assert isinstance(result, str)


class TestFindTestDirs:
    def test_finds_at_least_logistics(self):
        dirs = find_test_dirs()
        assert isinstance(dirs, list)
        # 至少应有 logistics-cost-skill-2.0
        assert "logistics-cost-skill-2.0" in dirs


class TestRunTests:
    def test_returns_list_of_results(self):
        results = run_tests(["logistics-cost-skill-2.0"])
        assert isinstance(results, list)
        assert len(results) >= 1
        r = results[0]
        assert r["project"] == "logistics-cost-skill-2.0"
        assert "passed" in r
        assert "failed" in r
        assert "errors" in r
        assert r["status"] in ("PASS", "FAIL")

    def test_nonexistent_project_skipped(self):
        results = run_tests(["nonexistent_project_xyz"])
        # 不存在的项目不会返回结果（找不到测试目录时跳过）
        assert isinstance(results, list)


class TestNextStepNumber:
    def test_empty_dir_returns_1(self, tmp_path):
        n = next_step_number(tmp_path)
        assert n == 1

    def test_existing_step_file_increments(self, tmp_path):
        (tmp_path / "step-01_test.md").write_text("# test")
        n = next_step_number(tmp_path)
        assert n == 2

    def test_multiple_step_files(self, tmp_path):
        (tmp_path / "step-01_test.md").write_text("# 1")
        (tmp_path / "step-03_test.md").write_text("# 3")
        n = next_step_number(tmp_path)
        assert n == 4


class TestGenerateReport:
    def test_generates_report_file(self, tmp_path, monkeypatch):
        """generate_report 在指定目录生成 markdown 报告。"""
        import tools.generate_step_report as mod

        # Mock git functions to avoid real git dependency
        monkeypatch.setattr(mod, "git_branch", lambda: "test-branch")
        monkeypatch.setattr(mod, "git_commit", lambda: "abc1234")
        monkeypatch.setattr(mod, "git_remote", lambda: "origin")
        monkeypatch.setattr(mod, "git_status", lambda: "")
        monkeypatch.setattr(mod, "git_diff_stat", lambda: "1 file changed")
        monkeypatch.setattr(mod, "find_test_dirs", lambda: [])
        monkeypatch.setattr(mod, "run_tests", lambda p: [{
            "project": "test-proj", "passed": 5, "failed": 0, "errors": 0, "status": "PASS"
        }])

        # Override report base
        original_root = mod.REPO_ROOT
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

        # Create the expected subdirectory
        (tmp_path / "review_packages" / "test-project" / "test-step").mkdir(parents=True, exist_ok=True)

        report_path = generate_report(
            project="test-project",
            step_name="test-step",
            implementation="test impl",
            design="test design",
            risks="test risks",
            issues="test issues",
        )

        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "步骤报告" in content
        assert "test impl" in content
        assert "test design" in content
        assert "test risks" in content
        assert "test issues" in content
        assert "test-branch" in content

    def test_report_contains_required_sections(self, tmp_path, monkeypatch):
        """报告文件包含 Git 状态、测试结果、实现内容等标准区块。"""
        import tools.generate_step_report as mod

        monkeypatch.setattr(mod, "git_branch", lambda: "main")
        monkeypatch.setattr(mod, "git_commit", lambda: "deadbeef")
        monkeypatch.setattr(mod, "git_remote", lambda: "https://github.com/test/repo")
        monkeypatch.setattr(mod, "git_status", lambda: "")
        monkeypatch.setattr(mod, "git_diff_stat", lambda: "")
        monkeypatch.setattr(mod, "find_test_dirs", lambda: [])
        monkeypatch.setattr(mod, "run_tests", lambda p: [])
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

        (tmp_path / "review_packages" / "basic-test" / "full").mkdir(parents=True, exist_ok=True)

        report_path = generate_report(
            project="basic-test",
            step_name="full",
            implementation="基本实现",
            design="关键设计点",
            risks="无",
            issues="无",
        )

        content = report_path.read_text(encoding="utf-8")
        assert "Git 状态" in content
        assert "测试结果" in content
        assert "实现内容" in content
        assert "关键设计" in content
        assert "真实风险" in content
        assert "遗留问题" in content
