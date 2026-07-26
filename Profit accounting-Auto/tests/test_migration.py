"""
旧数据库迁移测试 — v0/v1 → v3

模拟旧版DB(无freight_forwarder, 无route_config, schema v1)
验证：迁移后 schema=3, 货代表存在, 旧数据保留
"""

import sys, os, shutil, tempfile, sqlite3, json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from database.db_manager import DatabaseManager


class TestMigration:
    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "migrate_test.db")
        conn = sqlite3.connect(cls.db_path)
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
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
            snapshot_data TEXT NOT NULL, exchange_rate REAL, head_haul_rate REAL,
            fixed_service_fee REAL, rule_version INTEGER DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        conn.execute("INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (1, ?)", (datetime.now().isoformat(),))
        conn.execute("INSERT INTO config VALUES ('exchange_rate', '7.20')")
        conn.execute("INSERT INTO config VALUES ('default_tail_haul', '40.0')")
        conn.execute("INSERT INTO config VALUES ('_config_migrated_v1', '1')")
        now = datetime.now().isoformat()
        conn.execute("""INSERT INTO products VALUES (
            'old_prod', '旧商品', 50.0, 10.0,
            0.5, 30.0, 20.0, 10.0, 0.5, 30.0, 20.0, 10.0,
            75.0, 36.0, 0.0,
            NULL, 150.0, 20.83,
            30.0, 10.0, '', 'active', '', ?, ?
        )""", (now, now))
        conn.execute("INSERT INTO product_snapshots VALUES ('snap1', 'old_prod', ?, 7.2, 100.0, 36.0, 1, ?)",
                     (json.dumps({"name": "旧商品"}), now))
        conn.commit()
        conn.close()

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_migration_to_v3(self):
        db = DatabaseManager(self.db_path)
        assert db.get_schema_version() == 4

    def test_route_config_created(self):
        db = DatabaseManager(self.db_path)
        routes = db.get_all_routes()
        assert len(routes) == 2

    def test_old_product_preserved(self):
        db = DatabaseManager(self.db_path)
        p = db.get_product("old_prod")
        assert p is not None
        assert p["name"] == "旧商品"
        assert p["cost"] == 50.0
        assert p["freight_forwarder"] is None  # 旧商品无货代

    def test_old_snapshot_preserved(self):
        db = DatabaseManager(self.db_path)
        snap = db.get_snapshot("old_prod")
        assert snap is not None
        assert "_snapshot_exchange_rate" in snap

    def test_migration_idempotent(self):
        db1 = DatabaseManager(self.db_path)
        v1 = db1.get_schema_version()
        db2 = DatabaseManager(self.db_path)
        assert v1 == db2.get_schema_version() == 4
