"""simple-v2.1 集成测试 — AI JSON → estimator → dual freight forwarder + thin entry point。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
EXAMPLES = PROJECT / "examples"
sys.path.insert(0, str(PROJECT))

import pytest

from logistics_cost.ai_schema import validate, to_estimate_inputs, estimate_from_ai_json, AiProductJson
from logistics_cost.estimator import estimate
from logistics_cost.weight_rules import UserWeight
from logistics_cost.calculator import calc_freight_costs


def _load(path: str) -> AiProductJson:
    with open(EXAMPLES / path, encoding="utf-8") as f:
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
    assert freight["provider_costs"]["深圳货代"]["total_cost_rmb"] == 13.0  # min_head(3) + 10
    assert freight["provider_costs"]["义乌货代"]["total_cost_rmb"] == 9.0   # min_head(3) + 6


# === Both normal and conservative return dual provider costs ===

def test_both_modes_have_provider_costs():
    ai = _load("socks_ai.json")
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
    with open(EXAMPLES / "socks_ai.json", encoding="utf-8") as f:
        ai_data = json.load(f)
    result = estimate_from_ai_json(ai_data)
    assert result["status"] == "calculated"
    assert result["normal"]["recommended_provider"] in ("深圳货代", "义乌货代")
    assert "ai_meta" in result

def test_estimate_from_ai_json_with_weight():
    with open(EXAMPLES / "socks_ai.json", encoding="utf-8") as f:
        ai_data = json.load(f)
    result = estimate_from_ai_json(ai_data, user_weight=65, user_weight_unit="g")
    assert result["status"] == "calculated"
    # +0.05kg: (0.065+0.05)=0.115 → 0.115*80+10=19.2 / 0.115*100+6=17.5
    assert result["normal"]["recommended_provider"] == "义乌货代"


# === Existing tests — must still pass ===

def test_socks_no_user_weight():
    ai = _load("socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc)
    assert r["status"] == "calculated"
    # 0.09kg chargeable → 义乌 cheaper: 0.09*100+6=15.0
    assert r["normal"]["recommended_cost_rmb"] == 15.0


def test_socks_trusted_weight():
    ai = _load("socks_ai.json")
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(65, "g", "可信"))
    assert r["status"] == "calculated"
    # 0.065+0.05=0.115 → 义乌: 0.115*100+6=17.5
    assert r["normal"]["recommended_cost_rmb"] == 17.5
    assert r["normal"]["v21_added_005"] is True


def test_socks_untrusted_weight():
    ai = _load("socks_ai.json")
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
    ai = _load("socks_ai.json")
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
    r = subprocess.run(
        [sys.executable, str(PROJECT / "run.py"), "--ai-json", str(EXAMPLES / "socks_ai.json")],
        cwd=str(PROJECT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    data = json.loads(r.stdout)
    assert data["status"] == "calculated"
    assert "provider_costs" in data["normal"]
    assert "recommended_provider" in data["normal"]


# ============================================================
# Round 01 calibration tests — ultra-light weight rule + AI fields
# ============================================================

# -- Test 1: trusted ultra-light 15g/36g/50g no longer adds +50g --

def test_trusted_ultra_light_15g_no_increment():
    """15g可信: 不再+50g, 取max(0.015, ai_chargeable, vol_weight)。"""
    ai = validate({
        "product_type": "test", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft",
        "ai_net_weight_kg": 0.015, "ai_package_size_cm": [5, 5, 2],
        "ai_package_weight_kg": 0.02,
        "conservative_package_size_cm": [7, 7, 3],
        "conservative_package_weight_kg": 0.03,
        "confidence": "medium", "reasoning": "test",
    })
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(15, "g", "可信"))
    assert r["status"] == "calculated"
    w = r["normal"]
    assert w["v21_added_005"] is False, f"15g should NOT add +50g, got {w}"
    # chargeable = max(0.015, ai_chargeable(0.02 with no volume dominance), vol)
    assert "不加增重" in w["v21_weight_source"]


def test_trusted_ultra_light_36g_no_increment():
    """36g可信: ≤50g, 不加增重。"""
    ai = validate({
        "product_type": "test", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft",
        "ai_net_weight_kg": 0.036, "ai_package_size_cm": [8, 6, 3],
        "ai_package_weight_kg": 0.04,
        "conservative_package_size_cm": [10, 8, 4],
        "conservative_package_weight_kg": 0.06,
        "confidence": "medium", "reasoning": "test",
    })
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(36, "g", "可信"))
    assert r["status"] == "calculated"
    assert r["normal"]["v21_added_005"] is False, f"36g <= 50g should NOT add +50g"


def test_trusted_ultra_light_50g_boundary():
    """50g可信: 边界值, 仍不加增重(≤50g)。"""
    ai = validate({
        "product_type": "test", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft",
        "ai_net_weight_kg": 0.05, "ai_package_size_cm": [10, 8, 4],
        "ai_package_weight_kg": 0.06,
        "conservative_package_size_cm": [12, 10, 5],
        "conservative_package_weight_kg": 0.09,
        "confidence": "medium", "reasoning": "test",
    })
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(50, "g", "可信"))
    assert r["status"] == "calculated"
    assert r["normal"]["v21_added_005"] is False, f"50g boundary: should NOT add increment"


# -- Test 2: ultra-light uses max(user, ai, volume) --

def test_ultra_light_max_of_three():
    """超轻品: chargeable = max(用户净重, AI包装计费重, 体积重)。"""
    # user=20g, ai_package_weight=0.05, vol from [10,8,4]=320/8000=0.04
    # max(0.02, 0.05, 0.04) = 0.05 → user weight is NOT dominant, AI is
    ai = validate({
        "product_type": "test", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft", "foldability": "good", "compressibility": "good",
        "ai_net_weight_kg": 0.02, "ai_package_size_cm": [10, 8, 4],
        "ai_package_weight_kg": 0.05,
        "conservative_package_size_cm": [12, 10, 5],
        "conservative_package_weight_kg": 0.07,
        "confidence": "medium", "reasoning": "test",
    })
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(20, "g", "可信"))
    assert r["status"] == "calculated"
    v21 = r["normal"]["v21_weight_source"]
    assert "不加增重" in v21, f"20g <= 50g should not add increment: {v21}"
    # chargeable should be >= 0.04 (at least volume weight)
    assert r["normal"]["chargeable_weight_kg"] >= 0.04, f"chargeable too low: {r['normal']}"


# -- Test 3: trusted > 50g still adds +50g --

def test_trusted_over_50g_adds_increment():
    """51g可信: >50g, 维持原有+50g规则。"""
    ai = validate({
        "product_type": "test", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft",
        "ai_net_weight_kg": 0.051, "ai_package_size_cm": [10, 8, 4],
        "ai_package_weight_kg": 0.06,
        "conservative_package_size_cm": [12, 10, 5],
        "conservative_package_weight_kg": 0.09,
        "confidence": "medium", "reasoning": "test",
    })
    s, e, sc, _ = to_estimate_inputs(ai)
    r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                 user_weight=UserWeight(51, "g", "可信"))
    assert r["status"] == "calculated"
    assert r["normal"]["v21_added_005"] is True, f"51g > 50g should add +50g"


# -- Test 4: untrusted weight unchanged --

def test_untrusted_weight_unchanged():
    """约值/未核实: 仍然回退AI估重 + 标记需复核。"""
    ai = validate({
        "product_type": "test", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft",
        "ai_net_weight_kg": 0.04, "ai_package_size_cm": [8, 6, 3],
        "ai_package_weight_kg": 0.05,
        "conservative_package_size_cm": [10, 8, 4],
        "conservative_package_weight_kg": 0.07,
        "confidence": "medium", "reasoning": "test",
    })
    s, e, sc, _ = to_estimate_inputs(ai)
    for status in ("约值", "未核实", "参考", "低置信"):
        r = estimate(product_summary=s, raw_evidence=e, packaging_scenarios=sc,
                     user_weight=UserWeight(80, "g", status))
        assert r["normal"]["v21_needs_review"] is True, f"{status}: should need review"


# -- Test 5: min_head_charge_rmb=3 still effective --

def test_min_head_charge_effective():
    """≤30g 单品头程最低3元。"""
    freight = calc_freight_costs(0.025)
    assert freight["provider_costs"]["义乌货代"]["head_freight_rmb"] == 3.0
    assert freight["provider_costs"]["深圳货代"]["head_freight_rmb"] == 3.0


# -- Test 6: new AI fields validate, default, and pass through --

def test_new_ai_fields_validate_and_pass():
    """packaging_type/weight_scope/dimension_scope 校验、默认值、传递。"""
    ai = validate({
        "product_type": "test", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft",
        "ai_net_weight_kg": 0.1, "ai_package_size_cm": [10, 8, 4],
        "ai_package_weight_kg": 0.11,
        "conservative_package_size_cm": [12, 10, 5],
        "conservative_package_weight_kg": 0.15,
        "confidence": "medium", "reasoning": "test",
        "packaging_type": "retail_card",
        "weight_scope": "net_weight",
        "dimension_scope": "display_size",
    })
    assert ai.packaging_type == "retail_card"
    assert ai.weight_scope == "net_weight"
    assert ai.dimension_scope == "display_size"
    _, _, _, ai_meta = to_estimate_inputs(ai)
    assert ai_meta["packaging_type"] == "retail_card"
    assert ai_meta["weight_scope"] == "net_weight"
    assert ai_meta["dimension_scope"] == "display_size"


def test_new_ai_fields_default_unknown():
    """缺失新字段时默认 unknown。"""
    ai = validate({
        "product_type": "test", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft",
        "ai_net_weight_kg": 0.1, "ai_package_size_cm": [10, 8, 4],
        "ai_package_weight_kg": 0.11,
        "conservative_package_size_cm": [12, 10, 5],
        "conservative_package_weight_kg": 0.15,
        "confidence": "medium", "reasoning": "test",
    })
    assert ai.packaging_type == "unknown"
    assert ai.weight_scope == "unknown"
    assert ai.dimension_scope == "unknown"


def test_new_ai_fields_invalid_fallback():
    """非法值自动回退 unknown。"""
    ai = validate({
        "product_type": "test", "quantity": 1, "quantity_source": "assumed",
        "category": "general", "rigidity": "soft",
        "ai_net_weight_kg": 0.1, "ai_package_size_cm": [10, 8, 4],
        "ai_package_weight_kg": 0.11,
        "conservative_package_size_cm": [12, 10, 5],
        "conservative_package_weight_kg": 0.15,
        "confidence": "medium", "reasoning": "test",
        "packaging_type": "cardboard_box",  # invalid
        "weight_scope": "gross_weight",     # invalid
        "dimension_scope": "outer_size",    # invalid
    })
    assert ai.packaging_type == "unknown"
    assert ai.weight_scope == "unknown"
    assert ai.dimension_scope == "unknown"


# -- Test 7: old AI JSON without new fields still works --

def test_old_ai_json_compat():
    """旧 AI JSON 不含新字段时仍能运行 (socks_ai.json 不含 packaging_type 等)。"""
    with open(EXAMPLES / "socks_ai.json", encoding="utf-8") as f:
        ai_data = json.load(f)
    # Ensure old AI JSON doesn't have new fields
    assert "packaging_type" not in ai_data
    result = estimate_from_ai_json(ai_data)
    assert result["status"] == "calculated"
    assert result["ai_meta"]["packaging_type"] == "unknown"
    assert result["ai_meta"]["weight_scope"] == "unknown"
    assert result["ai_meta"]["dimension_scope"] == "unknown"


# -- Test 8: original file unchanged --

def test_original_file_unchanged():
    """原始 calibration_samples.json 至少包含 CAL-001。"""
    cal_path = PROJECT / "archive" / "calibration" / "calibration_samples.json"
    assert cal_path.exists(), "Original file must exist"
    with open(cal_path, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) >= 29
    ids = [d["sample_id"] for d in data]
    assert "CAL-001" in ids
    assert "CAL-029" in ids


# -- Test 9: cleaned file integrity --

def test_cleaned_file_integrity():
    """清洗文件 29 条, CAL-001~CAL-029, 无重复, 含新字段。"""
    cleaned_path = PROJECT / "archive" / "calibration" / "calibration_samples_cleaned_v1.json"
    assert cleaned_path.exists(), "Cleaned file must exist"
    with open(cleaned_path, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 29
    ids = [d["sample_id"] for d in data]
    assert ids[0] == "CAL-001"
    assert ids[-1] == "CAL-029"
    assert len(ids) == len(set(ids)), "No duplicates"
    for d in data:
        assert "data_quality_status" in d
        assert "data_quality_issues" in d
        assert "exclude_from_numeric_calibration" in d
        assert "evidence_level" in d


# -- Test 10: excluded samples --

def test_excluded_samples():
    """CAL-009, CAL-026, CAL-029 不进入精确数值校准。"""
    cleaned_path = PROJECT / "archive" / "calibration" / "calibration_samples_cleaned_v1.json"
    with open(cleaned_path, encoding="utf-8") as f:
        data = json.load(f)
    by_id = {d["sample_id"]: d for d in data}
    for sid in ("CAL-009", "CAL-026", "CAL-029"):
        assert by_id[sid]["exclude_from_numeric_calibration"] is True, f"{sid} should be excluded"
