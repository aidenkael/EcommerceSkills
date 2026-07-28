"""OCR 录入候选与用户确认结果的数据结构测试。

覆盖：
1. 有单位候选可以保存归一化值
2. 无单位候选保留 parsed_value 但 selectable=False
3. OCR 候选与用户确认结果相互独立
4. 用户修改确认值不会改变原始候选
5. measurement_group_id 可以关联同组尺寸
6. 价格字段 scope 可以使用 not_applicable
7. 尺寸字段支持 bare、packaged 和 unknown
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from image_intake.result_models import (
    OcrCandidate, FieldSelection, FieldCandidates, IntakeSession,
    MeasurementScope, DIMENSION_FIELDS, PRICE_FIELDS,
)


class TestOcrCandidate:
    """候选数据结构。"""

    def test_with_unit_saves_normalized_value(self):
        """1. 有单位候选可以保存归一化值。"""
        c = OcrCandidate(
            field_name="weight_g",
            parsed_value=0.5,
            source_image="img1",
            raw_text="0.5kg",
            confidence=0.9,
            normalized_value=500.0,
            unit_original="kg",
            unit_normalized="g",
            selectable=True,
        )
        assert c.normalized_value == 500.0
        assert c.unit_normalized == "g"
        assert c.selectable is True
        assert c.parsed_value == 0.5

    def test_without_unit_keeps_parsed_value_but_not_selectable(self):
        """2. 无单位候选保留 parsed_value 但 selectable=False。"""
        c = OcrCandidate(
            field_name="weight_g",
            parsed_value=12.0,
            source_image="img1",
            raw_text="12",
            confidence=0.8,
            # 不设 normalized_value / unit_original / selectable，用默认值
        )
        assert c.parsed_value == 12.0          # 保留不丢
        assert c.normalized_value is None       # 无单位无归一化
        assert c.unit_original is None
        assert c.unit_normalized is None
        assert c.selectable is False            # 默认不可选


class TestCandidateSelectionIndependence:
    """候选与确认结果相互独立。"""

    def test_selection_independent_from_candidate(self):
        """3. OCR 候选与用户确认结果相互独立。"""
        c = OcrCandidate(
            field_name="shein_price_usd",
            parsed_value=5.99,
            source_image="img1",
            raw_text="$5.99",
            confidence=0.95,
            normalized_value=5.99,
            unit_original="$",
            unit_normalized="usd",
            selectable=True,
        )
        sel = FieldSelection(
            field_name="shein_price_usd",
            source_candidate_id=c.candidate_id,
            confirmed_value=6.50,
            confirmed_unit="usd",
            measurement_scope=MeasurementScope.NOT_APPLICABLE,
            user_modified=True,
        )
        # 候选原值不变
        assert c.parsed_value == 5.99
        # 确认值独立保存
        assert sel.confirmed_value == 6.50
        assert sel.source_candidate_id == c.candidate_id

    def test_user_modify_does_not_change_candidate(self):
        """4. 用户修改确认值不会改变原始候选（frozen）。"""
        c = OcrCandidate(
            field_name="product_cost_rmb",
            parsed_value=12.8,
            source_image="img2",
            raw_text="12.8元",
            confidence=0.92,
            normalized_value=12.8,
            unit_original="元",
            unit_normalized="rmb",
            selectable=True,
        )
        original_value = c.parsed_value
        original_raw = c.raw_text
        # 用户确认时改成 13.0
        sel = FieldSelection(
            field_name="product_cost_rmb",
            source_candidate_id=c.candidate_id,
            confirmed_value=13.0,
            confirmed_unit="rmb",
            measurement_scope=MeasurementScope.NOT_APPLICABLE,
            user_modified=True,
        )
        # 候选对象不可变，原值不变
        assert c.parsed_value == original_value
        assert c.raw_text == original_raw
        # frozen=True 不可赋值
        with pytest.raises(Exception):
            c.parsed_value = 999
        # 确认值是改后的
        assert sel.confirmed_value == 13.0
        assert sel.user_modified is True


class TestMeasurementGroup:
    """measurement_group_id 关联。"""

    def test_dimension_group_link(self):
        """5. measurement_group_id 可以关联同组尺寸。"""
        group = "grp_001"
        w = OcrCandidate(
            field_name="weight_g", parsed_value=500, source_image="img3",
            raw_text="500g", confidence=0.9,
            normalized_value=500.0, unit_original="g", unit_normalized="g",
            selectable=True, measurement_group_id=group,
        )
        l = OcrCandidate(
            field_name="length_cm", parsed_value=20, source_image="img3",
            raw_text="20cm", confidence=0.88,
            normalized_value=20.0, unit_original="cm", unit_normalized="cm",
            selectable=True, measurement_group_id=group,
        )
        h = OcrCandidate(
            field_name="height_cm", parsed_value=15, source_image="img3",
            raw_text="15cm", confidence=0.85,
            normalized_value=15.0, unit_original="cm", unit_normalized="cm",
            selectable=True, measurement_group_id=group,
        )
        # 同组关联
        assert w.measurement_group_id == l.measurement_group_id == h.measurement_group_id == group

    def test_non_dimension_candidate_group_is_none(self):
        """非尺寸类候选 measurement_group_id 默认为 None。"""
        c = OcrCandidate(
            field_name="shein_price_usd", parsed_value=5.99,
            source_image="img1", raw_text="$5.99", confidence=0.9,
            normalized_value=5.99, unit_original="$", unit_normalized="usd",
            selectable=True,
        )
        assert c.measurement_group_id is None


class TestMeasurementScope:
    """measurement_scope 取值。"""

    def test_price_field_scope_not_applicable(self):
        """6. 价格字段 scope 可以使用 not_applicable。"""
        sel = FieldSelection(
            field_name="shein_price_usd",
            source_candidate_id="c1",
            confirmed_value=5.99,
            confirmed_unit="usd",
            measurement_scope=MeasurementScope.NOT_APPLICABLE,
        )
        assert sel.measurement_scope == MeasurementScope.NOT_APPLICABLE
        assert sel.user_modified is False

    def test_dimension_field_supports_bare_packaged_unknown(self):
        """7. 尺寸字段支持 bare、packaged 和 unknown。"""
        for scope in (MeasurementScope.BARE, MeasurementScope.PACKAGED, MeasurementScope.UNKNOWN):
            sel = FieldSelection(
                field_name="weight_g",
                source_candidate_id="c1",
                confirmed_value=500.0,
                confirmed_unit="g",
                measurement_scope=scope,
            )
            assert sel.measurement_scope == scope


class TestFieldCandidatesAndSession:
    """FieldCandidates 与 IntakeSession 基本结构。"""

    def test_field_candidates_keeps_all_and_no_auto_select(self):
        """FieldCandidates 保留全部候选，不自动选择，不删重复来源。"""
        c1 = OcrCandidate(
            field_name="product_cost_rmb", parsed_value=12.8,
            source_image="img_a", raw_text="12.8元", confidence=0.9,
            normalized_value=12.8, unit_original="元", unit_normalized="rmb",
            selectable=True,
        )
        c2 = OcrCandidate(
            field_name="product_cost_rmb", parsed_value=13.0,
            source_image="img_a", raw_text="13.0元", confidence=0.85,  # 同来源不同行
            normalized_value=13.0, unit_original="元", unit_normalized="rmb",
            selectable=True,
        )
        fc = FieldCandidates(field_name="product_cost_rmb", candidates=[c1, c2])
        assert len(fc.candidates) == 2
        assert fc.selected_candidate_id is None  # 不自动选最低价
        # 不删重复来源（两个都来自 img_a）
        assert fc.candidates[0].source_image == fc.candidates[1].source_image

    def test_intake_session_structure(self):
        """IntakeSession 基本字段可保存。"""
        session = IntakeSession(
            session_id="20260727_150000_a3f2",
            created_at="2026-07-27T15:00:00",
            session_dir="C:/tmp/ocr_sessions/20260727_150000_a3f2",
            engine_name="placeholder",
        )
        assert session.session_id == "20260727_150000_a3f2"
        assert session.images == []
        assert session.field_candidates == {}
        assert session.selections == {}
        assert session.engine_name == "placeholder"
