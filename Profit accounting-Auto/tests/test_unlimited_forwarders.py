import json
import sqlite3

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
    assert migrated.get_schema_version() == 5
    assert all(len(r["route_id"]) == 36 for r in migrated.get_all_routes())
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
