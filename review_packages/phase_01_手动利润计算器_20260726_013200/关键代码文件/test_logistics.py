"""
物流计算模块测试

覆盖：体积重、计费重量、头程费用、总物流成本
     正常值、边界值、None、负数
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculation.logistics import (
    volumetric_weight,
    chargeable_weight,
    head_haul_cost,
    total_logistics_cost,
)


class TestVolumetricWeight:
    """体积重计算"""

    def test_normal(self):
        assert volumetric_weight(40, 30, 20) == 24000 / 8000  # = 3.0

    def test_zero_dimensions(self):
        assert volumetric_weight(0, 30, 20) == 0.0

    def test_none_input(self):
        assert volumetric_weight(None, 30, 20) is None
        assert volumetric_weight(40, None, 20) is None
        assert volumetric_weight(40, 30, None) is None
        assert volumetric_weight(None, None, None) is None

    def test_negative_input(self):
        assert volumetric_weight(-1, 30, 20) is None
        assert volumetric_weight(40, -1, 20) is None
        assert volumetric_weight(40, 30, -1) is None


class TestChargeableWeight:
    """计费重量选择"""

    def test_actual_greater(self):
        assert chargeable_weight(5.0, 3.0) == 5.0

    def test_vol_greater(self):
        assert chargeable_weight(2.0, 4.0) == 4.0

    def test_equal(self):
        assert chargeable_weight(3.5, 3.5) == 3.5

    def test_none_input(self):
        assert chargeable_weight(None, 3.0) is None
        assert chargeable_weight(5.0, None) is None
        assert chargeable_weight(None, None) is None

    def test_negative_input(self):
        assert chargeable_weight(-1, 3.0) is None
        assert chargeable_weight(5.0, -1) is None

    def test_edge_zero(self):
        assert chargeable_weight(0, 0) == 0.0


class TestHeadHaulCost:
    """头程费用"""

    def test_normal(self):
        assert head_haul_cost(3.5, 100.0) == 350.0

    def test_none_weight(self):
        assert head_haul_cost(None, 100.0) is None

    def test_none_rate(self):
        assert head_haul_cost(3.5, None) is None

    def test_negative(self):
        assert head_haul_cost(-1, 100.0) is None
        assert head_haul_cost(3.5, -1) is None

    def test_zero(self):
        assert head_haul_cost(0, 100.0) == 0.0


class TestTotalLogisticsCost:
    """总物流成本"""

    def test_all_present(self):
        assert total_logistics_cost(350.0, 36.0, 50.0) == 436.0

    def test_some_none(self):
        # None 按 0 算
        assert total_logistics_cost(350.0, None, 50.0) == 400.0
        assert total_logistics_cost(None, 36.0, None) == 36.0

    def test_all_none(self):
        assert total_logistics_cost(None, None, None) == 0.0

    def test_zero_values(self):
        assert total_logistics_cost(0, 0, 0) == 0.0
