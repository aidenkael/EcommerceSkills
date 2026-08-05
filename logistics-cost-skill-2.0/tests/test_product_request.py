"""商品请求与尺寸事实测试 — 字段映射、优先级、scope语义、集成验证。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from logistics_cost.product_request import create_product_request

PROJECT = Path(__file__).resolve().parent.parent
EXAMPLES = PROJECT / "examples"


# ---- 重量 ----

class TestWeight:
    def test_user_overrides_ai(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.3, "ai_inferred", unit="kg")
        req.add_fact("net_weight", 0.5, "user_confirmed", unit="kg")
        assert req.get_resolved_net_weight()["value_kg"] == 0.5

    def test_ai_cannot_override_user(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.5, "user_confirmed", unit="kg")
        assert not req.add_fact("net_weight", 0.3, "ai_inferred", unit="kg")
        assert req.get_resolved_net_weight()["value_kg"] == 0.5

    def test_g_to_kg(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 700, "merchant_text", unit="g")
        assert abs(req.get_resolved_net_weight()["value_kg"] - 0.7) < 0.001

    def test_ai_is_not_merchant(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.16, "ai_inferred", unit="kg")
        assert not any(f.source == "merchant_text" for f in req.facts)

    def test_cmdline_weight_priority(self):
        with open(EXAMPLES / "socks_ai.json", encoding="utf-8") as f:
            ai = json.load(f)
        envelope = {
            "mode": "head_only",
            "product_display": {"title": "T", "quantity": 1, "unit": "件",
                                "normal_packaging": "袋装", "conservative_packaging": "袋装", "confidence": "low"},
            "facts": [{"field": "net_weight", "value": 50, "unit": "g", "source": "user_confirmed"}],
            "ai": ai,
        }
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown",
             "--weight-value", "200", "--weight-unit", "g", "--weight-trust", "可信"],
            cwd=str(PROJECT), input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr={r.stderr}"
        assert "250" in r.stdout, f"Expected 250g from cmdline 200g+increment: {r.stdout[:300]}"


# ---- 尺寸 scope 语义 ----

class TestScopeMapping:
    def test_shipping_to_shipping(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("shipping_package_size", [20, 15, 3], "user_confirmed", unit="cm", scope="shipping_package_size")
        d = req.get_resolved_dimensions()
        assert d["scope"] == "shipping_package_size"

    def test_product_to_product(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("product_size", [25, 18, 8], "merchant_text", unit="cm", scope="product_size")
        d = req.get_resolved_dimensions()
        assert d["scope"] == "product_size"

    def test_display_to_display(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("display_size", [30, 25, 12], "merchant_text", unit="cm", scope="display_size")
        d = req.get_resolved_dimensions()
        assert d["scope"] == "display_size"

    def test_unknown_not_product_size(self):
        """dimension_scope=unknown → field=unknown_size, scope=unknown, 不进高优先级覆盖。"""
        req = create_product_request("T", "S", 1)
        req.add_fact("unknown_size", [22, 18, 8], "ai_inferred", unit="cm", scope="unknown")
        f = req.get_fact("unknown_size")
        assert f is not None
        assert f.scope == "unknown"
        assert f.source == "ai_inferred"
        # 不进入 get_resolved_dimensions 高优先级路径
        d = req.get_resolved_dimensions()
        assert d["dims_cm"] is None  # unknown scope 不被 pickup


# ---- 端到端尺寸 ----

class TestDimensionE2E:
    def test_shipping_package_normal_and_conservative(self):
        """shipping_package_size 正常档和保守档都保持事实值。"""
        envelope = {
            "mode": "head_only",
            "product_display": {"title": "T", "quantity": 1, "unit": "件",
                                "normal_packaging": "已确认", "conservative_packaging": "已确认", "confidence": "high"},
            "facts": [
                {"field": "shipping_package_size", "value": [15, 10, 3], "unit": "cm",
                 "scope": "shipping_package_size", "source": "user_confirmed", "confidence": "high"},
                {"field": "net_weight", "value": 0.15, "unit": "kg", "source": "user_confirmed"},
            ],
            "ai": {"product_type": "test", "ai_net_weight_kg": 0.15,
                   "ai_package_size_cm": [20, 15, 8], "ai_package_weight_kg": 0.17,
                   "conservative_package_size_cm": [21, 16, 9], "conservative_package_weight_kg": 0.2,
                   "confidence": "low"},
        }
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin"],
            cwd=str(PROJECT), input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr={r.stderr}"
        result = json.loads(r.stdout)
        n = result["normal"]
        c = result["conservative"]
        assert n["packaged_size_cm"] == [15, 10, 3], f"Normal dims={n['packaged_size_cm']}"
        assert c["packaged_size_cm"] == [15, 10, 3], f"Conservative dims={c['packaged_size_cm']}"

    def test_product_size_replaces_ai_dims(self):
        """高优先级 product_size 替换 AI 尺寸。"""
        envelope = {
            "mode": "head_only",
            "product_display": {"title": "T", "quantity": 1, "unit": "件",
                                "normal_packaging": "袋装", "conservative_packaging": "袋装", "confidence": "medium"},
            "facts": [
                {"field": "product_size", "value": [20, 15, 5], "unit": "cm",
                 "scope": "product_size", "source": "merchant_text", "confidence": "high"},
                {"field": "net_weight", "value": 0.3, "unit": "kg", "source": "merchant_text"},
            ],
            "ai": {"product_type": "test",
                   "ai_net_weight_kg": 0.3, "ai_package_size_cm": [30, 25, 10],
                   "ai_package_weight_kg": 0.35, "conservative_package_size_cm": [31, 26, 11],
                   "conservative_package_weight_kg": 0.4, "confidence": "low"},
        }
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown"],
            cwd=str(PROJECT), input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr={r.stderr}"
        assert "20×" in r.stdout, f"Product size 20 not adopted: {r.stdout[:300]}"

    def test_display_size_enters_arbitration(self):
        """高优先级 display_size 进入仲裁输入。"""
        envelope = {
            "mode": "head_only",
            "product_display": {"title": "T", "quantity": 1, "unit": "件",
                                "normal_packaging": "袋装", "conservative_packaging": "袋装", "confidence": "medium"},
            "facts": [
                {"field": "display_size", "value": [25, 20, 8], "unit": "cm",
                 "scope": "display_size", "source": "merchant_text", "confidence": "high"},
                {"field": "net_weight", "value": 0.3, "unit": "kg", "source": "merchant_text"},
            ],
            "ai": {"product_type": "test",
                   "ai_net_weight_kg": 0.3, "ai_package_size_cm": [35, 30, 12],
                   "ai_package_weight_kg": 0.35, "conservative_package_size_cm": [36, 31, 13],
                   "conservative_package_weight_kg": 0.4, "confidence": "low"},
        }
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown"],
            cwd=str(PROJECT), input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr={r.stderr}"
        # display_size 25×20×8 被采用，不是 AI 的 35×30×12
        assert "25×" in r.stdout, f"Display size 25 not adopted: {r.stdout[:300]}"
