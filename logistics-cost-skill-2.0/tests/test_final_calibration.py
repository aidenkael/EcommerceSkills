from __future__ import annotations

import json

from logistics_cost.ai_schema import estimate_from_ai_json, to_estimate_inputs, validate
from logistics_cost.calculator import calc_freight_costs, calc_volume_weight
from logistics_cost.estimator import estimate


def _ai(**overrides):
    data = {
        "product_type": "generic_soft_item",
        "quantity": 1,
        "quantity_source": "user_confirmed",
        "category": "general",
        "material": "soft_fabric",
        "rigidity": "soft",
        "foldability": "good",
        "compressibility": "good",
        "has_rigid_parts": False,
        "requires_shape_retention": False,
        "packaging_state": "strong_compression",
        "has_hard_bottom": False,
        "has_hard_backboard": False,
        "has_frame": False,
        "has_rigid_insert": False,
        "retail_box_visible": False,
        "hard_card_visible": False,
        "protrusion_flattenable": False,
        "proposal_source": "local_fallback",
        "ai_net_weight_kg": 0.2,
        "ai_package_size_cm": [30, 20, 10],
        "ai_package_weight_kg": 0.25,
        "conservative_package_size_cm": [32, 22, 12],
        "conservative_package_weight_kg": 0.3,
        "packaging_method": "OPP袋",
        "folding_action": "折叠",
        "compression_action": "压缩",
        "confidence": "high",
        "reasoning": "structured test fixture",
    }
    data.update(overrides)
    return data


def test_shipping_package_size_is_preserved_and_not_soft_ignored():
    data = _ai(
        dimension_scope="shipping_package_size",
        ai_package_size_cm=[20, 10, 4],
        conservative_package_size_cm=[20, 10, 4],
        ai_net_weight_kg=0.08,
        ai_package_weight_kg=0.1,
        conservative_package_weight_kg=0.1,
    )
    result = estimate_from_ai_json(data)
    assert result["status"] == "calculated"
    assert result["accepted_evidence"]["dimensions"]["interpreted_as"] == "packaged_size"
    assert result["normal"]["packaged_size_cm"] == [20.0, 10.0, 4.0]
    assert result["normal"]["soft_volume_ignored"] is False


def test_display_size_is_not_packaged_size():
    result = estimate_from_ai_json(_ai(dimension_scope="display_size"))
    assert result["accepted_evidence"]["dimensions"]["interpreted_as"] == "product_body_size"
    assert result["accepted_evidence"]["dimensions"]["dimension_scope"] == "display_size"


def test_packaged_weight_and_net_weight_take_different_paths():
    packaged = estimate_from_ai_json(_ai(weight_scope="packaged_weight"))
    net = estimate_from_ai_json(_ai(weight_scope="net_weight"))
    assert packaged["accepted_evidence"]["weight"]["interpreted_as"] == "gross_weight"
    assert packaged["accepted_evidence"]["weight"]["value_kg"] == 0.25
    assert net["accepted_evidence"]["weight"]["interpreted_as"] == "net_weight"
    assert net["accepted_evidence"]["weight"]["value_kg"] == 0.2


def test_embedded_user_weight_is_not_silently_dropped():
    result = estimate_from_ai_json(
        _ai(user_weight_kg=0.4, user_weight_trust="可信", weight_scope="net_weight")
    )
    assert result["ai_meta"]["embedded_user_weight_mapped"] is True
    assert result["normal"]["v21_user_weight_kg"] == 0.4
    assert result["normal"]["v21_added_005"] is True


def test_unknown_hard_structure_does_not_enable_full_flat_fold():
    data = _ai(packaging_state="full_flat_fold")
    for field in (
        "has_hard_bottom", "has_hard_backboard", "has_frame",
        "has_rigid_insert", "retail_box_visible",
    ):
        data.pop(field)
    result = estimate_from_ai_json(data)
    calibration = result["packaging_calibration"]
    assert calibration["applied_rules"] == []
    assert calibration["conflicts"]
    assert result["needs_review"] is True


def test_missing_defaults_are_exposed_and_lower_confidence():
    ai = validate({"product_type": "legacy_minimal"})
    assert "ai_net_weight_kg" in ai.default_fields_used
    assert "ai_package_size_cm" in ai.default_fields_used
    assert ai.needs_review is True
    assert ai.confidence == "low"
    result = estimate_from_ai_json({"product_type": "legacy_minimal"})
    assert result["needs_review"] is True
    assert result["ai_meta"]["default_fields_used"]


def test_broken_calibration_profile_falls_back_safely(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{broken", encoding="utf-8")
    ai = validate(_ai())
    summary, evidence, scenarios, _ = to_estimate_inputs(ai)
    result = estimate(
        product_summary=summary,
        raw_evidence=evidence,
        packaging_scenarios=scenarios,
        calibration_profile_path=broken,
    )
    assert result["status"] == "calculated"
    assert result["normal"]["packaged_size_cm"] == [30.0, 20.0, 10.0]
    assert any("配置加载失败" in reason for reason in result["review_reasons"])


def test_old_ai_json_still_parses_and_calculates():
    result = estimate_from_ai_json({
        "product_type": "old_soft_item",
        "ai_net_weight_kg": 0.1,
        "ai_package_size_cm": [15, 10, 4],
        "ai_package_weight_kg": 0.12,
        "conservative_package_size_cm": [18, 12, 5],
        "conservative_package_weight_kg": 0.15,
        "confidence": "medium",
    })
    assert result["status"] == "calculated"
    assert result["ai_meta"]["packaging_state"] == "unknown"


def test_external_ai_conflict_preserves_original_candidate():
    data = _ai(proposal_source="external_ai")
    result = estimate_from_ai_json(data)
    calibration = result["packaging_calibration"]
    assert result["normal"]["packaged_size_cm"] == [30.0, 20.0, 10.0]
    assert calibration["original_scenarios"] == calibration["adjusted_scenarios"]
    assert calibration["conflicts"]
    assert result["needs_review"] is True


def test_deterministic_freight_formula_and_both_forwarders_unchanged():
    assert calc_volume_weight(20, 10, 4) == 0.1
    costs = calc_freight_costs(0.1)
    assert costs["provider_costs"]["深圳货代"]["head_freight_rmb"] == 8.0
    assert costs["provider_costs"]["深圳货代"]["fixed_service_fee_rmb"] == 10
    assert costs["provider_costs"]["义乌货代"]["head_freight_rmb"] == 10.0
    assert costs["provider_costs"]["义乌货代"]["fixed_service_fee_rmb"] == 6
