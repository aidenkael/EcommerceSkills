"""
fix_04 有效测试（保留）
"""

import sys, os, shutil, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from database.db_manager import DatabaseManager


class TestHistoricalPreserve:
    """历史商品保存不丢失头程"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "test.db")
        cls.db = DatabaseManager(cls.db_path)
        cls.data = {
            "name": "测试商品", "cost": 50.0, "domestic_shipping": 8.0,
            "packaged_weight": 0.5, "packaged_length": 30.0,
            "packaged_width": 20.0, "packaged_height": 10.0,
            "freight_forwarder": "yiwu", "head_haul_cost": 75.0,
            "fixed_service_fee": 6.0, "tail_haul_cost": 40.0,
            "selling_price_rmb": 200.0, "target_profit_rate": 30.0,
            "promotion_reserve_rate": 10.0,
        }
        cls.pid = cls.db.create_product(cls.data)
        cls.db.save_snapshot(cls.pid, cls.data, {"exchange_rate": 7.2, "head_haul_rate": 100.0,
            "fixed_service_fee": 6.0, "tail_haul_cost": 40.0, "volume_divisor": 8000,
            "forwarder": "yiwu", "rule_version": 2})

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_save_without_changes_preserves_head_haul(self):
        self.db.update_product(self.pid, {"name": "测试商品"})
        p = self.db.get_product(self.pid)
        assert p["head_haul_cost"] == 75.0

    def test_save_with_notes_only_preserves_head_haul(self):
        self.db.update_product(self.pid, {"notes": "新备注"})
        p = self.db.get_product(self.pid)
        assert p["head_haul_cost"] == 75.0

    def test_restore_snapshot_preserves(self):
        snap = self.db.get_snapshot(self.pid)
        assert snap["head_haul_cost"] == 75.0


class TestStrictCosts:
    """严格成本缺失"""

    def test_head_none_logistics_none(self):
        from calculation import total_logistics_cost
        assert total_logistics_cost(None, 6.0, 40.0) is None

    def test_cost_none_total_none(self):
        from calculation import total_cost
        assert total_cost(None, 10.0, 100.0) is None
