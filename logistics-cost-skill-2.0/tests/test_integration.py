"""simple-v2.1 集成测试 — AI JSON → estimator → head cost。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import pytest

from logistics_cost.ai_schema import validate, to_estimate_inputs, AiProductJson
from logistics_cost.estimator import estimate
from logistics_cost.weight_rules import UserWeight


def _load(path: str) -> AiProductJson:
    with open(path, encoding="utf-8") as f:
        return validate(json.load(f))


# === AI JSON → head cost ===

def test_socks_no_user_weight():
    ai = _load("examples/socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc)
    assert r["status"] == "calculated"
    assert r["normal"]["head_cost_cny"] == 9.0
    assert r["conservative"]["head_cost_cny"] == 13.5


def test_socks_trusted_weight():
    ai = _load("examples/socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(65, "g", "可信"))
    assert r["status"] == "calculated"
    assert r["normal"]["head_cost_cny"] == 11.5
    assert r["normal"]["v21_added_005"] is True


def test_socks_untrusted_weight():
    ai = _load("examples/socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(65, "g", "约值"))
    assert r["status"] == "calculated"
    assert r["normal"]["head_cost_cny"] == 9.0  # fallback
    assert r["normal"]["v21_added_005"] is False


# === Soft goods check ===

def test_soft_goods_ice_sleeves():
    ai = validate({
        "product_type": "uv_arm_sleeves", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft", "foldability": "good", "compressibility": "good",
        "ai_net_weight_kg": 0.06,
        "ai_package_size_cm": [18, 14, 42],  # 展开 42cm! should trigger soft check
        "ai_package_weight_kg": 0.07,
        "conservative_package_size_cm": [24, 19, 42],
        "conservative_package_weight_kg": 0.12,
        "confidence": "medium", "reasoning": "冰袖"
    })
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc)
    assert r["status"] == "calculated"
    assert r["normal"]["soft_volume_ignored"] is True
    assert r["normal"]["head_cost_cny"] == 7.0  # 0.07kg × 100


# === Quantity source ===

def test_quantity_source_assumed():
    ai = _load("examples/socks_ai.json")
    assert ai.quantity_source == "assumed"
    s, e, sc, meta = to_estimate_inputs(ai)
    assert meta["quantity_source"] == "assumed"


def test_quantity_source_user_confirmed():
    ai = validate({
        "product_type": "test", "quantity": 3, "quantity_source": "user_confirmed",
        "ai_net_weight_kg": 0.1, "ai_package_size_cm": [10, 8, 3], "ai_package_weight_kg": 0.11,
        "conservative_package_size_cm": [12, 10, 4], "conservative_package_weight_kg": 0.15,
        "confidence": "high", "reasoning": "test"
    })
    assert ai.quantity_source == "user_confirmed"


# === 1688 link no network ===

def test_link_no_network():
    import socket
    from unittest.mock import patch
    ai = _load("examples/socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    with patch.object(socket, "socket", side_effect=AssertionError("Network")):
        r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                    product_link="https://detail.1688.com/offer/123.html")
    assert r["product_link"] == "https://detail.1688.com/offer/123.html"


# === Calculator ===

def test_calculator():
    from logistics_cost.calculator import calc_head_cost, calc_volume_weight
    assert round(calc_volume_weight(15, 10, 4, {"volume_divisor": 8000}), 4) == 0.075
    assert calc_head_cost(0.09, "general", {"categories": {"general": {"head_price_per_kg": 100}}}) == 9.0


# === run.py CLI ===

def test_run_cli():
    import subprocess
    r = subprocess.run(
        ["python", "run.py", "--ai-json", "examples/socks_ai.json", "--weight-value", "65", "--weight-unit", "g"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "11.5" in r.stderr or "11.5" in r.stdout


# === AI schema validation ===

def test_validate_missing_product_type():
    with pytest.raises(ValueError):
        validate({})


def test_validate_defaults():
    ai = validate({"product_type": "test", "ai_net_weight_kg": 0.1,
                   "ai_package_size_cm": [10, 8, 3], "ai_package_weight_kg": 0.11,
                   "conservative_package_size_cm": [12, 10, 4], "conservative_package_weight_kg": 0.15,
                   "confidence": "medium", "reasoning": "t"})
    assert ai.category == "general"
    assert ai.quantity == 1
    assert ai.quantity_source == "assumed"


def test_validate_bad_category():
    ai = validate({"product_type": "test", "category": "invalid",
                   "ai_net_weight_kg": 0.1,
                   "ai_package_size_cm": [10, 8, 3], "ai_package_weight_kg": 0.11,
                   "conservative_package_size_cm": [12, 10, 4], "conservative_package_weight_kg": 0.15,
                   "confidence": "medium", "reasoning": "t"})
    assert ai.category == "general"  # defaulted


# === End-to-end: AI JSON → run.py ===

def test_e2e_socks():
    """完整端到端: AI JSON 文件 → run.py → 头程。"""
    import subprocess
    r = subprocess.run(
        ["python", "run.py", "--ai-json", "examples/socks_ai.json"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    stdout = r.stdout
    data = json.loads(stdout)
    assert data["status"] == "calculated"
    assert data["normal"]["head_cost_cny"] == 9.0
    assert data["conservative"]["head_cost_cny"] == 13.5
    assert data["ai_meta"]["quantity_source"] == "assumed"
