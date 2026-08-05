"""请求新鲜度守卫测试 — 所有身份字段必须存在。"""
from __future__ import annotations

import pytest
from logistics_cost.request_freshness_guard import validate_request_freshness, RequestFreshnessViolation


def _check(**result_kw):
    kw = {"request_id": "req-123", "product_signature": "sig-A", "title": "T", "selected_sku": "S", "quantity": 1,
          "result_request_id": "req-123", "result_signature": "sig-A", "result_title": "T", "result_sku": "S", "result_quantity": 1}
    kw.update(result_kw)
    validate_request_freshness(**kw)


class TestPass:
    def test_all_match(self): _check()

    def test_both_title_empty(self):
        validate_request_freshness("r", "s", "", "S", 1, "r", "s", "", "S", 1)

    def test_both_sku_empty(self):
        validate_request_freshness("r", "s", "T", "", 1, "r", "s", "T", "", 1)


class TestBlockMissing:
    def test_missing_request_id(self):
        with pytest.raises(RequestFreshnessViolation): _check(result_request_id="")

    def test_missing_signature(self):
        with pytest.raises(RequestFreshnessViolation): _check(result_signature="")

    def test_missing_title(self):
        with pytest.raises(RequestFreshnessViolation): _check(result_title="")

    def test_missing_sku(self):
        with pytest.raises(RequestFreshnessViolation): _check(result_sku="")


class TestBlockMismatch:
    def test_req_id(self):
        with pytest.raises(RequestFreshnessViolation): _check(result_request_id="req-999")

    def test_sig(self):
        with pytest.raises(RequestFreshnessViolation): _check(result_signature="sig-B")

    def test_title(self):
        with pytest.raises(RequestFreshnessViolation): _check(result_title="Wrong")

    def test_sku(self):
        with pytest.raises(RequestFreshnessViolation): _check(result_sku="Wrong")

    def test_quantity(self):
        with pytest.raises(RequestFreshnessViolation): _check(result_quantity=99)
