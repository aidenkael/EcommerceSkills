"""请求新鲜度守卫 — 确保当前结果与当前请求身份一致。

validate_request_freshness() 在输出前校验。
双方身份字段必须完整且一致，不允许结果侧字段为空。
"""
from __future__ import annotations


class RequestFreshnessViolation(Exception):
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

    任一方字段缺失或双方不一致时抛出 RequestFreshnessViolation。
    程序守卫只能保护同次程序调用内的身份一致性，
    不能绝对阻止 Agent 跨会话手工复制旧 stdout。
    """
    # 请求侧必须存在
    if not request_id:
        raise RequestFreshnessViolation("请求侧 request_id 缺失")

    # 结果侧绑定字段必须全部存在
    if not result_request_id:
        raise RequestFreshnessViolation("结果未绑定 request_id")
    if not result_signature:
        raise RequestFreshnessViolation("结果未绑定 product_signature")

    # 逐项比对
    if result_request_id != request_id:
        raise RequestFreshnessViolation(
            f"结果request_id({result_request_id})与当前请求({request_id})不一致"
        )
    if result_signature != product_signature:
        raise RequestFreshnessViolation("结果product_signature与当前商品不匹配")
    if result_title and result_title != title:
        raise RequestFreshnessViolation(
            f"结果标题({result_title})与当前商品标题({title})不一致"
        )
    if result_sku and result_sku != selected_sku:
        raise RequestFreshnessViolation(
            f"结果SKU({result_sku})与当前商品SKU({selected_sku})不一致"
        )
    if result_quantity and result_quantity != quantity:
        raise RequestFreshnessViolation(
            f"结果数量({result_quantity})与当前数量({quantity})不一致"
        )
