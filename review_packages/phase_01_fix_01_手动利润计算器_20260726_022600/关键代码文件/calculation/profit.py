"""
利润计算模块

公式：
  总成本 = 商品成本 + 发往义乌运费 + 总物流成本
  利润金额 = 售价人民币 - 总成本
  利润率(%) = 利润金额 ÷ 售价人民币 × 100
  建议售价 = 总成本 ÷ (1 - 目标利润率/100 - 推广预留比例/100)

所有输入必须是非负数值，缺失或非法返回 None。
"""


def total_cost(product_cost, domestic_shipping, logistics_cost):
    """
    计算总成本

    Args:
        product_cost:      商品成本 (元)
        domestic_shipping: 发往义乌中转仓运费 (元)
        logistics_cost:    总物流成本 (元)

    Returns:
        float: 总成本 (元)，缺失项按 0 计算
    """
    total = 0.0
    if product_cost is not None:
        total += product_cost
    if domestic_shipping is not None:
        total += domestic_shipping
    if logistics_cost is not None:
        total += logistics_cost
    return total


def profit_amount(selling_price_rmb, total_cost_val):
    """
    计算利润金额

    Args:
        selling_price_rmb: 售价人民币 (元)
        total_cost_val:    总成本 (元)

    Returns:
        float: 利润金额 (元)
        None:  售价或总成本缺失/非法
    """
    if selling_price_rmb is None or total_cost_val is None:
        return None
    if selling_price_rmb < 0:
        return None
    return selling_price_rmb - total_cost_val


def profit_rate(selling_price_rmb, total_cost_val):
    """
    计算利润率 (%)

    Args:
        selling_price_rmb: 售价人民币 (元)，必须 > 0
        total_cost_val:    总成本 (元)

    Returns:
        float: 利润率 (%)
        None:  售价缺失/为零/负数 或 总成本缺失
    """
    if selling_price_rmb is None or total_cost_val is None:
        return None
    if selling_price_rmb <= 0:
        return None
    profit = profit_amount(selling_price_rmb, total_cost_val)
    if profit is None:
        return None
    return (profit / selling_price_rmb) * 100


def suggested_price_from_rate(total_cost_val, target_rate, promotion_rate):
    """
    根据目标利润率和推广预留比例反算建议售价

    公式：售价 = 总成本 ÷ (1 - 目标利润率/100 - 推广预留比例/100)

    Args:
        total_cost_val:  总成本 (元)，必须 >= 0
        target_rate:     目标利润率 (%)，必须 >= 0
        promotion_rate:  推广预留比例 (%)，必须 >= 0

    Returns:
        float: 建议售价 (元)
        None:  总成本缺失，或目标利润率 + 推广预留 >= 100%
    """
    if total_cost_val is None:
        return None
    if target_rate is None or promotion_rate is None:
        return None
    if target_rate < 0 or promotion_rate < 0:
        return None

    total_rate = (target_rate + promotion_rate) / 100.0
    if total_rate >= 1.0:
        return None  # 无法覆盖成本

    return total_cost_val / (1.0 - total_rate)
