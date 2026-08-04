"""商品请求测试 — product_request.py。"""
from __future__ import annotations

import pytest
from logistics_cost.product_request import create_product_request, ProductRequest, Fact


class TestUniqueIds:
    def test_each_create_unique_request_id(self):
        r1 = create_product_request("A", "SKU1", 1)
        r2 = create_product_request("B", "SKU2", 1)
        assert r1.request_id != r2.request_id

    def test_same_identity_stable_signature(self):
        r1 = create_product_request("透明化妆包", "凯蒂猫大包", 1, image_fingerprint="abc")
        r2 = create_product_request("透明化妆包", "凯蒂猫大包", 1, image_fingerprint="abc")
        assert r1.product_signature == r2.product_signature

    def test_quantity_change_changes_signature(self):
        r1 = create_product_request("A", "SKU1", 1)
        r2 = create_product_request("A", "SKU1", 2)
        assert r1.product_signature != r2.product_signature


class TestFactPriority:
    def test_user_confirmed_overrides_ai_inferred(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("weight", 100, "ai_inferred", "low")
        ok = req.add_fact("weight", 150, "user_confirmed", "high")
        assert ok is True
        assert req.get_fact_value("weight") == 150
        assert req.get_fact("weight").source == "user_confirmed"

    def test_ai_inferred_cannot_override_user_confirmed(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("weight", 150, "user_confirmed", "high")
        ok = req.add_fact("weight", 100, "ai_inferred", "low")
        assert ok is False
        assert req.get_fact_value("weight") == 150
        assert req.get_fact("weight").source == "user_confirmed"

    def test_merchant_text_overrides_ai_inferred(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("weight", 100, "ai_inferred", "low")
        ok = req.add_fact("weight", 200, "merchant_text", "high")
        assert ok is True
        assert req.get_fact_value("weight") == 200

    def test_same_rank_does_not_overwrite(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("weight", 100, "user_confirmed", "high")
        ok = req.add_fact("weight", 200, "user_confirmed", "high")
        assert ok is False
        assert req.get_fact_value("weight") == 100

    def test_calibrated_does_not_override_user_confirmed(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("weight", 150, "user_confirmed", "high")
        ok = req.add_fact("weight", 70, "calibrated", "medium")
        assert ok is False
        assert req.get_fact_value("weight") == 150

    def test_calibrated_overrides_ai_inferred(self):
        req = create_product_request("T", "S", 1)
        req.add_fact("weight", 100, "ai_inferred", "low")
        ok = req.add_fact("weight", 70, "calibrated", "medium")
        assert ok is True
        assert req.get_fact_value("weight") == 70


class TestIsolation:
    def test_different_requests_not_share(self):
        r1 = create_product_request("A", "S1", 1)
        r2 = create_product_request("B", "S2", 1)
        r1.add_fact("weight", 100, "user_confirmed")
        assert r2.get_fact_value("weight") is None
        r1.ai_data_raw = {"x": 1}
        assert r2.ai_data_raw == {}
        r1.run_stdout = "hello"
        assert r2.run_stdout == ""


class TestRequestIdentity:
    def test_basic_creation(self):
        req = create_product_request("TestTitle", "TestSKU", 2, image_fingerprint="fp1")
        assert req.title == "TestTitle"
        assert req.selected_sku == "TestSKU"
        assert req.quantity == 2
        assert len(req.product_signature) == 16

    def test_empty_or_none_input(self):
        req = create_product_request("", "", 0)
        assert req.request_id != ""
        assert len(req.product_signature) == 16
