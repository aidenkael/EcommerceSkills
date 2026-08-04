"""精确校准解析测试 — calibration_resolver.py 单元测试。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from logistics_cost.calibration_resolver import (
    resolve_exact_calibration,
    apply_calibration_override,
    _normalize,
)


def _make_cases_file(cases: list[dict]) -> Path:
    """将案例列表写入临时 JSONL 并返回路径。"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
    for case in cases:
        tmp.write(json.dumps(case, ensure_ascii=False) + "\n")
    tmp.close()
    return Path(tmp.name)


# 标准案例（HelloKitty 大包）
_VALIDATED_CASE = {
    "case_id": "PVC-COSMETIC-BAG-001",
    "status": "validated",
    "confidence": "medium",
    "usage_scope": "exact_product_sku_only",
    "evidence_scope": "confirmed_pure_head_cost_only",
    "runtime_override": True,
    "derived_parameters_are_measured": False,
    "title_markers": ["透明手提化妆包", "HelloKitty", "可爱收纳包JL"],
    "selected_sku": "凯蒂猫大包",
    "quantity": 1,
    "runtime_overall_form": "soft_bulky",
    "runtime_modifiers": ["hollow"],
    "shape_retention_scope": "none",
    "calibrated_estimate_normal": {
        "packaged_size_cm": [22.0, 18.0, 1.4],
        "packaged_weight_g": 70.0,
        "chargeable_weight_g": 70.0,
        "packaging_method": "折叠压扁后袋装",
    },
    "calibrated_estimate_conservative": {
        "packaged_size_cm": [23.0, 19.0, 1.6],
        "packaged_weight_g": 87.5,
        "chargeable_weight_g": 87.5,
        "packaging_method": "较少压缩后袋装",
    },
}

FULL_TITLE = "2026新款透明手提化妆包大容量防水包包HelloKitty可爱收纳包JL"


class TestNormalize:
    def test_lowercase(self):
        assert _normalize("HelloKitty") == "hellokitty"

    def test_fullwidth_space(self):
        assert _normalize("A\u3000B") == "a b"

    def test_multiple_spaces(self):
        assert _normalize("a   b") == "a b"

    def test_strip(self):
        assert _normalize("  abc  ") == "abc"

    def test_empty(self):
        assert _normalize("") == ""
        assert _normalize("   ") == ""


class TestExactHit:
    """Test 1-5: 精确命中与不命中场景"""

    def test_hellokitty_bag_hit(self, tmp_path):
        """HelloKitty 大包、数量1精确命中。"""
        cases_path = _make_cases_file([_VALIDATED_CASE])
        result = resolve_exact_calibration(FULL_TITLE, "凯蒂猫大包", 1, cases_path)
        assert result is not None
        assert result["case_id"] == "PVC-COSMETIC-BAG-001"

    def test_wrong_sku_no_hit(self, tmp_path):
        """凯蒂猫小包不命中。"""
        cases_path = _make_cases_file([_VALIDATED_CASE])
        result = resolve_exact_calibration(FULL_TITLE, "凯蒂猫小包", 1, cases_path)
        assert result is None

    def test_quantity_two_no_hit(self, tmp_path):
        """数量2不命中。"""
        cases_path = _make_cases_file([_VALIDATED_CASE])
        result = resolve_exact_calibration(FULL_TITLE, "凯蒂猫大包", 2, cases_path)
        assert result is None

    def test_missing_title_marker_no_hit(self, tmp_path):
        """缺任一标题标记不命中。"""
        # 缺少"可爱收纳包JL"
        cases_path = _make_cases_file([_VALIDATED_CASE])
        result = resolve_exact_calibration("透明手提化妆包HelloKitty", "凯蒂猫大包", 1, cases_path)
        assert result is None

    def test_case_insensitive_hit(self, tmp_path):
        """大小写差异仍可命中。"""
        cases_path = _make_cases_file([_VALIDATED_CASE])
        result = resolve_exact_calibration(
            "2026新款透明手提化妆包大容量防水包包HELLOKITTY可爱收纳包JL",
            "凯蒂猫大包", 1, cases_path,
        )
        assert result is not None
        assert result["case_id"] == "PVC-COSMETIC-BAG-001"

    def test_pending_case_no_hit(self, tmp_path):
        """pending 案例不命中。"""
        pending_case = dict(_VALIDATED_CASE)
        pending_case["status"] = "pending"
        pending_case["case_id"] = "PVC-PENDING"
        cases_path = _make_cases_file([pending_case, _VALIDATED_CASE])
        # 即使标题/SKU匹配，pending 不命中；但下一个 validated 案例会命中
        result = resolve_exact_calibration(FULL_TITLE, "凯蒂猫大包", 1, cases_path)
        assert result is not None
        assert result["case_id"] == "PVC-COSMETIC-BAG-001"  # 从 validated 命中

    def test_pending_only_no_hit(self, tmp_path):
        """只有 pending 案例时不命中。"""
        pending_case = dict(_VALIDATED_CASE)
        pending_case["status"] = "pending"
        cases_path = _make_cases_file([pending_case])
        result = resolve_exact_calibration(FULL_TITLE, "凯蒂猫大包", 1, cases_path)
        assert result is None

    def test_corrupt_json_line_survives(self, tmp_path):
        """损坏JSON行不阻断后续查询。"""
        cases_path = _make_cases_file([_VALIDATED_CASE])
        # 在文件开头插入损坏行
        corrupt = cases_path.read_text(encoding="utf-8")
        cases_path.write_text("this is not json\n" + corrupt, encoding="utf-8")
        result = resolve_exact_calibration(FULL_TITLE, "凯蒂猫大包", 1, cases_path)
        assert result is not None
        assert result["case_id"] == "PVC-COSMETIC-BAG-001"


