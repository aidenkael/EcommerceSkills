"""phase_01_fix_06：数据库当前状态、迁移和原子保存测试。"""

import json
import os
import sqlite3
from unittest.mock import patch

import pytest

from database.db_manager import DatabaseManager


def _state(name="商品", forwarder="yiwu", head_rate=100.0, fixed_fee=6.0):
    data = {
        "name": name,
        "cost": 50.0,
        "domestic_shipping": 8.0,
        "freight_forwarder": forwarder,
        "head_haul_cost": 50.0,
        "fixed_service_fee": fixed_fee,
        "tail_haul_cost": 40.0,
        "selling_price_rmb": 200.0,
    }
    rules = {
        "exchange_rate": 7.2,
        "head_haul_rate": head_rate,
        "fixed_service_fee": fixed_fee,
        "tail_haul_cost": 40.0,
        "volume_divisor": 8000,
        "forwarder": forwarder,
        "rule_version": 2,
    }
    results = {
        "calculation_schema_version": 1,
        "head_haul_cost": 50.0,
        "total_logistics_cost": 96.0,
        "total_cost": 154.0,
        "net_profit_amount": 26.0,
        "net_profit_rate": 13.0,
    }
    return data, rules, results


def test_current_state_updates_while_initial_snapshot_stays_immutable(tmp_path):
    db = DatabaseManager(str(tmp_path / "state.db"))
    data, rules, results = _state()
    pid = db.save_product_state(data, rules, results)

    changed_data, changed_rules, changed_results = _state(
        name="已切深圳", forwarder="shenzhen", head_rate=80.0, fixed_fee=10.0
    )
    changed_results["head_haul_cost"] = 40.0
    db.save_product_state(changed_data, changed_rules, changed_results, pid=pid)

    product = db.get_product(pid)
    assert product["freight_forwarder"] == "shenzhen"
    assert product["_current_rule_snapshot"]["forwarder"] == "shenzhen"
    assert product["_current_rule_snapshot"]["head_haul_rate"] == 80.0
    assert product["_current_calculation_results"]["head_haul_cost"] == 40.0

    snapshot = db.get_snapshot(pid)
    assert snapshot["name"] == "商品"
    assert snapshot["_snapshot_rule_full"]["forwarder"] == "yiwu"
    assert snapshot["_calculation_results"]["head_haul_cost"] == 50.0


def test_first_save_rolls_back_product_when_snapshot_fails(tmp_path):
    path = str(tmp_path / "atomic.db")
    db = DatabaseManager(path)
    data, rules, results = _state()

    with patch.object(
        DatabaseManager, "_insert_initial_snapshot", side_effect=RuntimeError("snapshot failed")
    ):
        with pytest.raises(RuntimeError, match="snapshot failed"):
            db.save_product_state(data, rules, results)

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM product_snapshots").fetchone()[0] == 0
    finally:
        conn.close()


def test_v0_without_products_table_migrates_to_v3(tmp_path):
    path = str(tmp_path / "empty-v0.db")
    sqlite3.connect(path).close()

    db = DatabaseManager(path)

    assert db.get_schema_version() == 3
    conn = sqlite3.connect(path)
    try:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(product_snapshots)").fetchall()
        }
        assert {
            "exchange_rate",
            "head_haul_rate",
            "fixed_service_fee",
            "tail_haul_cost",
            "volume_divisor",
            "rule_version",
            "rule_snapshot",
        } <= columns
    finally:
        conn.close()


def test_v0_snapshot_record_missing_all_rule_columns_migrates(tmp_path):
    path = str(tmp_path / "minimal-v0.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE products (
            id TEXT PRIMARY KEY, name TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE product_snapshots (
            id TEXT PRIMARY KEY, product_id TEXT, snapshot_data TEXT, created_at TEXT
        );
        INSERT INTO products VALUES ('p1', '旧商品', 'old', 'old');
        """
    )
    conn.execute(
        "INSERT INTO product_snapshots VALUES ('s1', 'p1', ?, 'old')",
        (json.dumps({"name": "旧商品"}, ensure_ascii=False),),
    )
    conn.commit()
    conn.close()

    db = DatabaseManager(path)

    snapshot = db.get_snapshot("p1")
    product = db.get_product("p1")
    assert db.get_schema_version() == 3
    assert snapshot["name"] == "旧商品"
    assert snapshot["_snapshot_exchange_rate"] is None
    assert snapshot["_snapshot_head_haul_rate"] is None
    assert snapshot["_snapshot_fixed_service_fee"] is None
    assert snapshot["_snapshot_rule_version"] == 1
    assert product["cost"] is None
    assert product["_current_rule_snapshot"] is None


def test_existing_rule_version_one_is_upgraded(tmp_path):
    path = str(tmp_path / "rule-v1.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (2, 'old');
        CREATE TABLE business_rule_version (
            version INTEGER PRIMARY KEY, description TEXT, applied_at TEXT NOT NULL
        );
        INSERT INTO business_rule_version VALUES (1, 'old rule', 'old');
        """
    )
    conn.commit()
    conn.close()

    db = DatabaseManager(path)

    assert db.get_schema_version() == 3
    assert db.get_rule_version() == 2


def test_future_schema_is_rejected_without_mutation(tmp_path):
    path = str(tmp_path / "future.db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO schema_version VALUES (99, 'future')")
    conn.commit()
    conn.close()
    before = open(path, "rb").read()

    with pytest.raises(RuntimeError, match="高于程序支持"):
        DatabaseManager(path)

    assert open(path, "rb").read() == before


def test_migration_failure_restores_original_database(tmp_path):
    path = str(tmp_path / "rollback.db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO schema_version VALUES (2, 'old')")
    conn.execute("CREATE TABLE marker (value TEXT)")
    conn.execute("INSERT INTO marker VALUES ('original')")
    conn.commit()
    conn.close()
    before = open(path, "rb").read()

    with patch.object(
        DatabaseManager, "_apply_migration", side_effect=RuntimeError("forced migration failure")
    ):
        with pytest.raises(RuntimeError, match="forced migration failure"):
            DatabaseManager(path)

    assert open(path, "rb").read() == before
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT value FROM marker").fetchone()[0] == "original"
    finally:
        conn.close()
