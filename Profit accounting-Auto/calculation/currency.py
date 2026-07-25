"""
货币换算模块

公式：
  人民币 → 美元: USD = RMB ÷ 汇率
  美元 → 人民币: RMB = USD × 汇率
"""


def rmb_to_usd(rmb, exchange_rate):
    """
    人民币转美元

    Args:
        rmb:           人民币金额
        exchange_rate: 汇率 (1 USD = ? RMB)，必须 > 0

    Returns:
        float: 美元金额
        None:  rmb 或汇率缺失/非法
    """
    if rmb is None or exchange_rate is None:
        return None
    if exchange_rate <= 0:
        return None
    if rmb < 0:
        return None
    return rmb / exchange_rate


def usd_to_rmb(usd, exchange_rate):
    """
    美元转人民币

    Args:
        usd:           美元金额
        exchange_rate: 汇率 (1 USD = ? RMB)，必须 > 0

    Returns:
        float: 人民币金额
        None:  usd 或汇率缺失/非法
    """
    if usd is None or exchange_rate is None:
        return None
    if exchange_rate <= 0:
        return None
    if usd < 0:
        return None
    return usd * exchange_rate
