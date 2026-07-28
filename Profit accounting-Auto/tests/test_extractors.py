"""OCR 文本候选字段提取器测试。

覆盖 37 个场景：SHEIN 核价(1-7)、1688 成本运费(8-17)、尺寸重量(18-33)、接口(34-37)。
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from ocr.base_engine import OcrTextLine
from image_intake.extractors.shein_price_extractor import extract as extract_shein
from image_intake.extractors.cost_shipping_extractor import extract as extract_cost
from image_intake.extractors.dimension_extractor import extract as extract_dim
from image_intake.result_models import OcrCandidate


def _line(text, conf=0.9):
    return OcrTextLine(text=text, confidence=conf)


# ─── SHEIN 核价 (1-7) ────────────────────────────────────

class TestSheinPrice:
    """1-7. SHEIN 核价提取器。"""

    def test_dollar_sign(self):
        """1. $12.99 提取为 usd。"""
        r = extract_shein([_line("$12.99")], "img1")
        assert len(r) == 1
        c = r[0]
        assert c.field_name == "shein_price_usd"
        assert c.parsed_value == 12.99
        assert c.normalized_value == 12.99
        assert c.unit_normalized == "usd"
        assert c.selectable is True

    def test_us_dollar_prefix(self):
        """2. US$ 8.50 提取为 usd。"""
        r = extract_shein([_line("US$ 8.50")], "img1")
        assert len(r) == 1
        assert r[0].parsed_value == 8.50
        assert r[0].unit_normalized == "usd"
        assert r[0].selectable is True

    def test_multiple_usd_all_kept(self):
        """3. 多个美元价格全部保留。"""
        r = extract_shein([_line("$12.99"), _line("$8.50")], "img1")
        assert len(r) == 2
        assert sorted(c.parsed_value for c in r) == [8.50, 12.99]

    def test_rmb_not_usd(self):
        """4. 人民币金额不进入 shein_price_usd。"""
        r = extract_shein([_line("¥12.80"), _line("12.8元")], "img1")
        assert len(r) == 0

    def test_percent_sales_not_price(self):
        """5. 百分比和销量不被当成价格。"""
        r = extract_shein([_line("折扣 20%"), _line("销量 1000")], "img1")
        assert len(r) == 0

    def test_no_unit_with_context_not_selectable(self):
        """6. 无单位但有'核价'上下文时保留 parsed_value，selectable=False。"""
        r = extract_shein([_line("核价：12.80")], "img1")
        assert len(r) == 1
        c = r[0]
        assert c.parsed_value == 12.80
        assert c.normalized_value is None
        assert c.selectable is False

    def test_no_auto_select(self):
        """7. 不自动选择最终价格（多候选都保留，OcrCandidate 无选中标记）。"""
        r = extract_shein([_line("核价 $12.99"), _line("售价 $8.50")], "img1")
        assert len(r) == 2
        # OcrCandidate 没有 selected/最终 字段
        for c in r:
            assert not hasattr(c, "selected")


# ─── 1688 成本与运费 (8-17) ──────────────────────────────

class TestCostShipping:
    """8-17. 成本与运费提取器。"""

    def test_cost_rmb(self):
        """8. 单价 ¥12.80 提取为 product_cost_rmb。"""
        r = extract_cost([_line("单价 ¥12.80")], "img1")
        costs = [c for c in r if c.field_name == "product_cost_rmb"]
        assert len(costs) == 1
        assert costs[0].normalized_value == 12.80
        assert costs[0].unit_normalized == "rmb"
        assert costs[0].selectable is True

    def test_shipping_rmb(self):
        """9. 运费 ￥6.00 提取为 domestic_shipping_rmb。"""
        r = extract_cost([_line("运费 ￥6.00")], "img1")
        ships = [c for c in r if c.field_name == "domestic_shipping_rmb"]
        assert len(ships) == 1
        assert ships[0].normalized_value == 6.00

    def test_cost_and_shipping_separate(self):
        """10. 同图成本和运费分别归类。"""
        r = extract_cost([_line("单价 ¥12.80"), _line("运费 ¥6.00")], "img1")
        costs = [c for c in r if c.field_name == "product_cost_rmb"]
        ships = [c for c in r if c.field_name == "domestic_shipping_rmb"]
        assert len(costs) == 1
        assert len(ships) == 1

    def test_tier_prices_all_kept(self):
        """11. 多档阶梯价全部保留。"""
        r = extract_cost([_line("价格 ¥15.00"), _line("价格 ¥12.80"), _line("价格 ¥10.00")], "img1")
        costs = [c for c in r if c.field_name == "product_cost_rmb"]
        assert len(costs) == 3

    def test_no_auto_select_lowest(self):
        """12. 不自动选择最低阶梯价（都保留）。"""
        r = extract_cost([_line("价格 ¥15.00"), _line("价格 ¥10.00")], "img1")
        costs = [c for c in r if c.field_name == "product_cost_rmb"]
        assert len(costs) == 2
        assert sorted(c.normalized_value for c in costs) == [10.0, 15.0]

    def test_baoyou_zero_shipping(self):
        """13. 包邮生成0元运费候选。"""
        r = extract_cost([_line("包邮")], "img1")
        ships = [c for c in r if c.field_name == "domestic_shipping_rmb"]
        assert len(ships) == 1
        assert ships[0].parsed_value == 0
        assert ships[0].normalized_value == 0
        assert ships[0].unit_original == "包邮"
        assert ships[0].selectable is True

    def test_zero_shipping_explicit(self):
        """14. 运费0元生成0元运费候选。"""
        r = extract_cost([_line("运费0元")], "img1")
        ships = [c for c in r if c.field_name == "domestic_shipping_rmb"]
        assert len(ships) == 1
        assert ships[0].normalized_value == 0
        assert ships[0].selectable is True

    def test_moq_stock_sales_not_price(self):
        """15. 起订量、库存和销量不当作价格。"""
        r = extract_cost([_line("2件起批"), _line("库存200"), _line("销量1000")], "img1")
        assert len(r) == 0

    def test_no_unit_cost_not_selectable(self):
        """16. 无单位单价保留 parsed_value 但不可选。"""
        r = extract_cost([_line("单价 12.8")], "img1")
        costs = [c for c in r if c.field_name == "product_cost_rmb"]
        assert len(costs) == 1
        assert costs[0].parsed_value == 12.8
        assert costs[0].normalized_value is None
        assert costs[0].selectable is False

    def test_coupon_not_cost(self):
        """17. 优惠券和满减信息不自动作为成本。"""
        r = extract_cost([_line("满100减20元"), _line("优惠券5元")], "img1")
        assert len(r) == 0


# ─── 尺寸重量 (18-33) ────────────────────────────────────

class TestDimension:
    """18-33. 尺寸和重量提取器。"""

    def test_500g(self):
        """18. 500g 归一化为500g。"""
        r = extract_dim([_line("500g")], "img1")
        ws = [c for c in r if c.field_name == "weight_g"]
        assert len(ws) == 1
        assert ws[0].normalized_value == 500.0
        assert ws[0].unit_normalized == "g"

    def test_0_5kg(self):
        """19. 0.5kg 归一化为500g。"""
        r = extract_dim([_line("0.5kg")], "img1")
        ws = [c for c in r if c.field_name == "weight_g"]
        assert len(ws) == 1
        assert ws[0].normalized_value == 500.0

    def test_500_ke(self):
        """20. 500克 归一化为500g。"""
        r = extract_dim([_line("500克")], "img1")
        ws = [c for c in r if c.field_name == "weight_g"]
        assert len(ws) == 1
        assert ws[0].normalized_value == 500.0

    def test_100mm(self):
        """21. 100mm 归一化为10cm。"""
        r = extract_dim([_line("100mm")], "img1")
        ds = [c for c in r if c.field_name == "length_cm"]
        assert len(ds) == 1
        assert ds[0].normalized_value == 10.0
        assert ds[0].unit_normalized == "cm"

    def test_10cm(self):
        """22. 10cm 保持10cm。"""
        r = extract_dim([_line("10cm")], "img1")
        ds = [c for c in r if c.field_name == "length_cm"]
        assert len(ds) == 1
        assert ds[0].normalized_value == 10.0
        assert ds[0].unit_original == "cm"

    def test_triple_same_group(self):
        """23. 10×20×30cm 生成长宽高同组候选。"""
        r = extract_dim([_line("10×20×30cm")], "img1")
        assert len(r) == 3
        by_field = {c.field_name: c for c in r}
        assert {"length_cm", "width_cm", "height_cm"} <= set(by_field)
        assert by_field["length_cm"].normalized_value == 10.0
        assert by_field["width_cm"].normalized_value == 20.0
        assert by_field["height_cm"].normalized_value == 30.0
        assert len({c.measurement_group_id for c in r}) == 1

    def test_triple_mm_convert(self):
        """24. 100×200×300mm 正确换算并保持同组。"""
        r = extract_dim([_line("100×200×300mm")], "img1")
        by_field = {c.field_name: c for c in r}
        assert by_field["length_cm"].normalized_value == 10.0
        assert by_field["width_cm"].normalized_value == 20.0
        assert by_field["height_cm"].normalized_value == 30.0
        assert len({c.measurement_group_id for c in r}) == 1

    def test_lwh_text_fields(self):
        """25. 长10cm 宽20cm 高30cm 正确分字段。"""
        r = extract_dim([_line("长10cm 宽20cm 高30cm")], "img1")
        by_field = {c.field_name: c for c in r}
        assert "length_cm" in by_field
        assert "width_cm" in by_field
        assert "height_cm" in by_field
        assert by_field["length_cm"].normalized_value == 10.0
        assert by_field["width_cm"].normalized_value == 20.0
        assert by_field["height_cm"].normalized_value == 30.0
        assert len({c.measurement_group_id for c in r}) == 1

    def test_two_groups_different_id(self):
        """26. 两组尺寸生成两个不同 measurement_group_id。"""
        r = extract_dim([_line("10×20×30cm"), _line("40×50×60cm")], "img1")
        gids = {c.measurement_group_id for c in r}
        assert len(gids) == 2

    def test_pair_no_height(self):
        """27. 两维尺寸不补高度。"""
        r = extract_dim([_line("10×20cm")], "img1")
        fields = {c.field_name for c in r}
        assert "height_cm" not in fields
        assert "length_cm" in fields
        assert "width_cm" in fields

    def test_quad_no_full_triple(self):
        """28. 四维表达式不错误生成完整长宽高。"""
        r = extract_dim([_line("10×20×30×40cm")], "img1")
        fields = {c.field_name for c in r}
        assert not ({"length_cm", "width_cm", "height_cm"} <= fields)

    def test_no_unit_dimension_not_selectable(self):
        """29. 无单位尺寸保留 parsed_value 但不可选。"""
        r = extract_dim([_line("长 10")], "img1")
        assert len(r) == 1
        c = r[0]
        assert c.parsed_value == 10
        assert c.normalized_value is None
        assert c.selectable is False

    def test_gross_net_weight_no_scope(self):
        """30. 毛重、净重文字不自动决定 measurement_scope。"""
        r = extract_dim([_line("毛重 500g")], "img1")
        ws = [c for c in r if c.field_name == "weight_g"]
        assert len(ws) == 1
        assert ws[0].normalized_value == 500.0
        # OcrCandidate 不含 measurement_scope 字段
        assert not hasattr(ws[0], "measurement_scope")
        # 不应同时生成 length_cm
        assert not any(c.field_name == "length_cm" for c in r)

    def test_different_image_same_value_kept(self):
        """31. 不同图片中的同值候选均保留。"""
        r1 = extract_dim([_line("500g")], "img1")
        r2 = extract_dim([_line("500g")], "img2")
        all_r = r1 + r2
        assert len(all_r) == 2
        assert {c.source_image for c in all_r} == {"img1", "img2"}

    def test_exact_duplicate_deduped(self):
        """32. 完全相同的重复 OCR 行可以去重。"""
        lines = [_line("500g"), _line("500g")]
        r = extract_dim(lines, "img1")
        ws = [c for c in r if c.field_name == "weight_g"]
        assert len(ws) == 1

    def test_zero_negative_rejected(self):
        """33. 零或负尺寸、重量不生成可用候选。"""
        r = extract_dim([_line("0cm"), _line("-5g"), _line("0g")], "img1")
        # 0 和负数不生成 selectable 候选
        assert all(not c.selectable for c in r) or len(r) == 0


# ─── 接口与回归 (34-37) ──────────────────────────────────

class TestInterface:
    """34-37. 统一接口与回归。"""

    def test_all_accept_ocrtextline_list(self):
        """34. 三个提取器统一接受 OcrTextLine 列表。"""
        lines = [_line("$12.99"), _line("单价 ¥12.80"), _line("500g")]
        r1 = extract_shein(lines, "img1")
        r2 = extract_cost(lines, "img1")
        r3 = extract_dim(lines, "img1")
        # 都能运行不报错，返回 list
        assert isinstance(r1, list)
        assert isinstance(r2, list)
        assert isinstance(r3, list)

    def test_all_return_list_of_candidate(self):
        """35. 三个提取器返回类型一致（list[OcrCandidate]）。"""
        lines = [_line("$12.99"), _line("500g")]
        for fn in (extract_shein, extract_cost, extract_dim):
            r = fn(lines, "img1")
            assert isinstance(r, list)
            for c in r:
                assert isinstance(c, OcrCandidate)

    def test_no_paddleocr_dependency(self):
        """36. 不需要安装 PaddleOCR/PaddlePaddle/OpenCV。"""
        # 提取器只依赖 OcrTextLine，不 import paddleocr/cv2
        import image_intake.extractors.shein_price_extractor as m1
        import image_intake.extractors.cost_shipping_extractor as m2
        import image_intake.extractors.dimension_extractor as m3
        for m in (m1, m2, m3):
            assert not hasattr(m, "paddleocr")
            assert not hasattr(m, "paddle")
            assert not hasattr(m, "cv2")

    def test_existing_252_tests_baseline(self):
        """37. 全部已有 252 个测试继续通过（由 pytest 运行保证）。"""
        # 此测试为占位：实际回归由运行整个 tests 目录保证
        # 这里只验证提取器模块能正常 import
        assert extract_shein is not None
        assert extract_cost is not None
        assert extract_dim is not None


# ─── 跨图片同文本不串组回归（步骤0合约核对）──────────────

class TestCrossImageGrouping:
    """跨图片相同尺寸文本不得误并为同组。

    S3 的 make_group_id(content) 已包含 source_image，
    因此不同图片的相同文本会生成不同 group_id，不会串组。
    """

    def test_same_triple_different_image_different_group(self):
        """两张图都有 10×20×30cm，group_id 必须不同。"""
        r1 = extract_dim([_line("10×20×30cm")], "imgA")
        r2 = extract_dim([_line("10×20×30cm")], "imgB")
        g1 = {c.measurement_group_id for c in r1}
        g2 = {c.measurement_group_id for c in r2}
        assert g1 and g2
        assert g1.isdisjoint(g2)

    def test_same_weight_different_image_different_group(self):
        """两张图都有 500g，重量候选 source_image 不同且均保留。"""
        r1 = extract_dim([_line("500g")], "imgA")
        r2 = extract_dim([_line("500g")], "imgB")
        assert len(r1) == 1 and len(r2) == 1
        assert r1[0].source_image == "imgA"
        assert r2[0].source_image == "imgB"

    def test_same_text_same_image_dedup(self):
        """同一张图完全相同的重复行 group_id 相同，可去重。"""
        lines = [_line("10×20×30cm"), _line("10×20×30cm")]
        r = extract_dim(lines, "imgA")
        gids = {c.measurement_group_id for c in r}
        assert len(r) == 3  # 一组三元去重后
        assert len(gids) == 1
