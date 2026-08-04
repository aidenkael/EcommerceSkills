"""确定性按成本利润率计算 — 双售价模型 (OUTPUT_CONTRACT 2026-08-04-v1)。

公式：
  国内成本 = 采购价 + 国内运费
  核算成本 C = 国内成本 + 最低总头程 + 尾程人民币
  目标利润 P = C × 目标利润率（按成本）

  无活动售价：
    无活动售价人民币 = C + P
    无活动售价USD = 无活动售价人民币 ÷ 汇率
    SHEIN补贴：售价 < $29 时补贴 $2.99, 否则 0
    无活动利润RMB = 无活动售价USD×汇率 + 补贴USD×汇率 - C

  活动后售价：
    活动后售价USD = 无活动售价USD × (1 - 活动预留率)
    SHEIN补贴：售价 < $29 时补贴 $2.99, 否则 0
    活动后利润RMB = 活动后售价USD×汇率 + 补贴USD×汇率 - C
"""

from __future__ import annotations

from typing import Any

from .config import load_config


def _get_shein_subsidy_config():
    """从 logistics_config.json 读取 SHEIN 补贴配置。"""
    cfg = load_config()
    subsidy = cfg.get("shein_subsidy") or {}
    return {
        "price_threshold_usd": float(subsidy.get("price_threshold_usd", 29.0)),
        "amount_usd": float(subsidy.get("amount_usd", 2.99)),
    }


def _positive(value: Any, name: str) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} 必须是数字")
    if v < 0:
        raise ValueError(f"{name} 必须 >= 0")
    return v


def _apply_subsidy(price_usd: float, subsidy_config: dict[str, float]) -> float:
    """根据未舍入的 USD 售价判断补贴是否生效。"""
    if price_usd < subsidy_config["price_threshold_usd"]:
        return subsidy_config["amount_usd"]
    return 0.0


def calculate_profit(
    *,
    product_cost_rmb: float,
    domestic_freight_rmb: float = 0.0,
    total_head_cost_rmb: float,
    tail_cost_rmb: float = 0.0,
    exchange_rate: float,
    target_profit_markup_percent: float,
    activity_reserve_percent: float = 0.0,
) -> dict[str, Any]:
    """双售价利润模型。

    Args:
        product_cost_rmb: 商品采购成本 (¥)
        domestic_freight_rmb: 国内运费 (¥)
        total_head_cost_rmb: 总头程 (纯头程+固定费) (¥)
        tail_cost_rmb: 尾程人民币 (¥)
        exchange_rate: 美元汇率
        target_profit_markup_percent: 按成本的目标利润率 (例如 25%→25)
        activity_reserve_percent: 活动预留率 (例如 15%→15)

    Returns:
        {
            domestic_cost_rmb, total_head_cost_rmb, tail_cost_rmb,
            total_cost_rmb, target_profit_rmb,
            no_activity_price_usd, no_activity_subsidy_usd, no_activity_profit_rmb,
            activity_price_usd, activity_subsidy_usd, activity_profit_rmb,
        }
    """
    pc = _positive(product_cost_rmb, "product_cost_rmb")
    df = _positive(domestic_freight_rmb, "domestic_freight_rmb")
    hc = _positive(total_head_cost_rmb, "total_head_cost_rmb")
    tc = _positive(tail_cost_rmb, "tail_cost_rmb")
    rate = _positive(exchange_rate, "exchange_rate")
    markup_pct = _positive(target_profit_markup_percent, "target_profit_markup_percent") / 100.0
    reserve_pct = _positive(activity_reserve_percent, "activity_reserve_percent") / 100.0

    if reserve_pct >= 1.0:
        raise ValueError("活动预留率不能 >= 100%")

    subsidy_cfg = _get_shein_subsidy_config()

    domestic_cost = round(pc + df, 2)
    C = domestic_cost + hc + tc
    P = C * markup_pct

    # 无活动售价
    no_activity_price_rmb = C + P
    no_activity_price_usd = no_activity_price_rmb / rate
    no_activity_subsidy_usd = _apply_subsidy(no_activity_price_usd, subsidy_cfg)
    no_activity_profit_rmb = (
        no_activity_price_usd * rate + no_activity_subsidy_usd * rate - C
    )

    # 活动后售价
    activity_price_usd = no_activity_price_usd * (1.0 - reserve_pct)
    activity_subsidy_usd = _apply_subsidy(activity_price_usd, subsidy_cfg)
    activity_profit_rmb = (
        activity_price_usd * rate + activity_subsidy_usd * rate - C
    )

    return {
        "domestic_cost_rmb": round(domestic_cost, 2),
        "total_head_cost_rmb": round(hc, 2),
        "tail_cost_rmb": round(tc, 2),
        "total_cost_rmb": round(C, 2),
        "target_profit_rmb": round(P, 2),
        "target_profit_markup_percent": round(markup_pct * 100, 1),
        "no_activity_price_usd": round(no_activity_price_usd, 2),
        "no_activity_subsidy_usd": round(no_activity_subsidy_usd, 2),
        "no_activity_profit_rmb": round(no_activity_profit_rmb, 2),
        "activity_price_usd": round(activity_price_usd, 2),
        "activity_subsidy_usd": round(activity_subsidy_usd, 2),
        "activity_profit_rmb": round(activity_profit_rmb, 2),
    }
