"""
数据库模块测试 — Schema v3

P0修复：
- schema version 3
- route_config 表
- 不再有全局 head_haul_rate/fixed_service_fee config
"""

import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from database.db_manager import DatabaseManager


class TestDatabase:
    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "test.db")
        cls.db = DatabaseManager(cls.db_path)

    @classmethod
    def teardown_class(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_schema_version_is_3(self):
        assert self.db.get_schema_version() == 3

    def test_config_defaults(self):
        assert float(self.db.get_config("exchange_rate", "0")) == 7.20
        assert float(self.db.get_config("default_tail_haul", "0")) == 40.0

    def test_route_config_exists(self):
        routes = self.db.get_all_routes()
        assert len(routes) == 2
        forwarders = [r["forwarder"] for r in routes]
        assert "shenzhen" in forwarders
        assert "yiwu" in forwarders

    def test_shenzhen_rates(self):
        r = self.db.get_route_rates("shenzhen")
        assert r["head_haul_rate"] == 80.0
        assert r["fixed_service_fee"] == 10.0

    def test_yiwu_rates(self):
        r = self.db.get_route_rates("yiwu")
        assert r["head_haul_rate"] == 100.0
        assert r["fixed_service_fee"] == 6.0

    def test_config_set_get(self):
        self.db.set_config("exchange_rate", "7.50")
        assert self.db.get_config("exchange_rate") == "7.50"
        self.db.set_config("exchange_rate", "7.20")

    def test_create_product_with_freight_forwarder(self):
        pid = self.db.create_product({
            "name": "深圳商品", "cost": 50.0, "freight_forwarder": "shenzhen",
            "selling_price_rmb": 120.0,
        })
        product = self.db.get_product(pid)
        assert product["name"] == "深圳商品"
        assert product["freight_forwarder"] == "shenzhen"
        self.db.delete_product(pid)

    def test_create_product_without_forwarder(self):
        pid = self.db.create_product({"name": "无货代商品", "cost": 30.0})
        product = self.db.get_product(pid)
        assert product["freight_forwarder"] is None
        self.db.delete_product(pid)

    def test_update_product(self):
        pid = self.db.create_product({"name": "原名称", "cost": 100.0})
        self.db.update_product(pid, {"name": "新名称", "cost": 120.0, "freight_forwarder": "yiwu"})
        product = self.db.get_product(pid)
        assert product["name"] == "新名称"
        assert product["freight_forwarder"] == "yiwu"
        self.db.delete_product(pid)

    def test_search_products(self):
        pid1 = self.db.create_product({"name": "红色连衣裙"})
        pid2 = self.db.create_product({"name": "蓝色T恤", "freight_forwarder": "shenzhen"})
        results = self.db.search_products("红色")
        assert len(results) >= 1
        self.db.delete_product(pid1)
        self.db.delete_product(pid2)

    def test_delete_product(self):
        pid = self.db.create_product({"name": "待删除"})
        self.db.delete_product(pid)
        assert self.db.get_product(pid) is None

    def test_snapshot_with_full_rules(self):
        data = {"name": "快照商品", "cost": 88.0, "freight_forwarder": "yiwu"}
        rules = {
            "exchange_rate": 7.2, "head_haul_rate": 100.0, "fixed_service_fee": 6.0,
            "tail_haul_cost": 40.0, "volume_divisor": 8000, "forwarder": "yiwu", "rule_version": 2
        }
        pid = self.db.create_product(data)
        self.db.save_snapshot(pid, data, rules)
        snap = self.db.get_snapshot(pid)
        assert snap["_snapshot_exchange_rate"] == 7.2
        assert snap["_snapshot_rule_version"] == 2
        assert snap["_snapshot_volume_divisor"] == 8000
        assert snap["_snapshot_tail_haul_cost"] == 40.0
        assert snap["_snapshot_rule_full"] is not None
        assert snap["_snapshot_rule_full"]["forwarder"] == "yiwu"
        self.db.delete_product(pid)

    def test_get_nonexistent(self):
        assert self.db.get_product("nonexistent") is None
        assert self.db.get_snapshot("nonexistent") is None

    def test_rule_version(self):
        assert self.db.get_rule_version() == 2
