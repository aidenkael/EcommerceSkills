"""
数据库模块测试（更新版）

P0修复：
- 默认配置：6元固定费 + 40元尾程
- schema_version 表
- 快照含规则版本
- 配置迁移机制
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

    def test_schema_version_exists(self):
        """schema_version 表存在且版本为 1"""
        assert self.db.get_schema_version() == 1

    def test_config_defaults(self):
        """默认配置：6元固定费 + 40元尾程"""
        assert float(self.db.get_config("exchange_rate", "0")) == 7.20
        assert float(self.db.get_config("head_haul_rate", "0")) == 100.0
        assert float(self.db.get_config("fixed_service_fee", "0")) == 6.0
        assert float(self.db.get_config("default_tail_haul", "0")) == 40.0

    def test_config_set_get(self):
        self.db.set_config("exchange_rate", "7.50")
        assert self.db.get_config("exchange_rate") == "7.50"
        self.db.set_config("exchange_rate", "7.20")

    def test_create_product(self):
        pid = self.db.create_product({"name": "测试商品", "cost": 50.0, "selling_price_rmb": 120.0})
        assert pid is not None
        assert len(pid) == 8
        product = self.db.get_product(pid)
        assert product["name"] == "测试商品"
        assert product["cost"] == 50.0
        self.db.delete_product(pid)

    def test_update_product(self):
        pid = self.db.create_product({"name": "原名称", "cost": 100.0})
        self.db.update_product(pid, {"name": "新名称", "cost": 120.0})
        product = self.db.get_product(pid)
        assert product["name"] == "新名称"
        assert product["cost"] == 120.0
        self.db.delete_product(pid)

    def test_search_products(self):
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
        pid = self.db.create_product({"name": "待删除"})
        self.db.delete_product(pid)
        assert self.db.get_product(pid) is None

    def test_snapshot_with_rules(self):
        """快照保存含规则信息"""
        data = {"name": "快照测试", "cost": 88.0}
        rules = {"exchange_rate": 7.2, "head_haul_rate": 100.0, "fixed_service_fee": 6.0}
        pid = self.db.create_product(data)
        self.db.save_snapshot(pid, data, rules)

        snap = self.db.get_snapshot(pid)
        assert snap is not None
        assert snap["name"] == "快照测试"
        assert snap["_snapshot_exchange_rate"] == 7.2
        assert snap["_snapshot_head_haul_rate"] == 100.0
        assert snap["_snapshot_fixed_service_fee"] == 6.0
        assert snap["_snapshot_rule_version"] == 1

        # 再次保存不覆盖
        data2 = {"name": "新数据", "cost": 99.0}
        self.db.save_snapshot(pid, data2, {"exchange_rate": 8.0})
        snap2 = self.db.get_snapshot(pid)
        assert snap2["name"] == "快照测试"

        self.db.delete_product(pid)

    def test_get_nonexistent(self):
        assert self.db.get_product("nonexistent") is None
        assert self.db.get_snapshot("nonexistent") is None

    def test_config_migration(self):
        """配置迁移：旧值 36/0 应被更新（仅首次初始化时触发）"""
        # 模拟旧值 + 清除迁移标记
        self.db.set_config("fixed_service_fee", "36.0")
        self.db.set_config("default_tail_haul", "0.0")
        self.db.set_config("_config_migrated_v1", "0")  # 重置迁移标记

        # 重新初始化（触发迁移）
        db2 = DatabaseManager(self.db_path)
        assert float(db2.get_config("fixed_service_fee", "0")) == 6.0
        assert float(db2.get_config("default_tail_haul", "0")) == 40.0
        assert db2.get_config("_config_migrated_v1") == "1"  # 标记已设置
