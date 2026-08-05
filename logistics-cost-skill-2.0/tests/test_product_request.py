"""商品请求与尺寸事实测试 — 字段映射、优先级、集成验证。"""
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
        req.add_fact("net_weight", 0.5, "user_confirmed", unit="kg", confidence="high")
        r = req.get_resolved_net_weight()
        assert r["value_kg"] == 0.5

    def test_ai_cannot_override_user(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.5, "user_confirmed", unit="kg")
        assert not req.add_fact("net_weight", 0.3, "ai_inferred", unit="kg")
        assert req.get_resolved_net_weight()["value_kg"] == 0.5

    def test_g_to_kg(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 700, "merchant_text", unit="g")
        assert abs(req.get_resolved_net_weight()["value_kg"] - 0.7) < 0.001

    def test_ai_source_is_not_merchant(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("net_weight", 0.16, "ai_inferred", unit="kg")
        assert not any(f.source == "merchant_text" for f in req.facts)

    def test_cmdline_weight_priority(self):
        """命令行 --weight-value 优先于任何信封事实。通过子进程验证。"""
        with open(EXAMPLES / "socks_ai.json", encoding="utf-8") as f:
            ai = json.load(f)
        envelope = {
            "mode": "head_only",
            "product_display": {"title": "T", "quantity": 1, "unit": "件",
                                "normal_packaging": "袋装", "conservative_packaging": "袋装", "confidence": "low"},
            "facts": [{"field": "net_weight", "value": 50, "unit": "g", "source": "user_confirmed"}],
            "ai": ai,
        }
        # 命令行 200g 覆盖信封 50g
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown",
             "--weight-value", "200", "--weight-unit", "g", "--weight-trust", "可信"],
            cwd=str(PROJECT), input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr={r.stderr}"
        # 200g + 50g 增量 = 250g → 检查计费重
        assert "250" in r.stdout, f"Expected 250g from cmdline 200g+increment, got: {r.stdout[:300]}"


# ---- 尺寸事实 ----

class TestDimensionFieldMapping:
    def test_shipping_scope_to_field(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("shipping_package_size", [20, 15, 3], "user_confirmed", unit="cm", scope="shipping_package_size")
        d = req.get_resolved_dimensions()
        assert d["scope"] == "shipping_package_size"
        assert d["dims_cm"] == [20, 15, 3]

    def test_product_scope_to_field(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("product_size", [25, 18, 8], "merchant_text", unit="cm", scope="product_size")
        d = req.get_resolved_dimensions()
        assert d["scope"] == "product_size"
        assert d["source"] == "merchant_text"

    def test_ai_dims_map_by_dimension_scope(self):
        """AI 候选尺寸按 dimension_scope 映射到正确 field。"""
        req = create_product_request("T", "S", 1)
        req.add_fact("shipping_package_size", [22, 15, 5], "ai_inferred", unit="cm", scope="shipping_package_size")
        f = req.get_fact("shipping_package_size")
        assert f is not None
        assert f.field == "shipping_package_size"
        assert f.scope == "shipping_package_size"

    def test_unknown_scope_maps_to_product_size(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("product_size", [22, 18, 8], "ai_inferred", unit="cm", scope="unknown")
        d = req.get_resolved_dimensions()
        assert d is not None


class TestDimensionE2E:
    def test_shipping_package_size_enters_final_output(self):
        """用户确认运输尺寸进入最终计算，正常档和保守档都保持事实值。"""
        envelope = {
            "mode": "head_only",
            "product_display": {"title": "T", "quantity": 1, "unit": "件",
                                "normal_packaging": "已确认包装", "conservative_packaging": "已确认包装", "confidence": "high"},
            "facts": [
                {"field": "shipping_package_size", "value": [15, 10, 3], "unit": "cm",
                 "scope": "shipping_package_size", "source": "user_confirmed", "confidence": "high"},
                {"field": "net_weight", "value": 0.1, "unit": "kg", "source": "user_confirmed"},
            ],
            "ai": {"product_type": "test", "ai_net_weight_kg": 0.1,
                   "ai_package_size_cm": [20, 15, 8], "ai_package_weight_kg": 0.12,
                   "conservative_package_size_cm": [21, 16, 9], "conservative_package_weight_kg": 0.14,
                   "confidence": "low"},
        }
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown"],
            cwd=str(PROJECT), input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr={r.stderr}"
        assert "15×10×3" in r.stdout, f"Shipping dims not in output: {r.stdout[:300]}"

    def test_product_size_enters_arbitration(self):
        """高优先级 product_size 进入仲裁输入 — 尺寸被采用。"""
        envelope = {
            "mode": "head_only",
            "product_display": {"title": "T", "quantity": 1, "unit": "件",
                                "normal_packaging": "袋装", "conservative_packaging": "袋装", "confidence": "medium"},
            "facts": [
                {"field": "product_size", "value": [20, 15, 5], "unit": "cm",
                 "scope": "product_size", "source": "merchant_text", "confidence": "high"},
                {"field": "net_weight", "value": 0.2, "unit": "kg", "source": "merchant_text"},
            ],
            "ai": {"product_type": "test",
                   "ai_net_weight_kg": 0.2, "ai_package_size_cm": [30, 25, 10],
                   "ai_package_weight_kg": 0.25, "conservative_package_size_cm": [31, 26, 11],
                   "conservative_package_weight_kg": 0.3, "confidence": "low"},
        }
        r = subprocess.run(
            [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown"],
            cwd=str(PROJECT), input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr={r.stderr}"
        # product_size [20,15,5] 已进入（不再用 AI 的 [30,25,10]）
        assert "20×" in r.stdout, f"Product size 20 not found: {r.stdout[:300]}"