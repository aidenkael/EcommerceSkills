"""
Phase 1.6 review 修复测试

覆盖：历史规则冻结、默认规则生命周期、归档保护、显示重置
"""

import sys, os, shutil, tempfile, math
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import DatabaseManager
from config.config_manager import ConfigManager
from calculation import evaluate_rule
from ui.main_window import ProfitRulesDialog
from ui.product_page import ProductPage


class _Var:
    def __init__(self, value=""): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


class _Widget:
    def __init__(self): self.state = None
    def config(self, **kwargs): self.state = kwargs.get("state", self.state)


class _Listbox:
    def __init__(self): self.items = []
    def delete(self, *_args): self.items.clear()
    def insert(self, _index, value): self.items.append(value)


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

    def test_product_page_uses_frozen_rule_after_rule_is_archived(self):
        import tempfile
        db = DatabaseManager(os.path.join(tempfile.mkdtemp(), "frozen.db")); cfg = ConfigManager(db)
        current = db.get_enabled_profit_adjustment_rules()[0]
        frozen = dict(current); frozen["adjustment_value"] = 2.99
        current["adjustment_value"] = 3.99; db.save_profit_adjustment_rule(current, current["rule_id"])
        db.archive_or_delete_profit_adjustment_rule(current["rule_id"])
        page = object.__new__(ProductPage)
        page._cfg = cfg; page._entry_vars = {"price_usd": _Var("28.99"), "cost": _Var("50")}
        page._profit_adjustment_var = _Var(); page._computed = {}; page._saved_profit_rule = frozen
        page._profit_rule_source = "frozen"; page._profit_rule_display_to_id = {}; page._profit_rule_var = _Var("历史冻结规则：SHEIN 29美元以下运费补贴")
        adjusted, _rate = ProductPage._apply_profit_adjustment(page, 10.0, 208.728, 7.2, 20.0)
        assert math.isclose(adjusted, 10.0 + 2.99 * 7.2)
        assert "历史冻结规则" in page._profit_adjustment_var.get()
        assert current["rule_id"] not in page._profit_rule_display_to_id.values()

    def test_product_page_load_then_save_keeps_frozen_adjustment_snapshot(self):
        """真实 ProductPage 加载/保存路径不应把冻结规则替换为下拉映射中的当前规则。"""
        db = DatabaseManager(os.path.join(tempfile.mkdtemp(), "product-flow.db")); cfg = ConfigManager(db)
        rule = dict(db.get_enabled_profit_adjustment_rules()[0]); rule["adjustment_value"] = 2.99
        result = evaluate_rule(rule, {"final_price_usd": 28.99, "final_price_rmb": 208.728,
                                      "product_cost_rmb": 50.0, "logistics_cost_rmb": 20.0}, 7.2)
        adjustment = {"rule": rule, **result}
        data = {"name": "冻结规则商品", "cost": 50.0, "domestic_shipping": 8.0,
                "freight_forwarder": "yiwu", "head_haul_cost": 75.0, "fixed_service_fee": 6.0,
                "tail_haul_cost": 40.0, "selling_price_rmb": 208.728, "selling_price_usd": 28.99,
                "weight_unit_version": "g_v1"}
        rules = {"forwarder": "yiwu", "head_haul_rate": 100.0, "fixed_service_fee": 6.0,
                 "tail_haul_cost": 40.0, "exchange_rate": 7.2, "volume_divisor": 8000,
                 "rule_version": 6, "weight_unit": "g_v1", "profit_adjustment": adjustment}
        calc = {"profit_adjustment": adjustment, "profit_before_adjustment": 15.0,
                "net_profit_amount": 15.0 + result["adjustment_rmb"]}
        pid = db.save_product_state(data, rules, calc)

        page = object.__new__(ProductPage)
        page._db = db; page._cfg = cfg; page._product_id = None; page._has_snapshot = False
        page._calc_direction = None; page._last_modified = None; page._programmatic = False
        page._entry_vars = {"tail": _Var()}; page._var_name = _Var(); page._var_notes = _Var()
        page._forwarder_var = _Var(); page._profit_rule_var = _Var(); page._profit_adjustment_var = _Var()
        page._profit_rule_display_to_id = {}; page._result_labels = {key: _Var() for key in (
            "vol_weight", "charge_weight", "head_haul", "total_logistics", "total_cost", "profit",
            "profit_rate", "suggested_price", "converted_usd")}
        page._show_rate_notice = lambda _diffs: None; page._check_rate_changes = lambda: None
        page._get_invalid_list = lambda: []; page._gather_data = lambda: dict(data)

        ProductPage.load_product(page, pid)
        before = db.get_product(pid)["_current_rule_snapshot"]["profit_adjustment"]
        with patch("ui.product_page.messagebox.showinfo"), patch("ui.product_page.messagebox.showerror"):
            ProductPage.save_product(page)
        after = db.get_product(pid)["_current_rule_snapshot"]["profit_adjustment"]
        assert before == after
        assert page._profit_rule_source == "frozen"
        assert "历史冻结规则" in page._profit_adjustment_var.get()

    def test_save_immediately_freezes_current_rule_for_later_recalculation(self):
        db = DatabaseManager(os.path.join(tempfile.mkdtemp(), "save-freeze.db")); cfg = ConfigManager(db)
        rule = dict(db.get_enabled_profit_adjustment_rules()[0]); rule["adjustment_value"] = 2.99
        result = evaluate_rule(rule, {"final_price_usd": 28.0, "final_price_rmb": 201.6,
                                      "product_cost_rmb": 50.0, "logistics_cost_rmb": 20.0}, 7.2)
        adjustment = {"rule": rule, **result}
        page = object.__new__(ProductPage)
        page._db = db; page._cfg = cfg; page._product_id = None; page._has_snapshot = False
        page._computed = {"profit_adjustment": adjustment}; page._saved_rule_context = None
        page._get_invalid_list = lambda: []; page._gather_data = lambda: {"name": "即时冻结", "weight_unit_version": "g_v1"}
        page._build_rule_snapshot = lambda: {"profit_adjustment": adjustment}
        page._build_calculation_snapshot = lambda: {"profit_adjustment": adjustment}
        page._profit_rule_var = _Var(); page._profit_adjustment_var = _Var(); page._profit_rule_unavailable_notice = False
        with patch("ui.product_page.messagebox.showinfo"), patch("ui.product_page.messagebox.showerror"):
            ProductPage.save_product(page)
        assert page._profit_rule_source == "frozen"
        assert page._saved_profit_rule["adjustment_value"] == 2.99
        current = db.get_profit_adjustment_rule(rule["rule_id"]); current["adjustment_value"] = 3.99
        db.save_profit_adjustment_rule(current, current["rule_id"])
        page._entry_vars = {"price_usd": _Var("28"), "cost": _Var("50")}; page._profit_rule_display_to_id = {}
        adjusted, _ = ProductPage._apply_profit_adjustment(page, 10.0, 201.6, 7.2, 20.0)
        assert math.isclose(adjusted, 10.0 + 2.99 * 7.2)

    def test_force_recalc_keeps_unavailable_frozen_rule_reason(self):
        db = DatabaseManager(os.path.join(tempfile.mkdtemp(), "unavailable.db")); cfg = ConfigManager(db)
        rule = dict(db.get_enabled_profit_adjustment_rules()[0]); db.archive_or_delete_profit_adjustment_rule(rule["rule_id"])
        page = object.__new__(ProductPage)
        page._cfg = cfg; page._saved_rule_context = None; page._show_rate_banner = False
        page._show_rate_notice = lambda _diffs: None; page._saved_profit_rule = rule; page._profit_rule_source = "frozen"
        page._profit_rule_unavailable_notice = False; page._profit_rule_var = _Var(); page._profit_adjustment_var = _Var()
        page._entry_vars = {"tail": _Var()}; page._set_profit_rule_id = lambda _rid: page._profit_rule_var.set("无")
        page.recalculate = lambda: ProductPage._apply_profit_adjustment(page, 10.0, 201.6, 7.2, 20.0)
        page._computed = {}; page._profit_rule_display_to_id = {}; page._entry_vars.update({"price_usd": _Var("28"), "cost": _Var("50")})
        with patch("ui.product_page.messagebox.showwarning") as warning:
            ProductPage._force_recalc(page)
        assert warning.called and page._profit_rule_source == "none"
        assert "原冻结规则当前已停用、归档或不存在" in page._profit_adjustment_var.get()


