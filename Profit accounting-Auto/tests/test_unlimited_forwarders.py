import json
import sqlite3
from unittest.mock import patch

import pytest

from calculation import chargeable_weight, grams_to_kg, volumetric_weight
from config.forwarder_manager import ForwarderManager
from database.db_manager import DatabaseManager


def route(name, **changes):
    data = {"display_name": name, "head_haul_rate": 80, "fixed_service_fee": 10,
            "volume_divisor": 8000, "is_enabled": True, "description": ""}
    data.update(changes)
    return data


def test_can_create_twenty_routes_and_rules_are_independent(tmp_path):
    manager = ForwarderManager(DatabaseManager(str(tmp_path / "routes.db")))
    for i in range(20):
        manager.create(route(f"线路{i}", volume_divisor=6000 if i == 0 else 8000))
    routes = {r["display_name"]: r for r in manager.list()}
    assert len(routes) == 22
    assert volumetric_weight(40, 30, 20, routes["线路0"]["volume_divisor"]) == 4
    assert volumetric_weight(40, 30, 20, routes["线路1"]["volume_divisor"]) == 3


def test_name_validation_and_disable_archive_delete(tmp_path):
    db = DatabaseManager(str(tmp_path / "ops.db")); manager = ForwarderManager(db)
    rid = manager.create(route("可归档"))
    with pytest.raises(ValueError): manager.create(route(" 可归档 "))
    manager.set_enabled(rid, False)
    assert rid not in {r["route_id"] for r in manager.enabled()}
    pid = db.save_product_state({"name": "历史", "freight_forwarder": rid, "weight_unit_version": "g_v1"},
                                {"route_id": rid, "route_display_name": "可归档"}, {})
    assert manager.archive_or_delete(rid) == "archived"
    saved = db.get_product(pid)
    assert saved["_current_rule_snapshot"]["route_display_name"] == "可归档"
    unused = manager.create(route("可删除"))
    assert manager.archive_or_delete(unused) == "deleted"
    assert db.get_route_rates(unused) is None
    with pytest.raises(ValueError, match="货代不存在"):
        manager.archive_or_delete(unused)
    manager.restore(rid)
    restored = db.get_route_rates(rid)
    assert restored["is_archived"] is False
    assert restored["is_enabled"] is False


