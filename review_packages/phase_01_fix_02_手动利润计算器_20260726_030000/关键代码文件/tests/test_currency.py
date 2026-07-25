"""
货币换算模块测试

覆盖：人民币↔美元 正常转换、零值、None、负数、汇率为零
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculation.currency import rmb_to_usd, usd_to_rmb


class TestRmbToUsd:
    """人民币 → 美元"""

    def test_normal(self):
        assert rmb_to_usd(720.0, 7.2) == 100.0

    def test_zero_rmb(self):
        assert rmb_to_usd(0, 7.2) == 0.0

    def test_none_input(self):
        assert rmb_to_usd(None, 7.2) is None
        assert rmb_to_usd(100.0, None) is None

    def test_negative_rmb(self):
        assert rmb_to_usd(-100, 7.2) is None

    def test_zero_exchange_rate(self):
        assert rmb_to_usd(100.0, 0) is None

    def test_negative_rate(self):
        assert rmb_to_usd(100.0, -1) is None


class TestUsdToRmb:
    """美元 → 人民币"""

    def test_normal(self):
        assert usd_to_rmb(100.0, 7.2) == 720.0

    def test_zero_usd(self):
        assert usd_to_rmb(0, 7.2) == 0.0

    def test_none_input(self):
        assert usd_to_rmb(None, 7.2) is None
        assert usd_to_rmb(100.0, None) is None

    def test_negative_usd(self):
        assert usd_to_rmb(-100, 7.2) is None

    def test_zero_rate(self):
        assert usd_to_rmb(100.0, 0) is None