class TestOverride:
    """Test 8-10: 覆盖行为"""

    def test_normal_weight_70g(self):
        """命中后正常档为70g。"""
        ai_data = {"ai_net_weight_kg": 0.3, "ai_package_weight_kg": 0.3, "product_type": "test"}
        result = apply_calibration_override(ai_data, _VALIDATED_CASE)
        assert result["ai_package_weight_kg"] == 0.07  # 70g / 1000

    def test_conservative_weight_87_5g(self):
        """命中后保守档为87.5g。"""
        ai_data = {}
        result = apply_calibration_override(ai_data, _VALIDATED_CASE)
        assert result["conservative_package_weight_kg"] == 0.0875

    def test_does_not_override_price(self):
        """不覆盖采购价、国内运费和利润参数。"""
        ai_data = {
            "product_type": "test",
            "purchase_price_rmb": 47,
            "domestic_freight_rmb": 5,
            "exchange_rate": 6.8,
        }
        result = apply_calibration_override(ai_data, _VALIDATED_CASE)
        assert result.get("purchase_price_rmb") == 47
        assert result.get("domestic_freight_rmb") == 5
        assert result.get("exchange_rate") == 6.8
        # 校准元数据存在但不进入输出
        assert result.get("_calibration_applied") == True
        assert result.get("_calibration_case_id") == "PVC-COSMETIC-BAG-001"

    def test_empty_title_safe(self):
        """空标题安全返回None。"""
        assert resolve_exact_calibration("", "任何", 1) is None

    def test_empty_sku_safe(self):
        """空SKU安全返回None。"""
        assert resolve_exact_calibration("标题", "", 1) is None

    def test_no_runtime_override_no_hit(self, tmp_path):
        """没有 runtime_override 的案例不命中。"""
        case = dict(_VALIDATED_CASE)
        del case["runtime_override"]
        cases_path = _make_cases_file([case])
        result = resolve_exact_calibration(FULL_TITLE, "凯蒂猫大包", 1, cases_path)
        assert result is None

    def test_no_calibrated_estimates_no_hit(self, tmp_path):
        """缺少两档覆盖参数的案例不命中。"""
        case = dict(_VALIDATED_CASE)
        del case["calibrated_estimate_normal"]
        cases_path = _make_cases_file([case])
        result = resolve_exact_calibration(FULL_TITLE, "凯蒂猫大包", 1, cases_path)
        assert result is None

    def test_runtime_overall_form_override(self):
        """runtime_overall_form 正确覆盖。"""
        ai_data = {}
        result = apply_calibration_override(ai_data, _VALIDATED_CASE)
        assert result["overall_form"] == "soft_bulky"
        assert "hollow" in result.get("modifiers", [])

    def test_packaging_method_override(self):
        """包装方法正确覆盖。"""
        ai_data = {"packaging_method": "气泡袋"}
        result = apply_calibration_override(ai_data, _VALIDATED_CASE)
        assert result["packaging_method"] == "折叠压扁后袋装"
