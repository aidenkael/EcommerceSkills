"""Configuration-driven local packaging calibration.

This module adjusts packaging candidates only.  It never calculates freight.
Evidence-rich external-AI candidates are retained; conflicts are surfaced for
review instead of being silently overwritten.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import BASE_DIR


DEFAULT_PROFILE_PATH = BASE_DIR / "config" / "packaging_calibration_profile_v1.json"
SUPPORTED_STATES = {
    "full_flat_fold", "strong_compression", "moderate_compression",
    "shape_retained", "unknown",
}
STRUCTURE_FLAGS = (
    "has_hard_bottom", "has_hard_backboard", "has_frame",
    "has_rigid_insert", "has_rigid_parts", "requires_shape_retention",
    "retail_box_visible", "hard_card_visible",
)
SAFE_PROFILE = {
    "schema_version": "safe-fallback",
    "profile_version": "built-in-safe-default",
    "enabled": False,
    "supported_packaging_states": sorted(SUPPORTED_STATES),
    "active_rules": [],
    "tentative_rules": [],
    "observation_rules": [],
    "safety_limits": {
        "minimum_axis_cm": 1.0,
        "maximum_axis_cm": 200.0,
        "unknown_state_allows_aggressive_compression": False,
    },
    "evidence_refs": [],
}


def _validate_profile(profile: dict[str, Any]) -> None:
    required = {
        "schema_version", "profile_version", "enabled",
        "supported_packaging_states", "active_rules", "tentative_rules",
        "observation_rules", "safety_limits", "evidence_refs",
    }
    missing = required.difference(profile)
    if missing:
        raise ValueError(f"calibration profile missing fields: {sorted(missing)}")
    if not isinstance(profile["enabled"], bool):
        raise ValueError("calibration profile enabled must be boolean")
    if set(profile["supported_packaging_states"]) != SUPPORTED_STATES:
        raise ValueError("calibration profile packaging states do not match schema")
    for group in ("active_rules", "tentative_rules", "observation_rules"):
        if not isinstance(profile[group], list):
            raise ValueError(f"{group} must be a list")
        for rule in profile[group]:
            if not all(key in rule for key in ("id", "enabled", "conditions", "ranges", "prohibitions", "evidence_refs")):
                raise ValueError(f"invalid rule in {group}")
            for value in rule["ranges"].values():
                if not isinstance(value, list) or len(value) != 2 or value[0] > value[1]:
                    raise ValueError(f"invalid range in rule {rule['id']}")


def load_calibration_profile(
    profile_path: str | Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Load the profile, returning safe fallback plus an explicit warning on failure."""
    path = Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH
    try:
        with path.open("r", encoding="utf-8") as file:
            profile = json.load(file)
        _validate_profile(profile)
        return profile, []
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return deepcopy(SAFE_PROFILE), [f"包装校准配置加载失败，已使用内置安全默认且未自动压缩: {exc}"]


def _rule(profile: dict[str, Any], rule_id: str) -> dict[str, Any] | None:
    for group in ("active_rules", "tentative_rules"):
        for item in profile.get(group, []):
            if item.get("id") == rule_id and item.get("enabled"):
                return item
    return None


def _mid(rule: dict[str, Any], key: str) -> float:
    low, high = rule["ranges"][key]
    return (float(low) + float(high)) / 2.0


def _scale_smallest(dims: list[float], ratio: float, minimum: float) -> list[float]:
    adjusted = [float(value) for value in dims]
    index = min(range(3), key=adjusted.__getitem__)
    adjusted[index] = max(minimum, adjusted[index] * ratio)
    return [round(value, 4) for value in adjusted]


def _full_fold(dims: list[float], secondary_ratio: float, thickness_ratio: float, minimum: float) -> list[float]:
    adjusted = [float(value) for value in dims]
    indices = sorted(range(3), key=adjusted.__getitem__, reverse=True)
    adjusted[indices[1]] = max(minimum, adjusted[indices[1]] * secondary_ratio)
    adjusted[indices[2]] = max(minimum, adjusted[indices[2]] * thickness_ratio)
    return [round(value, 4) for value in adjusted]


def _all_structure_flags_explicitly_false(summary: dict[str, Any]) -> bool:
    return all(summary.get(name) is False for name in STRUCTURE_FLAGS)


