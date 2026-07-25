"""
物流计算模块

公式：
  体积重(kg) = 长(cm) × 宽(cm) × 高(cm) ÷ 8000
  计费重量(kg) = max(实际重量, 体积重)
  头程费用 = 计费重量 × 头程单价
  总物流成本 = 头程费用 + 固定服务费 + 尾程费用

所有输入必须是非负数值，缺失值返回 None。
"""

VOLUME_DIVISOR = 8000  # 体积重除数 (cm³ → kg)


def volumetric_weight(length_cm, width_cm, height_cm):
    """
    计算体积重 (kg)

    Args:
        length_cm: 长 (cm)，必须 >= 0
        width_cm:  宽 (cm)，必须 >= 0
        height_cm: 高 (cm)，必须 >= 0

    Returns:
        float: 体积重 (kg)
        None:  任一参数为 None 或负数
    """
    if any(v is None for v in (length_cm, width_cm, height_cm)):
        return None
    if any(v < 0 for v in (length_cm, width_cm, height_cm)):
        return None
    return (length_cm * width_cm * height_cm) / VOLUME_DIVISOR


def chargeable_weight(actual_weight_kg, vol_weight_kg):
    """
    计算计费重量：取实际重量与体积重的较高值

    Args:
        actual_weight_kg: 实际重量 (kg)，必须 >= 0
        vol_weight_kg:    体积重 (kg)，必须 >= 0

    Returns:
        float: 计费重量 (kg)
        None:  任一参数为 None 或负数
    """
    if actual_weight_kg is None or vol_weight_kg is None:
        return None
    if actual_weight_kg < 0 or vol_weight_kg < 0:
        return None
    return max(actual_weight_kg, vol_weight_kg)


def head_haul_cost(chargeable_weight_kg, rate_per_kg):
    """
    计算头程费用

    Args:
        chargeable_weight_kg: 计费重量 (kg)
        rate_per_kg:          头程单价 (元/kg)

    Returns:
        float: 头程费用 (元)
        None:  任一参数缺失或非法
    """
    if chargeable_weight_kg is None or rate_per_kg is None:
        return None
    if chargeable_weight_kg < 0 or rate_per_kg < 0:
        return None
    return chargeable_weight_kg * rate_per_kg


def total_logistics_cost(head_haul, fixed_service_fee, tail_haul):
    """
    计算总物流成本（严格模式：任意一项缺失返回 None）

    Args:
        head_haul:        头��费用 (元)
        fixed_service_fee: 固定服务费 (元)
        tail_haul:         尾程费用 (元)

    Returns:
        float: 总物流成本 (元)
        None:  任一参数为 None 或负数
    """
    if head_haul is None or fixed_service_fee is None or tail_haul is None:
        return None
    if head_haul < 0 or fixed_service_fee < 0 or tail_haul < 0:
        return None
    return head_haul + fixed_service_fee + tail_haul


def known_logistics_subtotal(head_haul, fixed_service_fee, tail_haul):
    """
    计算已知物流费用之和（仅用于界面显示下限）

    Returns:
        float: 已知部分之和
    """
    total = 0.0
    if head_haul is not None:
        total += head_haul
    if fixed_service_fee is not None:
        total += fixed_service_fee
    if tail_haul is not None and tail_haul >= 0:
        total += tail_haul
    return total
