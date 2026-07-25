"""
净利润 + 推广预留扣除测试（fix_02 新增）

验证：
- 推广预留从利润中扣除后的净利率 = 毛利率 - 推广比例
- 建议售价代入后净利率 ≈ 目标净利率
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculation.profit import (
    total_cost, profit_amount, profit_rate,
    net_profit_amount, net_profit_rate,
    suggested_price_from_rate,
)


class TestNetProfit:
    """净利润（扣除推广预留后）"""

    def test_no_promotion(self):
        """推广0%时净利润=毛利润"""
        tc = 179.0; price = 300.0; promo = 0.0
        gp = profit_amount(price, tc)  # 121
        np = net_profit_amount(price, tc, promo)
        assert abs(np - gp) < 0.01

    def test_with_promotion(self):
        """推广10%时净利润正确扣除"""
        tc = 179.0; price = 298.33; promo = 10.0
        # 毛利 = 298.33 - 179 = 119.33
        # 推广费 = 298.33 * 0.10 = 29.833
        # 净利 = 119.33 - 29.833 = 89.497 ≈ 89.50
        np = net_profit_amount(price, tc, promo)
        assert abs(np - 89.50) < 0.01

    def test_rate_matches_target(self):
        """建议售价代入后净利率 ≈ 目标净利率"""
        tc = 179.0; target = 30.0; promo = 10.0
        suggested = suggested_price_from_rate(tc, target, promo)
        # suggested = 179 / (1 - 0.3 - 0.1) = 179 / 0.6 = 298.333...
        assert suggested is not None
        npr = net_profit_rate(suggested, tc, promo)
        assert abs(npr - target) < 0.01  # 净利率应≈30%

    def test_no_promotion_rate(self):
        """无推广时净利率=毛利率"""
        tc = 100.0; price = 200.0; promo = 0.0
        pr = profit_rate(price, tc)  # 50%
        npr = net_profit_rate(price, tc, promo)
        assert abs(npr - pr) < 0.01

    def test_promotion_reduces_rate(self):
        """推广会降低净利率"""
        tc = 100.0; price = 200.0; promo = 15.0
        pr = profit_rate(price, tc)  # 50%
        npr = net_profit_rate(price, tc, promo)
        # 净利率 = 50% - 15% = 35%
        assert abs(npr - 35.0) < 0.01

    def test_none_promotion(self):
        """推广为None时净利润=毛利润"""
        tc = 100.0; price = 150.0
        np = net_profit_amount(price, tc, None)
        assert abs(np - 50.0) < 0.01

    def test_none_inputs(self):
        assert net_profit_amount(None, 100.0, 10.0) is None
        assert net_profit_amount(150.0, None, 10.0) is None
        assert net_profit_rate(None, 100.0, 10.0) is None
        assert net_profit_rate(150.0, None, 10.0) is None

    def test_negative_promotion(self):
        assert net_profit_amount(150.0, 100.0, -5) is None
        assert net_profit_rate(150.0, 100.0, -5) is None

    def test_zero_price(self):
        assert net_profit_rate(0, 100.0, 10.0) is None
        assert net_profit_rate(-10, 100.0, 10.0) is None