class TestProfitRulesDialogState:
    def _dialog_with_widgets(self):
        dialog = object.__new__(ProfitRulesDialog)
        dialog._suspend_dirty = False; dialog._dirty = False
        dialog._on_condition_change = lambda: None; dialog._on_type_change = lambda: None
        for name in ("_name_entry", "_cond_val_entry", "_adjustment_entry", "_description_entry", "_enabled_check",
                     "_cond_cb", "_op_cb", "_direction_cb", "_type_cb", "_currency_cb", "_base_cb",
                     "_new_button", "_save_button", "_archive_button", "_restore_button"):
            setattr(dialog, name, _Widget())
        return dialog

    def test_programmatic_dirty_guard_and_discard_reload(self):
        dialog = self._dialog_with_widgets()
        ProfitRulesDialog._mark_dirty(dialog)
        assert dialog._dirty is True
        dialog._dirty = False; dialog._suspend_dirty = True
        ProfitRulesDialog._mark_dirty(dialog)
        assert dialog._dirty is False
        dialog._suspend_dirty = False; dialog._dirty = True
        reloaded = []; dialog._load_current = lambda: reloaded.append(True)
        with patch("ui.main_window.messagebox.askyesnocancel", return_value=False):
            assert ProfitRulesDialog._check_dirty(dialog, "切换规则") is True
        assert reloaded == [True]
        assert dialog._dirty is False

    def test_archived_rule_disables_every_edit_control_and_restore_reenables(self):
        dialog = self._dialog_with_widgets()
        ProfitRulesDialog._set_editor_read_only(dialog, True)
        for name in ("_name_entry", "_cond_val_entry", "_adjustment_entry", "_description_entry", "_enabled_check",
                     "_cond_cb", "_op_cb", "_direction_cb", "_type_cb", "_currency_cb", "_base_cb",
                     "_new_button", "_save_button", "_archive_button"):
            assert getattr(dialog, name).state == "disabled"
        assert dialog._restore_button.state == "normal"
        ProfitRulesDialog._set_editor_read_only(dialog, False)
        assert dialog._name_entry.state == "normal"
        assert dialog._cond_cb.state == "readonly"
        assert dialog._restore_button.state == "disabled"

    def test_rule_list_uses_chinese_labels_only(self):
        dialog = object.__new__(ProfitRulesDialog)
        dialog._manager = type("Manager", (), {"list": lambda _self, _all: [{
            "rule_id": "r1", "display_name": "测试规则", "is_archived": False, "is_enabled": True,
            "condition_field": "final_price_usd", "condition_operator": "<", "condition_value": 29,
            "adjustment_direction": "income", "adjustment_type": "fixed", "adjustment_value": 2.99,
            "currency": "USD", "percentage_base": None} ]})()
        dialog._list = _Listbox(); dialog._on_change = None
        ProfitRulesDialog._refresh(dialog)
        assert dialog._list.items == ["测试规则 | 最终售价（美元） 小于 29 | 增加收入/固定金额 2.99 美元"]

    def test_load_current_preserves_zero_threshold_and_adjustment(self):
        dialog = object.__new__(ProfitRulesDialog)
        dialog._selected_id = "zero"; dialog._suspend_dirty = False; dialog._dirty = False
        dialog._rows = [{"rule_id": "zero", "display_name": "零值", "condition_field": "final_price_usd",
                         "condition_operator": "<", "condition_value": 0, "adjustment_direction": "income",
                         "adjustment_type": "fixed", "adjustment_value": 0, "currency": "USD",
                         "percentage_base": None, "description": "", "is_enabled": True}]
        dialog._vars = {key: _Var() for key in ("display_name", "condition_field", "condition_operator", "condition_value",
                       "adjustment_direction", "adjustment_type", "adjustment_value", "currency", "percentage_base", "description")}
        dialog._enabled = _Var(); dialog._on_condition_change = lambda: None; dialog._on_type_change = lambda: None
        dialog._update_status = lambda: None
        ProfitRulesDialog._load_current(dialog)
        assert dialog._vars["condition_value"].get() == "0"
        assert dialog._vars["adjustment_value"].get() == "0"
