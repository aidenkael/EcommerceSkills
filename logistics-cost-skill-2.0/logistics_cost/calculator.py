"""不包含视觉推理的确定性物流公式。

头程费率:
  旧规则(已作废): 包类 80元/kg / 非包类 100元/kg, 根据 category 选择
  新规则(当前): 按货代区分
    深圳(sz):  80元/kg + 固定服务费 10元/单
    义乌(yw): 100元/kg + 固定服务费  6元/单
  兼容: default_freight_forwarder 为 null 时, 旧 categories 费率仍然可用

体积重: 长×宽×高(cm) ÷ 8000
计费重: max(实重, 体积重)
"""

from __future__ import annotations

from typing import Any

from .config import (
    get_exchange_rate_status,
    load_config,
    normalize_category,
    positive_number,
)


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


# ---- 货代费率 (2026-07-26 替换旧 categories) ----

def get_freight_rate(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """返回当前使用的货代费率(含单价和固定服务费)。

    优先: freight_forwarders[default_freight_forwarder]
    回退: categories[general] (兼容旧配置)
    """
    config = config or load_config()
    fw = config.get("default_freight_forwarder")
    ff = config.get("freight_forwarders", {})
    if fw and fw in ff:
        return dict(ff[fw])
    # 回退: 旧 categories 费率 (标记为 deprecated)
    cats = config.get("categories", {})
    gen = cats.get("general", cats.get("bag", {}))
    if gen:
        return {"head_price_per_kg": gen.get("head_price_per_kg", 100),
                "fixed_service_fee": gen.get("fixed_service_fee", 6),
                "_deprecated_fallback": True}
    return {"head_price_per_kg": 100, "fixed_service_fee": 6}


# ---- deprecated helper, 保留兼容 ----

def _category(category_type: str, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """[已作废] 旧的按包类/非包类选择费率。保留用于 calc_logistics 等旧入口兼容。"""
    key = normalize_category(category_type, config)
    return key, config["categories"][key]


def calc_head_cost(
    chargeable_weight_kg: float,
    category_type: str,
    config: dict[str, Any] | None = None,
) -> float:
    config = config or load_config()
    rate_info = get_freight_rate(config)
    weight = positive_number(chargeable_weight_kg, "chargeable_weight_kg", allow_zero=True)
    return round(weight * float(rate_info["head_price_per_kg"]), 2)


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
    rate_info = get_freight_rate(config)
    return round(
        positive_number(head_cost, "head_cost", allow_zero=True)
        + positive_number(tail_cost_cny, "tail_cost_cny", allow_zero=True)
        + float(rate_info["fixed_service_fee"]),
        2,
    )


def infer_chargeable_weight_from_head_cost(
    actual_head_cost: float,
    category_type: str,
    config: dict[str, Any] | None = None,
) -> float:
    config = config or load_config()
    _, category = _category(category_type, config)
    cost = positive_number(actual_head_cost, "actual_head_cost", allow_zero=True)
    return cost / float(category["head_price_per_kg"])


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
    error_percent = error_amount / estimated
    threshold = config["correction_threshold"]
    attention = (
        abs(error_amount) > float(threshold["amount_cny"])
        or abs(error_percent) > float(threshold["percent"])
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
    rate_info = get_freight_rate(config)
    category_type, category = _category(product_category, config)  # 旧兼容
    volume_weight = calc_volume_weight(length_cm, width_cm, height_cm, config)
    chargeable_weight = calc_chargeable_weight(actual_weight_kg, volume_weight)
    rate = config["usd_cny_rate"] if usd_to_cny is None else usd_to_cny
    head_cost = calc_head_cost(chargeable_weight, category_type, config)
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
        "category_type": category_type,
        "product_category": category["category_cn"],
        "first_leg_rate": rate_info["head_price_per_kg"],
        "first_leg_cost": head_cost,
        "last_leg_cost_usd": config["tail_fee_usd"],
        "usd_to_cny": float(rate),
        "usd_cny_rate_updated_at": rate_status["updated_at"],
        "usd_cny_rate_source": rate_status["source"],
        "usd_cny_rate_is_stale": rate_status["is_stale"],
        "last_leg_cost_cny": tail_cost,
        "service_fee": rate_info["fixed_service_fee"],
        "total_cost": calc_total_cost(head_cost, tail_cost, category_type, config),
        "formula_version": config["formula_version"],
    }
