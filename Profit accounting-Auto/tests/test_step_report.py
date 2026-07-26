"""步骤报告工具测试。

覆盖纯函数和 generate（注入 test_runner 避免实际跑测试）。
"""
import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from tools.generate_step_report import load_config, parse_test_summary, generate


class TestLoadConfig:
    def test_returns_dict_with_test_command(self):
        cfg = load_config()
        assert isinstance(cfg, dict)
        assert "test_command" in cfg
        assert "pytest" in cfg["test_command"]


class TestParseTestSummary:
    def test_passed_only(self):
        s = parse_test_summary("289 passed in 3.38s")
        assert s["passed"] == 289
        assert s["failed"] == 0
        assert s["skipped"] == 0

    def test_failed_and_passed(self):
        s = parse_test_summary("1 failed, 288 passed in 3.0s")
        assert s["passed"] == 288
        assert s["failed"] == 1

    def test_with_skipped(self):
        s = parse_test_summary("2 skipped, 287 passed in 2.0s")
        assert s["passed"] == 287
        assert s["skipped"] == 2

    def test_empty_output(self):
        s = parse_test_summary("no tests ran")
        assert s["passed"] == 0
        assert s["failed"] == 0


class TestGenerate:
    def test_generate_writes_report_with_mock_runner(self, tmp_path):
        """generate 用注入的 test_runner 生成报告文件。"""
        out_path = tmp_path / "step_report.md"
        result = generate(
            phase="test-phase",
            output_path=out_path,
            test_runner=lambda cmd: ("3 passed in 0.1s", 0),
        )
        assert result["status"] == "PASS"
        assert result["summary"]["passed"] == 3
        assert out_path.is_file()
        content = out_path.read_text(encoding="utf-8")
        assert "步骤报告" in content
        assert "3 passed" in content or "passed：3" in content
        assert "test-phase" in content or "PASS" in content

    def test_generate_fail_status_when_test_fails(self, tmp_path):
        """测试失败时状态为 FAIL，仍生成报告。"""
        out_path = tmp_path / "fail_report.md"
        result = generate(
            phase="fail-phase",
            output_path=out_path,
            test_runner=lambda cmd: ("1 failed, 2 passed", 1),
        )
        assert result["status"] == "FAIL"
        assert result["summary"]["failed"] == 1
        assert out_path.is_file()
