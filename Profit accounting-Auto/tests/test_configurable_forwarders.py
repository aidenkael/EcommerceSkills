"""Schema v5：动态货代、克重和旧重量兼容。"""

import sqlite3

import pytest

from calculation import chargeable_weight, grams_to_kg, volumetric_weight
from config.config_manager import ConfigManager
from database.db_manager import DatabaseManager


def test_default_routes_are_independent_and_named(tmp_path):
    cfg = ConfigManager(DatabaseManager(str(tmp_path / "new.db")))
    routes = {route["display_name"]: route for route in cfg.get_all_routes()}
    assert (routes["深圳"]["head_haul_rate"], routes["深圳"]["fixed_service_fee"], routes["深圳"]["volume_divisor"]) == (80.0, 10.0, 8000.0)
    assert (routes["义乌"]["head_haul_rate"], routes["义乌"]["fixed_service_fee"], routes["义乌"]["volume_divisor"]) == (100.0, 6.0, 8000.0)


def test_route_update_is_atomic_and_disabled_route_is_hidden(tmp_path):
    cfg = ConfigManager(DatabaseManager(str(tmp_path / "routes.db")))
    routes = cfg.get_all_routes()
    routes[0].update(display_name="广东A货代", volume_divisor=6000, is_enabled=True)
    routes[1].update(display_name="义乌", volume_divisor=8000, is_enabled=False)
    cfg.save_settings_and_routes(7.3, 45.0, routes)
    assert [r["route_id"] for r in cfg.get_enabled_routes()] == [routes[0]["route_id"]]
    assert cfg.get_route_rates(routes[0]["route_id"])["display_name"] == "广东A货代"
    assert volumetric_weight(40, 30, 20, cfg.get_route_rates(routes[0]["route_id"])["volume_divisor"]) == 4.0
    assert volumetric_weight(40, 30, 20, cfg.get_route_rates(routes[1]["route_id"])["volume_divisor"]) == 3.0


def test_grams_convert_to_kg_and_never_to_500kg():
    assert grams_to_kg(500) == 0.5
    assert chargeable_weight(grams_to_kg(500), 0.3) == 0.5


def test_v3_product_migrates_to_legacy_unknown_weight(tmp_path):
    path = str(tmp_path / "v3.db")
    db = DatabaseManager(path)
    pid = db.create_product({"name": "old", "packaged_weight": 0.5})
    conn = sqlite3.connect(path)
    conn.execute("DELETE FROM schema_version WHERE version>=4")
    conn.execute("INSERT OR REPLACE INTO schema_version VALUES (3, 'old')")
    conn.execute("UPDATE products SET weight_unit_version=NULL WHERE id=?", (pid,))
    conn.commit(); conn.close()
    migrated = DatabaseManager(path).get_product(pid)
    assert migrated["weight_unit_version"] == "legacy_unknown"


def test_new_product_marks_gram_unit(tmp_path):
    db = DatabaseManager(str(tmp_path / "g.db"))
    pid = db.save_product_state({"name": "g", "packaged_weight": 500, "weight_unit_version": "g_v1"}, {}, {})
    assert db.get_product(pid)["weight_unit_version"] == "g_v1"
