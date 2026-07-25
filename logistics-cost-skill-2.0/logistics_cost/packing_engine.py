"""把有依据的尺寸重量范围转换为现实打包结果。"""

from __future__ import annotations

from math import prod
from typing import Any


class InsufficientVisualFactsError(ValueError):
    """缺少尺寸或重量范围时拒绝输出伪精确结果。"""


def _mid(bounds: list[float]) -> float:
    return sum(bounds) / 2


def _rounded(values: list[float]) -> dict[str, float]:
    return {name: round(max(value, 0.5), 1) for name, value in zip(
        ("length_cm", "width_cm", "height_cm"), values
    )}


def _fold(values: list[float], count: int, settle_ratio: float) -> list[float]:
    result = values[:]
    for _ in range(count):
        index = 0 if result[0] >= result[1] else 1
        result[index] /= 2
        result[2] *= 2 * settle_ratio
    return result


def _fold_count(facts: dict[str, Any], profile: dict[str, Any], mode: str, dimensions: list[float]) -> int:
    if facts["has_rigid_parts"] or facts["requires_shape_retention"]:
        return 0
    foldability = facts["foldability"]
    if foldability == "unknown":
        foldability = profile.get("behavior", {}).get("foldability", "none")
    if foldability not in {"good", "limited"}:
        return 0
    maximum = int(profile["packing"][mode].get("max_folds", 0))
    if foldability == "limited":
        maximum = min(maximum, 1)
    if facts["shape_type"] != "long" or max(dimensions[:2]) < 35:
        maximum = min(maximum, 1)
    return maximum


def _dimensions(facts: dict[str, Any], profile: dict[str, Any], mode: str) -> tuple[dict[str, float], int]:
    ranges = facts.get("dimension_range_cm")
    if not ranges:
        raise InsufficientVisualFactsError("缺少尺寸范围；请由AI给出范围或由用户提供尺寸")
    base = [(_mid(ranges[field]) if mode == "normal" else ranges[field][1])
            for field in ("length_cm", "width_cm", "height_cm")]
    if facts["dimension_kind"] == "packaged":
        return _rounded(base), 0
    policy = profile["packing"][mode]
    folds = _fold_count(facts, profile, mode, base)
    values = _fold(base, folds, float(policy.get("settle_ratio", 1)))
    compression = float(policy.get("compression_ratio", 1))
    values[2] *= compression
    allowance = policy.get("allowance_cm", [0, 0, 0])
    values = [value + float(allowance[index]) for index, value in enumerate(values)]
    return _rounded(values), folds


def _weight(facts: dict[str, Any], profile: dict[str, Any], mode: str) -> float:
    bounds = facts.get("weight_range_kg")
    if not bounds:
        raise InsufficientVisualFactsError("缺少重量范围；请由AI给出范围或由用户提供重量")
    weight = (_mid(bounds) if mode == "normal" else bounds[1]) * facts["quantity"]
    if facts["weight_kind"] != "gross":
        weight += float(profile["packing"][mode].get("packaging_weight_kg", 0))
    return round(weight, 3)


def build_packaging_estimates(facts: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """使用范围中值和上沿生成常规、偏松两档，不追求极限压缩。"""
    warnings: list[str] = []
    if facts["dimension_source"] == "visual_estimate" and not facts["has_scale_reference"]:
        warnings.append("尺寸来自无可靠参照物的视觉范围，已保留较宽保守区间。")
    if facts["weight_source"] == "visual_estimate":
        warnings.append("重量来自视觉范围，只能通过后续实际头程费用校准计费重量。")
    if facts["quantity"] > 1:
        warnings.append("多件商品的叠放或嵌套方式待后续反馈校准。")
    result: dict[str, Any] = {"warnings": warnings, "packaging_method": profile["packaging_method"]}
    folds: dict[str, int] = {}
    for mode in ("normal", "conservative"):
        dimensions, folds[mode] = _dimensions(facts, profile, mode)
        result[mode] = {**dimensions, "actual_weight_kg": _weight(facts, profile, mode)}
    normal_volume = prod(result["normal"][field] for field in ("length_cm", "width_cm", "height_cm"))
    conservative_volume = prod(result["conservative"][field] for field in ("length_cm", "width_cm", "height_cm"))
    if conservative_volume < normal_volume:
        warnings.append("保守体积小于常规体积，包装画像需要复核。")
    result["fold_count"] = folds
    result["dimension_range_cm"] = facts["dimension_range_cm"]
    result["weight_range_kg"] = facts["weight_range_kg"]
    return result
