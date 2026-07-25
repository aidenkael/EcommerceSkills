"""
数据库模块测试

覆盖：创建、读取、更新、删除、搜索、快照、配置
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import DatabaseManager


class TestDatabase:
    """数据库 CRUD 测试"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "test.db")
        cls.db = DatabaseManager(cls.db_path)

    @classmethod
    def teardown_class(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_config_defaults(self):
        """默认配置存在"""
        assert float(self.db.get_config("exchange_rate", "0")) == 7.20
        assert float(self.db.get_config("head_haul_rate", "0")) == 100.0
        assert float(self.db.get_config("fixed_service_fee", "0")) == 36.0

    def test_config_set_get(self):
        """配置读写"""
        self.db.set_config("exchange_rate", "7.50")
        assert self.db.get_config("exchange_rate") == "7.50"
        self.db.set_config("exchange_rate", "7.20")  # 恢复

    def test_create_product(self):
        """创建商品"""
        data = {
            "name": "测试商品",
            "cost": 50.0,
            "selling_price_rmb": 120.0,
            "target_profit_rate": 30.0,
        }
        pid = self.db.create_product(data)
        assert pid is not None
        assert len(pid) == 8

        product = self.db.get_product(pid)
        assert product["name"] == "测试商品"
        assert product["cost"] == 50.0

        # 清理
        self.db.delete_product(pid)

    def test_update_product(self):
        """更新商品"""
        pid = self.db.create_product({"name": "原名称", "cost": 100.0})
        self.db.update_product(pid, {"name": "新名称", "cost": 120.0})

        product = self.db.get_product(pid)
        assert product["name"] == "新名称"
        assert product["cost"] == 120.0

        self.db.delete_product(pid)

    def test_search_products(self):
        """搜索商品"""
        pid1 = self.db.create_product({"name": "红色连衣裙"})
        pid2 = self.db.create_product({"name": "蓝色T恤"})

        results = self.db.search_products("红色")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "红色连衣裙" in names

        results_empty = self.db.search_products("不存在的")
        assert len(results_empty) == 0

        self.db.delete_product(pid1)
        self.db.delete_product(pid2)

    def test_delete_product(self):
        """删除商品"""
        pid = self.db.create_product({"name": "待删除"})
        self.db.delete_product(pid)
        assert self.db.get_product(pid) is None

    def test_snapshot(self):
        """快照保存与读取"""
        data = {"name": "快照测试", "cost": 88.0}
        pid = self.db.create_product(data)
        self.db.save_snapshot(pid, data)

        snap = self.db.get_snapshot(pid)
        assert snap is not None
        assert snap["name"] == "快照测试"
        assert snap["cost"] == 88.0

        # 再次保存不应覆盖
        data2 = {"name": "新数据", "cost": 99.0}
        self.db.save_snapshot(pid, data2)
        snap2 = self.db.get_snapshot(pid)
        assert snap2["name"] == "快照测试"  # 仍然是第一份

        self.db.delete_product(pid)

    def test_get_nonexistent(self):
        """读取不存在商品返回 None"""
        assert self.db.get_product("nonexistent") is None
        assert self.db.get_snapshot("nonexistent") is None
