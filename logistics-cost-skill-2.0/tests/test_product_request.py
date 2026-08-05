"""商品请求测试 — 事实优先级、重量归一化、尺寸语义。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from logistics_cost.product_request import create_product_request, ProductRequest, Fact

PROJECT = Path(__file__).resolve().parent.parent
EXAMPLES = PROJECT / "examples"

# ---- 事实优先级 ----

class TestWeightFacts:
    def test_user_confirmed_overrides_ai(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.3, "ai_inferred", unit="kg")
        ok = req.add_fact("net_weight", 0.5, "user_confirmed", unit="kg", confidence="high")
        assert ok is True
        r = req.get_resolved_net_weight()
        assert r["value_kg"] == 0.5
        assert r["source"] == "user_confirmed"

    def test_ai_cannot_override_user(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.5, "user_confirmed", unit="kg", confidence="high")
        ok = req.add_fact("net_weight", 0.3, "ai_inferred", unit="kg")
        assert ok is False
        assert req.get_resolved_net_weight()["value_kg"] == 0.5

    def test_merchant_overrides_ai(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.3, "ai_inferred", unit="kg")
        ok = req.add_fact("net_weight", 0.7, "merchant_text", unit="kg")
        assert ok is True
        assert req.get_resolved_net_weight()["value_kg"] == 0.7

    def test_g_unit_normalized_to_kg(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 700, "merchant_text", unit="g")
        r = req.get_resolved_net_weight()
        assert abs(r["value_kg"] - 0.7) < 0.001

    def test_calibrated_overrides_ai_inferred(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.3, "ai_inferred", unit="kg")
        ok = req.add_fact("net_weight", 0.07, "calibrated", unit="kg")
        assert ok is True
        assert abs(req.get_resolved_net_weight()["value_kg"] - 0.07) < 0.001

    def test_same_rank_no_override(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.5, "user_confirmed", unit="kg")
        ok = req.add_fact("net_weight", 0.7, "user_confirmed", unit="kg")
        assert ok is False
        assert req.get_resolved_net_weight()["value_kg"] == 0.5

    def test_ai_weight_not_merchant_text(self):
        """AI候选重量默认来源为 ai_inferred，不是 merchant_text。"""
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.16, "ai_inferred", unit="kg")
        assert not any(f.source == "merchant_text" for f in req.facts if f.field == "net_weight")

    def test_cmdline_weight_priority(self):
        """命令行用户重量优先于任何事实。"""
        pass  # 由 run.py 集成测试覆盖


# ---- 尺寸事实 ----

class TestDimensionFacts:
    def test_user_shipping_package_overrides(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("product_size", [22, 18, 8], "ai_inferred", unit="cm", scope="product_size")
        ok = req.add_fact("shipping_package_size", [20, 15, 3], "user_confirmed", unit="cm", scope="shipping_package_size")
        assert ok is True
        d = req.get_resolved_dimensions()
        assert d["dims_cm"] == [20, 15, 3]
        assert d["scope"] == "shipping_package_size"
        assert d["source"] == "user_confirmed"

    def test_product_size_not_mistaken_for_shipping(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("product_size", [22, 18, 8], "merchant_text", unit="cm", scope="product_size")
        d = req.get_resolved_dimensions()
        assert d["scope"] == "product_size"  # 保持本体语义

    def test_ai_dims_are_ai_inferred(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("product_size", [22, 18, 8], "ai_inferred", unit="cm", scope="unknown")
        assert not any(f.source == "merchant_text" for f in req.facts if f.field == "product_size")


# ---- 信封事实 ----

class TestEnvelopeFacts:
    def test_import_envelope_facts(self):
        req = create_product_request("T", "S", 1)
        facts = [
            {"field": "net_weight", "value": 700, "unit": "g", "scope": "product", "source": "merchant_text", "confidence": "high"},
            {"field": "product_size", "value": [25, 15, 5], "unit": "cm", "scope": "product_size", "source": "user_confirmed", "confidence": "high"},
        ]
        req.import_envelope_facts(facts)
        w = req.get_resolved_net_weight()
        assert abs(w["value_kg"] - 0.7) < 0.001
        d = req.get_resolved_dimensions()
        assert d["dims_cm"] == [25, 15, 5]

    def test_bad_source_ignored(self):
        req = create_product_request("T", "S", 1)
        req.import_envelope_facts([{"field": "x", "value": 1, "source": "invalid"}])
        assert len(req.facts) == 0


# ---- 集成：重量实际进入 estimate ----

class TestWeightIntegration:
    def test_user_weight_enters_estimate(self):
        """用户确认重量进入可信重量入口并影响计费重。"""
        with open(EXAMPLES / "socks_ai.json", encoding="utf-8") as f:
            ai = json.load(f)
        envelope = {
            "mode": "head_only",
            "product_display": {"title": "TEST", "unit": "件", "quantity": 1,
                                "normal_packaging": "袋装", "conservative_packaging": "袋装", "confidence": "low"},
            "facts": [{"field": "net_weight", "value": 500, "unit": "g", "scope": "product", "source": "user_confirmed", "confidence": "high"}],
            "ai": ai,
        }
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown"],
            cwd=str(PROJECT), input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr={r.stderr}"
        # 用户确认500g(+50g增量=550g)应体现在输出中
        assert "550" in r.stdout, f"User weight not found in output: {r.stdout[:300]}"


class TestRequestIdentity:
    def test_basic(self):
        req = create_product_request("T", "S", 2)
        assert req.title == "T"
        assert len(req.product_signature) == 16

    def test_unique_ids(self):
        r1 = create_product_request("A", "S1", 1)
        r2 = create_product_request("B", "S2", 1)
        assert r1.request_id != r2.request_id
        assert r1.product_signature != r2.product_signature
