"""Validate AI-proposed packaging without allowing AI to calculate costs."""

from __future__ import annotations

from math import isfinite, prod
from typing import Any

from .config import load_config, positive_number


FORBIDDEN_FIELDS = {
    "head_cost", "head_cost_cny", "first_leg_cost", "rate", "head_rate",
    "head_rate_cny_per_kg", "volume_divisor", "chargeable_weight",
    "chargeable_weight_kg", "volume_weight", "volume_weight_kg", "category_type",
    "estimated_head_cost", "conservative_head_cost", "head_price_per_kg",
    "tail_cost", "tail_cost_cny", "service_fee", "fixed_service_fee",
    "total_cost", "total_cost_cny", "exchange_rate", "usd_cny_rate",
}
CONFIDENCE = {"low", "medium", "high"}


class PackagingDecisionError(ValueError):
    """Raised when an AI proposal violates a hard input contract."""


def _contains_forbidden(value: Any, path: str = "packaging_scenarios") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_FIELDS:
                found.append(f"{path}.{key}")
            found.extend(_contains_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_contains_forbidden(child, f"{path}[{index}]"))
    return found


def _dimensions(value: Any, field: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise PackagingDecisionError(f"{field} 必须是三个数字")
    result = [positive_number(item, field) for item in value]
    if not all(isfinite(item) for item in result):
        raise PackagingDecisionError(f"{field} 必须是有限数字")
    return [round(item, 4) for item in result]


def _action(value: Any) -> str:
    return str(value or "none").strip().lower().replace("_", " ")


def _boolean(value: Any, field: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise PackagingDecisionError(f"{field} 必须是JSON布尔值")
    return value


def _normalize_scenario(raw: dict[str, Any], mode: str) -> dict[str, Any]:
    dimensions = _dimensions(raw.get("packaged_size_cm"), f"{mode}.packaged_size_cm")
    weight = positive_number(raw.get("packaged_weight_kg"), f"{mode}.packaged_weight_kg")
    if not isfinite(weight):
        raise PackagingDecisionError(f"{mode}.packaged_weight_kg 必须是有限数字")
    reason = str(raw.get("reason") or "").strip()
    method = str(raw.get("method") or raw.get("packaging_method") or "").strip()
    confidence = str(raw.get("confidence") or "low").strip().lower()
    if not reason:
        raise PackagingDecisionError(f"{mode}.reason 不能为空")
    if not method:
        raise PackagingDecisionError(f"{mode}.method 不能为空")
    if confidence not in CONFIDENCE:
        raise PackagingDecisionError(f"{mode}.confidence 只能是 high/medium/low")
    used_evidence_indices = raw.get("used_evidence_indices")
    if not isinstance(used_evidence_indices, list) or not used_evidence_indices:
        raise PackagingDecisionError(f"{mode}.used_evidence_indices 必须是非空数组")
    if any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in used_evidence_indices):
        raise PackagingDecisionError(f"{mode}.used_evidence_indices 只能包含非负整数")
    return {
        "packaged_size_cm": dimensions,
        "packaged_weight_kg": round(weight, 6),
        "method": method,
        "folding_action": str(raw.get("folding_action") or "none").strip(),
        "compression_action": str(raw.get("compression_action") or "none").strip(),
        "requires_box": _boolean(raw.get("requires_box"), f"{mode}.requires_box"),
        "requires_bubble_wrap": _boolean(raw.get("requires_bubble_wrap"), f"{mode}.requires_bubble_wrap"),
        "used_evidence_indices": list(dict.fromkeys(used_evidence_indices)),
        "reason": reason,
        "confidence": confidence,
        "needs_review": _boolean(raw.get("needs_review"), f"{mode}.needs_review"),
    }


def _relative_match(left: list[float], right: list[float], tolerance: float) -> bool:
    return all(abs(a - b) <= max(abs(b) * tolerance, 0.1) for a, b in zip(sorted(left), sorted(right)))


def _is_soft(summary: dict[str, Any]) -> bool:
    material = str(summary.get("material") or "").lower().replace("-", "_")
    return (
        summary.get("rigidity") == "soft"
        or summary.get("foldability") in {"good", "limited"}
        or summary.get("compression") in {"good", "limited", "moderate", "high"}
        or any(word in material for word in ("fabric", "textile", "plush", "silicone", "soft_pu", "knit", "felt"))
    )


def validate_packaging_scenarios(
    product_summary: dict[str, Any],
    evidence_resolution: dict[str, Any],
    scenarios: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return normalized scenarios plus sticky review/error information."""
    forbidden = _contains_forbidden(scenarios)
    if forbidden:
        raise PackagingDecisionError(f"AI包装方案不得提供费用或公式字段: {', '.join(forbidden)}")
    if not isinstance(scenarios, dict) or not all(isinstance(scenarios.get(mode), dict) for mode in ("normal", "conservative")):
        raise PackagingDecisionError("AI必须同时提供 normal 和 conservative 两档包装方案")
    config = config or load_config()
    quality = config.get("evidence_quality", {})
    reject_tolerance = float(quality.get("scenario_rejected_match_tolerance", 0.05))
    packaged_tolerance = float(quality.get("packaged_evidence_dimension_tolerance", 0.02))
    packaged_weight_tolerance = float(quality.get("packaged_evidence_weight_tolerance", 0.02))
    hard_protection_ratio = float(quality.get("hard_protection_min_volume_ratio", 1.02))
    max_axis = float(quality.get("max_axis_without_context_cm", 200))
    small_volume_limit = float(quality.get("small_item_max_volume_weight_kg", 0.3))
    soft_bag_volume_limit = float(quality.get("soft_bag_max_volume_weight_kg", 1.0))
    small_weight_limit = float(quality.get("small_item_max_weight_kg", 0.5))
    max_weight_multiple = float(quality.get("scenario_max_weight_multiple", 5))
    max_weight_addition = float(quality.get("scenario_max_weight_addition_kg", 0.5))
    soft_min_axis_ratio = float(quality.get("soft_package_min_axis_ratio", 0.05))
    soft_min_volume_ratio = float(quality.get("soft_package_min_volume_ratio", 0.03))
    divisor = float(config["volume_divisor"])
    normal = _normalize_scenario(scenarios["normal"], "normal")
    conservative = _normalize_scenario(scenarios["conservative"], "conservative")
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def error(code: str, reason: str) -> None:
        errors.append({"code": code, "reason": reason})

    def warn(code: str, reason: str) -> None:
        warnings.append({"code": code, "reason": reason})

    if prod(conservative["packaged_size_cm"]) < prod(normal["packaged_size_cm"]):
        error("conservative_volume_below_normal", "保守档包装体积不得小于正常档")
    if conservative["packaged_weight_kg"] < normal["packaged_weight_kg"]:
        error("conservative_weight_below_normal", "保守档包装重量不得小于正常档")

    accepted_dimensions = evidence_resolution.get("accepted_dimensions")
    accepted_weight = evidence_resolution.get("accepted_weight")
    context_dimensions = evidence_resolution.get("context_dimensions") or []
    dimension_items = context_dimensions + ([accepted_dimensions] if accepted_dimensions else [])
    dimension_indices = {item.get("evidence_index") for item in dimension_items}
    weight_indices = {accepted_weight.get("evidence_index")} if accepted_weight else set()
    usable_indices = (dimension_indices | weight_indices) - {None}
    soft = _is_soft(product_summary)
    allows_shape_reduction = (
        product_summary.get("rigidity") == "soft"
        and not bool(product_summary.get("requires_shape_retention"))
        and (
            product_summary.get("foldability") in {"good", "limited"}
            or product_summary.get("compression") in {"good", "limited", "moderate", "high"}
        )
    )
    rigid = product_summary.get("rigidity") == "hard" or bool(product_summary.get("requires_shape_retention"))
    product_type = str(product_summary.get("product_type") or "").lower()
    small = product_summary.get("size_class") in {"tiny", "small"} or any(
        word in product_type for word in ("keychain", "hair_clip", "hair_accessory", "hairpin", "barrette", "bag_charm", "small_ornament")
    )
    rigid_min = product_summary.get("rigid_part_min_size_cm")
    if product_summary.get("has_rigid_parts") and not rigid_min:
        # rigid_part_size_missing: 如果 AI 提供了有效包装尺寸且未设置折叠/强压缩，降级为 warn
        has_valid_pkg = (
            all(isinstance(d, (int, float)) and d > 0 for d in normal["packaged_size_cm"])
            and len(normal["packaged_size_cm"]) == 3
        )
        is_hard_or_semi = product_summary.get("rigidity") in ("hard", "semi_rigid")
        n_fold_raw = str(normal.get("folding_action", "")).strip()
        c_fold_raw = str(conservative.get("folding_action", "")).strip()
        n_comp_raw = str(normal.get("compression_action", "")).strip()
        c_comp_raw = str(conservative.get("compression_action", "")).strip()
        # 折叠/压缩检查: 直接检查原始值, 不使用 _action 归一化
        no_fold = all(a in ("", "none", "no", "无", "不折", "不折叠", "n/a")
                     for a in (n_fold_raw, c_fold_raw))
        no_strong_compress = all(a in ("", "none", "no", "无", "不压缩", "轻度压缩", "弱压", "light", "n/a")
                                for a in (n_comp_raw, c_comp_raw))
        if has_valid_pkg and is_hard_or_semi and no_fold and no_strong_compress:
            warn("rigid_part_size_unverified", "硬质部件最小外廓未提供, 但包装方案已禁用折叠/强压缩, 以 AI 包装尺寸继续计算")
        else:
            error("rigid_part_size_missing", "商品包含硬质部件，但缺少硬质部件最小外廓，不能验证折叠方案")

    for mode, scenario in (("normal", normal), ("conservative", conservative)):
        folding = _action(scenario["folding_action"])
        compression = _action(scenario["compression_action"])
        used_indices = set(scenario["used_evidence_indices"])
        unknown_indices = used_indices - usable_indices
        if unknown_indices:
            error("invalid_evidence_reference", f"{mode}档引用了未采用或不存在的证据索引: {sorted(unknown_indices)}")
        if dimension_indices and dimension_indices.isdisjoint(used_indices):
            error("dimension_evidence_not_cited", f"{mode}档未引用采用的尺寸或折叠依据")
        if weight_indices and weight_indices.isdisjoint(used_indices):
            error("weight_evidence_not_cited", f"{mode}档未引用采用的重量证据")
        scenario_volume_weight = prod(scenario["packaged_size_cm"]) / divisor
        if max(scenario["packaged_size_cm"]) > max_axis:
            error("scenario_axis_anomaly", f"{mode}档包装最大边超过安全复核阈值")
        if small and scenario_volume_weight > small_volume_limit:
            error("small_item_package_anomaly", f"{mode}档小商品包装体积重异常偏大")
        if small and scenario["packaged_weight_kg"] > small_weight_limit:
            error("small_item_package_weight_anomaly", f"{mode}档小商品包装重量异常偏大")
        if product_summary.get("category_type") == "bag" and soft and scenario_volume_weight > soft_bag_volume_limit:
            error("soft_bag_package_anomaly", f"{mode}档软袋包装体积重异常偏大")
        if rigid and folding not in {"", "none", "no", "不折叠", "无"}:
            error("rigid_item_folded", f"{mode}档对硬质或需保形商品提出了折叠")
        if product_summary.get("rigidity") == "hard" and compression not in {"", "none", "no", "不压缩", "无"}:
            error("hard_item_compressed", f"{mode}档对硬质商品提出了压缩")
        if product_summary.get("rigidity") == "hard" and product_summary.get("fragility") in {"medium", "high"}:
            if not scenario["requires_box"] and not scenario["requires_bubble_wrap"]:
                error("hard_item_protection_missing", f"{mode} scenario lacks box or bubble protection")
        if scenario["confidence"] == "low":
            warn("low_packaging_confidence", f"{mode}档包装方案置信度低")

        for rejected in evidence_resolution.get("rejected_dimensions") or []:
            rejected_value = rejected.get("value_cm")
            if rejected_value and _relative_match(scenario["packaged_size_cm"], rejected_value, reject_tolerance):
                error("rejected_dimension_reused", f"{mode}档直接复用了已拒绝的{rejected.get('interpreted_as', '尺寸')}数据")

        if accepted_dimensions:
            body = accepted_dimensions.get("value_cm")
            context = accepted_dimensions.get("interpreted_as")
            if context == "packaged_size" and body and not _relative_match(scenario["packaged_size_cm"], body, packaged_tolerance):
                error("packaged_dimension_changed", f"{mode}档与可信包装尺寸偏差过大，不得重复打包")
            if context == "product_body_size" and body and rigid:
                scenario_sorted = sorted(scenario["packaged_size_cm"])
                body_sorted = sorted(body)
                if any(after + 0.1 < before for after, before in zip(scenario_sorted, body_sorted)):
                    error("rigid_package_smaller_than_product", f"{mode}档包装外廓小于硬质商品本体")
                if product_summary.get("fragility") in {"medium", "high"} and prod(scenario_sorted) < prod(body_sorted) * hard_protection_ratio:
                    error("hard_protection_allowance_missing", f"{mode}档硬质易损商品包装未留出保护空间")
        if accepted_dimensions and accepted_dimensions.get("interpreted_as") == "product_body_size":
            body = accepted_dimensions.get("value_cm")
            if body:
                scenario_sorted = sorted(scenario["packaged_size_cm"])
                body_sorted = sorted(body)
                smaller_than_body = any(
                    after + 0.1 < before for after, before in zip(scenario_sorted, body_sorted)
                )
                if smaller_than_body and not allows_shape_reduction:
                    code = "rigid_package_smaller_than_product" if rigid else "unverified_structure_compression"
                    error(code, f"{mode}档未确认可折叠时，包装外廓不得小于商品本体")
                if allows_shape_reduction:
                    axis_ratio = min(after / before for after, before in zip(scenario_sorted, body_sorted))
                    volume_ratio = prod(scenario_sorted) / prod(body_sorted)
                    if axis_ratio < soft_min_axis_ratio or volume_ratio < soft_min_volume_ratio:
                        error("soft_package_overcompressed", f"{mode}档软商品包装相对本体压缩过度")

        if rigid_min:
            minimum = _dimensions(rigid_min, "product_summary.rigid_part_min_size_cm")
            if any(after + 0.1 < before for after, before in zip(sorted(scenario["packaged_size_cm"]), sorted(minimum))):
                error("rigid_part_overcompressed", f"{mode}档包装尺寸小于硬质部件最小外廓")

        if accepted_weight:
            evidence_weight = float(accepted_weight.get("value_kg", 0))
            if accepted_weight.get("interpreted_as") == "gross_weight" and abs(scenario["packaged_weight_kg"] - evidence_weight) > max(evidence_weight * packaged_weight_tolerance, 0.005):
                error("packaged_weight_changed", f"{mode}档改变了可信毛重，不得重复增加包材")
            max_package_weight = max(evidence_weight * max_weight_multiple, evidence_weight + max_weight_addition)
            if scenario["packaged_weight_kg"] > max_package_weight:
                error("package_weight_growth_anomaly", f"{mode}档包装重量相对采用证据增长异常")
            elif scenario["packaged_weight_kg"] + 1e-9 < evidence_weight:
                error("packaged_weight_below_evidence", f"{mode}档包装重量小于采用的净重/毛重")

    if soft and context_dimensions:
        unfolded_max = max(max(item["value_cm"]) for item in context_dimensions if item.get("value_cm"))
        for mode, scenario in (("normal", normal), ("conservative", conservative)):
            for item in context_dimensions:
                unfolded = item.get("value_cm")
                if not unfolded:
                    continue
                scenario_sorted = sorted(scenario["packaged_size_cm"])
                unfolded_sorted = sorted(unfolded)
                axis_ratio = min(after / before for after, before in zip(scenario_sorted, unfolded_sorted))
                volume_ratio = prod(scenario_sorted) / prod(unfolded_sorted)
                if axis_ratio < soft_min_axis_ratio or volume_ratio < soft_min_volume_ratio:
                    error("soft_package_overcompressed", f"{mode}档软商品包装相对展开几何压缩过度")
            if max(scenario["packaged_size_cm"]) >= unfolded_max * 0.95:
                error("soft_unfolded_size_reused", f"{mode}档仍把软商品展开尺寸当作包装最大边")

    resolution_blocked = evidence_resolution.get("status") == "blocked"
    if resolution_blocked:
        error("insufficient_safe_evidence", "没有足够安全的尺寸或重量证据支撑包装方案")
    review_reasons = list(evidence_resolution.get("review_reasons") or [])
    review_reasons.extend(item["reason"] for item in errors + warnings)
    if normal["needs_review"] or conservative["needs_review"]:
        review_reasons.append("AI包装方案主动要求人工复核")
    review_reasons = list(dict.fromkeys(review_reasons))
    return {
        "normal": normal,
        "conservative": conservative,
        "parameter_source": "ai_proposal_validated_by_python",
        "validator_version": config.get("packaging_validator_version", "unknown"),
        "can_calculate": not errors,
        "needs_review": bool(review_reasons),
        "review_reasons": review_reasons,
        "validation_errors": errors,
        "validation_warnings": warnings,
    }
