"""phase_01_fix_06 最小修正：历史尾程缺失与有限配置值。"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from config.config_manager import ConfigManager
from database.db_manager import DatabaseManager
from ui.main_window import SettingsDialog
from ui.product_page import ProductPage


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _page_fields(default_tail=40.0):
    page = object.__new__(ProductPage)
    page._cfg = SimpleNamespace(default_tail_haul=default_tail)
    page._programmatic = False
    page._entry_vars = {"tail": FakeVar("old")}
    page._var_name = FakeVar()
    page._var_notes = FakeVar()
    page._forwarder_var = FakeVar()
    page._result_labels = {
        key: FakeVar()
        for key in [
            "vol_weight",
            "charge_weight",
            "head_haul",
            "total_logistics",
            "total_cost",
            "profit",
            "profit_rate",
            "suggested_price",
            "converted_usd",
        ]
    }
    page._show_rate_notice = lambda _diffs: None
    return page


def _missing_tail_data(notes=""):
    return {
        "name": "历史缺尾程商品",
        "cost": 50.0,
        "domestic_shipping": 8.0,
        "freight_forwarder": "yiwu",
        "head_haul_cost": 75.0,
        "fixed_service_fee": 6.0,
        "tail_haul_cost": None,
        "selling_price_rmb": 200.0,
        "notes": notes,
    }


def _missing_tail_rules():
    return {
        "exchange_rate": 7.2,
        "head_haul_rate": 100.0,
        "fixed_service_fee": 6.0,
        "tail_haul_cost": None,
        "volume_divisor": 8000,
        "forwarder": "yiwu",
        "rule_version": 2,
    }


def _missing_tail_results():
    return {
        "calculation_schema_version": 1,
        "volumetric_weight": None,
        "chargeable_weight": None,
        "head_haul_cost": 75.0,
        "total_logistics_cost": None,
        "total_cost": None,
        "net_profit_amount": None,
        "net_profit_rate": None,
        "suggested_price_rmb": None,
        "converted_usd": None,
    }


def test_history_product_missing_tail_loads_as_blank(tmp_path):
    db = DatabaseManager(str(tmp_path / "history.db"))
    pid = db.save_product_state(
        _missing_tail_data(), _missing_tail_rules(), _missing_tail_results()
    )
    page = _page_fields(default_tail=99.0)
    page._db = db
    page._check_rate_changes = lambda: None

    ProductPage.load_product(page, pid)

    assert page._entry_vars["tail"].get() == ""
    assert db.get_product(pid)["tail_haul_cost"] is None
    for key in ["total_logistics", "total_cost", "profit", "profit_rate"]:
        assert page._result_labels[key].get().startswith("数据不足")


def test_note_only_save_keeps_missing_tail_as_none(tmp_path):
    db = DatabaseManager(str(tmp_path / "note.db"))
    data = _missing_tail_data()
    rules = _missing_tail_rules()
    results = _missing_tail_results()
    pid = db.save_product_state(data, rules, results)

    page = object.__new__(ProductPage)
    page._db = db
    page._product_id = pid
    page._has_snapshot = True
    page._saved_rule_context = dict(rules)
    page._computed = {
        "exchange_rate": 7.2,
        "head_haul_rate": 100.0,
        "fixed_service_fee": 6.0,
        "tail_haul_cost": None,
        "volume_divisor": 8000,
        "forwarder": "yiwu",
        "rule_version": 2,
        "calculation_schema_version": 1,
        "volumetric_weight": None,
        "chargeable_weight": None,
        "head_haul": 75.0,
        "total_logistics": None,
        "total_cost": None,
        "profit": None,
        "profit_rate": None,
        "suggested_price": None,
        "converted_usd": None,
    }
    page._get_invalid_list = lambda: []
    page._gather_data = lambda: _missing_tail_data(notes="只改备注")

    with patch("ui.product_page.messagebox.showinfo"), patch(
        "ui.product_page.messagebox.showerror"
    ):
        ProductPage.save_product(page)

    saved = db.get_product(pid)
    assert saved["notes"] == "只改备注"
    assert saved["tail_haul_cost"] is None
    assert saved["_current_rule_snapshot"]["tail_haul_cost"] is None


def test_restore_snapshot_missing_tail_keeps_input_blank(tmp_path):
    db = DatabaseManager(str(tmp_path / "restore.db"))
    pid = db.save_product_state(
        _missing_tail_data(), _missing_tail_rules(), _missing_tail_results()
    )
    page = _page_fields(default_tail=88.0)
    page._db = db
    page._product_id = pid

    with patch("ui.product_page.messagebox.showinfo"):
        ProductPage.restore_product(page)

    assert page._entry_vars["tail"].get() == ""
    assert page._saved_rule_context["tail_haul_cost"] is None
    for key in ["total_logistics", "total_cost", "profit", "profit_rate"]:
        assert page._result_labels[key].get().startswith("数据不足")


def test_new_product_still_uses_current_default_tail():
    page = _page_fields(default_tail=55.0)

    ProductPage.new_product(page)

    assert page._entry_vars["tail"].get() == "55.0"


class ConfigDb:
    def __init__(self, value):
        self.value = value

    def get_config(self, _key):
        return self.value


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "not-a-number"])
def test_config_get_float_rejects_non_finite_or_non_numeric(value):
    cfg = ConfigManager(ConfigDb(value))
    assert cfg.get_float("setting", 12.5) == 12.5


def _settings_dialog(rate, tail):
    dialog = object.__new__(SettingsDialog)
    dialog._var_rate = FakeVar(rate)
    dialog._var_tail = FakeVar(tail)
    dialog._cfg = SimpleNamespace(exchange_rate=7.2, default_tail_haul=40.0)
    dialog._on_save = None
    dialog.destroy = lambda: None
    return dialog


@pytest.mark.parametrize(
    "rate,tail",
    [
        ("NaN", "40"),
        ("Infinity", "40"),
        ("-Infinity", "40"),
        ("abc", "40"),
        ("0", "40"),
        ("-1", "40"),
        ("7.2", "NaN"),
        ("7.2", "Infinity"),
        ("7.2", "-Infinity"),
        ("7.2", "abc"),
        ("7.2", "-1"),
    ],
)
def test_settings_reject_invalid_rate_and_tail(rate, tail):
    dialog = _settings_dialog(rate, tail)

    with patch("ui.main_window.messagebox.showerror") as showerror, patch(
        "ui.main_window.messagebox.showinfo"
    ) as showinfo:
        SettingsDialog._save(dialog)

    assert dialog._cfg.exchange_rate == 7.2
    assert dialog._cfg.default_tail_haul == 40.0
    showerror.assert_called_once()
    showinfo.assert_not_called()


def test_settings_accept_finite_positive_rate_and_zero_tail():
    dialog = _settings_dialog("7.3", "0")

    with patch("ui.main_window.messagebox.showerror") as showerror, patch(
        "ui.main_window.messagebox.showinfo"
    ) as showinfo:
        SettingsDialog._save(dialog)

    assert dialog._cfg.exchange_rate == 7.3
    assert dialog._cfg.default_tail_haul == 0.0
    showerror.assert_not_called()
    showinfo.assert_called_once()


def test_config_manager_can_filter_archived_routes(tmp_path):
    cfg = ConfigManager(DatabaseManager(str(tmp_path / "routes.db")))
    route = cfg.get_all_routes()[0]
    route["is_archived"] = True
    cfg._db.save_route(route, route_id=route["route_id"])

    visible_ids = {
        item["route_id"] for item in cfg.get_all_routes(include_archived=False)
    }
    assert route["route_id"] not in visible_ids


def test_settings_archive_delete_action_refreshes_routes():
    events = []
    dialog = object.__new__(SettingsDialog)
    dialog._cfg = SimpleNamespace(
        get_route_rates=lambda _route_id: {"display_name": "未使用货代"}
    )
    dialog._forwarders = SimpleNamespace(
        is_referenced=lambda _route_id: False,
        archive_or_delete=lambda route_id: events.append(("delete", route_id)) or "deleted",
    )
    dialog._on_save = lambda: events.append(("saved", None))
    dialog._render_routes = lambda: events.append(("rendered", None))

    with patch("ui.main_window.messagebox.askyesno", return_value=True), patch(
        "ui.main_window.messagebox.showinfo"
    ):
        SettingsDialog._archive_or_delete(dialog, "route-1")

    assert events == [
        ("delete", "route-1"),
        ("saved", None),
        ("rendered", None),
    ]


def test_settings_restore_action_keeps_route_disabled_and_refreshes():
    events = []
    dialog = object.__new__(SettingsDialog)
    dialog._cfg = SimpleNamespace(
        get_route_rates=lambda _route_id: {"display_name": "历史货代"}
    )
    dialog._forwarders = SimpleNamespace(
        restore=lambda route_id: events.append(("restore", route_id))
    )
    dialog._on_save = lambda: events.append(("saved", None))
    dialog._render_routes = lambda: events.append(("rendered", None))
    dialog._active_tab = object()
    dialog._route_tabs = SimpleNamespace(
        select=lambda tab: events.append(("selected", tab))
    )

    with patch("ui.main_window.messagebox.askyesno", return_value=True), patch(
        "ui.main_window.messagebox.showinfo"
    ):
        SettingsDialog._restore_route(dialog, "route-2")

    assert events[:3] == [
        ("restore", "route-2"),
        ("saved", None),
        ("rendered", None),
    ]
    assert events[3] == ("selected", dialog._active_tab)


def test_settings_refresh_guard_defaults_to_cancel_and_never_discards_changes():
    dialog = object.__new__(SettingsDialog)
    dialog._has_unsaved_changes = lambda: True
    dialog._save = lambda **_kwargs: pytest.fail("取消不能保存或放弃修改")

    with patch("ui.main_window.messagebox.askyesnocancel", return_value=None) as prompt:
        assert SettingsDialog._confirm_refresh_with_unsaved_changes(dialog) is False

    assert prompt.call_args.kwargs["default"] == "cancel"


def test_settings_refresh_guard_supports_save_or_explicit_discard():
    dialog = object.__new__(SettingsDialog)
    dialog._has_unsaved_changes = lambda: True
    calls = []
    dialog._save = lambda **kwargs: calls.append(kwargs) or True

    with patch("ui.main_window.messagebox.askyesnocancel", return_value=True):
        assert SettingsDialog._confirm_refresh_with_unsaved_changes(dialog) is True
    assert calls == [{"close_after": False}]

    with patch("ui.main_window.messagebox.askyesnocancel", return_value=False):
        assert SettingsDialog._confirm_refresh_with_unsaved_changes(dialog) is True
    assert calls == [{"close_after": False}]
