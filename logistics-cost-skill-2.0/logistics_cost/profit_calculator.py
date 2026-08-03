"""确定性按成本利润率计算。

总成本 = 商品成本 + 国内运费 + 总头程 + 尾程
目标利润 = 总成本 × 目标利润率（按成本）
活动预留按售价比例扣减。
"""
from __future__ import annotations

from typing import Any


def _positive(value: Any, name: str) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} 必须是数字")
    if v < 0:
        raise ValueError(f"{name} 必须 >= 0")
    return v


def calculate_profit(
    *,
    product_cost_rmb: float,
    domestic_freight_rmb: float = 0.0,
    total_head_cost_rmb: float,
    tail_cost_rmb: float = 0.0,
    target_profit_markup_percent: float,
    activity_reserve_percent: float = 0.0,
    shein_subsidy_type: str = "none",
    shein_subsidy_value: float = 0.0,
) -> dict[str, Any]:
    """计算建议活动售价和预计利润。

    Args:
        product_cost_rmb: 商品采购成本
        domestic_freight_rmb: 国内运费
        total_head_cost_rmb: 总头程（纯头程+固定服务费）
        tail_cost_rmb: 尾程人民币
        target_profit_markup_percent: 按成本的目标利润加成率（例如20%→20）
        activity_reserve_percent: 活动预留比例（例如15%→15）
        shein_subsidy_type: none / percent_of_sale / fixed_cny
        shein_subsidy_value: 补贴数值
    """
    pc = _positive(product_cost_rmb, "product_cost_rmb")
    df = _positive(domestic_freight_rmb, "domestic_freight_rmb")
    hc = _positive(total_head_cost_rmb, "total_head_cost_rmb")
    tc = _positive(tail_cost_rmb, "tail_cost_rmb")
    markup_pct = _positive(target_profit_markup_percent, "target_profit_markup_percent") / 100.0
    reserve_pct = _positive(activity_reserve_percent, "activity_reserve_percent") / 100.0
    subsidy_type = str(shein_subsidy_type).strip().lower()
    subsidy_val = _positive(shein_subsidy_value, "shein_subsidy_value") if subsidy_type != "none" else 0.0

    C = pc + df + hc + tc
    P = C * markup_pct  # 按成本的目标利润

    if subsidy_type == "none":
        if reserve_pct >= 1.0:
            raise ValueError("活动预留率不能 >= 100%")
        list_price = (C + P) / (1.0 - reserve_pct)
        subsidy_amount = 0.0
    elif subsidy_type == "percent_of_sale":
        subsidy_rate = subsidy_val / 100.0
        denom = 1.0 + subsidy_rate - reserve_pct
        if denom <= 0:
            raise ValueError(f"补贴率+活动预留率组合无效: 分母={denom:.4f}")
        list_price = (C + P) / denom
        subsidy_amount = list_price * subsidy_rate
    elif subsidy_type == "fixed_cny":
        if reserve_pct >= 1.0:
            raise ValueError("活动预留率不能 >= 100%")
        list_price = (C + P - subsidy_val) / (1.0 - reserve_pct)
        if list_price < 0:
            raise ValueError("固定补贴导致售价为负")
        subsidy_amount = subsidy_val
    else:
        raise ValueError(f"shein_subsidy_type 无效: {subsidy_type}")

    activity_deduction = list_price * reserve_pct
    expected_profit = list_price + subsidy_amount - activity_deduction - C

    return {
        "product_cost_rmb": round(pc, 2),
        "domestic_freight_rmb": round(df, 2),
        "total_head_cost_rmb": round(hc, 2),
        "tail_cost_rmb": round(tc, 2),
        "total_cost_rmb": round(C, 2),
        "target_profit_markup_percent": round(markup_pct * 100, 1),
        "target_profit_rmb": round(P, 2),
        "list_price_rmb": round(list_price, 2),
        "activity_reserve_percent": round(reserve_pct * 100, 1),
        "activity_deduction_rmb": round(activity_deduction, 2),
        "shein_subsidy_type": subsidy_type,
        "shein_subsidy_amount_rmb": round(subsidy_amount, 2),
        "expected_profit_rmb": round(expected_profit, 2),
        "expected_profit_rate_on_cost": round(expected_profit / C, 4) if C > 0 else 0.0,
    }
