"""
旧数据库迁移测试（fix_02 新增）

模拟：打开一个旧版 DB（fixed=36, tail=0, 无 schema_version, 快照无规则列）
验证：DatabaseManager 能正确迁移、不崩溃、配置正确更新
"""

import sys
import os
import shutil
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import DatabaseManager


class TestMigration:
    """旧数据库 → 新版本迁移"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "migrate_test.db")

        # 创建旧版数据库（36/0, 无schema_version, 快照无规则列）
        import sqlite3, json
        from datetime import datetime
        conn = sqlite3.connect(cls.db_path)
        conn.executescript("""
        CREATE TABLE products (
            id TEXT PRIMARY KEY, name TEXT DEFAULT '', cost REAL, domestic_shipping REAL,
            net_weight REAL, net_length REAL, net_width REAL, net_height REAL,
            packaged_weight REAL, packaged_length REAL, packaged_width REAL, packaged_height REAL,
            head_haul_cost REAL, fixed_service_fee REAL, tail_haul_cost REAL,
            shein_price REAL, selling_price_rmb REAL, selling_price_usd REAL,
            target_profit_rate REAL, promotion_reserve_rate REAL,
            notes TEXT DEFAULT '', status TEXT DEFAULT 'active', image_path TEXT DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE product_snapshots (
            id TEXT PRIMARY KEY, product_id TEXT NOT NULL UNIQUE,
            snapshot_data TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)

        # 插入旧默认配置
        conn.execute("INSERT INTO config VALUES ('exchange_rate', '7.20')")
        conn.execute("INSERT INTO config VALUES ('head_haul_rate', '100.0')")
        conn.execute("INSERT INTO config VALUES ('fixed_service_fee', '36.0')")
        conn.execute("INSERT INTO config VALUES ('default_tail_haul', '0.0')")

        # 插入一条旧商品
        now = datetime.now().isoformat()
        conn.execute("""INSERT INTO products VALUES (
            'old_prod', '旧商品', 50.0, 10.0,
            0.5, 30.0, 20.0, 10.0,
            0.5, 30.0, 20.0, 10.0,
            75.0, 36.0, 0.0,
            NULL, 150.0, 20.83,
            30.0, 10.0,
            '', 'active', '',
            ?, ?
        )""", (now, now))
        conn.execute("INSERT INTO product_snapshots VALUES ('snap1', 'old_prod', ?, ?)",
                     (json.dumps({"name": "旧商品"}), now))
        conn.commit()
        conn.close()

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_migration_adds_schema_version(self):
        """迁移后 schema_version = 1"""
        db = DatabaseManager(self.db_path)
        assert db.get_schema_version() == 1

    def test_migration_updates_config(self):
        """旧默认值 36/0 → 6/40"""
        db = DatabaseManager(self.db_path)
        assert float(db.get_config("fixed_service_fee", "0")) == 6.0
        assert float(db.get_config("default_tail_haul", "0")) == 40.0

    def test_migration_adds_snapshot_columns(self):
        """快照表自动补列（exchange_rate, head_haul_rate, rule_version）"""
        db = DatabaseManager(self.db_path)
        snap = db.get_snapshot("old_prod")
        assert snap is not None
        assert "_snapshot_exchange_rate" in snap
        assert "_snapshot_head_haul_rate" in snap
        assert "_snapshot_rule_version" in snap

    def test_old_product_still_accessible(self):
        """迁移后旧商品数据完整可读"""
        db = DatabaseManager(self.db_path)
        product = db.get_product("old_prod")
        assert product is not None
        assert product["name"] == "旧商品"
        assert product["cost"] == 50.0
        assert product["selling_price_rmb"] == 150.0

    def test_migration_idempotent(self):
        """第二次打开相同DB不会重复迁移"""
        db1 = DatabaseManager(self.db_path)
        v1 = db1.get_schema_version()
        db2 = DatabaseManager(self.db_path)
        v2 = db2.get_schema_version()
        assert v1 == v2 == 1
