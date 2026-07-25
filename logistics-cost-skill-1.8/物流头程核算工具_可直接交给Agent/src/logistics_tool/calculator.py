from __future__ import annotations

from typing import Any

from .models import ProductAnalysis
from .utils import clamp, round_or_none


def _volumetric_weight(dimensions: list[float] | None, divisor: float) -> float | None:
    if not dimensions:
        return None
    l, w, h = dimensions
    return l * w * h / divisor


def _add_padding(dimensions: list[float] | None, padding: list[float]) -> list[float] | None:
    if not dimensions:
        return None
    return [max(0.1, float(dimensions[i]) + float(padding[i])) for i in range(3)]


def calculate(
    analysis: ProductAnalysis,
    rules: dict[str, Any],
    calibration: dict[str, Any],
    *,
    tail_cost_rmb: float | None = None,
    other_fixed_cost_rmb: float | None = None,
) -> dict[str, Any]:
    package_cfg = rules["package_adjustments"].get(
        analysis.package_type,
        rules["package_adjustments"]["未知"],
    )
    divisor = float(rules["volume_weight_divisor_cm3_per_kg"])
    package_weight = float(package_cfg["extra_weight_kg"])
    padding = [float(x) for x in package_cfg["padding_cm"]]

    packed_weight = analysis.packed_weight_kg
    if packed_weight is None and analysis.actual_weight_kg is not None:
        packed_weight = analysis.actual_weight_kg + package_weight

    packed_dims = analysis.packed_dimensions_cm
    if packed_dims is None:
        packed_dims = _add_padding(analysis.dimensions_cm, padding)

    volumetric = _volumetric_weight(packed_dims, divisor)
    measurement_sources: list[str] = []
    if packed_weight is not None:
        measurement_sources.append("实重")
    if volumetric is not None:
        measurement_sources.append("体积重")

    if packed_weight is not None or volumetric is not None:
        raw_weight = max(x for x in (packed_weight, volumetric) if x is not None)
        source = "与".join(measurement_sources) + "取较高值"
    else:
        ref = calibration.get("reference_weight_kg")
        if ref is not None:
            raw_weight = float(ref) + package_weight
            source = "相似校准记录推断"
        else:
            raw_weight = 0.10 + package_weight
            source = "无可靠测量，使用保守默认值"

    ratio = calibration.get("historical_correction_ratio")
    strength = float(calibration.get("correction_strength") or 0.0)
    if analysis.confidence == "low":
        strength *= 0.75
    elif analysis.confidence == "high":
        strength *= 1.05
    strength = clamp(strength, 0.0, 0.85)
    corrected_weight = raw_weight
    if ratio is not None:
        corrected_weight = raw_weight * (1.0 + strength * (float(ratio) - 1.0))
    corrected_weight = max(0.001, corrected_weight)

    unc_cfg = rules["uncertainty"]
    if packed_weight is not None and packed_dims is not None:
        uncertainty = float(unc_cfg["measured_weight_and_dimensions"])
    elif packed_weight is not None or packed_dims is not None:
        uncertainty = float(unc_cfg["one_measurement_available"])
    elif calibration.get("neighbor_count", 0) > 0:
        uncertainty = float(unc_cfg["calibration_inferred"])
    else:
        uncertainty = float(unc_cfg["image_only_low_confidence"])
    if analysis.confidence == "low":
        uncertainty += 0.10
    if calibration.get("top_similarity", 0.0) < 0.25:
        uncertainty += 0.08
    uncertainty = clamp(uncertainty, 0.08, float(unc_cfg["max"]))
    weight_low = max(0.001, corrected_weight * (1.0 - uncertainty))
    weight_high = corrected_weight * (1.0 + uncertainty)

    provider_costs: dict[str, Any] = {}
    for name, cfg in rules["providers"].items():
        if not cfg.get("enabled", True):
            continue
        rate = float(cfg["rate_per_kg_rmb"])
        fixed = float(cfg["fixed_service_fee_rmb"])
        provider_costs[name] = {
            "rate_per_kg_rmb": rate,
            "fixed_service_fee_rmb": fixed,
            "estimated_cost_rmb": rate * corrected_weight + fixed,
            "cost_range_rmb": [rate * weight_low + fixed, rate * weight_high + fixed],
        }

    recommended_provider = min(provider_costs, key=lambda n: provider_costs[n]["estimated_cost_rmb"])
    recommended = provider_costs[recommended_provider]
    reasons: list[str] = []
    if analysis.actual_weight_kg is None and analysis.packed_weight_kg is None:
        reasons.append("缺少实重")
    if analysis.dimensions_cm is None and analysis.packed_dimensions_cm is None:
        reasons.append("缺少尺寸")
    if analysis.confidence == "low":
        reasons.append("图片判断置信度低")
    if calibration.get("neighbor_count", 0) == 0:
        reasons.append("没有足够相似的校准记录")
    elif calibration.get("top_similarity", 0.0) < 0.25:
        reasons.append("相似记录匹配较弱")
    crossover = float(rules["selection"].get("provider_crossover_weight_kg", 0.2))
    if weight_low < crossover < weight_high:
        reasons.append("重量区间跨过两家货代成本分界点，推荐货代可能变化")
    needs_review = bool(reasons and (uncertainty >= 0.35 or len(reasons) >= 2))

    tail = tail_cost_rmb
    extra = 0.0 if other_fixed_cost_rmb is None else float(other_fixed_cost_rmb)
    total = None
    if tail is not None:
        total = recommended["estimated_cost_rmb"] + float(tail) + extra

    weight_digits = int(rules["rounding"]["weight_decimals"])
    cost_digits = int(rules["rounding"]["cost_decimals"])
    for item in provider_costs.values():
        item["estimated_cost_rmb"] = round(item["estimated_cost_rmb"], cost_digits)
        item["cost_range_rmb"] = [round(x, cost_digits) for x in item["cost_range_rmb"]]

    return {
        "image_path": analysis.image_path,
        "product_name": analysis.product_name,
        "analysis": analysis.as_dict(),
        "packed_weight_kg": round_or_none(packed_weight, weight_digits),
        "packed_dimensions_cm": packed_dims,
        "volumetric_weight_kg": round_or_none(volumetric, weight_digits),
        "raw_chargeable_weight_kg": round(raw_weight, weight_digits),
        "chargeable_weight_kg": round(corrected_weight, weight_digits),
        "chargeable_weight_range_kg": [round(weight_low, weight_digits), round(weight_high, weight_digits)],
        "weight_source": source,
        "historical_correction_ratio": round_or_none(ratio, 4),
        "historical_correction_strength": round(strength, 4),
        "uncertainty_ratio": round(uncertainty, 4),
        "provider_costs": provider_costs,
        "recommended_provider": recommended_provider,
        "recommended_cost_rmb": provider_costs[recommended_provider]["estimated_cost_rmb"],
        "recommended_cost_range_rmb": provider_costs[recommended_provider]["cost_range_rmb"],
        "optional_total_logistics_rmb": round(total, cost_digits) if total is not None else None,
        "calibration": calibration,
        "needs_review": needs_review,
        "review_reasons": reasons,
        "scope_note": "默认结果仅为头程费用；尾程费用未传入时不计入。",
    }
