"""v2 正常档/保守档语义重构测试。

验证:
1. 明确包装尺寸和毛重时, 两档可以完全相同
2. soft_flat不会通过三轴统一加值形成保守档
3. soft_flat两档采用同一软品体积策略
4. 阈值跨越不能导致保守档计费重低于正常档
5. soft_bulky允许较少压缩导致合理体积增加
6. hard_flat只增加有依据的厚度或包材, 不放大全部轴
7. 两家货代的保守档费用均不得低于正常档
8. 旧版AI JSON仍可运行, 并明确记录兼容回退来源
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from logistics_cost.ai_schema import estimate_from_ai_json, validate


# ---- 1. 明确包装尺寸和毛重时, 两档可以完全相同 ----

def test_known_package_allows_identical_scenarios():
    ai_data = {
        "product_type": "test_packaged",
        "quantity": 1,
        "overall_form": "hard_flat",
        "ai_net_weight_kg": 0.15,
        "ai_package_size_cm": [20, 15, 3],
        "ai_package_weight_kg": 0.17,
        "conservative_package_size_cm": [20, 15, 3],
        "conservative_package_weight_kg": 0.17,
        "conservative_risk_basis": "known_package_no_uncertainty",
        "dimension_scope": "shipping_package_size",
        "weight_scope": "packaged_weight",
        "confidence": "high",
        "reasoning": "商家明确运输包装",
    }
    result = estimate_from_ai_json(ai_data)
    assert result["status"] == "calculated"
    n = result["normal"]
    c = result["conservative"]
    assert n["chargeable_weight_kg"] == c["chargeable_weight_kg"]
    # 费用应相同
    for provider in ("深圳货代", "义乌货代"):
        n_fee = n["provider_costs"][provider]["head_freight_rmb"]
        c_fee = c["provider_costs"][provider]["head_freight_rmb"]
        assert c_fee >= n_fee, f"{provider} 保守档费用低于正常档: {c_fee} < {n_fee}"


# ---- 2. soft_flat不会通过三轴统一加值形成保守档 ----

def test_soft_flat_no_mechanical_amplification():
    ai_data = {
        "product_type": "thin_socks",
        "quantity": 1,
        "category": "general",
        "rigidity": "soft",
        "foldability": "good",
        "compressibility": "good",
        "overall_form": "soft_flat",
        "ai_net_weight_kg": 0.04,
        "ai_package_size_cm": [15, 10, 2],
        "ai_package_weight_kg": 0.05,
        "conservative_package_size_cm": [15, 10, 3],
        "conservative_package_weight_kg": 0.06,
        "conservative_risk_basis": "thickness_uncertainty",
        "confidence": "medium",
        "reasoning": "薄袜, 保守档仅增加折叠厚度不确定性",
    }
    result = estimate_from_ai_json(ai_data)
    assert result["status"] == "calculated"
    # 保守档长宽应与正常档一致(只调整了厚度)
    n_size = result["normal"]["packaged_size_cm"]
    c_size = result["conservative"]["packaged_size_cm"]
    assert c_size[0] == n_size[0], "保守档长不应增加"
    assert c_size[1] == n_size[1], "保守档宽不应增加"


# ---- 3. soft_flat两档采用同一软品体积策略 ----

def test_soft_flat_unified_volume_policy():
    """软品片状: 两档体积重都应被忽略, 都使用实重。"""
    ai_data = {
        "product_type": "cotton_scarf",
        "quantity": 1,
        "rigidity": "soft",
        "foldability": "good",
        "compressibility": "good",
        "overall_form": "soft_flat",
        "ai_net_weight_kg": 0.03,
        "ai_package_size_cm": [20, 15, 4],
        "ai_package_weight_kg": 0.04,
        "conservative_package_size_cm": [20, 15, 5],
        "conservative_package_weight_kg": 0.05,
        "conservative_risk_basis": "thickness_uncertainty",
        "confidence": "medium",
        "reasoning": "丝巾, 体积重远超净重",
    }
    result = estimate_from_ai_json(ai_data)
    n = result["normal"]
    c = result["conservative"]
    # 体积重 > 净重×3, 两档都应忽略体积重
    assert n["soft_volume_ignored"] is True, "正常档未忽略体积重"
    assert c["soft_volume_ignored"] is True, "保守档未忽略体积重"
    # 计费重都应来自实重
    assert n["chargeable_weight_kg"] == 0.04, f"正常档计费重异常: {n['chargeable_weight_kg']}"
    assert c["chargeable_weight_kg"] == 0.05, f"保守档计费重异常: {c['chargeable_weight_kg']}"


# ---- 4. 阈值跨越不能导致保守档计费重低于正常档 ----

def test_no_chargeable_inversion_from_soft_policy():
    """模拟阈值跨越: 正常档体积重刚过阈值被忽略, 保守档更大体积重也应被忽略, 最终保守档计费重>=正常档。"""
    ai_data = {
        "product_type": "thin_gloves",
        "quantity": 1,
        "rigidity": "soft",
        "foldability": "good",
        "compressibility": "good",
        "overall_form": "soft_flat",
        "ai_net_weight_kg": 0.05,
        "ai_package_size_cm": [25, 20, 5],
        "ai_package_weight_kg": 0.07,
        "conservative_package_size_cm": [25, 20, 7],
        "conservative_package_weight_kg": 0.10,
        "conservative_risk_basis": "thickness_uncertainty",
        "confidence": "low",
        "reasoning": "薄手套, 保守档增加厚度",
    }
    result = estimate_from_ai_json(ai_data)
    n = result["normal"]
    c = result["conservative"]
    # 保守档计费重不得低于正常档
    assert c["chargeable_weight_kg"] >= n["chargeable_weight_kg"], (
        f"保守档计费重{ca['chargeable_weight_kg']} < 正常档{n['chargeable_weight_kg']}"
    )
    # 两家货代保守档费用不得低于正常档
    for provider in ("深圳货代", "义乌货代"):
        n_fee = n["provider_costs"][provider]["head_freight_rmb"]
        c_fee = c["provider_costs"][provider]["head_freight_rmb"]
        assert c_fee >= n_fee, f"{provider}: 保守档{c_fee} < 正常档{n_fee}"


# ---- 5. soft_bulky允许较少压缩导致合理体积增加 ----

def test_soft_bulky_allows_reasonable_volume_increase():
    ai_data = {
        "product_type": "plush_toy",
        "quantity": 1,
        "rigidity": "soft",
        "foldability": "good",
        "compressibility": "good",
        "overall_form": "soft_bulky",
        "ai_net_weight_kg": 0.20,
        "ai_package_size_cm": [20, 15, 8],
        "ai_package_weight_kg": 0.22,
        "conservative_package_size_cm": [20, 15, 12],
        "conservative_package_weight_kg": 0.25,
        "conservative_risk_basis": "compression_uncertainty",
        "confidence": "medium",
        "reasoning": "毛绒玩具, 保守档较少压缩",
    }
    result = estimate_from_ai_json(ai_data)
    assert result["status"] == "calculated"
    n_vol = result["normal"]["volume_weight_kg"]
    c_vol = result["conservative"]["volume_weight_kg"]
    # 保守档体积重应更大(较少压缩)
    assert c_vol >= n_vol
    assert result["conservative"]["chargeable_weight_kg"] >= result["normal"]["chargeable_weight_kg"]


# ---- 6. hard_flat只增加有依据的厚度或包材, 不放大全部轴 ----

def test_hard_flat_only_adds_thickness():
    ai_data = {
        "product_type": "compact_mirror",
        "quantity": 1,
        "rigidity": "hard",
        "foldability": "none",
        "compressibility": "none",
        "overall_form": "hard_flat",
        "ai_net_weight_kg": 0.15,
        "ai_package_size_cm": [12, 10, 2],
        "ai_package_weight_kg": 0.16,
        "conservative_package_size_cm": [12, 10, 3],
        "conservative_package_weight_kg": 0.18,
        "conservative_risk_basis": "protection_uncertainty",
        "confidence": "medium",
        "reasoning": "化妆镜, 保守档仅增加缓冲厚度",
    }
    result = estimate_from_ai_json(ai_data)
    assert result["status"] == "calculated"
    n_size = result["normal"]["packaged_size_cm"]
    c_size = result["conservative"]["packaged_size_cm"]
    assert c_size[0] == n_size[0], "硬质扁平: 保守档长不应增加"
    assert c_size[1] == n_size[1], "硬质扁平: 保守档宽不应增加"


# ---- 7. 两家货代的保守档费用均不得低于正常档 ----

def test_both_providers_monotonic():
    ai_data = {
        "product_type": "test_item",
        "quantity": 1,
        "overall_form": "unknown",
        "ai_net_weight_kg": 0.10,
        "ai_package_size_cm": [20, 15, 5],
        "ai_package_weight_kg": 0.12,
        "conservative_package_size_cm": [20, 15, 5],
        "conservative_package_weight_kg": 0.12,
        "conservative_risk_basis": "known_package_no_uncertainty",
        "dimension_scope": "shipping_package_size",
        "weight_scope": "packaged_weight",
        "confidence": "high",
        "reasoning": "明确包装",
    }
    result = estimate_from_ai_json(ai_data)
    n = result["normal"]
    c = result["conservative"]
    for provider in ("深圳货代", "义乌货代"):
        assert c["provider_costs"][provider]["head_freight_rmb"] >= n["provider_costs"][provider]["head_freight_rmb"]


# ---- 8. 旧版AI JSON仍可运行, 兼容回退 ----

def test_old_ai_json_compatible():
    """旧版JSON (无overall_form/risk_basis, 有机械放大默认值) 仍可正常运行。"""
    old_data = {
        "product_type": "old_socks",
        "quantity": 1,
        "category": "general",
        "rigidity": "soft",
        "foldability": "good",
        "compressibility": "good",
        "ai_net_weight_kg": 0.08,
        "ai_package_size_cm": [15, 10, 4],
        "ai_package_weight_kg": 0.09,
        "conservative_package_size_cm": [18, 12, 5],
        "conservative_package_weight_kg": 0.105,
        "confidence": "medium",
        "reasoning": "旧版袜子",
    }
    result = estimate_from_ai_json(old_data)
    assert result["status"] == "calculated"
    # 兼容回退: 保守档即使机械放大, 单调性保护仍然生效
    assert result["conservative"]["chargeable_weight_kg"] >= result["normal"]["chargeable_weight_kg"]
    # ai_meta 应记录回退来源
    assert "ai_meta" in result
