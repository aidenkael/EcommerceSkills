import sqlite3
from unittest.mock import patch

import pytest

from calculation.profit_adjustments import evaluate_rule
from config.profit_adjustment_manager import ProfitAdjustmentManager
from database.db_manager import DatabaseManager


def rule(name="规则", **updates):
    value = {"display_name": name, "condition_field": "final_price_usd", "condition_operator": "<",
             "condition_value": 29, "adjustment_direction": "income", "adjustment_type": "fixed",
             "adjustment_value": 2.99, "currency": "USD", "percentage_base": None, "is_enabled": True}
    value.update(updates); return value


def test_new_database_is_v7_with_explicit_default_subsidy(tmp_path):
    db = DatabaseManager(str(tmp_path / "new.db"))
    rules = db.get_enabled_profit_adjustment_rules()
    default = next(item for item in rules if item["display_name"] == "SHEIN 29美元以下运费补贴")
    assert db.get_schema_version() == 7
    assert (default["condition_field"], default["condition_operator"], default["condition_value"], default["adjustment_value"], default["currency"]) == ("final_price_usd", "<", 29.0, 2.99, "USD")


def test_v6_to_v7_and_repeat_open_are_safe(tmp_path):
    path = str(tmp_path / "v6.db")
    db = DatabaseManager(path)
    conn = sqlite3.connect(path); conn.execute("DELETE FROM schema_version"); conn.execute("INSERT INTO schema_version VALUES (6, 'old')"); conn.execute("DROP TABLE profit_adjustment_rules"); conn.commit(); conn.close()
    migrated = DatabaseManager(path)
    ids = [item["rule_id"] for item in migrated.get_profit_adjustment_rules()]
    assert migrated.get_schema_version() == 7
    assert [item["rule_id"] for item in DatabaseManager(path).get_profit_adjustment_rules()] == ids


def test_v6_to_v7_failure_restores_original_database(tmp_path):
    path = str(tmp_path / "fail.db")
    db = DatabaseManager(path)
    conn = sqlite3.connect(path); conn.execute("DELETE FROM schema_version"); conn.execute("INSERT INTO schema_version VALUES (6, 'old')"); conn.execute("DROP TABLE profit_adjustment_rules"); conn.commit(); conn.close()
    with patch.object(DatabaseManager, "_seed_profit_adjustment_rules", side_effect=RuntimeError("forced")):
        with pytest.raises(RuntimeError): DatabaseManager(path)
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 6
    with pytest.raises(sqlite3.OperationalError): conn.execute("SELECT * FROM profit_adjustment_rules")
    conn.close()


def test_rule_evaluation_boundaries_and_adjustment_types():
    subsidy = rule()
    assert evaluate_rule(subsidy, {"final_price_usd": 28.99}, 7.2)["adjustment_rmb"] == pytest.approx(21.528)
    assert evaluate_rule(subsidy, {"final_price_usd": 29.00}, 7.2)["adjustment_rmb"] == 0
    assert evaluate_rule(subsidy, {"final_price_usd": 29.01}, 7.2)["adjustment_rmb"] == 0
    assert "缺少最终售价" in evaluate_rule(subsidy, {}, 7.2)["reason"]
    assert evaluate_rule(rule("rmb", currency="RMB", adjustment_value=10), {"final_price_usd": 1}, 7.2)["adjustment_rmb"] == 10
    assert evaluate_rule(rule("pct", adjustment_type="percent", adjustment_value=10, percentage_base="final_price_rmb", currency="RMB"), {"final_price_usd": 1, "final_price_rmb": 100}, 7.2)["adjustment_rmb"] == 10
    assert evaluate_rule(rule("cost", adjustment_direction="cost", adjustment_value=10, currency="RMB"), {"final_price_usd": 1}, 7.2)["adjustment_rmb"] == -10


def test_rule_lifecycle_archives_referenced_and_rejects_invalid_numbers(tmp_path):
    db = DatabaseManager(str(tmp_path / "rules.db")); manager = ProfitAdjustmentManager(db)
    with pytest.raises(ValueError): manager.create(rule("bad", adjustment_value="NaN"))
    rid = manager.create(rule("引用规则"))
    db.save_product_state({"name": "p", "weight_unit_version": "g_v1"}, {"profit_adjustment": {"rule": {"rule_id": rid, "display_name": "引用规则"}}}, {})
    assert manager.archive_or_delete(rid) == "archived"
    assert manager.restore(rid) == rid
    assert db.get_profit_adjustment_rule(rid)["is_enabled"] is False
    unused = manager.create(rule("可删除"))
    assert manager.archive_or_delete(unused) == "deleted"


def test_saved_product_keeps_complete_profit_adjustment_snapshot(tmp_path):
    db = DatabaseManager(str(tmp_path / "snapshot.db")); item = db.get_enabled_profit_adjustment_rules()[0]
    adjustment = {"rule": item, "selected": True, "matched": True, "condition_input": 28.99,
                  "amount_original": 2.99, "currency": "USD", "exchange_rate": 7.2, "adjustment_rmb": 21.528}
    pid = db.save_product_state({"name": "冻结", "weight_unit_version": "g_v1"},
                                {"profit_adjustment": adjustment},
                                {"profit_before_adjustment": 10, "net_profit_amount": 31.528, "profit_adjustment": adjustment})
    snapshot = db.get_snapshot(pid)
    assert snapshot["_snapshot_rule_full"]["profit_adjustment"]["rule"]["rule_id"] == item["rule_id"]
    assert snapshot["_calculation_results"]["profit_adjustment"]["adjustment_rmb"] == 21.528
