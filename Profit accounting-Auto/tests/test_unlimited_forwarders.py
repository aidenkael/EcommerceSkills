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


def test_v4_keys_migrate_to_uuid_in_products_and_snapshots(tmp_path):
    path = str(tmp_path / "v4.db")
    db = DatabaseManager(path)
    route_id = db.get_all_routes()[0]["route_id"]
    conn = sqlite3.connect(path)
    conn.execute("ALTER TABLE route_config ADD COLUMN route_key TEXT")
    conn.execute("UPDATE route_config SET route_key='shenzhen' WHERE route_id=?", (route_id,))
    conn.execute("UPDATE products SET freight_forwarder='shenzhen'")
    conn.execute("DELETE FROM schema_version WHERE version>=5")
    conn.execute("INSERT INTO schema_version VALUES (4, 'old')")
    conn.commit(); conn.close()
    migrated = DatabaseManager(path)
    assert migrated.get_schema_version() == 5
    assert all(len(r["route_id"]) == 36 for r in migrated.get_all_routes())


def test_grams_are_not_treated_as_kg():
    assert grams_to_kg(500) == 0.5
    assert chargeable_weight(grams_to_kg(500), 0.3) == 0.5
