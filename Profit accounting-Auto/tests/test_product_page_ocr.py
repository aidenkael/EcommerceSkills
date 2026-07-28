"""S5 ProductPage OCR 回填接入测试。

测试回填逻辑，不做像素级 UI 测试。用 FakeDialog 避免真实 OCR。
"""
import sys
import os
import sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tkinter as tk
import pytest

from database.db_manager import DatabaseManager
from config.config_manager import ConfigManager
from ui.product_page import ProductPage
from image_intake.result_models import FieldSelection, MeasurementScope


class FakeDialog:
    """测试用假对话框，result 为预设的 selections 或 None（取消）。"""
    def __init__(self, parent, controller, result=None):
        self.result = result
        self.parent = parent
        self.controller = controller


def _sel(field, value, unit, scope=MeasurementScope.NOT_APPLICABLE, modified=True):
    return FieldSelection(
        field_name=field, source_candidate_id="fake",
        confirmed_value=value, confirmed_unit=unit,
        measurement_scope=scope, user_modified=modified,
    )


@pytest.fixture
def page(tmp_path):
    """创建 ProductPage 实例（真实 db + cfg，tmp_path 隔离）。"""
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tkinter 不可用")
    db = DatabaseManager(db_path=str(tmp_path / "t.db"))
    cfg = ConfigManager(db)
    p = ProductPage(root, db, cfg)
    yield p
    root.destroy()


class TestOcrButtonAndCancel:
    """1-2. 按钮打开对话框、取消不变。"""

    def test_button_opens_dialog(self, page):
        """1. OCR录入按钮可以打开对话框（factory 被调用）。"""
        called = []
        def factory(parent, ctrl):
            called.append(parent)
            return FakeDialog(parent, ctrl, result={})
        page._ocr_dialog_factory = factory
        page._open_ocr_intake()
        assert len(called) == 1

    def test_cancel_no_change(self, page):
        """2. 取消对话框后字段完全不变。"""
        page._entry_vars["shein"].set("9.99")
        page._entry_vars["cost"].set("10.00")
        page._ocr_dialog_factory = lambda p, c: FakeDialog(p, c, result=None)
        page._open_ocr_intake()
        assert page._entry_vars["shein"].get() == "9.99"
        assert page._entry_vars["cost"].get() == "10.00"


class TestPriceFillback:
    """3-5. 价格/成本/运费回填。"""

    def test_shein_usd_fillback(self, page):
        """3. 美元核价正确回填 shein 字段。"""
        page._apply_ocr_selections({"shein_price_usd": _sel("shein_price_usd", 12.99, "usd")})
        assert page._entry_vars["shein"].get() == "12.99"

    def test_cost_rmb_fillback(self, page):
        """4. 商品成本正确回填 cost 字段。"""
        page._apply_ocr_selections({"product_cost_rmb": _sel("product_cost_rmb", 12.80, "rmb")})
        assert page._entry_vars["cost"].get() == "12.80"

    def test_domestic_shipping_fillback(self, page):
        """5. 国内运费正确回填 domestic 字段。"""
        page._apply_ocr_selections({"domestic_shipping_rmb": _sel("domestic_shipping_rmb", 6.00, "rmb")})
        assert page._entry_vars["domestic"].get() == "6.00"


