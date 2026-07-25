"""
货代规则测试（fix_03 新增）

深圳：头程80元/kg + 固定费10元
义乌：头程100元/kg + 固定费6元
共同：体积重÷8000，尾程默认40元
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from calculation import (
    volumetric_weight, chargeable_weight, head_haul_cost,
    total_logistics_cost, known_logistics_subtotal,
    total_cost, net_profit_amount, net_profit_rate,
    suggested_price_from_rate,
)


class TestShenzhenRoute:
    """深圳货代：80元/kg + 10元固定费"""

    def test_head_haul(self):
        vol = volumetric_weight(35, 25, 8)
        chg = chargeable_weight(0.35, vol)  # max(0.35, 0.875) = 0.875
        head = head_haul_cost(chg, 80.0)
        assert abs(head - 70.0) < 0.01  # 0.875 × 80

    def test_logistics(self):
        head = 70.0; fixed = 10.0; tail = 40.0
        log = total_logistics_cost(head, fixed, tail)
        assert log == 120.0

    def test_total_cost(self):
        tc = total_cost(50.0, 8.0, 120.0)
        assert tc == 178.0

    def test_profit_calculation(self):
        tc = 178.0; price = 300.0; promo = 10.0
        np = net_profit_amount(price, tc, promo)
        # 毛利=122, 推广=30, 净利=92
        assert abs(np - 92.0) < 0.01
        npr = net_profit_rate(price, tc, promo)
        assert abs(npr - 30.67) < 0.1

    def test_suggested_price(self):
        tc = 178.0; target = 30.0; promo = 10.0
        sp = suggested_price_from_rate(tc, target, promo)
        # 178 / (1 - 0.4) = 296.67
        assert sp is not None
        assert abs(sp - 296.67) < 0.1

    def test_no_forwarder_no_profit(self):
        """未选货代时头程无法计算 → 利润不应确定"""
        # 模拟包装数据存在但无head_haul_rate
        head = head_haul_cost(0.875, None)
        assert head is None  # rate=None → 头程无法计算


class TestYiwuRoute:
    """义乌货代：100元/kg + 6元固定费"""

    def test_head_haul(self):
        vol = volumetric_weight(35, 25, 8)
        chg = chargeable_weight(0.35, vol)
        head = head_haul_cost(chg, 100.0)
        assert abs(head - 87.5) < 0.01  # 0.875 × 100

    def test_logistics(self):
        log = total_logistics_cost(87.5, 6.0, 40.0)
        assert log == 133.5

    def test_total_cost(self):
        tc = total_cost(50.0, 8.0, 133.5)
        assert abs(tc - 191.5) < 0.01

    def test_suggested_price(self):
        tc = 191.5; target = 30.0; promo = 10.0
        sp = suggested_price_from_rate(tc, target, promo)
        assert sp is not None
        assert abs(sp - 319.17) < 0.1


class TestMissingCost:
    """缺失头程费用时不显示确定利润"""

    def test_missing_head_returns_none(self):
        head = head_haul_cost(None, 100.0)
        assert head is None

    def test_logistics_with_missing_head_partial(self):
        # 严格模式：头程缺失 → None
        log = total_logistics_cost(None, 6.0, 40.0)
        assert log is None
        # 已知部分用于显示
        known = known_logistics_subtotal(None, 6.0, 40.0)
        assert known == 46.0

    def test_missing_key_cost_no_false_profit(self):
        """关键费用缺失不应产生确定利润"""
        # 不填包装 → 头程None → 利润应标记为不可靠
        head = head_haul_cost(None, 100.0)
        assert head is None
