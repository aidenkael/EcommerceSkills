"""请求新鲜度守卫 — 确保结果 dict 包含完整身份字段并与请求一致。

validate_request_freshness(request=req, result=result) 直接检查结果字典键。
字段缺失立即阻断；字段存在但值不同立即阻断。
程序守卫只保护同次调用内身份一致性。
"""
from __future__ import annotations


class RequestFreshnessViolation(Exception):
    pass


def validate_request_freshness(request, result: dict) -> None:
    """校验 ProductRequest 与 result dict 的身份一致。

    Args:
        request: ProductRequest 对象
        result: estimate 返回的 result dict（必须含 _request_id / _product_signature / _title / _selected_sku / _quantity）

    Raises:
        RequestFreshnessViolation: 字段缺失或不一致
    """
    # 请求侧
    if not request.request_id:
        raise RequestFreshnessViolation("请求侧 request_id 缺失")
    if not request.product_signature:
        raise RequestFreshnessViolation("请求侧 product_signature 缺失")

    # 结果侧字段存在性（使用 key in result，不用默认值）
    for key in ("_request_id", "_product_signature", "_title", "_selected_sku", "_quantity"):
        if key not in result:
            raise RequestFreshnessViolation(f"结果缺少 {key} 键")

    # 逐项比对
    if result["_request_id"] != request.request_id:
        raise RequestFreshnessViolation(
            f"_request_id 不一致: result={result['_request_id']} vs request={request.request_id}"
        )
    if result["_product_signature"] != request.product_signature:
        raise RequestFreshnessViolation("_product_signature 不一致")
    if result["_title"] != request.title:
        raise RequestFreshnessViolation(
            f"_title 不一致: result={result['_title']!r} vs request={request.title!r}"
        )
    if result["_selected_sku"] != request.selected_sku:
        raise RequestFreshnessViolation(
            f"_selected_sku 不一致: result={result['_selected_sku']!r} vs request={request.selected_sku!r}"
        )
    if result["_quantity"] != request.quantity:
        raise RequestFreshnessViolation(
            f"_quantity 不一致: result={result['_quantity']} vs request={request.quantity}"
        )
