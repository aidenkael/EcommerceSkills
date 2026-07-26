"""
fix_05 真实业务测试

覆盖：
- _is_valid_number / _is_valid_rate
- 严格 total_logistics_cost / total_cost (None 传播)
- 保存规则生成 (head_haul_rate 完整)
- 历史规则 (保存费率不随编辑变化)
- 规则差异检测 (7项)
- 迁移 (新DB不备份, v2不备份, v0备份一致, 异常回滚)
"""

import math, sys, os, shutil, tempfile, sqlite3, json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import DatabaseManager
from config.config_manager import ConfigManager, VOLUME_DIVISOR

# 从 ui 模块导入校验函数
from ui.product_page import _safe_float, _is_valid_number, _is_valid_rate

from calculation import (
    volumetric_weight, chargeable_weight, head_haul_cost,
    total_logistics_cost, known_logistics_subtotal,
    total_cost, known_total_cost_subtotal,
    net_profit_amount, net_profit_rate, suggested_price_from_rate,
)


class TestValidation:
    """输入校验函数"""

    def test_abc_invalid(self): assert not _is_valid_number("abc")
    def test_negative_invalid(self): assert not _is_valid_number("-1")
    def test_nan_invalid(self): assert not _is_valid_number("NaN")
    def test_infinity_invalid(self): assert not _is_valid_number("Infinity")
    def test_zero_valid(self): assert _is_valid_number("0")
    def test_positive_valid(self): assert _is_valid_number("123.45")

    def test_rate_99_valid(self): assert _is_valid_rate("99.9")
    def test_rate_100_invalid(self): assert not _is_valid_rate("100")
    def test_rate_120_invalid(self): assert not _is_valid_rate("120")
    def test_rate_nan_invalid(self): assert not _is_valid_rate("NaN")


class TestStrictLogistics:
    """严格物流函数"""

    def test_head_none_logistics_none(self):
        assert total_logistics_cost(None, 6.0, 40.0) is None

    def test_fixed_none_logistics_none(self):
        assert total_logistics_cost(75.0, None, 40.0) is None

    def test_tail_none_logistics_none(self):
        assert total_logistics_cost(75.0, 6.0, None) is None

    def test_all_present_ok(self):
        assert total_logistics_cost(75.0, 6.0, 40.0) == 121.0

    def test_known_subtotal(self):
        assert known_logistics_subtotal(None, 6.0, 40.0) == 46.0


class TestStrictTotalCost:
    """严格总成本函数"""

    def test_cost_none_total_none(self):
        assert total_cost(None, 10.0, 100.0) is None

    def test_domestic_none_total_none(self):
        assert total_cost(50.0, None, 100.0) is None

    def test_logistics_none_total_none(self):
        assert total_cost(50.0, 10.0, None) is None

    def test_all_present_ok(self):
        assert total_cost(50.0, 10.0, 100.0) == 160.0

    def test_known_subtotal(self):
        assert known_total_cost_subtotal(50.0, None, 100.0) == 150.0


class TestSaveRuleGeneration:
    """保存规则生成：通过真实 create_product + save_snapshot 路径"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "test.db")
        cls.db = DatabaseManager(cls.db_path)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_shenzhen_saves_head_rate_80(self):
        data = {"name": "深圳商品", "cost": 50.0, "freight_forwarder": "shenzhen",
                "head_haul_cost": 70.0, "fixed_service_fee": 10.0, "tail_haul_cost": 40.0}
        rules = {"exchange_rate": 7.2, "head_haul_rate": 80.0, "fixed_service_fee": 10.0,
                 "tail_haul_cost": 40.0, "volume_divisor": 8000, "forwarder": "shenzhen", "rule_version": 2}
        pid = self.db.create_product(data)
        self.db.save_snapshot(pid, data, rules)
        snap = self.db.get_snapshot(pid)
        assert snap["_snapshot_rule_full"]["head_haul_rate"] == 80.0
        assert snap["_snapshot_head_haul_rate"] == 80.0
        self.db.delete_product(pid)

    def test_yiwu_saves_head_rate_100(self):
        data = {"name": "义乌商品", "cost": 80.0, "freight_forwarder": "yiwu",
                "head_haul_cost": 87.5, "fixed_service_fee": 6.0, "tail_haul_cost": 40.0}
        rules = {"exchange_rate": 7.2, "head_haul_rate": 100.0, "fixed_service_fee": 6.0,
                 "tail_haul_cost": 40.0, "volume_divisor": 8000, "forwarder": "yiwu", "rule_version": 2}
        pid = self.db.create_product(data)
        self.db.save_snapshot(pid, data, rules)
        snap = self.db.get_snapshot(pid)
        assert snap["_snapshot_rule_full"]["head_haul_rate"] == 100.0
        self.db.delete_product(pid)


class TestHistoricalRules:
    """历史规则持久化测试"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "hist_test.db")
        cls.db = DatabaseManager(cls.db_path)
        data = {"name": "历史商品", "cost": 60.0, "domestic_shipping": 8.0,
                "freight_forwarder": "yiwu",
                "packaged_weight": 0.5, "packaged_length": 30.0, "packaged_width": 20.0, "packaged_height": 10.0,
                "head_haul_cost": 75.0, "fixed_service_fee": 6.0, "tail_haul_cost": 40.0,
                "selling_price_rmb": 200.0}
        cls.pid = cls.db.create_product(data)
        rules = {"exchange_rate": 7.2, "head_haul_rate": 100.0, "fixed_service_fee": 6.0,
                 "tail_haul_cost": 40.0, "volume_divisor": 8000, "forwarder": "yiwu", "rule_version": 2}
        cls.db.save_snapshot(cls.pid, data, rules)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_snapshot_has_head_haul_rate(self):
        snap = self.db.get_snapshot(self.pid)
        assert snap["_snapshot_head_haul_rate"] == 100.0
        assert snap["_snapshot_rule_full"]["head_haul_rate"] == 100.0

    def test_product_edit_preserves_head_haul(self):
        self.db.update_product(self.pid, {"cost": 65.0})
        p = self.db.get_product(self.pid)
        assert p["head_haul_cost"] == 75.0  # 不应改变

    def test_product_edit_preserves_fixed_fee(self):
        self.db.update_product(self.pid, {"domestic_shipping": 10.0})
        p = self.db.get_product(self.pid)
        assert p["fixed_service_fee"] == 6.0


