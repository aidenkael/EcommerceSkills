import os
import sys

import pytest

from database.db_manager import DatabaseManager


def test_backup_and_restore_round_trip(tmp_path):
    db_path = str(tmp_path / "current.db")
    backup_path = str(tmp_path / "manual_backup.db")
    db = DatabaseManager(db_path)
    db.set_config("exchange_rate", "7.35")
    original_id = db.create_product({"name": "备份中的商品", "cost": 20})

    assert db.backup_to(backup_path) == os.path.abspath(backup_path)

    db.set_config("exchange_rate", "9.99")
    later_id = db.create_product({"name": "恢复前新增", "cost": 99})
    safety_path = db.restore_from(backup_path)

    restored = DatabaseManager(db_path)
    safety = DatabaseManager(safety_path)
    assert restored.get_config("exchange_rate") == "7.35"
    assert restored.get_product(original_id)["name"] == "备份中的商品"
    assert restored.get_product(later_id) is None
    assert safety.get_config("exchange_rate") == "9.99"
    assert safety.get_product(later_id)["name"] == "恢复前新增"


def test_backup_cannot_overwrite_live_database(tmp_path):
    db_path = str(tmp_path / "live.db")
    db = DatabaseManager(db_path)

    with pytest.raises(ValueError, match="不能覆盖"):
        db.backup_to(db_path)


def test_restore_rejects_non_sqlite_file_without_changing_current_data(tmp_path):
    db_path = str(tmp_path / "live.db")
    invalid_path = tmp_path / "not-a-backup.db"
    invalid_path.write_text("not sqlite", encoding="utf-8")
    db = DatabaseManager(db_path)
    product_id = db.create_product({"name": "保留", "cost": 10})

    with pytest.raises(ValueError, match="不是有效"):
        db.restore_from(str(invalid_path))

    assert DatabaseManager(db_path).get_product(product_id)["name"] == "保留"


def test_packaged_app_uses_stable_local_appdata_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    db = DatabaseManager()

    assert db.db_path == str(
        tmp_path / "ProfitAccountingAuto" / "profit_accounting.db"
    )
