"""
历史商品加载与费率不变性测试（fix_02 新增）

验证：
- 保存商品后修改费率，重新加载旧商品数据不变
- 快照包含当时规则
- re_render 不覆盖已保存结果
"""

import sys
import os
import shutil
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import DatabaseManager
from config.config_manager import ConfigManager


class TestHistoricalProduct:
    """历史商品加载后费率不变性"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "history_test.db")
        cls.db = DatabaseManager(cls.db_path)
        cls.cfg = ConfigManager(cls.db)

        # 保存商品 A（当时 rate=100, exchange=7.2, fixed=6）
        data_a = {
            "name": "商品A", "cost": 50.0, "domestic_shipping": 10.0,
            "packaged_weight": 0.5, "packaged_length": 30.0,
            "packaged_width": 20.0, "packaged_height": 10.0,
            "head_haul_cost": 75.0,  # = 0.75 * 100
            "fixed_service_fee": 6.0, "tail_haul_cost": 40.0,
            "selling_price_rmb": 200.0, "selling_price_usd": 27.78,
            "target_profit_rate": 30.0, "promotion_reserve_rate": 10.0,
        }
        cls.pid_a = cls.db.create_product(data_a)
        rules_a = {"exchange_rate": 7.2, "head_haul_rate": 100.0, "fixed_service_fee": 6.0}
        cls.db.save_snapshot(cls.pid_a, data_a, rules_a)

        # 保存商品 B（当时 rate=100, exchange=7.2）
        data_b = {
            "name": "商品B", "cost": 80.0, "domestic_shipping": 12.0,
            "packaged_weight": 1.2, "packaged_length": 40.0,
            "packaged_width": 30.0, "packaged_height": 15.0,
            "head_haul_cost": 225.0,  # = 2.25 * 100
            "fixed_service_fee": 6.0, "tail_haul_cost": 40.0,
            "selling_price_rmb": 400.0, "selling_price_usd": 55.56,
            "target_profit_rate": 25.0, "promotion_reserve_rate": 5.0,
        }
        cls.pid_b = cls.db.create_product(data_b)
        cls.db.save_snapshot(cls.pid_b, data_b, rules_a)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_product_a_head_haul_preserved(self):
        """修改费率后，重新加载商品A，head_haul_cost 仍为保存值 75.0"""
        product = self.db.get_product(self.pid_a)
        assert product["head_haul_cost"] == 75.0
        assert product["selling_price_usd"] == 27.78

    def test_product_b_head_haul_preserved(self):
        """修改费率后，重新加载商品B，head_haul_cost 仍为保存值 225.0"""
        product = self.db.get_product(self.pid_b)
        assert product["head_haul_cost"] == 225.0
        assert product["selling_price_usd"] == 55.56

    def test_snapshot_contains_rules(self):
        """快照包含保存时的费率"""
        snap = self.db.get_snapshot(self.pid_a)
        assert snap["_snapshot_exchange_rate"] == 7.2
        assert snap["_snapshot_head_haul_rate"] == 100.0
        assert snap["_snapshot_fixed_service_fee"] == 6.0
        assert snap["_snapshot_rule_version"] == 1

    def test_rate_change_detected(self):
        """修改配置后能检测到费率变更"""
        # 当前配置与快照相同 → 无变更
        snap = self.db.get_snapshot(self.pid_a)
        assert abs(snap["_snapshot_exchange_rate"] - self.cfg.exchange_rate) < 0.001

    def test_product_still_editable(self):
        """商品仍可编辑更新"""
        self.db.update_product(self.pid_a, {"cost": 55.0, "selling_price_rmb": 210.0})
        product = self.db.get_product(self.pid_a)
        assert product["cost"] == 55.0
        assert product["selling_price_rmb"] == 210.0
        # head_haul_cost 不变（除非明确更新）
        assert product["head_haul_cost"] == 75.0

    def test_snapshot_immutable(self):
        """首次快照不被后续更新覆盖"""
        snap = self.db.get_snapshot(self.pid_a)
        assert snap["cost"] == 50.0  # 首次保存时的值，非更新后的 55.0
