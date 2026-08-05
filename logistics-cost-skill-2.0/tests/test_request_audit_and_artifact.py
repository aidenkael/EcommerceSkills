"""审计与交付测试 — 真实调用计数、审计失败路径。"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT = Path(__file__).resolve().parent.parent
EXAMPLES = PROJECT / "examples"


def _mode2_env():
    with open(EXAMPLES / "pu_small_chain_shoulder_bag_ai.json", encoding="utf-8") as f:
        ai = json.load(f)
    return {"mode": "head_only",
            "product_display": {"title": "PU轻潮斜挎肩部链条包（小方包）", "quantity": 1, "unit": "件",
                                "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
                                "normal_packaging": "把手折叠、肩带收纳后纸盒装",
                                "conservative_packaging": "较少压缩并增加局部五金保护", "confidence": "high"},
            "ai": ai}


# ---- 审计正常路径 ----

class TestAudit:
    def test_creates_file(self, tmp_path):
        p = str(tmp_path / "a.md")
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown", "--audit-md", p],
            cwd=str(PROJECT), input=json.dumps(_mode2_env(), ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr={r.stderr}"
        assert Path(p).exists()

    def test_renderer_not_empty(self, tmp_path):
        p = str(tmp_path / "a.md")
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown", "--audit-md", p],
            cwd=str(PROJECT), input=json.dumps(_mode2_env(), ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0
        content = Path(p).read_text(encoding="utf-8")
        assert "```" in content
        lines = content.split("\n```\n")
        renderer_section = lines[-2] if len(lines) > 2 else ""
        assert "(无)" not in renderer_section

    def test_audit_content_consistency(self, tmp_path):
        p = str(tmp_path / "a.md")
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown", "--audit-md", p],
            cwd=str(PROJECT), input=json.dumps(_mode2_env(), ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0
        content = Path(p).read_text(encoding="utf-8")
        assert r.stdout.strip() in content


# ---- 调用计数 ----

class TestEstimateCount:
    def test_audit_mode_estimate_once(self):
        """审计模式下 estimate 只调用一次。通过 patch run 模块中的 estimate。"""
        import run
        original = run.estimate
        calls = [0]

        def counting(*a, **kw):
            calls[0] += 1
            return original(*a, **kw)

        with patch.object(run, "estimate", side_effect=counting):
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
                prefs = tf.name
            with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as af:
                audit_path = af.name
            try:
                env = json.dumps(_mode2_env(), ensure_ascii=False)
                with patch("sys.stdin", io.StringIO(env)):
                    exit_code = run.main(["--stdin", "--render-markdown", "--audit-md", audit_path, "--prefs-path", prefs])
                assert exit_code == 0
                assert calls[0] == 1, f"estimate called {calls[0]} times, expected 1"
            finally:
                Path(prefs).unlink(missing_ok=True)
                Path(audit_path).unlink(missing_ok=True)


# ---- 审计失败路径 ----

class TestAuditFailure:
    def test_audit_write_failure_no_stdout(self):
        """审计写入失败时 stdout 为空，stderr 含错误，estimate 仍只调用一次。"""
        import run
        original = run.estimate
        calls = [0]

        def counting(*a, **kw):
            calls[0] += 1
            return original(*a, **kw)

        with patch.object(run, "estimate", side_effect=counting):
            with patch("run.write_markdown_artifact") as mock_write:
                mock_write.side_effect = OSError("mock failure")
                with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
                    prefs = tf.name

                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = io.StringIO()
                sys.stderr = io.StringIO()
                try:
                    sys.argv = ["run.py", "--stdin", "--render-markdown",
                                "--audit-md", str(Path(tf.name).parent / "audit.md"),
                                "--prefs-path", prefs]
                    env = json.dumps(_mode2_env(), ensure_ascii=False)
                    with patch("sys.stdin", io.StringIO(env)):
                        exit_code = run.main(["--stdin", "--render-markdown",
                                              "--audit-md", str(Path(tf.name).parent / "audit.md"),
                                              "--prefs-path", prefs])
                finally:
                    captured_stdout = sys.stdout.getvalue()
                    captured_stderr = sys.stderr.getvalue()
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    Path(prefs).unlink(missing_ok=True)

                assert exit_code == 2, f"Expected exit 2, got {exit_code}"
                assert captured_stdout.strip() == "", f"stdout should be empty, got: {captured_stdout[:200]}"
                assert "审计文件写入失败" in captured_stderr, f"stderr: {captured_stderr}"
                assert calls[0] == 1, f"estimate called {calls[0]} times, expected 1"


# ---- 利润门禁 ----

class TestProfitGate:
    def _pf(self, **p):
        return {"mode": "profit",
                "product_display": {"title": "T", "quantity": 1, "unit": "件", "purchase_price_rmb": 10, "domestic_freight_rmb": 3,
                                    "normal_packaging": "袋装", "conservative_packaging": "袋装", "confidence": "low"},
                "profit_parameters": p,
                "ai": {"product_type": "test", "ai_net_weight_kg": 0.1, "ai_package_size_cm": [15, 10, 3],
                       "ai_package_weight_kg": 0.12, "conservative_package_size_cm": [16, 11, 4],
                       "conservative_package_weight_kg": 0.14, "confidence": "medium"}}

    def test_missing_all(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            pp = tf.name
        try:
            r = subprocess.run(
                [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown", "--prefs-path", pp],
                cwd=str(PROJECT), input=json.dumps(self._pf(), ensure_ascii=False),
                capture_output=True, text=True)
            assert r.returncode != 0
            assert "profit_parameters_required" in r.stderr
            assert r.stdout.strip() == ""
        finally:
            Path(pp).unlink(missing_ok=True)
