"""估算器 — simple-v2.1 唯一流水线。

调用链:
  ai_schema.to_estimate_inputs()  → product_summary + evidence + scenarios
  estimator.estimate()
    → evidence_resolver    (证据仲裁)
    → packaging_decision_ai (包装校验)
    → soft_goods_rules     (软品体积重过冲)
    → weight_rules         (可信重量 +0.05kg)
    → calculator           (确定性头程)

使用:
  result = estimate(
      product_summary={...}, raw_evidence=[...], packaging_scenarios={...},
      user_weight=UserWeight(65, "g", "可信"),
      product_link="https://detail.1688.com/offer/xxx.html",
  )
"""
from __future__ import annotations

import uuid
from datetime import datetime
from math import prod
from pathlib import Path
from typing import Any

from .calculator import calc_head_cost, calc_volume_weight, calc_freight_costs
from .config import BASE_DIR, load_config, normalize_category
from .evidence_resolver import resolve_evidence, _is_soft
from .packaging_decision_ai import validate_packaging_scenarios
from .soft_goods_rules import (
    check_soft_goods_volume, is_soft_goods,
    determine_soft_volume_policy,
    SOFT_VOLUME_POLICY_NOT_SOFT,
)
from .storage import archive_local_image
from .weight_rules import UserWeight, apply_weight_correction


def _volume_weight(dims: list[float], divisor: float) -> float:
    return prod(dims) / divisor if dims and len(dims) == 3 else 0.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _apply_monotonicity_guard(scenarios_result: dict[str, Any]) -> None:
    """v2 保守档单调性保护: 确保保守档计费重和费用不低于正常档。

    不修改正常档, 不交换两档名称, 不倒挂时不做任何事。
    """
    normal = scenarios_result.get("normal") or {}
    conservative = scenarios_result.get("conservative") or {}
    if not normal.get("chargeable_weight_kg") or not conservative.get("chargeable_weight_kg"):
        return

    normal_cw = float(normal["chargeable_weight_kg"])
    cons_cw = float(conservative["chargeable_weight_kg"])
    adjusted = False
    reasons: list[str] = []

    # 检查计费重倒挂
    if cons_cw < normal_cw:
        conservative["chargeable_weight_kg"] = normal_cw
        cons_cw = normal_cw
        adjusted = True
        reasons.append("soft_volume_policy_threshold_inversion")

    # 重新计算保守档费用 (基于修正后的计费重)
    if adjusted:
        from .calculator import calc_freight_costs
        ft = calc_freight_costs(cons_cw)
        rec_provider = ft["recommended_provider"]
        rec_costs = ft["provider_costs"].get(rec_provider, {})
        conservative["provider_costs"] = ft["provider_costs"]
        conservative["recommended_provider"] = rec_provider
        conservative["recommended_cost_rmb"] = ft["recommended_cost_rmb"]
        conservative["head_cost_cny"] = rec_costs.get("head_freight_rmb", 0.0)
        conservative["service_fee_cny"] = rec_costs.get("service_fee_rmb", 0.0)
        conservative["total_head_cost_cny"] = round(
            float(rec_costs.get("head_freight_rmb", 0.0)) + float(rec_costs.get("service_fee_rmb", 0.0)), 2
        )

    # 检查两家货代费用倒挂
    for provider in ("深圳货代", "义乌货代"):
        n_fee = float((normal.get("provider_costs") or {}).get(provider, {}).get("head_freight_rmb", 0))
        c_fee = float((conservative.get("provider_costs") or {}).get(provider, {}).get("head_freight_rmb", 0))
        if c_fee < n_fee and not adjusted:
            adjusted = True
            reasons.append(f"provider_fee_inversion_{provider}")
        if c_fee < n_fee:
            reasons.append(f"{provider}_fee_corrected")

    # 标记诊断
    scenarios_result["scenario_monotonicity_adjusted"] = adjusted
    scenarios_result["scenario_monotonicity_reason"] = "; ".join(reasons) if reasons else ""


