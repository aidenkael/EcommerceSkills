"""OCR 录入弹窗与控制器测试。

测试状态和交互逻辑，不做像素级 UI 测试。
覆盖：多图管理、类型切换、来源不混淆、勾选编辑、不可选不能确认、
measurement_scope、同组关联、跨图片不串组、引擎异常、确认不写入正式字段。
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from ocr.base_engine import BaseOcrEngine, OcrPageResult, OcrTextLine, EngineStatus
from image_intake.intake_controller import OcrIntakeController
from image_intake.image_types import ImageType
from image_intake.result_models import MeasurementScope


class FakeEngine(BaseOcrEngine):
    """测试用假引擎，按图片路径返回预设文本行；可模拟异常。"""
    def __init__(self, lines_by_path=None, raise_on=None):
        self._lines = lines_by_path or {}
        self._raise_on = raise_on

    @property
    def name(self):
        return "fake"

    def status(self):
        return EngineStatus.READY

    def recognize(self, image_path, image_id):
        if self._raise_on and image_path == self._raise_on:
            raise RuntimeError("模拟引擎异常")
        lines = list(self._lines.get(image_path, []))
        return OcrPageResult(image_id=image_id, lines=lines, success=True)


@pytest.fixture
def img_factory(tmp_path):
    """创建临时图片文件。"""
    def _make(name="a.png", content=b"\x89PNG fake"):
        p = tmp_path / name
        p.write_bytes(content)
        return str(p)
    return _make


class TestImageManagement:
    """1-3. 多图添加、删除、替换、类型切换。"""

    def test_add_multiple_images(self, img_factory):
        ctrl = OcrIntakeController()
        p1 = img_factory("a.png")
        p2 = img_factory("b.png")
        id1 = ctrl.add_image(p1, ImageType.SHEIN_PRICING)
        id2 = ctrl.add_image(p2, ImageType.SUPPLIER_COST_SHIPPING)
        assert len(ctrl.images) == 2
        assert id1 != id2

    def test_remove_image(self, img_factory):
        ctrl = OcrIntakeController()
        p = img_factory()
        img_id = ctrl.add_image(p, ImageType.SHEIN_PRICING)
        ctrl.remove_image(img_id)
        assert len(ctrl.images) == 0

    def test_replace_image(self, img_factory):
        ctrl = OcrIntakeController()
        p1 = img_factory("a.png")
        p2 = img_factory("b.png")
        id1 = ctrl.add_image(p1, ImageType.SHEIN_PRICING)
        id2 = ctrl.replace_image(id1, p2, ImageType.DIMENSIONS_WEIGHT)
        assert len(ctrl.images) == 1
        assert ctrl.images[0]["image_id"] == id2
        assert ctrl.images[0]["image_type"] == ImageType.DIMENSIONS_WEIGHT

    def test_set_image_type(self, img_factory):
        ctrl = OcrIntakeController()
        p = img_factory()
        img_id = ctrl.add_image(p, ImageType.SHEIN_PRICING)
        ctrl.set_image_type(img_id, ImageType.SUPPLEMENTARY)
        assert ctrl.images[0]["image_type"] == ImageType.SUPPLEMENTARY

    def test_invalid_image_type_rejected(self, img_factory):
        ctrl = OcrIntakeController()
        with pytest.raises(ValueError):
            ctrl.add_image(img_factory(), "shein_pricing")


class TestCandidateSelection:
    """4-5. 候选勾选、编辑、不可选不能确认。"""

    def test_process_and_select(self, img_factory):
        p = img_factory()
        engine = FakeEngine({p: [OcrTextLine(text="$12.99", confidence=0.9)]})
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p, ImageType.SHEIN_PRICING)
        ctrl.process_all()
        assert len(ctrl.candidates) == 1
        sel = ctrl.select_candidate("shein_price_usd", ctrl.candidates[0].candidate_id)
        assert sel.confirmed_value == 12.99
        assert sel.measurement_scope == MeasurementScope.NOT_APPLICABLE

    def test_edit_confirmed_value(self, img_factory):
        p = img_factory()
        engine = FakeEngine({p: [OcrTextLine(text="$12.99", confidence=0.9)]})
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p, ImageType.SHEIN_PRICING)
        ctrl.process_all()
        cid = ctrl.candidates[0].candidate_id
        ctrl.select_candidate("shein_price_usd", cid)
        ctrl.edit_confirmed_value("shein_price_usd", 13.50, "usd")
        assert ctrl.selections["shein_price_usd"].confirmed_value == 13.50
        assert ctrl.selections["shein_price_usd"].user_modified is True

    def test_unselectable_cannot_confirm(self, img_factory):
        p = img_factory()
        # 无单位但有核价上下文 → selectable=False
        engine = FakeEngine({p: [OcrTextLine(text="核价：12.80", confidence=0.9)]})
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p, ImageType.SHEIN_PRICING)
        ctrl.process_all()
        assert len(ctrl.candidates) == 1
        assert ctrl.candidates[0].selectable is False
        ctrl.select_candidate("shein_price_usd", ctrl.candidates[0].candidate_id)
        assert ctrl.can_confirm() is False
        with pytest.raises(RuntimeError):
            ctrl.confirm()


class TestMeasurementScope:
    """6-7. scope 设置与同组关联。"""

    def test_scope_for_dimension(self, img_factory):
        p = img_factory()
        engine = FakeEngine({p: [OcrTextLine(text="10×20×30cm", confidence=0.9)]})
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p, ImageType.DIMENSIONS_WEIGHT)
        ctrl.process_all()
        length_c = ctrl.candidates_for_field("length_cm")[0]
        ctrl.select_candidate("length_cm", length_c.candidate_id)
        # 默认 UNKNOWN
        assert ctrl.selections["length_cm"].measurement_scope == MeasurementScope.UNKNOWN
        # 改为 BARE
        ctrl.set_measurement_scope("length_cm", MeasurementScope.BARE)
        assert ctrl.selections["length_cm"].measurement_scope == MeasurementScope.BARE
        assert ctrl.selections["length_cm"].user_modified is True

    def test_same_group_association(self, img_factory):
        p = img_factory()
        engine = FakeEngine({p: [OcrTextLine(text="10×20×30cm", confidence=0.9)]})
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p, ImageType.DIMENSIONS_WEIGHT)
        ctrl.process_all()
        gids = {c.measurement_group_id for c in ctrl.candidates}
        assert len(gids) == 1


class TestCrossImageNoMix:
    """8. 跨图片相同文本不串组。"""

    def test_same_text_different_image_no_mix(self, img_factory):
        p1 = img_factory("a.png")
        p2 = img_factory("b.png")
        engine = FakeEngine({
            p1: [OcrTextLine(text="10×20×30cm", confidence=0.9)],
            p2: [OcrTextLine(text="10×20×30cm", confidence=0.9)],
        })
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p1, ImageType.DIMENSIONS_WEIGHT)
        ctrl.add_image(p2, ImageType.DIMENSIONS_WEIGHT)
        ctrl.process_all()
        # 来源不同
        sources = {c.source_image for c in ctrl.candidates}
        assert len(sources) == 2
        # group_id 不同（含 source_image）
        gids = {c.measurement_group_id for c in ctrl.candidates}
        assert len(gids) == 2


class TestEngineError:
    """9. 引擎异常不致命。"""

    def test_engine_error_does_not_crash(self, img_factory):
        p1 = img_factory("a.png")
        p2 = img_factory("b.png")
        engine = FakeEngine(
            lines_by_path={p2: [OcrTextLine(text="$8.50", confidence=0.9)]},
            raise_on=p1,
        )
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p1, ImageType.SHEIN_PRICING)
        ctrl.add_image(p2, ImageType.SHEIN_PRICING)
        ctrl.process_all()
        assert ctrl.last_error is not None
        assert "a.png" in ctrl.last_error
        assert len(ctrl.candidates) == 1  # 只有 p2 的候选


class TestConfirmResult:
    """10. 确认结果不写入正式字段。"""

    def test_confirm_returns_selections_only(self, img_factory):
        p = img_factory()
        engine = FakeEngine({p: [OcrTextLine(text="$12.99", confidence=0.9)]})
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p, ImageType.SHEIN_PRICING)
        ctrl.process_all()
        cid = ctrl.candidates[0].candidate_id
        ctrl.select_candidate("shein_price_usd", cid)
        result = ctrl.confirm()
        # 只返回 dict，无 db / ProductPage 引用
        assert isinstance(result, dict)
        assert "shein_price_usd" in result
        assert result["shein_price_usd"].confirmed_value == 12.99
        assert not hasattr(ctrl, "_db")
        assert not hasattr(ctrl, "_product_page")

    def test_confirm_without_selection(self, img_factory):
        """无选中时确认返回空 dict（can_confirm True，因为无不可选项）。"""
        p = img_factory()
        engine = FakeEngine({p: [OcrTextLine(text="$12.99", confidence=0.9)]})
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p, ImageType.SHEIN_PRICING)
        ctrl.process_all()
        # 未选中任何候选
        assert ctrl.can_confirm() is True
        result = ctrl.confirm()
        assert result == {}


class TestDialogInstantiation:
    """UI 实例化（最小，不测像素）。"""

    def test_dialog_can_instantiate(self):
        tkinter = pytest.importorskip("tkinter")
        try:
            root = tkinter.Tk()
            root.withdraw()
        except Exception:
            pytest.skip("Tkinter 不可用")
        try:
            from ui.ocr_intake_dialog import OcrIntakeDialog
            ctrl = OcrIntakeController()
            dlg = OcrIntakeDialog(root, controller=ctrl)
            assert dlg.result is None
            assert dlg.controller is ctrl
            dlg.destroy()
        finally:
            root.destroy()


class TestManualConfirmation:
    """步骤A：无单位候选人工确认规则。"""

    def _setup(self, img_factory, text, image_type=ImageType.SHEIN_PRICING):
        p = img_factory()
        engine = FakeEngine({p: [OcrTextLine(text=text, confidence=0.9)]})
        ctrl = OcrIntakeController(engine=engine)
        ctrl.add_image(p, image_type)
        ctrl.process_all()
        return ctrl

    def test_unselectable_not_edited_cannot_confirm(self, img_factory):
        """1. 无单位候选未编辑时不能确认。"""
        ctrl = self._setup(img_factory, "核价：12.80")
        cid = ctrl.candidates[0].candidate_id
        assert ctrl.candidates[0].selectable is False
        ctrl.select_candidate("shein_price_usd", cid)
        assert ctrl.can_confirm() is False
        with pytest.raises(RuntimeError):
            ctrl.confirm()

    def test_manual_confirm_allows_unselectable(self, img_factory):
        """2. 用户填写合法数值和单位后可以确认。"""
        ctrl = self._setup(img_factory, "核价：12.80")
        cid = ctrl.candidates[0].candidate_id
        ctrl.confirm_candidate_manual("shein_price_usd", cid, 12.80, "usd")
        assert ctrl.can_confirm() is True
        result = ctrl.confirm()
        assert result["shein_price_usd"].confirmed_value == 12.80

    def test_original_candidate_unchanged(self, img_factory):
        """3. 原 OcrCandidate 内容保持不变。"""
        ctrl = self._setup(img_factory, "核价：12.80")
        c = ctrl.candidates[0]
        orig_parsed = c.parsed_value
        orig_raw = c.raw_text
        orig_selectable = c.selectable
        ctrl.confirm_candidate_manual("shein_price_usd", c.candidate_id, 99.99, "usd")
        c2 = ctrl.candidate_by_id(c.candidate_id)
        assert c2.parsed_value == orig_parsed
        assert c2.raw_text == orig_raw
        assert c2.selectable == orig_selectable

    def test_user_modified_true(self, img_factory):
        """4. FieldSelection 记录 user_modified=True。"""
        ctrl = self._setup(img_factory, "核价：12.80")
        cid = ctrl.candidates[0].candidate_id
        sel = ctrl.confirm_candidate_manual("shein_price_usd", cid, 12.80, "usd")
        assert sel.user_modified is True

    def test_kg_to_g(self, img_factory):
        """5. kg 正确换算为 g。"""
        ctrl = self._setup(img_factory, "500g", ImageType.DIMENSIONS_WEIGHT)
        cid = ctrl.candidates[0].candidate_id
        sel = ctrl.confirm_candidate_manual("weight_g", cid, 0.5, "kg")
        assert sel.confirmed_value == 500.0
        assert sel.confirmed_unit == "g"

    def test_mm_to_cm(self, img_factory):
        """6. mm 正确换算为 cm。"""
        ctrl = self._setup(img_factory, "10cm", ImageType.DIMENSIONS_WEIGHT)
        cid = ctrl.candidates[0].candidate_id
        sel = ctrl.confirm_candidate_manual("length_cm", cid, 100, "mm")
        assert sel.confirmed_value == 10.0
        assert sel.confirmed_unit == "cm"

    def test_invalid_weight_unit_rejected(self, img_factory):
        """7. 非法重量单位被拒绝。"""
        ctrl = self._setup(img_factory, "500g", ImageType.DIMENSIONS_WEIGHT)
        cid = ctrl.candidates[0].candidate_id
        with pytest.raises(ValueError):
            ctrl.confirm_candidate_manual("weight_g", cid, 500, "吨")

    def test_invalid_dim_unit_rejected(self, img_factory):
        """8. 非法尺寸单位被拒绝。"""
        ctrl = self._setup(img_factory, "10cm", ImageType.DIMENSIONS_WEIGHT)
        cid = ctrl.candidates[0].candidate_id
        with pytest.raises(ValueError):
            ctrl.confirm_candidate_manual("length_cm", cid, 10, "英寸")

    def test_price_field_unit_restriction(self, img_factory):
        """9. 价格字段只允许对应货币单位。"""
        ctrl = self._setup(img_factory, "$12.99")
        cid = ctrl.candidates[0].candidate_id
        # shein 不接受人民币
        with pytest.raises(ValueError):
            ctrl.confirm_candidate_manual("shein_price_usd", cid, 12.99, "元")

    def test_price_scope_forced_not_applicable(self, img_factory):
        """10. 价格字段 scope 强制 not_applicable。"""
        ctrl = self._setup(img_factory, "$12.99")
        cid = ctrl.candidates[0].candidate_id
        sel = ctrl.confirm_candidate_manual("shein_price_usd", cid, 12.99, "usd")
        assert sel.measurement_scope == MeasurementScope.NOT_APPLICABLE
        # select 后设 bare 应被拒
        ctrl.select_candidate("shein_price_usd", cid)
        with pytest.raises(ValueError):
            ctrl.set_measurement_scope("shein_price_usd", MeasurementScope.BARE)

    def test_dimension_scopes(self, img_factory):
        """11. 尺寸和重量支持 bare、packaged、unknown，不支持 not_applicable。"""
        ctrl = self._setup(img_factory, "10cm", ImageType.DIMENSIONS_WEIGHT)
        cid = ctrl.candidates[0].candidate_id
        for scope in (MeasurementScope.BARE, MeasurementScope.PACKAGED, MeasurementScope.UNKNOWN):
            sel = ctrl.confirm_candidate_manual("length_cm", cid, 10, "cm", scope=scope)
            assert sel.measurement_scope == scope
        with pytest.raises(ValueError):
            ctrl.confirm_candidate_manual("length_cm", cid, 10, "cm", scope=MeasurementScope.NOT_APPLICABLE)

    def test_invalid_values_rejected(self, img_factory):
        """12. 空值、NaN 和 Infinity 被拒绝。"""
        ctrl = self._setup(img_factory, "$12.99")
        cid = ctrl.candidates[0].candidate_id
        for bad in (None, "nan", "inf", "abc", ""):
            with pytest.raises(ValueError):
                ctrl.confirm_candidate_manual("shein_price_usd", cid, bad, "usd")
