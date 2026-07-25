"""不包含视觉推理的确定性物流公式。

货代费率 (2026-07-26):
  深圳: 80元/kg + 10元/单固定服务费
  义乌: 100元/kg +  6元/单固定服务费

体积重: 长×宽×高(cm) ÷ 8000
计费重: max(实重, 体积重)
包类/非包类只作为商品属性, 不影响费率。

旧规则 "包类80/非包类100" 已于 2026-07-26 作废。
"""

from __future__ import annotations

from typing import Any

from .config import (
    get_exchange_rate_status,
    load_config,
    positive_number,
)

# ---- 货代定义 ----

FREIGHT_FORWARDERS = {
    "sz": {"label": "深圳货代", "rate_per_kg_rmb": 80, "fixed_service_fee_rmb": 10},
    "yw": {"label": "义乌货代", "rate_per_kg_rmb": 100, "fixed_service_fee_rmb": 6},
}

# ---- 核心计算 ----

def calc_volume_weight(
    length_cm: float,
    width_cm: float,
    height_cm: float,
    config: dict[str, Any] | None = None,
) -> float:
    config = config or load_config()
    values = [positive_number(value, name) for value, name in (
        (length_cm, "length_cm"), (width_cm, "width_cm"), (height_cm, "height_cm")
    )]
    return values[0] * values[1] * values[2] / positive_number(
        config["volume_divisor"], "volume_divisor"
    )


def calc_chargeable_weight(actual_weight_kg: float, volume_weight_kg: float) -> float:
    return max(
        positive_number(actual_weight_kg, "actual_weight_kg", allow_zero=True),
        positive_number(volume_weight_kg, "volume_weight_kg", allow_zero=True),
    )


def calc_freight_costs(chargeable_weight_kg: float) -> dict[str, Any]:
    """同时计算两家货代费用，返回 provider_costs + recommended_provider。

    返回:
      {
        "provider_costs": { "深圳货代": {...}, "义乌货代": {...} },
        "recommended_provider": "义乌货代",
        "recommended_cost_rmb": 16.0,
      }
    """
    w = positive_number(chargeable_weight_kg, "chargeable_weight_kg", allow_zero=True)
    costs = {}
    lowest = None
    lowest_key = ""
    for key, fw in FREIGHT_FORWARDERS.items():
        total = round(w * fw["rate_per_kg_rmb"] + fw["fixed_service_fee_rmb"], 2)
        costs[fw["label"]] = {
            "rate_per_kg_rmb": fw["rate_per_kg_rmb"],
            "fixed_service_fee_rmb": fw["fixed_service_fee_rmb"],
            "total_cost_rmb": total,
        }
        if lowest is None or total < lowest:
            lowest = total
            lowest_key = fw["label"]
    return {
        "provider_costs": costs,
        "recommended_provider": lowest_key,
        "recommended_cost_rmb": lowest,
    }


def calc_head_cost(
    chargeable_weight_kg: float,
    category_type: str,
    config: dict[str, Any] | None = None,
) -> float:
    """[兼容保留] 使用推荐货代计算头程。新调用应用 calc_freight_costs。"""
    freight = calc_freight_costs(chargeable_weight_kg)
    return freight["recommended_cost_rmb"]


# ---- deprecated: retained for signature compatibility only ----

