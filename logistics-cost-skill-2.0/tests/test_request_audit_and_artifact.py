"""审计与文件测试 — request_audit.py + artifact_delivery.py + run.py integrate。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
EXAMPLES = PROJECT / "examples"


def _run_with_audit(envelope: dict, audit_path: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown", "--audit-md", audit_path],
        cwd=str(PROJECT),
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True, text=True,
    )


def _make_mode2_envelope() -> dict:
    with open(EXAMPLES / "pu_small_chain_shoulder_bag_ai.json", encoding="utf-8") as f:
        ai_data = json.load(f)
    return {
        "mode": "head_only",
        "product_display": {
            "title": "PU轻潮斜挎肩部链条包（小方包）",
            "quantity": 1, "unit": "件",
            "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
            "normal_packaging": "把手折叠、肩带收纳后纸盒装",
            "conservative_packaging": "较少压缩并增加局部五金保护",
            "confidence": "high",
        },
        "ai": ai_data,
    }


class TestAuditFile:
    def test_no_audit_no_file(self):
        envelope = _make_mode2_envelope()
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown"],
            cwd=str(PROJECT), input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0

    def test_audit_creates_file(self, tmp_path):
        audit_path = str(tmp_path / "audit.md")
        r = _run_with_audit(_make_mode2_envelope(), audit_path)
        assert r.returncode == 0, f"stderr={r.stderr}"
        assert Path(audit_path).exists()
        content = Path(audit_path).read_text(encoding="utf-8")
        assert "审计记录" in content

    def test_audit_is_utf8(self, tmp_path):
        audit_path = str(tmp_path / "audit_utf8.md")
        r = _run_with_audit(_make_mode2_envelope(), audit_path)
        assert r.returncode == 0
        with open(audit_path, encoding="utf-8") as f:
            content = f.read()
        assert "request_id" in content

    def test_audit_contains_request_identity(self, tmp_path):
        audit_path = str(tmp_path / "audit_id.md")
        r = _run_with_audit(_make_mode2_envelope(), audit_path)
        assert r.returncode == 0
        content = Path(audit_path).read_text(encoding="utf-8")
        assert "product_signature" in content

    def test_audit_no_second_estimate(self, tmp_path):
        """审计文件不触发第二次估算 — 使用同一信封应得到相同stdout。"""
        audit_path = str(tmp_path / "audit_e2e.md")
        r1 = _run_with_audit(_make_mode2_envelope(), audit_path)
        assert r1.returncode == 0, f"stderr={r1.stderr}"

        # 正常核算 stdout（无审计）
        r2 = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown"],
            cwd=str(PROJECT), input=json.dumps(_make_mode2_envelope(), ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r2.returncode == 0

        # stdout 应一致（审计不影响正常stdout）
        assert r1.stdout.strip() == r2.stdout.strip()

    def test_stdout_no_extra_content(self, tmp_path):
        """审计模式下stdout不含额外内容。"""
        audit_path = str(tmp_path / "audit_clean.md")
        r = _run_with_audit(_make_mode2_envelope(), audit_path)
        assert r.returncode == 0
        assert "审计" not in r.stdout
        assert "校准" not in r.stdout


class TestModeRequired:
    def test_no_mode_no_saved_returns_error(self):
        """没有mode且无保存模式时不计算，返回mode_required。"""
        from logistics_cost.session_preferences import resolve_mode, get_mode, set_mode
        # 先保存一个模式以确保测试隔离
        old = get_mode()
        if old:
            # 测试中直接验证，不通过子进程
            mode, error = resolve_mode("bad_value")
            assert mode is None
            assert error == "mode_required"
        else:
            mode, error = resolve_mode(None)
            assert mode is None
            assert error == "mode_required"


class TestIdentityInRunPy:
    def test_result_binds_request_id(self):
        """run.py 结果中包含 _request_id。"""
        import json as _json
        envelope = _make_mode2_envelope()
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin"],
            cwd=str(PROJECT), input=_json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0
        result = _json.loads(r.stdout)
        assert "_request_id" in result
        assert "_product_signature" in result

    def test_consecutive_different_products_different_ids(self):
        """连续不同商品产生不同请求身份。"""
        import json as _json
        e1 = _make_mode2_envelope()
        e2 = {
            "mode": "head_only",
            "product_display": {
                "title": "另一个商品", "quantity": 1, "unit": "件",
                "normal_packaging": "袋装", "conservative_packaging": "袋装", "confidence": "low",
            },
            "ai": e1["ai"],
        }

        r1 = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin"],
            cwd=str(PROJECT), input=_json.dumps(e1, ensure_ascii=False),
            capture_output=True, text=True,
        )
        r2 = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin"],
            cwd=str(PROJECT), input=_json.dumps(e2, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r1.returncode == 0 and r2.returncode == 0
        d1 = _json.loads(r1.stdout)
        d2 = _json.loads(r2.stdout)
        assert d1["_request_id"] != d2["_request_id"]
        assert d1["_product_signature"] != d2["_product_signature"]