def test_v4_keys_migrate_to_uuid_in_products_and_snapshots(tmp_path):
    path = str(tmp_path / "v4.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (4, 'old');
        CREATE TABLE business_rule_version (
            version INTEGER PRIMARY KEY, description TEXT, applied_at TEXT NOT NULL
        );
        INSERT INTO business_rule_version VALUES (3, '双货代规则', 'old');
        CREATE TABLE products (
            id TEXT PRIMARY KEY, name TEXT, freight_forwarder TEXT,
            current_rule_snapshot TEXT, current_calculation_results TEXT,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE product_snapshots (
            id TEXT PRIMARY KEY, product_id TEXT NOT NULL UNIQUE,
            snapshot_data TEXT NOT NULL, rule_snapshot TEXT, created_at TEXT
        );
        CREATE TABLE route_config (
            route_key TEXT PRIMARY KEY, display_name TEXT NOT NULL,
            head_haul_rate REAL NOT NULL, fixed_service_fee REAL NOT NULL,
            volume_divisor REAL NOT NULL DEFAULT 8000,
            is_enabled INTEGER NOT NULL DEFAULT 1, description TEXT DEFAULT ''
        );
        CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO route_config VALUES ('shenzhen', '深圳旧名', 80, 10, 8000, 1, '');
        INSERT INTO route_config VALUES ('yiwu', '义乌', 100, 6, 8000, 1, '');
        """
    )
    rules = {
        "route_key": "shenzhen",
        "forwarder": "shenzhen",
        "route_display_name": "深圳旧名",
    }
    snapshot_data = {"name": "旧商品", "freight_forwarder": "shenzhen"}
    conn.execute(
        "INSERT INTO products VALUES (?,?,?,?,?,?,?)",
        ("p1", "旧商品", "shenzhen", json.dumps(rules), "{}", "old", "old"),
    )
    conn.execute(
        "INSERT INTO product_snapshots VALUES (?,?,?,?,?)",
        ("s1", "p1", json.dumps(snapshot_data), json.dumps(rules), "old"),
    )
    conn.commit()
    conn.close()

    migrated = DatabaseManager(path)
    routes = {route["display_name"]: route for route in migrated.get_all_routes()}
    route_id = routes["深圳旧名"]["route_id"]
    assert migrated.get_schema_version() == 7
    assert all(len(r["route_id"]) == 36 for r in migrated.get_all_routes())
    conn = sqlite3.connect(path)
    route_columns = {row[1]: row for row in conn.execute("PRAGMA table_info(route_config)")}
    assert route_columns["route_id"][3] == 1  # NOT NULL
    assert route_columns["route_id"][5] == 1  # PRIMARY KEY
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO route_config SELECT * FROM route_config LIMIT 1")
    conn.rollback()
    conn.close()
    product = migrated.get_product("p1")
    snapshot = migrated.get_snapshot("p1")
    assert product["freight_forwarder"] == route_id
    assert product["_current_rule_snapshot"]["route_id"] == route_id
    assert product["_current_rule_snapshot"]["route_display_name"] == "深圳旧名"
    assert snapshot["freight_forwarder"] == route_id
    assert snapshot["_snapshot_rule_full"]["forwarder"] == route_id
    assert snapshot["_snapshot_rule_full"]["route_display_name"] == "深圳旧名"

    extra = ForwarderManager(migrated).create(route("迁移后新增"))
    assert migrated.get_route_rates(extra)["display_name"] == "迁移后新增"
    reopened = DatabaseManager(path)
    assert reopened.get_product("p1")["freight_forwarder"] == route_id


def _make_legacy_v5(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (5, 'old');
        CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT, freight_forwarder TEXT,
            current_rule_snapshot TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE product_snapshots (id TEXT PRIMARY KEY, product_id TEXT NOT NULL UNIQUE,
            snapshot_data TEXT NOT NULL, rule_snapshot TEXT, created_at TEXT);
        CREATE TABLE route_config (route_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
            head_haul_rate REAL NOT NULL, fixed_service_fee REAL NOT NULL,
            volume_divisor REAL NOT NULL, is_enabled INTEGER NOT NULL,
            is_archived INTEGER NOT NULL, description TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    route_id = "legacy-v5-route"
    rules = {"route_id": route_id, "route_display_name": "V5旧货代", "forwarder": route_id}
    conn.execute("INSERT INTO route_config VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (route_id, "V5旧货代", 88, 7, 7000, 1, 0, "old", "old", "old"))
    conn.execute("INSERT INTO products VALUES (?,?,?,?,?,?)",
                 ("p-v5", "v5商品", route_id, json.dumps(rules), "old", "old"))
    conn.execute("INSERT INTO product_snapshots VALUES (?,?,?,?,?)",
                 ("s-v5", "p-v5", json.dumps({"freight_forwarder": route_id}), json.dumps(rules), "old"))
    conn.commit(); conn.close()
    return route_id


def test_legacy_non_strict_v5_migrates_to_v6_without_changing_uuid_or_snapshots(tmp_path):
    path = str(tmp_path / "legacy-v5.db")
    route_id = _make_legacy_v5(path)
    db = DatabaseManager(path)
    conn = sqlite3.connect(path)
    info = {row[1]: row for row in conn.execute("PRAGMA table_info(route_config)")}
    conn.close()
    assert db.get_schema_version() == 7
    assert info["route_id"][3] == 1 and info["route_id"][5] == 1
    assert db.get_product("p-v5")["freight_forwarder"] == route_id
    assert db.get_product("p-v5")["_current_rule_snapshot"]["route_display_name"] == "V5旧货代"
    assert db.get_snapshot("p-v5")["_snapshot_rule_full"]["route_id"] == route_id
    assert DatabaseManager(path).get_route_rates(route_id)["display_name"] == "V5旧货代"


def test_legacy_v5_rebuild_failure_restores_original_database(tmp_path):
    path = str(tmp_path / "v5-fail.db")
    _make_legacy_v5(path)
    with patch.object(DatabaseManager, "_rebuild_route_config_v6", side_effect=RuntimeError("forced")):
        with pytest.raises(RuntimeError, match="forced"):
            DatabaseManager(path)
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 5
    assert {row[1]: row for row in conn.execute("PRAGMA table_info(route_config)")}["route_id"][3] == 0
    conn.close()


def test_atomic_settings_reject_case_insensitive_duplicate_names(tmp_path):
    db = DatabaseManager(str(tmp_path / "duplicate.db"))
    routes = db.get_all_routes()
    before_rate = db.get_config("exchange_rate")
    routes[0].update(display_name="Forwarder", is_enabled=True)
    routes[1].update(display_name="forwarder", is_enabled=True)

    with pytest.raises(ValueError, match="名称不能重复"):
        db.save_settings_and_routes(
            {"exchange_rate": 9.9, "default_tail_haul": 40},
            routes,
        )

    assert db.get_config("exchange_rate") == before_rate


def test_grams_are_not_treated_as_kg():
    assert grams_to_kg(500) == 0.5
    assert chargeable_weight(grams_to_kg(500), 0.3) == 0.5