def get_freight_rate(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """[已作废] 请改用 calc_freight_costs() 同时计算两家。
    
    保留此函数仅用于向后兼容旧调用者(如 calc_logistics),
    返回推荐货运的费用信息。
    """
    freight = calc_freight_costs(0.0)
    rec = freight["recommended_provider"]
    cost = freight["provider_costs"][rec]
    return {"head_price_per_kg": cost["rate_per_kg_rmb"], "fixed_service_fee": cost["fixed_service_fee_rmb"]}


def _category(category_type: str, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """[已作废] 旧的按包类/非包类选择费率。仅用于 calc_logistics 签名兼容。"""
    from .config import normalize_category
    key = normalize_category(category_type, config)
    # no longer reads config["categories"] — returns dummy
    return key, {"category_cn": "已作废", "head_price_per_kg": 0, "fixed_service_fee": 0}


def calc_tail_cost(
    usd_cny_rate: float | None = None,
    config: dict[str, Any] | None = None,
) -> float:
    config = config or load_config()
    rate = config["usd_cny_rate"] if usd_cny_rate is None else usd_cny_rate
    return round(float(config["tail_fee_usd"]) * positive_number(rate, "usd_cny_rate"), 2)


def calc_total_cost(
    head_cost: float,
    tail_cost_cny: float,
    category_type: str,
    config: dict[str, Any] | None = None,
) -> float:
    config = config or load_config()
    return round(
        positive_number(head_cost, "head_cost", allow_zero=True)
        + positive_number(tail_cost_cny, "tail_cost_cny", allow_zero=True),
        2,
    )


def infer_chargeable_weight_from_head_cost(
    actual_head_cost: float,
    category_type: str,
    config: dict[str, Any] | None = None,
) -> float:
    config = config or load_config()
    freight = calc_freight_costs(0.0)
    rate = freight["provider_costs"][freight["recommended_provider"]]["rate_per_kg_rmb"]
    cost = positive_number(actual_head_cost, "actual_head_cost", allow_zero=True)
    return cost / rate


def compare_head_cost_feedback(
    estimated_head_cost: float,
    actual_head_cost: float,
    category_type: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_config()
    estimated = positive_number(estimated_head_cost, "estimated_head_cost")
    actual = positive_number(actual_head_cost, "actual_head_cost", allow_zero=True)
    error_amount = actual - estimated
    error_percent = error_amount / estimated if estimated else 0
    threshold = config.get("correction_threshold", {})
    attention = (
        abs(error_amount) > float(threshold.get("amount_cny", 5))
        or abs(error_percent) > float(threshold.get("percent", 0.1))
    )
    direction = "underestimate" if error_amount > 0 else "overestimate" if error_amount < 0 else "match"
    return {
        "estimated_chargeable_weight": infer_chargeable_weight_from_head_cost(
            estimated, category_type, config
        ),
        "implied_actual_chargeable_weight": infer_chargeable_weight_from_head_cost(
            actual, category_type, config
        ),
        "error_amount": error_amount,
        "error_percent": error_percent,
        "error_direction": direction,
        "need_attention": attention,
    }


def calc_logistics(
    length_cm: float,
    width_cm: float,
    height_cm: float,
    actual_weight_kg: float,
    product_category: str,
    usd_to_cny: float | None = None,
    *,
    packaging_profile_key: str | None = None,
) -> dict[str, Any]:
    config = load_config()
    volume_weight = calc_volume_weight(length_cm, width_cm, height_cm, config)
    chargeable_weight = calc_chargeable_weight(actual_weight_kg, volume_weight)
    freight = calc_freight_costs(chargeable_weight)
    rate = config["usd_cny_rate"] if usd_to_cny is None else usd_to_cny
    tail_cost = calc_tail_cost(rate, config)
    rate_status = get_exchange_rate_status(config)
    return {
        "length_cm": float(length_cm),
        "width_cm": float(width_cm),
        "height_cm": float(height_cm),
        "actual_weight_kg": round(float(actual_weight_kg), 3),
        "volume_weight_kg": round(volume_weight, 4),
        "chargeable_weight_kg": round(chargeable_weight, 4),
        "packaging_profile_key": packaging_profile_key or "",
        "first_leg_rate": freight["provider_costs"][freight["recommended_provider"]]["rate_per_kg_rmb"],
        "first_leg_cost": freight["recommended_cost_rmb"],
        "last_leg_cost_usd": config["tail_fee_usd"],
        "usd_to_cny": float(rate),
        "usd_cny_rate_updated_at": rate_status["updated_at"],
        "usd_cny_rate_source": rate_status["source"],
        "usd_cny_rate_is_stale": rate_status["is_stale"],
        "last_leg_cost_cny": tail_cost,
        "provider_costs": freight["provider_costs"],
        "recommended_provider": freight["recommended_provider"],
        "recommended_cost_rmb": freight["recommended_cost_rmb"],
        "total_cost": calc_total_cost(freight["recommended_cost_rmb"], tail_cost, product_category, config),
        "formula_version": config["formula_version"],
    }
