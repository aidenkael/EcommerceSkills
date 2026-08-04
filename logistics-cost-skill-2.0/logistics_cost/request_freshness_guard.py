"""请求新鲜度守卫 — 确保当前结果与当前请求身份一致。

提供 validate_request_freshness() 在输出前校验。
"""
from __future__ import annotations


class RequestFreshnessViolation(Exception):
    """结果身份与请求不一致。"""
    pass


def validate_request_freshness(
    request_id: str,
    product_signature: str,
    title: str,
    selected_sku: str,
    quantity: int,
    result_request_id: str = "",
    result_signature: str = "",
    result_title: str = "",
    result_sku: str = "",
    result_quantity: int = 0,
) -> None:
    """校验当前请求身份与结果身份一致。

    任一不一致时抛出 RequestFreshnessViolation，阻止输出旧结果。

    Args:
        request_id: 当前请求 ID
        product_signature: 当前商品签名
        title: 当前标题
        selected_sku: 当前 SKU
        quantity: 当前数量
        result_request_id: 结果中绑定的 request_id（可为空表示未绑定）
        result_signature: 结果中绑定的 product_signature
        result_title: 结果中的标题
        result_sku: 结果中的 SKU
        result_quantity: 结果中的数量
    """
    if result_request_id and result_request_id != request_id:
        raise RequestFreshnessViolation(
            f"结果request_id({result_request_id})与当前请求({request_id})不一致"
        )

    if result_signature and result_signature != product_signature:
        raise RequestFreshnessViolation(
            f"结果product_signature与当前商品不匹配"
        )

    if result_title and result_title != title:
        raise RequestFreshnessViolation(
            f"结果标题与当前商品标题不一致"
        )

    if result_sku and result_sku != selected_sku:
        raise RequestFreshnessViolation(
            f"结果SKU与当前商品SKU不一致"
        )

    if result_quantity and result_quantity != quantity:
        raise RequestFreshnessViolation(
            f"结果数量({result_quantity})与当前数量({quantity})不一致"
        )
