"""请求新鲜度守卫 — 直接检查 result dict 键。"""
from __future__ import annotations

import pytest
from logistics_cost.request_freshness_guard import validate_request_freshness, RequestFreshnessViolation
from logistics_cost.product_request import create_product_request


def _result(req, **overrides):
    r = {"_request_id": req.request_id, "_product_signature": req.product_signature,
         "_title": req.title, "_selected_sku": req.selected_sku, "_quantity": req.quantity}
    r.update(overrides)
    return r


def _req(title="T", sku="S", qty=1):
    return create_product_request(title, sku, qty)


class TestPass:
    def test_all_match(self):
        req = _req()
        validate_request_freshness(request=req, result=_result(req))

    def test_both_title_empty(self):
        req = _req(title="")
        validate_request_freshness(request=req, result=_result(req))

    def test_both_sku_empty(self):
        req = _req(sku="")
        validate_request_freshness(request=req, result=_result(req))


class TestBlockMissing:
    def test_missing_request_id(self):
        req = _req()
        r = _result(req)
        del r["_request_id"]
        with pytest.raises(RequestFreshnessViolation): validate_request_freshness(request=req, result=r)

    def test_missing_signature(self):
        req = _req()
        r = _result(req)
        del r["_product_signature"]
        with pytest.raises(RequestFreshnessViolation): validate_request_freshness(request=req, result=r)

    def test_missing_title(self):
        req = _req()
        r = _result(req)
        del r["_title"]
        with pytest.raises(RequestFreshnessViolation): validate_request_freshness(request=req, result=r)

    def test_missing_sku(self):
        req = _req()
        r = _result(req)
        del r["_selected_sku"]
        with pytest.raises(RequestFreshnessViolation): validate_request_freshness(request=req, result=r)

    def test_missing_quantity(self):
        req = _req()
        r = _result(req)
        del r["_quantity"]
        with pytest.raises(RequestFreshnessViolation): validate_request_freshness(request=req, result=r)


class TestBlockMismatch:
    def test_req_id(self):
        req = _req()
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(request=req, result=_result(req, _request_id="wrong"))

    def test_sig(self):
        req = _req()
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(request=req, result=_result(req, _product_signature="wrong"))

    def test_title(self):
        req = _req()
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(request=req, result=_result(req, _title="Wrong"))

    def test_sku(self):
        req = _req()
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(request=req, result=_result(req, _selected_sku="Wrong"))

    def test_quantity(self):
        req = _req()
        with pytest.raises(RequestFreshnessViolation):
            validate_request_freshness(request=req, result=_result(req, _quantity=99))