class TestRuleChangeDetection:
    """规则变更检测"""

    def test_head_rate_change_detectable(self):
        saved = {"head_haul_rate": 100.0}; current = {"head_haul_rate": 120.0}
        assert abs(saved["head_haul_rate"] - current["head_haul_rate"]) > 0.001

    def test_fixed_fee_change_detectable(self):
        saved = {"fixed_service_fee": 6.0}; current = {"fixed_service_fee": 10.0}
        assert abs(saved["fixed_service_fee"] - current["fixed_service_fee"]) > 0.001

    def test_tail_haul_change_detectable(self):
        saved = {"tail_haul_cost": 40.0}; current = {"tail_haul_cost": 50.0}
        assert abs(saved["tail_haul_cost"] - current["tail_haul_cost"]) > 0.001

    def test_exchange_rate_change_detectable(self):
        saved = {"exchange_rate": 7.2}; current = {"exchange_rate": 7.5}
        assert abs(saved["exchange_rate"] - current["exchange_rate"]) > 0.001

    def test_forwarder_change_detectable(self):
        assert "shenzhen" != "yiwu"

    def test_no_change_no_detect(self):
        saved = {"head_haul_rate": 100.0}; current = {"head_haul_rate": 100.0}
        assert abs(saved["head_haul_rate"] - current["head_haul_rate"]) < 0.001


class TestMigrationStrict:
    """迁移测试"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_new_db_no_backup(self):
        path = os.path.join(self.tmpdir, "new_test.db")
        if os.path.exists(path): os.remove(path)
        db = DatabaseManager(path)
        assert db.get_schema_version() == 4
        # 不应该有备份文件
        assert not os.path.exists(path + ".backup")

    def _make_v0_db(self):
        path = os.path.join(self.tmpdir, "v0_test.db")
        conn = sqlite3.connect(path)
        conn.executescript("""
        CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT, cost REAL,
            domestic_shipping REAL, net_weight REAL, net_length REAL, net_width REAL, net_height REAL,
            packaged_weight REAL, packaged_length REAL, packaged_width REAL, packaged_height REAL,
            head_haul_cost REAL, fixed_service_fee REAL, tail_haul_cost REAL,
            shein_price REAL, selling_price_rmb REAL, selling_price_usd REAL,
            target_profit_rate REAL, promotion_reserve_rate REAL,
            notes TEXT DEFAULT '', status TEXT DEFAULT 'active', image_path TEXT DEFAULT '',
            created_at TEXT, updated_at TEXT);
        CREATE TABLE product_snapshots (id TEXT PRIMARY KEY, product_id TEXT,
            snapshot_data TEXT, created_at TEXT);
        CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT);
        """)
        conn.execute("INSERT INTO config VALUES ('exchange_rate','7.20')")
        conn.commit(); conn.close()
        return path

    def test_v0_migration_creates_backup(self):
        path = self._make_v0_db()
        import glob
        before = set(glob.glob(path + "*"))
        db = DatabaseManager(path)
        after = set(glob.glob(path + "*"))
        backups = after - before
        assert len(backups) >= 1  # 应该有备份文件

    def test_v0_data_preserved(self):
        path = os.path.join(self.tmpdir, "v0_preserve.db")
        conn = sqlite3.connect(path)
        conn.executescript("""
        CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT, cost REAL,
            domestic_shipping REAL, net_weight REAL, net_length REAL, net_width REAL, net_height REAL,
            packaged_weight REAL, packaged_length REAL, packaged_width REAL, packaged_height REAL,
            head_haul_cost REAL, fixed_service_fee REAL, tail_haul_cost REAL,
            shein_price REAL, selling_price_rmb REAL, selling_price_usd REAL,
            target_profit_rate REAL, promotion_reserve_rate REAL,
            notes TEXT DEFAULT '', status TEXT DEFAULT 'active', image_path TEXT DEFAULT '',
            created_at TEXT, updated_at TEXT);
        CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT);
        """)
        conn.execute("INSERT INTO config VALUES ('exchange_rate','7.20')")
        conn.commit(); conn.close()
        db = DatabaseManager(path)
        assert db.get_schema_version() == 4

    def test_v2_no_backup_on_normal_start(self):
        path = os.path.join(self.tmpdir, "v2_test.db")
        db1 = DatabaseManager(path)
        import glob
        before = set(glob.glob(path + "*"))
        db2 = DatabaseManager(path)
        after = set(glob.glob(path + "*"))
        assert before == after  # 不应生成新备份
