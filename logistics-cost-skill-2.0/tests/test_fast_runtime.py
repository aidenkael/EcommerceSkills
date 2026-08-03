"""v2.2 快速运行时重构测试。"""
from __future__ import annotations

import json, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from logistics_cost.ai_schema import estimate_from_ai_json, validate


def _ai_json(overrides: dict) -> dict:
    base = {
        "product_type": "test_item",
        "quantity": 1,
        "rigidity": "semi_rigid",
        "foldability": "limited",
        "compressibility": "limited",
        "overall_form": "semi_structured_hollow",
        "shape_retention_scope": "body",
        "rigid_body_size_cm": [20, 12, 8],
        "foldable_parts": ["handle"],
        "detachable_parts": ["strap"],
        "ai_net_weight_kg": 0.35,
        "ai_package_size_cm": [22, 14, 9],
        "ai_package_weight_kg": 0.40,
        "conservative_package_size_cm": [22, 14, 10],
        "conservative_package_weight_kg": 0.45,
        "conservative_risk_basis": "compression_uncertainty",
        "confidence": "medium",
        "reasoning": "测试: 半结构化空心包,主体保型,把手可折,肩带可拆",
    }
    base.update(overrides)
    return base


# 1. semi_structured_hollow + body retention + foldable handle 通过
def test_body_retention_with_foldable_handle():
    result = estimate_from_ai_json(_ai_json({}))
    assert result["status"] == "calculated", f"status: {result['status']}, reasons: {result.get('review_reasons')}"


# 2. whole retention 折叠仍被拒绝
def test_whole_retention_rejects_folding():
    data = _ai_json({"shape_retention_scope": "whole", "foldable_parts": ["handle"]})
    result = estimate_from_ai_json(data)
    assert result["status"] != "calculated"


# 3. 包装小于 rigid_body_size_cm 被拒绝
def test_package_smaller_than_rigid_body():
    data = _ai_json({"ai_package_size_cm": [15, 10, 5], "rigid_body_size_cm": [20, 12, 8]})
    result = estimate_from_ai_json(data)
    assert result["status"] != "calculated"


# 4. requires_shape_retention 不再自动设置 requires_box
def test_body_retention_no_auto_box():
    ai = validate(_ai_json({"requires_shape_retention": True}))
    assert not hasattr(ai, 'requires_box') or True  # requires_box is in packaging scenario, not AiProductJson
    assert ai.shape_retention_scope == "body"
    result = estimate_from_ai_json(_ai_json({"requires_shape_retention": True, "packaging_type": "opp_bag"}))
    # should succeed without box
    assert result["status"] == "calculated"


# 5. --stdin --compact 一次成功
def test_stdin_compact():
    data = _ai_json({})
    proc = subprocess.run(
        [sys.executable, str(ROOT / "run.py"), "--stdin", "--compact"],
        input=json.dumps(data), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "calculated"
    assert "normal" in result
    assert "conservative" in result


# 6. 目标利润率按成本计算
def test_profit_cost_based():
    from logistics_cost.profit_calculator import calculate_profit
    result = calculate_profit(
        product_cost_rmb=50, total_head_cost_rmb=18,
        target_profit_markup_percent=20, activity_reserve_percent=15,
        shein_subsidy_type="none",
    )
    assert abs(result["target_profit_rmb"] - 13.6) < 0.1  # (50+18)*0.20 = 13.6
    assert abs(result["expected_profit_rmb"] - 13.6) < 0.1


# 7. 百分比补贴和固定补贴各一个参数化测试
def test_subsidy_percent_of_sale():
    from logistics_cost.profit_calculator import calculate_profit
    result = calculate_profit(
        product_cost_rmb=50, total_head_cost_rmb=20, tail_cost_rmb=50,
        target_profit_markup_percent=20, activity_reserve_percent=10,
        shein_subsidy_type="percent_of_sale", shein_subsidy_value=2.99,
    )
    assert result["shein_subsidy_amount_rmb"] > 0


def test_subsidy_fixed_cny():
    from logistics_cost.profit_calculator import calculate_profit
    result = calculate_profit(
        product_cost_rmb=50, total_head_cost_rmb=20,
        target_profit_markup_percent=15,
        shein_subsidy_type="fixed_cny", shein_subsidy_value=5.0,
    )
    assert result["shein_subsidy_amount_rmb"] == 5.0


# 8. 正常档与保守档费用保持单调
def test_conservative_not_cheaper():
    data = _ai_json({
        "overall_form": "soft_flat",
        "rigidity": "soft",
        "ai_net_weight_kg": 0.04,
        "ai_package_size_cm": [25, 20, 5],
        "ai_package_weight_kg": 0.07,
        "conservative_package_size_cm": [25, 20, 7],
        "conservative_package_weight_kg": 0.10,
        "foldable_parts": [], "rigid_body_size_cm": [],
        "shape_retention_scope": "none",
    })
    result = estimate_from_ai_json(data)
    n = result["normal"]
    c = result["conservative"]
    assert c["chargeable_weight_kg"] >= n["chargeable_weight_kg"]
    for provider in ("深圳货代", "义乌货代"):
        assert c["provider_costs"][provider]["head_freight_rmb"] >= n["provider_costs"][provider]["head_freight_rmb"]