def estimate(
    *,
    product_summary: dict[str, Any] | None = None,
    raw_evidence: list[dict[str, Any]] | None = None,
    packaging_scenarios: dict[str, Any] | None = None,
    image_path: str = "",
    product_link: str = "",
    user_weight: UserWeight | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """执行完整的融合估算流水线。

    所有输入字段可选：缺失字段由对应子模块自动推理或拒绝。

    Returns 包含 evidence_resolution, packaging, head_cost 的完整结果。
    """
    config = load_config()
    divisor = float(config["volume_divisor"])
    summary = dict(product_summary or {})
    evidence = list(raw_evidence or [])
    scenarios = dict(packaging_scenarios or {})

    # ---- 1. 证据仲裁 ----
    resolution = resolve_evidence(summary, evidence)

    # ---- 2. 包装校验 ----
    if scenarios and "normal" in scenarios and "conservative" in scenarios:
        category_type = normalize_category(summary.get("category_type"), config)
        if not summary.get("category_type"):
            summary["category_type"] = category_type
        decision = validate_packaging_scenarios(summary, resolution, scenarios)
    else:
        # 无包装方案 → blocked
        decision = {
            "normal": {},
            "conservative": {},
            "can_calculate": False,
            "needs_review": True,
            "review_reasons": [resolution.get("review_reasons", ["缺少包装方案"])][0],
            "validation_errors": resolution.get("issues", []),
            "validation_warnings": [],
        }

    # ---- 3. 计费场景 ----
    category_type = normalize_category(summary.get("category_type"), config)
    # 2026-07-26: 费率按货代区分, 两家同时计算
    accepted_weight = resolution.get("accepted_weight") or {}
    accepted_dimensions = resolution.get("accepted_dimensions") or {}
    ai_net_weight = _safe_float(accepted_weight.get("value_kg"))
    is_packaged = accepted_dimensions.get("interpreted_as") == "packaged_size" if accepted_dimensions else False

    soft = is_soft_goods(summary) or (summary and _is_soft(summary))

    # ---- 3.0 统一软品体积策略 (v2) ----
    overall_form = str(summary.get("overall_form") or scenarios["normal"].get("overall_form", "unknown"))
    normal_dims = (decision.get("normal") or {}).get("packaged_size_cm", [0, 0, 0])
    normal_vol_weight = round(_volume_weight(normal_dims, divisor), 4)
    soft_policy = SOFT_VOLUME_POLICY_NOT_SOFT
    if soft:
        soft_policy = determine_soft_volume_policy(
            is_soft=True,
            is_packaged_dimension=is_packaged,
            overall_form=overall_form,
            ai_net_weight_kg=ai_net_weight,
            normal_volume_weight_kg=normal_vol_weight,
        )

    calculate_ok = decision.get("can_calculate", False)
    scenarios_result = {}

    for mode in ("normal", "conservative"):
        scenario = decision.get(mode) or {}
        if not scenario or not calculate_ok:
            scenarios_result[mode] = {
                "head_cost_cny": 0.0,
                "service_fee_cny": 0.0,
                "total_head_cost_cny": 0.0,
                "chargeable_weight_kg": 0.0,
                "volume_weight_kg": 0.0,
                "provider_costs": {},
                "recommended_provider": "",
                "recommended_cost_rmb": 0.0,
            }
            continue

        dims = scenario.get("packaged_size_cm", [0, 0, 0])
        pkg_weight = _safe_float(scenario.get("packaged_weight_kg"))
        vol_weight = round(_volume_weight(dims, divisor), 4)

        # ---- 3a. 软品体积重检查 (v2: 统一策略) ----
        soft_result = {"volume_ignored": False, "chargeable_kg": pkg_weight, "warning": "", "policy_used": SOFT_VOLUME_POLICY_NOT_SOFT}
        if soft:
            soft_result = check_soft_goods_volume(
                vol_weight, pkg_weight, ai_net_weight,
                is_packaged_dimension=is_packaged,
                soft_volume_policy=soft_policy,
                scenario_label=mode,
            )

        # ---- 3b. 用户重量修正 ----
        if soft_result["volume_ignored"]:
            # 软品忽略体积重后，直接用实重作为计费基础
            chargeable_after_soft = soft_result["chargeable_kg"]
        else:
            # 正常取 max(实重, 体积重)
            from .calculator import calc_chargeable_weight
            chargeable_after_soft = calc_chargeable_weight(pkg_weight, vol_weight)

        weight_result = apply_weight_correction(
            chargeable_after_soft,
            vol_weight,
            user_weight=user_weight,
            no_increment_max_g=int(
                config.get("trusted_weight_no_increment_max_g", 50)
            ),
        )

        chargeable = weight_result["chargeable_kg"]
        freight = calc_freight_costs(chargeable)
        rec_provider = freight["recommended_provider"]
        rec_costs = freight["provider_costs"].get(rec_provider, {})
        head_freight = rec_costs.get("head_freight_rmb", 0.0)
        service_fee = rec_costs.get("service_fee_rmb", 0.0)

        scenarios_result[mode] = {
            "packaged_size_cm": dims,
            "packaged_weight_kg": pkg_weight,
            "volume_weight_kg": vol_weight,
            "chargeable_weight_kg": round(chargeable, 4),
            "head_cost_cny": head_freight,
            "service_fee_cny": service_fee,
            "total_head_cost_cny": round(head_freight + service_fee, 2),
            "provider_costs": freight["provider_costs"],
            "recommended_provider": rec_provider,
            "recommended_cost_rmb": freight["recommended_cost_rmb"],
            "method": scenario.get("method", ""),
            "folding_action": scenario.get("folding_action", ""),
            "soft_volume_ignored": soft_result["volume_ignored"],
            "soft_volume_warning": soft_result["warning"],
            "v21_user_weight_kg": weight_result["user_weight_kg"],
            "v21_trust_status": weight_result["trust_status"],
            "v21_weight_source": weight_result["weight_source"],
            "v21_added_005": weight_result["added_005"],
            "v21_needs_review": weight_result["needs_review"],
            "v21_review_reason": weight_result["review_reason"],
        }

    # ---- 3c. v2 单调性保护: 保守档费用不得低于正常档 ----
    _apply_monotonicity_guard(scenarios_result)

    # ---- 4. 合并输出 ----
    estimate_id = f"EST-{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
    review_reasons: list[str] = []
    for mode in ("normal", "conservative"):
        w = scenarios_result[mode].get("soft_volume_warning", "")
        if w:
            review_reasons.append(w)
        r = scenarios_result[mode].get("v21_review_reason", "")
        if r:
            review_reasons.append(r)
    review_reasons.extend(resolution.get("review_reasons") or [])
    review_reasons.extend(decision.get("review_reasons") or [])
    review_reasons = list(dict.fromkeys(r for r in review_reasons if r))

    result: dict[str, Any] = {
        "estimate_id": estimate_id,
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "calculated" if calculate_ok else "blocked",
        "product_type": summary.get("product_type", "unknown"),
        "category_type": category_type,
        "product_link": product_link,
        "quantity": summary.get("quantity", 1),
        "product_summary": summary,
        "accepted_evidence": {
            "dimensions": accepted_dimensions or None,
            "weight": accepted_weight or None,
            "context_dimensions": resolution.get("context_dimensions", []),
        },
        "rejected_evidence": {
            "dimensions": resolution.get("rejected_dimensions", []),
            "weights": resolution.get("rejected_weights", []),
        },
        "packaging_method": scenarios_result["normal"].get("method", ""),
        "folding_action": scenarios_result["normal"].get("folding_action", ""),
        "normal": scenarios_result["normal"],
        "conservative": scenarios_result["conservative"],
        "needs_review": bool(review_reasons),
        "review_reasons": review_reasons,
        "confidence": str(summary.get("confidence") or "low"),
        "formula_version": config.get("formula_version", "unknown"),
    }

    # ---- 5. 持久化(可选) ----
    if persist and image_path:
        image_dir = BASE_DIR / "data" / "estimate_images"
        archived = archive_local_image(image_path, image_dir, estimate_id)
        if archived:
            try:
                result["image_path"] = Path(archived).resolve().relative_to(BASE_DIR).as_posix()
            except ValueError:
                result["image_path"] = Path(archived).resolve().as_posix()

    return result
