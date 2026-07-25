"""
历史商品加载与费率不变性测试 — fix_03

验证：快照含新规则字段、历史产品不受当前费率影响
"""

import sys, os, shutil, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from database.db_manager import DatabaseManager
from config.config_manager import ConfigManager


class TestHistoricalProduct:
    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "history_test.db")
        cls.db = DatabaseManager(cls.db_path)
        cls.cfg = ConfigManager(cls.db)

        data_a = {
            "name": "商品A", "cost": 50.0, "domestic_shipping": 10.0,
            "packaged_weight": 0.5, "packaged_length": 30.0,
            "packaged_width": 20.0, "packaged_height": 10.0,
            "freight_forwarder": "yiwu",
            "head_haul_cost": 75.0,
            "fixed_service_fee": 6.0, "tail_haul_cost": 40.0,
            "selling_price_rmb": 200.0, "selling_price_usd": 27.78,
            "target_profit_rate": 30.0, "promotion_reserve_rate": 10.0,
        }
        cls.pid_a = cls.db.create_product(data_a)
        rules_a = {
            "exchange_rate": 7.2, "head_haul_rate": 100.0, "fixed_service_fee": 6.0,
            "tail_haul_cost": 40.0, "volume_divisor": 8000,
            "forwarder": "yiwu", "rule_version": 2,
        }
        cls.db.save_snapshot(cls.pid_a, data_a, rules_a)

        data_b = {
            "name": "商品B", "cost": 80.0, "domestic_shipping": 12.0,
            "packaged_weight": 1.2, "packaged_length": 40.0,
            "packaged_width": 30.0, "packaged_height": 15.0,
            "freight_forwarder": "shenzhen",
            "head_haul_cost": 180.0,
            "fixed_service_fee": 10.0, "tail_haul_cost": 40.0,
            "selling_price_rmb": 400.0, "selling_price_usd": 55.56,
            "target_profit_rate": 25.0, "promotion_reserve_rate": 5.0,
        }
        cls.pid_b = cls.db.create_product(data_b)
        rules_b = {
            "exchange_rate": 7.2, "head_haul_rate": 80.0, "fixed_service_fee": 10.0,
            "tail_haul_cost": 40.0, "volume_divisor": 8000,
            "forwarder": "shenzhen", "rule_version": 2,
        }
        cls.db.save_snapshot(cls.pid_b, data_b, rules_b)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_product_a_forwarder_preserved(self):
        p = self.db.get_product(self.pid_a)
        assert p["freight_forwarder"] == "yiwu"
        assert p["head_haul_cost"] == 75.0

    def test_product_b_forwarder_preserved(self):
        p = self.db.get_product(self.pid_b)
        assert p["freight_forwarder"] == "shenzhen"
        assert p["head_haul_cost"] == 180.0

    def test_snapshot_full_rules(self):
        snap = self.db.get_snapshot(self.pid_a)
        assert snap["_snapshot_rule_version"] == 2
        assert snap["_snapshot_tail_haul_cost"] == 40.0
        assert snap["_snapshot_volume_divisor"] == 8000
        assert snap["_snapshot_rule_full"] is not None
        assert snap["_snapshot_rule_full"]["forwarder"] == "yiwu"

    def test_product_still_editable(self):
        self.db.update_product(self.pid_a, {"cost": 55.0})
        p = self.db.get_product(self.pid_a)
        assert p["cost"] == 55.0
        assert p["head_haul_cost"] == 75.0  # 不变

    def test_snapshot_immutable(self):
        snap = self.db.get_snapshot(self.pid_a)
        assert snap["cost"] == 50.0  # 首次保存的值
