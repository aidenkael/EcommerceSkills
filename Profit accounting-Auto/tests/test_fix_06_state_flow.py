"""phase_01_fix_06：当前规则、冻结结果和历史展示真实路径测试。"""

from unittest.mock import patch

from calculation import compare_rule_contexts, volumetric_weight
from database.db_manager import DatabaseManager
from ui.history_page import saved_or_legacy_net_rate
from ui.product_page import ProductPage


def _computed(forwarder, head_rate, fixed_fee, head_cost):
    return {
        "forwarder": forwarder,
        "head_haul_rate": head_rate,
        "fixed_service_fee": fixed_fee,
        "tail_haul_cost": 40.0,
        "exchange_rate": 7.2,
        "volume_divisor": 8000,
        "rule_version": 2,
        "calculation_schema_version": 1,
        "volumetric_weight": 0.75,
        "chargeable_weight": 0.75,
        "head_haul": head_cost,
        "total_logistics": head_cost + fixed_fee + 40.0,
        "total_cost": head_cost + fixed_fee + 98.0,
        "profit": 20.0,
        "profit_rate": 10.0,
        "suggested_price": 220.0,
        "converted_usd": 30.56,
    }


def _data(forwarder, head_cost, fixed_fee):
    return {
        "name": "切换货代商品",
        "cost": 50.0,
        "domestic_shipping": 8.0,
        "packaged_weight": 0.5,
        "packaged_length": 30.0,
        "packaged_width": 20.0,
        "packaged_height": 10.0,
        "freight_forwarder": forwarder,
        "head_haul_cost": head_cost,
        "fixed_service_fee": fixed_fee,
        "tail_haul_cost": 40.0,
        "selling_price_rmb": 200.0,
        "selling_price_usd": 27.78,
        "promotion_reserve_rate": 10.0,
    }


def _page_for_save(db, data, computed):
    page = object.__new__(ProductPage)
    page._db = db
    page._product_id = None
    page._has_snapshot = False
    page._saved_rule_context = None
    page._computed = computed
    page._get_invalid_list = lambda: []
    page._gather_data = lambda: data
    return page


def test_yiwu_switch_to_shenzhen_save_and_reopen_uses_current_rule(tmp_path):
    db = DatabaseManager(str(tmp_path / "flow.db"))
    yiwu_data = _data("yiwu", 75.0, 6.0)
    page = _page_for_save(db, yiwu_data, _computed("yiwu", 100.0, 6.0, 75.0))

    with patch("ui.product_page.messagebox.showinfo"), patch(
        "ui.product_page.messagebox.showerror"
    ):
        ProductPage.save_product(page)
        pid = page._product_id
        shenzhen_data = _data("shenzhen", 60.0, 10.0)
        page._computed = _computed("shenzhen", 80.0, 10.0, 60.0)
        page._gather_data = lambda: shenzhen_data
        ProductPage.save_product(page)

    reopened = db.get_product(pid)
    current_rules = ProductPage._build_product_rule_context(reopened)
    assert reopened["freight_forwarder"] == "shenzhen"
    assert reopened["head_haul_cost"] == 60.0
    assert current_rules["forwarder"] == "shenzhen"
    assert current_rules["head_haul_rate"] == 80.0

    initial = db.get_snapshot(pid)
    initial_rules = ProductPage._build_snapshot_rule_context(initial)
    assert initial["freight_forwarder"] == "yiwu"
    assert initial_rules["forwarder"] == "yiwu"
    assert initial_rules["head_haul_rate"] == 100.0


class _ResultVar:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


def test_saved_calculation_results_are_displayed_without_recalculation():
    page = object.__new__(ProductPage)
    page._result_labels = {
        key: _ResultVar()
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
    page._computed = {}
    data = _data("yiwu", 75.0, 6.0)
    data["cost"] = 9999.0
    calc = {
        "calculation_schema_version": 1,
        "volumetric_weight": 0.75,
        "chargeable_weight": 0.75,
        "head_haul_cost": 75.0,
        "total_logistics_cost": 121.0,
        "total_cost": 179.0,
        "net_profit_amount": 1.0,
        "net_profit_rate": 0.5,
        "suggested_price_rmb": 250.0,
        "converted_usd": 34.72,
    }
    rules = {
        "forwarder": "yiwu",
        "head_haul_rate": 100.0,
        "fixed_service_fee": 6.0,
        "tail_haul_cost": 40.0,
        "exchange_rate": 7.2,
        "volume_divisor": 8000,
        "rule_version": 2,
    }

    ProductPage._populate_results_from_saved(page, data, calc, rules)

    assert page._result_labels["total_cost"].value == "179.00 元"
    assert page._result_labels["profit"].value == "1.00 元"
    assert page._result_labels["profit_rate"].value == "0.50 %"
    assert page._computed["total_cost"] == 179.0


def test_volume_divisor_is_part_of_the_actual_formula():
    assert volumetric_weight(40, 30, 20, 6000) == 4.0
    assert volumetric_weight(40, 30, 20, 8000) == 3.0
    assert volumetric_weight(40, 30, 20, 0) is None


def test_rule_comparison_detects_missing_value_transitions():
    assert compare_rule_contexts(
        {"forwarder": None, "head_haul_rate": None},
        {"forwarder": "yiwu", "head_haul_rate": 100.0},
    ) == {
        "forwarder": (None, "yiwu"),
        "head_haul_rate": (None, 100.0),
    }


def test_history_prefers_saved_rate_and_never_treats_missing_cost_as_zero():
    complete_but_changed = {
        "cost": 9999.0,
        "domestic_shipping": 8.0,
        "head_haul_cost": 75.0,
        "fixed_service_fee": 6.0,
        "tail_haul_cost": 40.0,
        "selling_price_rmb": 200.0,
        "promotion_reserve_rate": 10.0,
        "_current_calculation_results": {"net_profit_rate": 12.5},
    }
    assert saved_or_legacy_net_rate(complete_but_changed) == 12.5

    missing_cost = dict(complete_but_changed)
    missing_cost["_current_calculation_results"] = None
    missing_cost["cost"] = None
    assert saved_or_legacy_net_rate(missing_cost) is None