def calibrate_packaging_scenarios(
    product_summary: dict[str, Any],
    scenarios: dict[str, Any],
    *,
    profile_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return calibrated scenarios and an auditable before/after decision."""
    profile, warnings = load_calibration_profile(profile_path)
    original = deepcopy(scenarios)
    adjusted = deepcopy(scenarios)
    state = str(product_summary.get("packaging_state") or "unknown")
    source = str(product_summary.get("proposal_source") or "legacy_local")
    metadata: dict[str, Any] = {
        "profile_version": profile.get("profile_version"),
        "packaging_state": state,
        "proposal_source": source,
        "applied_rules": [],
        "conflicts": [],
        "warnings": list(warnings),
        "original_scenarios": original,
        "adjusted_scenarios": adjusted,
    }
    if not profile.get("enabled") or state not in SUPPORTED_STATES:
        if state not in SUPPORTED_STATES:
            metadata["warnings"].append(f"未知 packaging_state={state}，未自动压缩")
        return adjusted, metadata
    if product_summary.get("dimension_scope") == "shipping_package_size":
        metadata["warnings"].append("尺寸已确认为 shipping_package_size，本地校准不得改写")
        return adjusted, metadata
    if state == "unknown":
        metadata["warnings"].append("包装结构信息不足，packaging_state=unknown，禁止自动强压缩")
        return adjusted, metadata
    if state == "shape_retained":
        return adjusted, metadata

    safe_structure = _all_structure_flags_explicitly_false(product_summary)
    if not safe_structure:
        metadata["conflicts"].append("包装状态要求压缩，但硬结构/保形字段存在、为真或仍未知")
        return adjusted, metadata

    rule = _rule(profile, state)
    if rule is None:
        return adjusted, metadata
    minimum = float(profile["safety_limits"].get("minimum_axis_cm", 1.0))
    material = str(product_summary.get("material") or "").lower()
    thin_rule = _rule(profile, "thin_soft_fabric_fold")
    thin_matches = bool(
        thin_rule
        and state in thin_rule["conditions"].get("packaging_states", [])
        and product_summary.get("hard_card_visible") is False
        and any(marker in material for marker in thin_rule["conditions"].get("material_markers", []))
        and any(marker in material for marker in thin_rule["conditions"].get("material_family_markers", []))
    )
    protrusion_rule = (
        _rule(profile, "soft_flattened_protrusion")
        if product_summary.get("protrusion_flattenable") is True
        else None
    )

    def proposed(mode: str) -> list[float]:
        dims = list(adjusted[mode]["packaged_size_cm"])
        if state == "full_flat_fold" and mode == "normal":
            thickness_rule = thin_rule if thin_matches else rule
            return _full_fold(
                dims,
                _mid(rule, "normal_secondary_axis_ratio"),
                _mid(thickness_rule, "normal_thickness_ratio"),
                minimum,
            )
        key = "normal_thickness_ratio" if mode == "normal" else "conservative_thickness_ratio"
        ratio_rule = protrusion_rule or (thin_rule if thin_matches else rule)
        return _scale_smallest(dims, _mid(ratio_rule, key), minimum)

    candidates = {mode: proposed(mode) for mode in ("normal", "conservative")}
    if source in {"external_ai", "vision_api"}:
        if any(candidates[mode] != adjusted[mode]["packaged_size_cm"] for mode in candidates):
            metadata["conflicts"].append(
                "AI包装候选与本地校准区间不一致；已保留AI原始候选，未静默覆盖"
            )
        return adjusted, metadata

    for mode, dims in candidates.items():
        adjusted[mode]["packaged_size_cm"] = dims
        adjusted[mode]["needs_review"] = bool(adjusted[mode].get("needs_review"))
        adjusted[mode]["reason"] = (
            f"{adjusted[mode].get('reason', '')}；本地条件规则 {state} "
            f"按原候选比例生成{mode}档"
        ).strip("；")
    metadata["applied_rules"].append(rule["id"])
    if thin_matches and thin_rule["id"] not in metadata["applied_rules"]:
        metadata["applied_rules"].append(thin_rule["id"])
    if protrusion_rule and protrusion_rule["id"] not in metadata["applied_rules"]:
        metadata["applied_rules"].append(protrusion_rule["id"])
    metadata["adjusted_scenarios"] = deepcopy(adjusted)
    return adjusted, metadata
