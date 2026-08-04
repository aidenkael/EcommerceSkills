"""包装候选仲裁测试 — packaging_arbitrator.py 边界测试。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from logistics_cost.packaging_arbitrator import (
    arbitrate_packaging_candidate,
    _has_strong_hard_evidence,
    _has_strong_protrusion_evidence,
)


def _make_rules_file(rules: list[dict]) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(rules, tmp, ensure_ascii=False)
    tmp.close()
    return Path(tmp.name)


def _thin_pvc_ai(**overrides) -> dict:
    base = {
        "product_type": "透明化妆包",
        "category": "bag",
        "rigidity": "soft",
        "foldability": "good",
        "compressibility": "good",
        "has_rigid_parts": False,
        "requires_shape_retention": False,
        "shape_retention_scope": "none",
        "overall_form": "unknown",
        "material_family": "pvc",
        "structure_evidence": [],
        "dimension_scope": "product_size",
        "ai_net_weight_kg": 0.16,
        "ai_package_size_cm": [22, 18, 8],
        "ai_package_weight_kg": 0.18,
        "conservative_package_size_cm": [23, 19, 9],
        "conservative_package_weight_kg": 0.2,
        "confidence": "medium",
    }
    base.update(overrides)
    return base


# ============================================================
# 测试 1-2: 无 SKU/标题时仍执行通用仲裁
# ============================================================

def test_no_sku_still_arbitrates():
    """无 SKU 时仍执行通用仲裁。"""
    ai = _thin_pvc_ai()
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=False)
    assert result["overall_form"] == "soft_hollow"


def test_no_title_still_arbitrates():
    """标题和 SKU 都缺失时仍执行通用仲裁（不报错）。"""
    ai = _thin_pvc_ai()
    ai["product_type"] = ""
    # 仲裁仍运行，不抛异常；只是不匹配任何规则
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=False)
    assert result is not None
    # 至少字段合法化已执行
    assert "material_family" in result


# ============================================================
# 测试 3: 精确半结构化校准不降级
# ============================================================

def test_exact_calibration_preserves_semi_structured():
    """精确校准为 semi_structured_hollow 时不被降级。"""
    ai = {
        "product_type": "校准包",
        "category": "bag",
        "rigidity": "semi_rigid",
        "foldability": "none",
        "compressibility": "none",
        "has_rigid_parts": True,
        "requires_shape_retention": True,
        "shape_retention_scope": "body",
        "overall_form": "semi_structured_hollow",
        "structure_evidence": [],  # 无强证据
        "ai_net_weight_kg": 0.7,
        "ai_package_size_cm": [29, 21, 15],
        "ai_package_weight_kg": 0.75,
        "conservative_package_size_cm": [31, 22, 17],
        "conservative_package_weight_kg": 0.78,
        "confidence": "medium",
    }
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=True)
    assert result["rigidity"] == "semi_rigid"
    assert result["overall_form"] == "semi_structured_hollow"
    assert result["has_rigid_parts"] == True
    assert result["requires_shape_retention"] == True
    assert result["shape_retention_scope"] == "body"
    assert result["ai_package_size_cm"] == [29, 21, 15]
    assert abs(result["ai_package_weight_kg"] - 0.75) < 0.001


# ============================================================
# 测试 4: soft_hollow + 用户确认硬底 → 升级为半结构化
# ============================================================

def test_soft_hollow_with_user_confirmed_hard_bottom_upgrades():
    """soft_hollow + 用户确认硬底 → semi_structured_hollow + semi_rigid。"""
    ai = _thin_pvc_ai(
        overall_form="soft_hollow",
        category="bag",
        structure_evidence=[
            {"fact": "hard_bottom", "source": "user_confirmed", "location": "用户明确确认"}
        ]
    )
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=False)
    assert result["overall_form"] == "semi_structured_hollow"
    assert result["rigidity"] == "semi_rigid"
    assert result["has_rigid_parts"] == True
    assert result["shape_retention_scope"] == "body"


# ============================================================
# 测试 5-6: 非包类硬商品不降级
# ============================================================

def test_non_bag_hard_3d_not_downgraded():
    """非包类 hard_3d 硬壳收纳盒不被降级。"""
    ai = {
        "product_type": "hard_shell_case",
        "category": "general",
        "rigidity": "hard",
        "foldability": "none",
        "compressibility": "none",
        "has_rigid_parts": True,
        "requires_shape_retention": True,
        "shape_retention_scope": "whole",
        "overall_form": "hard_3d",
        "material_family": "unknown",
        "structure_evidence": [],
        "ai_net_weight_kg": 0.5,
        "ai_package_size_cm": [25, 20, 10],
        "ai_package_weight_kg": 0.55,
        "conservative_package_size_cm": [26, 21, 11],
        "conservative_package_weight_kg": 0.6,
        "confidence": "medium",
    }
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=False)
    assert result["rigidity"] == "hard"
    assert result["overall_form"] == "hard_3d"


def test_non_bag_hard_flat_not_downgraded():
    """非包类 hard_flat 硬质镜不被降级。"""
    ai = {
        "product_type": "rigid_cosmetic_mirror",
        "category": "general",
        "rigidity": "hard",
        "foldability": "none",
        "compressibility": "none",
        "has_rigid_parts": True,
        "requires_shape_retention": True,
        "shape_retention_scope": "whole",
        "overall_form": "hard_flat",
        "material_family": "unknown",
        "structure_evidence": [],
        "ai_net_weight_kg": 0.3,
        "ai_package_size_cm": [20, 15, 3],
        "ai_package_weight_kg": 0.35,
        "conservative_package_size_cm": [21, 16, 4],
        "conservative_package_weight_kg": 0.4,
        "confidence": "medium",
    }
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=False)
    assert result["rigidity"] == "hard"
    assert result["overall_form"] == "hard_flat"


# ============================================================
# 测试 7-8: 突出件证据
# ============================================================

def test_soft_shell_not_trigger_protrusion():
    """soft_shell/foldable_handle/detachable_strap 不触发突出件。"""
    assert not _has_strong_protrusion_evidence({
        "structure_evidence": [
            {"fact": "soft_shell", "source": "image_visible", "location": "可见"}
        ],
        "rigidity": "semi_rigid",
    })
    assert not _has_strong_protrusion_evidence({
        "structure_evidence": [
            {"fact": "foldable_handle", "source": "user_confirmed", "location": "折叠"}
        ],
        "rigidity": "semi_rigid",
    })


def test_rigid_protrusion_triggers():
    """rigid_protrusion 强证据触发突出件。"""
    assert _has_strong_protrusion_evidence({
        "structure_evidence": [
            {"fact": "rigid_protrusion", "source": "user_confirmed", "location": "突出件"}
        ],
        "rigidity": "semi_rigid",
    })
    assert _has_strong_protrusion_evidence({
        "structure_evidence": [
            {"fact": "non_detachable_hard_protrusion", "source": "merchant_text", "location": "不可拆"}
        ],
        "rigidity": "hard",
    })


# ============================================================
# 测试 9-11: 尺寸修正行为
# ============================================================

def test_shipping_package_size_preserved():
    """shipping_package_size [30,20,8] 三轴完全保持。"""
    ai = _thin_pvc_ai(
        ai_package_size_cm=[30, 20, 8],
        conservative_package_size_cm=[31, 21, 9],
        dimension_scope="shipping_package_size",
    )
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=False)
    assert result["ai_package_size_cm"] == [30, 20, 8]
    assert result["conservative_package_size_cm"] == [31, 21, 9]


def test_product_size_only_min_axis_changed():
    """product_size [30,20,10] 只改变最小轴。"""
    ai = _thin_pvc_ai(
        ai_package_size_cm=[30, 20, 10],
        conservative_package_size_cm=[31, 21, 11],
        dimension_scope="product_size",
    )
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=False)
    dims = result["ai_package_size_cm"]
    # 两个较大轴保持不变
    assert dims[0] == 30
    assert dims[1] == 20
    # 最小轴被修改
    assert dims[2] < 10


def test_conservative_not_lower_than_normal():
    """保守厚度不低于正常厚度。"""
    ai = _thin_pvc_ai(
        ai_package_size_cm=[30, 20, 10],
        conservative_package_size_cm=[30, 20, 10],
        dimension_scope="product_size",
    )
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=False)
    norm_min = min(result["ai_package_size_cm"])
    con_min = min(result["conservative_package_size_cm"])
    assert con_min >= norm_min


# ============================================================
# 测试 12: 原始输入不修改
# ============================================================

def test_input_not_mutated():
    """原始输入 dict 不被原地修改。"""
    original = _thin_pvc_ai()
    before = original.copy()
    _ = arbitrate_packaging_candidate(original, exact_calibration_applied=False)
    for key in before:
        assert before[key] == original[key], f"Input key '{key}' was mutated"


# ============================================================
# 测试 13: 精确校准优先于通用规则
# ============================================================

def test_exact_calibration_priority():
    """精确SKU校准仍优先于通用规则。"""
    # 精确校准参数
    ai = _thin_pvc_ai(
        ai_package_size_cm=[22, 18, 1.4],
        ai_package_weight_kg=0.07,
    )
    result = arbitrate_packaging_candidate(ai, exact_calibration_applied=True)
    assert result["ai_package_size_cm"] == [22, 18, 1.4]
    assert abs(result["ai_package_weight_kg"] - 0.07) < 0.001


# ============================================================
# 测试 14: 性能
# ============================================================

def test_performance_median_under_50ms():
    import time
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        arbitrate_packaging_candidate(_thin_pvc_ai())
        times.append(time.perf_counter() - t0)
    times.sort()
    median = times[len(times) // 2]
    assert median < 0.05, f"Median {median:.4f}s exceeds 0.05s"
