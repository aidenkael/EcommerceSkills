"""请求新鲜度守卫测试 — 结果身份字段必须存在。"""
from __future__ import annotations

import pytest
from logistics_cost.request_freshness_guard import validate_request_freshness, RequestFreshnessViolation


class TestPass:
    def test_all_match(self):
        validate_request_freshness("req-123", "sig-A", "Title", "SKU1", 1,
                                   "req-123", "sig-A", "Title", "SKU1", 1)


class TestBlockMissing:
    def test_result_request_id_empty_blocks(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness("req-123", "sig-A", "Title", "SKU1", 1,
                                       "", "sig-A", "Title", "SKU1", 1)

    def test_result_signature_empty_blocks(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness("req-123", "sig-A", "Title", "SKU1", 1,
                                       "req-123", "", "Title", "SKU1", 1)

    def test_all_empty_blocks(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness("req-123", "sig-A", "Title", "SKU1", 1,
                                       "", "", "", "", 0)


class TestBlockMismatch:
    def test_request_id(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness("req-123", "sig-A", "Title", "SKU1", 1,
                                       "req-999", "sig-A", "Title", "SKU1", 1)

    def test_signature(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness("req-123", "sig-A", "Title", "SKU1", 1,
                                       "req-123", "sig-B", "Title", "SKU1", 1)

    def test_title(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness("req-123", "sig-A", "Title", "SKU1", 1,
                                       "req-123", "sig-A", "Wrong", "SKU1", 1)

    def test_sku(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness("req-123", "sig-A", "Title", "SKU1", 1,
                                       "req-123", "sig-A", "Title", "SKU2", 1)

    def test_quantity(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness("req-123", "sig-A", "Title", "SKU1", 1,
                                       "req-123", "sig-A", "Title", "SKU1", 99)
