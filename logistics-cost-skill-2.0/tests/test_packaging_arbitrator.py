"""包装候选仲裁测试 — packaging_arbitrator.py 单元测试。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from logistics_cost.packaging_arbitrator import (
    arbitrate_packaging_candidate,
    _has_strong_hard_evidence,
    _evidence_gate,
    _match_rule,
    _load_rules,
)


def _make_rules_file(rules: list[dict]) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(rules, tmp, ensure_ascii=False)
    tmp.close()
    return Path(tmp.name)


def _thin_pvc_bag_ai() -> dict:
    """薄款透明软塑料化妆包, 无硬证据, 展示厚度8cm。"""
    return {
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


class TestThinPVCBagNoHardEvidence:
    """测试1: 薄款透明软塑料化妆包、无硬证据"""

    def test_result_is_soft_hollow(self):
        result = arbitrate_packaging_candidate(_thin_pvc_bag_ai())
        assert result["overall_form"] == "soft_hollow"

    def test_not_semi_structured_hollow(self):
        result = arbitrate_packaging_candidate(_thin_pvc_bag_ai())
        assert result["overall_form"] != "semi_structured_hollow"

    def test_thickness_not_display_thickness(self):
        result = arbitrate_packaging_candidate(_thin_pvc_bag_ai())
        # 运输厚度不得继续使用展示厚度 8cm
        dims = result["ai_package_size_cm"]
        assert dims[2] < 5.0, f"Thickness {dims[2]} still looks like display thickness"

    def test_head_cost_not_84_level(self):
        """纯头程不得出现原先约¥84的量级。"""
        result = arbitrate_packaging_candidate(_thin_pvc_bag_ai())
        dims = result["ai_package_size_cm"]
        vol_wt = dims[0] * dims[1] * dims[2] / 8000
        # 体积重应远低于原先的 22×18×8/8000 = 0.396kg
        assert vol_wt < 0.15, f"Volume weight {vol_wt:.3f} too high"


class TestStructuredPVCWithHardEvidence:
    """测试2: 同类商品存在明确硬底证据"""

    def test_hits_structured_rule(self):
        ai = _thin_pvc_bag_ai()
        ai["rigidity"] = "semi_rigid"
        ai["structure_evidence"] = [
            {"fact": "hard_bottom", "source": "user_confirmed", "location": "用户明确说明"}
        ]
        result = arbitrate_packaging_candidate(ai)
        # 有强证据时不会被降级
        assert result["rigidity"] == "semi_rigid"

    def test_no_full_folding(self):
        ai = _thin_pvc_bag_ai()
        ai["rigidity"] = "semi_rigid"
        ai["foldability"] = "none"
        ai["structure_evidence"] = [
            {"fact": "hard_bottom", "source": "user_confirmed", "location": "底部硬板"}
        ]
        result = arbitrate_packaging_candidate(ai)
        dims = result["ai_package_size_cm"]
        min_v = min(dims)
        # 最低厚度不低于4cm
        assert min_v >= 3.9, f"Min axis {min_v} should not be fully compressed"


class TestSoftPUBag:
    """测试3: 柔软PU包"""

    def test_only_min_axis_compressed(self):
        ai = {
            "product_type": "pu_crossbody_bag",
            "category": "bag",
            "rigidity": "soft",
            "foldability": "good",
            "compressibility": "good",
            "overall_form": "soft_hollow",
            "material_family": "pu",
            "structure_evidence": [],
            "ai_net_weight_kg": 0.4,
            "ai_package_size_cm": [30, 20, 8],
            "ai_package_weight_kg": 0.45,
            "conservative_package_size_cm": [31, 21, 9],
            "conservative_package_weight_kg": 0.5,
            "confidence": "medium",
        }
        result = arbitrate_packaging_candidate(ai)
        dims = result["ai_package_size_cm"]
        # 长宽保持不变
        assert dims[0] == 30, f"Length changed from 30 to {dims[0]}"
        assert dims[1] == 20, f"Width changed from 20 to {dims[1]}"
        # 厚度被压缩
        assert dims[2] < 8, f"Thickness {dims[2]} not compressed"


class TestOxfordBag:
    """测试4: 无硬背板的牛津布书包"""

    def test_both_modes_different_compression(self):
        ai = {
            "product_type": "牛津布书包",
            "category": "bag",
            "rigidity": "soft",
            "foldability": "good",
            "compressibility": "good",
            "overall_form": "unknown",
            "material_family": "oxford",
            "structure_evidence": [],
            "ai_net_weight_kg": 0.5,
            "ai_package_size_cm": [40, 30, 10],
            "ai_package_weight_kg": 0.55,
            "conservative_package_size_cm": [41, 31, 11],
            "conservative_package_weight_kg": 0.6,
            "confidence": "medium",
        }
        result = arbitrate_packaging_candidate(ai)
        norm_dims = result["ai_package_size_cm"]
        con_dims = result["conservative_package_size_cm"]
        # 正常档压缩率更大（0.40 vs 0.62）
        assert norm_dims[2] < con_dims[2], "Normal should be more compressed than conservative"


class TestThinTextile:
    """测试5: 薄袜/薄针织"""

    def test_no_hard_box(self):
        ai = {
            "product_type": "thin_socks",
            "category": "general",
            "rigidity": "soft",
            "foldability": "good",
            "compressibility": "good",
            "overall_form": "soft_flat",
            "material_family": "thin_textile",
            "structure_evidence": [],
            "ai_net_weight_kg": 0.03,
            "ai_package_size_cm": [15, 10, 3],
            "ai_package_weight_kg": 0.035,
            "conservative_package_size_cm": [16, 11, 4],
            "conservative_package_weight_kg": 0.04,
            "confidence": "medium",
        }
        result = arbitrate_packaging_candidate(ai)
        # 不添加硬盒
        assert result.get("packaging_type") != "small_box"


class TestHardProtrusion:
    """测试6: 硬质突出件"""

    def test_only_min_axis_protection(self):
        ai = {
            "product_type": "metal_decor_bag",
            "category": "bag",
            "rigidity": "semi_rigid",
            "foldability": "none",
            "compressibility": "none",
            "overall_form": "semi_structured_hollow",
            "material_family": "pu",
            "structure_evidence": [
                {"fact": "hard_bottom", "source": "image_visible", "location": "底部金属支架"}
            ],
            "ai_net_weight_kg": 0.6,
            "ai_package_size_cm": [25, 15, 5],
            "ai_package_weight_kg": 0.65,
            "conservative_package_size_cm": [26, 16, 6],
            "conservative_package_weight_kg": 0.7,
            "confidence": "medium",
        }
        result = arbitrate_packaging_candidate(ai)
        dims = result["ai_package_size_cm"]
        # 只有最小轴增加保护
        assert dims[0] == 25, "Length should not change"
        assert dims[1] == 15, "Width should not change"
        # 最小轴增加了保护空间
        assert dims[2] >= 5, f"Min axis should have protection added"


class TestUnsupportedRigidity:
    """测试7: AI仅凭拉链/提手声称半硬质"""

    def test_downgraded_to_soft(self):
        ai = {
            "product_type": "fabric_pouch",
            "category": "bag",
            "rigidity": "semi_rigid",
            "foldability": "none",
            "compressibility": "none",
            "has_rigid_parts": True,
            "requires_shape_retention": True,
            "shape_retention_scope": "body",
            "overall_form": "semi_structured_hollow",
            "material_family": "fabric",
            "structure_evidence": [],
            "ai_net_weight_kg": 0.1,
            "ai_package_size_cm": [20, 15, 5],
            "ai_package_weight_kg": 0.12,
            "conservative_package_size_cm": [21, 16, 6],
            "conservative_package_weight_kg": 0.14,
            "confidence": "medium",
        }
        result = arbitrate_packaging_candidate(ai)
        # 应降级
        assert result["rigidity"] == "soft"
        assert result["has_rigid_parts"] == False
        assert result["requires_shape_retention"] == False


class TestStrongEvidenceRegression:
    """测试8: 强证据与优先级回归"""

    def test_user_confirmed_hard_bottom_preserves(self):
        ai = {
            "product_type": "structured_bag",
            "category": "bag",
            "rigidity": "semi_rigid",
            "foldability": "none",
            "compressibility": "none",
            "has_rigid_parts": True,
            "requires_shape_retention": True,
            "shape_retention_scope": "body",
            "overall_form": "semi_structured_hollow",
            "material_family": "pu",
            "structure_evidence": [
                {"fact": "hard_bottom", "source": "user_confirmed", "location": "用户确认硬底"}
            ],
            "ai_net_weight_kg": 0.5,
            "ai_package_size_cm": [30, 20, 8],
            "ai_package_weight_kg": 0.55,
            "conservative_package_size_cm": [31, 21, 9],
            "conservative_package_weight_kg": 0.6,
            "confidence": "medium",
        }
        result = arbitrate_packaging_candidate(ai)
        # 用户确认硬底时保留半结构化
        assert result["rigidity"] == "semi_rigid"
        assert result["has_rigid_parts"] == True

    def test_exact_calibration_skip_rules(self):
        """精确SKU校准优先于通用规则。"""
        ai = _thin_pvc_bag_ai()
        ai["ai_package_size_cm"] = [22, 18, 1.4]  # 精确校准参数
        ai["ai_package_weight_kg"] = 0.07
        result = arbitrate_packaging_candidate(ai, exact_calibration_applied=True)
        # 精确校准参数不被通用规则覆盖
        dims = result["ai_package_size_cm"]
        assert dims == [22, 18, 1.4], f"Exact calibration dimensions should not change, got {dims}"


class TestPerformance:
    """性能测试"""

    def test_arbitration_median_under_50ms(self):
        import time
        times = []
        for _ in range(100):
            t0 = time.perf_counter()
            arbitrate_packaging_candidate(_thin_pvc_bag_ai())
            times.append(time.perf_counter() - t0)
        times.sort()
        median = times[len(times) // 2]
        assert median < 0.05, f"Median {median:.4f}s exceeds 0.05s"