class TestDimensionFillback:
    """6-9. 尺寸/重量 bare 回填，packaged/unknown 不回填。"""

    def test_bare_weight_fillback(self, page):
        """6. bare 重量正确回填 net_w。"""
        page._apply_ocr_selections({"weight_g": _sel("weight_g", 500, "g", MeasurementScope.BARE)})
        assert page._entry_vars["net_w"].get() == "500.00"

    def test_bare_dimensions_fillback(self, page):
        """7. bare 长宽高正确回填 net_l、net_wi、net_h。"""
        page._apply_ocr_selections({
            "length_cm": _sel("length_cm", 10, "cm", MeasurementScope.BARE),
            "width_cm": _sel("width_cm", 20, "cm", MeasurementScope.BARE),
            "height_cm": _sel("height_cm", 30, "cm", MeasurementScope.BARE),
        })
        assert page._entry_vars["net_l"].get() == "10.00"
        assert page._entry_vars["net_wi"].get() == "20.00"
        assert page._entry_vars["net_h"].get() == "30.00"

    def test_packaged_not_fillback(self, page):
        """8. packaged 重量和尺寸不回填 net_*。"""
        page._entry_vars["net_w"].set("")
        page._entry_vars["net_l"].set("")
        page._apply_ocr_selections({
            "weight_g": _sel("weight_g", 500, "g", MeasurementScope.PACKAGED),
            "length_cm": _sel("length_cm", 10, "cm", MeasurementScope.PACKAGED),
        })
        assert page._entry_vars["net_w"].get() == ""
        assert page._entry_vars["net_l"].get() == ""

    def test_unknown_not_fillback(self, page):
        """9. unknown 重量和尺寸不回填 net_*。"""
        page._entry_vars["net_w"].set("")
        page._apply_ocr_selections({"weight_g": _sel("weight_g", 500, "g", MeasurementScope.UNKNOWN)})
        assert page._entry_vars["net_w"].get() == ""


class TestFillbackRules:
    """10-13. 回填规则。"""

    def test_unselected_field_kept(self, page):
        """10. 没有 FieldSelection 的字段保持原值。"""
        page._entry_vars["cost"].set("99.00")
        page._entry_vars["shein"].set("8.88")
        page._apply_ocr_selections({"shein_price_usd": _sel("shein_price_usd", 12.99, "usd")})
        # shein 被回填
        assert page._entry_vars["shein"].get() == "12.99"
        # cost 保持原值
        assert page._entry_vars["cost"].get() == "99.00"

    def test_user_modified_value_preferred(self, page):
        """11. 用户修改后的 confirmed_value 优先。"""
        # confirmed_value=13.50（用户改过），即使原候选 normalized_value 是别的
        page._apply_ocr_selections({"shein_price_usd": _sel("shein_price_usd", 13.50, "usd", modified=True)})
        assert page._entry_vars["shein"].get() == "13.50"

    def test_invalid_selection_no_fill(self, page):
        """12. 无效 FieldSelection（confirmed_value=None）不回填。"""
        page._entry_vars["shein"].set("9.99")
        page._apply_ocr_selections({"shein_price_usd": _sel("shein_price_usd", None, "usd")})
        assert page._entry_vars["shein"].get() == "9.99"

    def test_recalculate_triggered(self, page):
        """13. 回填后触发现有重新计算。"""
        called = []
        orig = page.recalculate
        def fake_recalc():
            called.append(True)
            orig()
        page.recalculate = fake_recalc
        page._apply_ocr_selections({"shein_price_usd": _sel("shein_price_usd", 12.99, "usd")})
        assert len(called) == 1


class TestNoDbWrite:
    """14-15. 不写数据库、不创建快照。"""

    def test_no_db_save(self, page, tmp_path):
        """14. 确认操作不调用数据库保存。"""
        page._apply_ocr_selections({
            "shein_price_usd": _sel("shein_price_usd", 12.99, "usd"),
            "product_cost_rmb": _sel("product_cost_rmb", 10.00, "rmb"),
        })
        conn = sqlite3.connect(str(tmp_path / "t.db"))
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0

    def test_no_snapshot_created(self, page, tmp_path):
        """15. 确认操作不创建历史快照。"""
        page._apply_ocr_selections({
            "weight_g": _sel("weight_g", 500, "g", MeasurementScope.BARE),
        })
        conn = sqlite3.connect(str(tmp_path / "t.db"))
        assert conn.execute("SELECT COUNT(*) FROM product_snapshots").fetchone()[0] == 0


class TestFakeDialogIntegration:
    """16. FakeDialog 可完成无真实 OCR 测试。"""

    def test_fake_dialog_flow(self, page):
        """16. 用 FakeDialog 完成 打开→确认→回填 全流程。"""
        selections = {
            "shein_price_usd": _sel("shein_price_usd", 12.99, "usd"),
            "weight_g": _sel("weight_g", 500, "g", MeasurementScope.BARE),
        }
        page._ocr_dialog_factory = lambda p, c: FakeDialog(p, c, result=selections)
        page._open_ocr_intake()
        assert page._entry_vars["shein"].get() == "12.99"
        assert page._entry_vars["net_w"].get() == "500.00"
