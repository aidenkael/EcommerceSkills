"""
Phase 1.6 review 修复测试

覆盖：历史规则冻结、默认规则生命周期、归档保护、显示重置
"""

import sys, os, shutil, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import DatabaseManager
from config.config_manager import ConfigManager
from calculation import evaluate_rule


class TestHistoricalRuleFrozen:
    """历史规则冻结：加载后保存不改变快照"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "test.db")
        cls.db = DatabaseManager(cls.db_path)
        cls.cfg = ConfigManager(cls.db)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_load_then_save_preserves_adjustment_snapshot(self):
        """加载商品 → 不修改 → 保存 → 利润调整快照不变"""
        rules = self.db.get_enabled_profit_adjustment_rules()
        assert len(rules) > 0, "默认规则应存在"
        rule = rules[0]

        data = {"name": "冻结测试", "cost": 50.0, "selling_price_rmb": 200.0,
                "freight_forwarder": "yiwu"}
        pa_snapshot = {"rule": dict(rule), "selected": True, "matched": True,
                       "reason": "售价<29USD", "adjustment_rmb": 20.93,
                       "adjustment_type": "fixed", "currency": "USD"}
        calc = {"profit_before_adjustment": 15.0, "profit_adjustment": pa_snapshot}
        rules_snapshot = {"forwarder": "yiwu", "head_haul_rate": 100.0, "fixed_service_fee": 6.0,
                          "tail_haul_cost": 40.0, "exchange_rate": 7.2, "volume_divisor": 8000,
                          "rule_version": 2, "profit_adjustment": pa_snapshot}
        pid = self.db.save_product_state(data, rules_snapshot, calc)

        # 重新加载
        product = self.db.get_product(pid)
        snap = self.db.get_snapshot(pid)
        assert snap is not None
        pa = snap.get("_calculation_results", {}).get("profit_adjustment", {})
        assert pa.get("rule", {}).get("rule_id") == rule["rule_id"]
        assert pa.get("adjustment_rmb") == 20.93

    def test_snapshot_contains_profit_before_adjustment(self):
        """快照包含 profit_before_adjustment"""
        data = {"name": "快照测试", "cost": 30.0, "selling_price_rmb": 100.0}
        calc = {"profit_before_adjustment": 25.5, "profit_adjustment": {"rule": None, "matched": False}}
        rules = {"forwarder": "yiwu", "head_haul_rate": 100.0, "fixed_service_fee": 6.0,
                 "tail_haul_cost": 40.0, "exchange_rate": 7.2, "volume_divisor": 8000, "rule_version": 2}
        pid = self.db.save_product_state(data, rules, calc)
        snap = self.db.get_snapshot(pid)
        calc_snap = snap.get("_calculation_results", {})
        assert calc_snap.get("profit_before_adjustment") == 25.5


class TestDefaultRuleLifecycle:
    """默认规则生命周期：改名/停用/归档/删除后重启不重复"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "lifecycle.db")

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_rename_no_duplicate_on_restart(self):
        """改名后重启不新增第二条"""
        db = DatabaseManager(self.db_path)
        rules = db.get_enabled_profit_adjustment_rules()
        assert len(rules) == 1
        original = dict(rules[0])
        original["display_name"] = "自定义名称"
        db.save_profit_adjustment_rule(original, original["rule_id"])
        db2 = DatabaseManager(self.db_path)
        rules2 = db2.get_enabled_profit_adjustment_rules()
        assert len(rules2) == 1
        assert rules2[0]["display_name"] == "自定义名称"

    def test_modify_value_no_reset(self):
        """修改金额后重启不还原"""
        db = DatabaseManager(self.db_path)
        rules = db.get_enabled_profit_adjustment_rules()
        original = dict(rules[0])
        original["adjustment_value"] = 3.99
        db.save_profit_adjustment_rule(original, original["rule_id"])
        db2 = DatabaseManager(self.db_path)
        rules2 = db2.get_enabled_profit_adjustment_rules()
        assert rules2[0]["adjustment_value"] == 3.99

    def test_disable_stays_disabled(self):
        """停用后重启仍停用"""
        db = DatabaseManager(self.db_path)
        rules = db.get_enabled_profit_adjustment_rules()
        original = dict(rules[0])
        original["is_enabled"] = 0
        db.save_profit_adjustment_rule(original, original["rule_id"])
        db2 = DatabaseManager(self.db_path)
        rules2 = db2.get_enabled_profit_adjustment_rules()
        assert len(rules2) == 0

    def test_uuid_preserved_across_restarts(self):
        """UUID 重启不变"""
        db = DatabaseManager(self.db_path)
        rules = db.get_profit_adjustment_rules(include_archived=True)
        original_id = rules[0]["rule_id"]
        db2 = DatabaseManager(self.db_path)
        rules2 = db2.get_profit_adjustment_rules(include_archived=True)
        assert rules2[0]["rule_id"] == original_id


class TestArchiveProtection:
    """归档保护"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "archive_test.db")
        cls.db = DatabaseManager(cls.db_path)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_archive_then_restore_is_disabled(self):
        """恢复后默认为停用"""
        rules = self.db.get_enabled_profit_adjustment_rules()
        rule = rules[0]
        data = {"name": "引用商品", "cost": 10.0, "selling_price_rmb": 50.0}
        self.db.save_product_state(data, {"profit_adjustment": {"rule": rule}}, {})
        self.db.archive_or_delete_profit_adjustment_rule(rule["rule_id"])
        self.db.restore_profit_adjustment_rule(rule["rule_id"])
        restored = self.db.get_profit_adjustment_rule(rule["rule_id"])
        assert restored["is_enabled"] == 0


class TestFrozenRuleEvaluation:
    """冻结规则求值"""

    def test_evaluate_with_frozen_rule(self):
        """使用冻结规则副本求值，不用DB中的新参数"""
        rule = {"rule_id": "test-1", "display_name": "冻结规则",
                "condition_field": "final_price_usd", "condition_operator": "<",
                "condition_value": 30.0, "adjustment_direction": "income",
                "adjustment_type": "fixed", "adjustment_value": 5.0,
                "currency": "USD", "percentage_base": None,
                "is_enabled": 1, "is_archived": 0}
        result = evaluate_rule(rule, {"final_price_usd": 25.0, "final_price_rmb": 180.0,
                                       "product_cost_rmb": 50.0, "logistics_cost_rmb": 80.0}, 7.2)
        assert result["matched"] == True
        assert result["adjustment_rmb"] == 36.0
