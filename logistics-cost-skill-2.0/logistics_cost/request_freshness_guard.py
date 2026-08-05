"""请求新鲜度守卫 — 确保当前结果与当前请求身份一致。

结果侧所有身份字段必须存在并与请求侧逐项一致。
缺失任一字段或值不同均抛出 RequestFreshnessViolation。
程序守卫只能保护同次程序调用内的身份一致性。
"""
from __future__ import annotations


class RequestFreshnessViolation(Exception):
    pass


REQUIRED_RESULT_FIELDS = ("_request_id", "_product_signature", "_title", "_selected_sku", "_quantity")


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
    """校验当前请求身份与结果身份一致。"""
    # 结果侧必填字段检查（空字符串允许但字段必须存在）
    for field, val in [
        ("request_id", result_request_id),
        ("signature", result_signature),
    ]:
        if not val:
            raise RequestFreshnessViolation(f"结果未绑定 {field}")

    # title/sku 允许为空字符串但必须能比对
    if result_title is None:
        raise RequestFreshnessViolation("结果未绑定 title")
    if result_sku is None:
        raise RequestFreshnessViolation("结果未绑定 sku")

    # 逐项比对
    if result_request_id != request_id:
        raise RequestFreshnessViolation(f"结果request_id({result_request_id})≠当前({request_id})")
    if result_signature != product_signature:
        raise RequestFreshnessViolation("结果product_signature不匹配")
    if result_title != title:
        raise RequestFreshnessViolation(f"结果标题({result_title})≠当前({title})")
    if result_sku != selected_sku:
        raise RequestFreshnessViolation(f"结果SKU({result_sku})≠当前({selected_sku})")
    if result_quantity != quantity:
        raise RequestFreshnessViolation(f"结果数量({result_quantity})≠当前({quantity})")
