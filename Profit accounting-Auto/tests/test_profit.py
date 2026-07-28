"""
利润计算模块测试

覆盖：总成本、利润金额、利润率、反算售价
     正常值、边界值、None、异常
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculation.profit import (
    total_cost, known_total_cost_subtotal,
    profit_amount, profit_rate, suggested_price_from_rate,
)


class TestTotalCost:
    """总成本计算 — 严格模式"""

    def test_all_present(self):
        assert total_cost(50.0, 10.0, 100.0) == 160.0

    def test_some_none(self):
        assert total_cost(50.0, None, 100.0) is None
        assert total_cost(None, 10.0, 100.0) is None

    def test_all_none(self):
        assert total_cost(None, None, None) is None

    def test_zero(self):
        assert total_cost(0, 0, 0) == 0.0

    def test_known_subtotal(self):
        assert known_total_cost_subtotal(50.0, None, 100.0) == 150.0


class TestProfitAmount:
    """利润金额"""

    def test_normal(self):
        assert profit_amount(200.0, 150.0) == 50.0

    def test_loss(self):
        assert profit_amount(100.0, 150.0) == -50.0

    def test_none_price(self):
        assert profit_amount(None, 150.0) is None

    def test_none_cost(self):
        assert profit_amount(200.0, None) is None

    def test_negative_price(self):
        assert profit_amount(-10, 50.0) is None


class TestProfitRate:
    """利润率"""

    def test_normal(self):
        assert profit_rate(200.0, 150.0) == 25.0  # (200-150)/200*100 = 25%

    def test_high_margin(self):
        assert profit_rate(1000.0, 100.0) == 90.0

    def test_loss(self):
        assert profit_rate(100.0, 150.0) == -50.0

    def test_zero_price(self):
        assert profit_rate(0, 50.0) is None

    def test_none_inputs(self):
        assert profit_rate(None, 50.0) is None
        assert profit_rate(100.0, None) is None

    def test_negative_price(self):
        assert profit_rate(-10, 50.0) is None


class TestSuggestedPriceFromRate:
    """反算建议售价"""

    def test_normal(self):
        # 成本100, 利润率30%, 推广10% → 售价 = 100 / (1-0.3-0.1) = 100/0.6 = 166.67
        result = suggested_price_from_rate(100.0, 30.0, 10.0)
        assert abs(result - 166.67) < 0.01

    def test_no_promotion(self):
        # 成本100, 利润率30%, 推广0% → 售价 = 100 / (1-0.3) = 142.86
        result = suggested_price_from_rate(100.0, 30.0, 0.0)
        assert abs(result - 142.86) < 0.01

    def test_zero_cost(self):
        assert suggested_price_from_rate(0.0, 30.0, 10.0) == 0.0

    def test_none_inputs(self):
        assert suggested_price_from_rate(None, 30.0, 10.0) is None
        assert suggested_price_from_rate(100.0, None, 10.0) is None
        assert suggested_price_from_rate(100.0, 30.0, None) is None

    def test_negative_inputs(self):
        assert suggested_price_from_rate(100.0, -1, 10.0) is None
        assert suggested_price_from_rate(100.0, 30.0, -1) is None

    def test_over_100_percent(self):
        # 利润率+推广 >= 100%, 无法定价
        assert suggested_price_from_rate(100.0, 60.0, 50.0) is None
        assert suggested_price_from_rate(100.0, 100.0, 0.0) is None
