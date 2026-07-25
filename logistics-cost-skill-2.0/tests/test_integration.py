"""simple-v2.1 集成测试 — AI JSON → estimator → dual freight forwarder + thin entry point。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import pytest

from logistics_cost.ai_schema import validate, to_estimate_inputs, estimate_from_ai_json, AiProductJson
from logistics_cost.estimator import estimate
from logistics_cost.weight_rules import UserWeight
from logistics_cost.calculator import calc_freight_costs


def _load(path: str) -> AiProductJson:
    with open(path, encoding="utf-8") as f:
        return validate(json.load(f))


# === Freight forwarder dual calculation ===

def test_freight_01kg():
    """0.1kg: 深圳=18, 义乌=16 → 推荐义乌。"""
    freight = calc_freight_costs(0.1)
    assert freight["provider_costs"]["深圳货代"]["total_cost_rmb"] == 18.0
    assert freight["provider_costs"]["义乌货代"]["total_cost_rmb"] == 16.0
    assert freight["recommended_provider"] == "义乌货代"
    assert freight["recommended_cost_rmb"] == 16.0


def test_freight_03kg():
    """0.3kg: 深圳=34, 义乌=36 → 推荐深圳。"""
    freight = calc_freight_costs(0.3)
    assert freight["provider_costs"]["深圳货代"]["total_cost_rmb"] == 34.0
    assert freight["provider_costs"]["义乌货代"]["total_cost_rmb"] == 36.0
    assert freight["recommended_provider"] == "深圳货代"
    assert freight["recommended_cost_rmb"] == 34.0


def test_freight_service_fee_included():
    """固定服务费不遗漏。"""
    freight = calc_freight_costs(0.0)
    assert freight["provider_costs"]["深圳货代"]["total_cost_rmb"] == 10.0  # 0 + 10
    assert freight["provider_costs"]["义乌货代"]["total_cost_rmb"] == 6.0   # 0 + 6


# === Both normal and conservative return dual provider costs ===

def test_both_modes_have_provider_costs():
    ai = _load("examples/socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc)
    assert r["status"] == "calculated"
    for mode in ("normal", "conservative"):
        pc = r[mode]["provider_costs"]
        assert "深圳货代" in pc
        assert "义乌货代" in pc
        assert r[mode]["recommended_provider"] in ("深圳货代", "义乌货代")
        assert r[mode]["recommended_cost_rmb"] > 0


# === Category does not affect rate ===

def test_category_does_not_affect_rate():
    ai_bag = validate({
        "product_type": "test_bag", "quantity": 1, "quantity_source": "assumed",
        "category": "bag", "rigidity": "soft",
        "ai_net_weight_kg": 0.1, "ai_package_size_cm": [10, 10, 10],
        "ai_package_weight_kg": 0.11,
        "conservative_package_size_cm": [12, 12, 12],
        "conservative_package_weight_kg": 0.15,
        "confidence": "medium", "reasoning": "test"
    })
    ai_gen = validate({
        "product_type": "test_gen", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft",
        "ai_net_weight_kg": 0.1, "ai_package_size_cm": [10, 10, 10],
        "ai_package_weight_kg": 0.11,
        "conservative_package_size_cm": [12, 12, 12],
        "conservative_package_weight_kg": 0.15,
        "confidence": "medium", "reasoning": "test"
    })
    s1, e1, sc1, _ = to_estimate_inputs(ai_bag)
    s2, e2, sc2, _ = to_estimate_inputs(ai_gen)
    r1 = estimate(product_summary=s1, raw_evidence=e1, packaging_scenarios=sc1)
    r2 = estimate(product_summary=s2, raw_evidence=e2, packaging_scenarios=sc2)
    # Same weight/dims → same cost regardless of category
    assert r1["normal"]["recommended_cost_rmb"] == r2["normal"]["recommended_cost_rmb"]


# === No old categories fallback ===

def test_no_categories_fallback():
    """categories[general][head_price_per_kg] 不再影响结果。"""
    from logistics_cost import calculator
    freight = calculator.calc_freight_costs(0.1)
    # Must come from FREIGHT_FORWARDERS, not config[categories]
    assert freight["provider_costs"]["深圳货代"]["rate_per_kg_rmb"] == 80
    assert freight["provider_costs"]["义乌货代"]["rate_per_kg_rmb"] == 100


# === estimate_from_ai_json thin entry ===

def test_estimate_from_ai_json():
    with open("examples/socks_ai.json", encoding="utf-8") as f:
        ai_data = json.load(f)
    result = estimate_from_ai_json(ai_data)
    assert result["status"] == "calculated"
    assert result["normal"]["recommended_provider"] in ("深圳货代", "义乌货代")
    assert "ai_meta" in result

def test_estimate_from_ai_json_with_weight():
    with open("examples/socks_ai.json", encoding="utf-8") as f:
        ai_data = json.load(f)
    result = estimate_from_ai_json(ai_data, user_weight=65, user_weight_unit="g")
    assert result["status"] == "calculated"
    # +0.05kg: (0.065+0.05)=0.115 → 0.115*80+10=19.2 / 0.115*100+6=17.5
    assert result["normal"]["recommended_provider"] == "义乌货代"


# === Existing tests — must still pass ===

def test_socks_no_user_weight():
    ai = _load("examples/socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc)
    assert r["status"] == "calculated"
    # 0.09kg chargeable → 义乌 cheaper: 0.09*100+6=15.0
    assert r["normal"]["recommended_cost_rmb"] == 15.0


def test_socks_trusted_weight():
    ai = _load("examples/socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(65, "g", "可信"))
    assert r["status"] == "calculated"
    # 0.065+0.05=0.115 → 义乌: 0.115*100+6=17.5
    assert r["normal"]["recommended_cost_rmb"] == 17.5
    assert r["normal"]["v21_added_005"] is True


def test_socks_untrusted_weight():
    ai = _load("examples/socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(65, "g", "约值"))
    assert r["status"] == "calculated"
    # fallback to AI weight: 0.09 → 义乌: 0.09*100+6=15.0
    assert r["normal"]["recommended_cost_rmb"] == 15.0


def test_soft_goods_ice_sleeves():
    ai = validate({
        "product_type": "uv_arm_sleeves", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft", "foldability": "good", "compressibility": "good",
        "ai_net_weight_kg": 0.06,
        "ai_package_size_cm": [18, 14, 42],
        "ai_package_weight_kg": 0.07,
        "conservative_package_size_cm": [24, 19, 42],
        "conservative_package_weight_kg": 0.12,
        "confidence": "medium", "reasoning": "冰袖"
    })
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc)
    assert r["status"] == "calculated"
    assert r["normal"]["soft_volume_ignored"] is True


def test_link_no_network():
    import socket
    from unittest.mock import patch
    ai = _load("examples/socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    with patch.object(socket, "socket", side_effect=AssertionError("Network")):
        r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                    product_link="https://detail.1688.com/offer/123.html")
    assert r["product_link"] == "https://detail.1688.com/offer/123.html"


def test_calculator():
    from logistics_cost.calculator import calc_chargeable_weight, calc_volume_weight
    from logistics_cost.config import load_config
    config = load_config()
    assert round(calc_volume_weight(15, 10, 4, config), 4) == 0.075
    assert calc_chargeable_weight(0.08, 0.075) == 0.08


def test_validate_missing_product_type():
    with pytest.raises(ValueError):
        validate({})


def test_validate_defaults():
    ai = validate({"product_type": "test", "ai_net_weight_kg": 0.1,
                   "ai_package_size_cm": [10, 8, 3], "ai_package_weight_kg": 0.11,
                   "conservative_package_size_cm": [12, 10, 4], "conservative_package_weight_kg": 0.15,
                   "confidence": "medium", "reasoning": "t"})
    assert ai.category == "general"


# === End-to-end via run.py ===

def test_e2e_socks():
    import subprocess
    r = subprocess.run(["python", "run.py", "--ai-json", "examples/socks_ai.json"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["status"] == "calculated"
    assert "provider_costs" in data["normal"]
    assert "recommended_provider" in data["normal"]
