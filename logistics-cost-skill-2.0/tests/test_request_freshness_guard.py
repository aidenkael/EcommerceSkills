"""请求新鲜度守卫测试 — request_freshness_guard.py。"""
from __future__ import annotations

import pytest
from logistics_cost.request_freshness_guard import validate_request_freshness, RequestFreshnessViolation


class TestPass:
    def test_all_match(self):
        validate_request_freshness(
            "req-123", "sig-A", "Title", "SKU1", 1,
            "req-123", "sig-A", "Title", "SKU1", 1,
        )

    def test_empty_result_fields_passes(self):
        validate_request_freshness(
            "req-123", "sig-A", "Title", "SKU1", 1,
            "", "", "", "", 0,
        )


class TestBlock:
    def test_request_id_mismatch(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(
                "req-123", "sig-A", "Title", "SKU1", 1,
                "req-999", "sig-A", "Title", "SKU1", 1,
            )

    def test_signature_mismatch(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(
                "req-123", "sig-A", "Title", "SKU1", 1,
                "req-123", "sig-B", "Title", "SKU1", 1,
            )

    def test_title_mismatch(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(
                "req-123", "sig-A", "Title", "SKU1", 1,
                "req-123", "sig-A", "Wrong", "SKU1", 1,
            )

    def test_sku_mismatch(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(
                "req-123", "sig-A", "Title", "SKU1", 1,
                "req-123", "sig-A", "Title", "SKU2", 1,
            )

    def test_quantity_mismatch(self):
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(
                "req-123", "sig-A", "Title", "SKU1", 1,
                "req-123", "sig-A", "Title", "SKU1", 99,
            )
