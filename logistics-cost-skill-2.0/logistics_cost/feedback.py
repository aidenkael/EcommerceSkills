"""仅使用实际头程金额的反馈记录、归因和报告。"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime
from math import isfinite
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from .calculator import compare_head_cost_feedback
from .config import load_config, load_package_profiles, normalize_category, positive_number
from .storage import read_csv, write_csv


# ---- 从旧 packaging.py 内联的工具函数 ----

def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("category_type") not in {"bag", "general"}:
        raise ValueError("包装画像 category_type 只能是 bag 或 general")
    for mode in ("normal", "conservative"):
        values = profile.get("packing", {}).get(mode, {})
        if len(values.get("allowance_cm", [])) != 3:
            raise ValueError(f"packing.{mode}.allowance_cm 必须有3个值")
        positive_number(values.get("settle_ratio"), f"packing.{mode}.settle_ratio")
        positive_number(values.get("compression_ratio"), f"packing.{mode}.compression_ratio")
        positive_number(values.get("packaging_weight_kg"), f"packing.{mode}.packaging_weight_kg", allow_zero=True)


def _number(raw: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def diagnose_feedback(
    raw: dict[str, Any],
    comparison: dict[str, Any],
    profiles: dict[str, Any] | None = None,
) -> dict[str, str]:
    estimated = _number(raw, "estimated_head_cost")
    actual = _number(raw, "actual_head_cost")
    conservative = _number(raw, "conservative_head_cost")
    if None not in (estimated, actual, conservative) and min(estimated, conservative) <= actual <= max(estimated, conservative):
        return {
            "diagnosis_code": "expected_packing_range",
            "diagnosis_confidence": "high",
            "diagnosis_reason": "实际头程费用落在正常与保守估算区间内，属于可接受的打包操作差异。",
            "review_focus": "无需修改包装画像，继续积累反馈。",
        }
    if not comparison["need_attention"]:
        return {
            "diagnosis_code": "normal_operational_variance",
            "diagnosis_confidence": "high",
            "diagnosis_reason": "误差未超过金额或比例阈值，按打包人员操作和测量差异记录。",
            "review_focus": "无需修改包装画像，继续积累反馈。",
        }
    profiles = profiles or load_package_profiles()
    profile = profiles.get(str(raw.get("packaging_profile_key") or ""), {})
    behavior = profile.get("behavior", {})
    foldability = str(raw.get("foldability") or behavior.get("foldability") or "unknown")
    volume = _number(raw, "estimated_volume_weight_kg", "volume_weight_kg")
    weight = _number(raw, "estimated_actual_weight_kg", "actual_weight_kg")
    driver = "volume" if volume is not None and weight is not None and volume >= weight else "weight" if weight is not None else "unknown"
    direction = comparison["error_direction"]
    notes = str(raw.get("notes") or "").lower()
    explicit_volume_clue = any(
        word in notes for word in ("尺寸过高", "包装尺寸", "放大过多", "体积", "dimensions", "volume")
    )
    if direction == "overestimate" and (driver == "volume" or explicit_volume_clue):
        code = "package_volume_overestimated"
        if foldability in {"good", "high", "limited"}:
            reason = "最可能高估了折叠/卷绕后的外廓、压缩后厚度，或误用了纸盒/过厚保护。"
            focus = "复查可折叠性、折叠次数范围、压缩后厚度和包装容器。"
        else:
            reason = "最可能高估了裸品比例、缓冲空间或纸盒外廓，使用了过大的保护包装。"
            focus = "复查图片比例、硬质主体尺寸、贴合包装和缓冲材料厚度。"
    elif direction == "underestimate" and driver == "volume":
        code = "package_volume_underestimated"
        reason = "估算由体积重主导但仍偏低，最可能漏算不可压缩部位、保护空间或包装鼓起量。"
        focus = "复查硬质突出部件、易碎保护、空隙和封口后的最大外廓。"
    elif direction == "overestimate" and driver == "weight":
        code = "packed_weight_overestimated"
        reason = "估算由重量主导，最可能高估了商品数量、商品净重或包装材料重量。"
        focus = "复查销售数量、页面净重/毛重含义和包装材料。"
    elif direction == "underestimate" and driver == "weight":
        code = "packed_weight_underestimated"
        reason = "估算由重量主导，最可能漏算多件数量、硬质配件或包装材料重量。"
        focus = "复查销售数量、配件、礼盒和缓冲材料。"
    else:
        code = "packaging_context_incomplete"
        reason = "只有估算与实际头程金额，缺少当时的尺寸、重量或包装判断，无法唯一定位误差来源。"
        focus = "结合原图复查商品数量、类别、可折叠性、包装方式和打包后体积。"
    if foldability in {"good", "high"} and direction == "overestimate":
        reason += " 该画像允许折叠/压缩，应优先检查是否把裸品长度直接当成包装长度。"
    return {
        "diagnosis_code": code,
        "diagnosis_confidence": "medium" if driver != "unknown" or explicit_volume_clue else "low",
        "diagnosis_reason": reason,
        "review_focus": focus,
    }


def dominant_diagnosis(rows: Iterable[dict[str, str]]) -> str:
    codes = [row.get("diagnosis_code", "") for row in rows]
    codes = [code for code in codes if code and code != "normal_operational_variance"]
    return Counter(codes).most_common(1)[0][0] if codes else "normal_operational_variance"


# ---- 反馈记录主逻辑 ----


MODE_NOTE = (
    "当前为头程费用反推纠错：实际金额只能反推计费重量，原因由商品图、包装判断和"
    "误差方向综合诊断，不能据此声称知道真实长宽高或真实重量。"
)

FEEDBACK_FIELDS = [
    "feedback_id", "date", "estimate_id", "product_id", "product_link", "image_path",
    "product_type", "quantity", "category_type", "packaging_profile_key", "packaging_method",
    "shape_type", "size_class", "dimension_source", "weight_source", "foldability", "rigidity", "requires_shape_retention", "fold_count",
    "ai_product_summary", "accepted_dimensions", "accepted_weight", "rejected_evidence",
    "normal_packaged_size", "conservative_packaged_size",
    "estimated_length_cm", "estimated_width_cm",
    "estimated_height_cm", "estimated_actual_weight_kg", "estimated_volume_weight_kg",
    "estimated_head_cost", "conservative_head_cost", "actual_head_cost",
    "estimated_chargeable_weight", "implied_actual_chargeable_weight", "error_amount",
    "error_percent", "error_direction", "need_attention", "within_estimate_range",
    "diagnosis_code", "diagnosis_confidence", "diagnosis_reason", "suggested_action",
    "error_reason_category",
    "applied_to_profile", "notes",
]

REPORT_FIELDS = [
    "category_type", "product_type", "packaging_profile_key", "size_class", "case_count", "avg_error_amount",
    "avg_abs_error_amount", "avg_error_percent", "avg_estimated_chargeable_weight",
    "avg_implied_actual_chargeable_weight", "underestimate_count", "overestimate_count",
    "attention_count", "expected_range_count", "range_coverage_rate",
    "implied_weight_p25", "implied_weight_p50", "implied_weight_p75", "implied_weight_p90",
    "dominant_diagnosis",
    "suggested_profile_update", "notes",
]



ERROR_REASON_CATEGORIES = {
    "PAGE_DATA_MISUSE", "UNFOLDED_SIZE_MISUSE", "SOFT_GOODS_UNDER_FOLDED",
    "SOFT_GOODS_OVER_COMPRESSED", "HARD_GOODS_UNDER_PROTECTED", "WEIGHT_UNDERESTIMATED",
    "WEIGHT_OVERESTIMATED", "PRODUCT_TYPE_MISCLASSIFIED", "CATEGORY_MISCLASSIFIED",
    "SKU_QUANTITY_ERROR", "DETAIL_PAGE_DATA_ERROR", "AI_VISUAL_ERROR", "USER_INPUT_ERROR",
    "UNKNOWN",
}


def _error_reason_category(raw: dict[str, Any], diagnosis_code: str) -> str:
    explicit = str(raw.get("error_reason_category") or "").strip()
    if explicit:
        if explicit not in ERROR_REASON_CATEGORIES:
            raise ValueError("error_reason_category is not allowed")
        return explicit
    notes = str(raw.get("notes") or "").lower()
    if any(word in notes for word in ("unfolded", "flat size")):
        return "UNFOLDED_SIZE_MISUSE"
    if "page data" in notes:
        return "PAGE_DATA_MISUSE"
    foldability = str(raw.get("foldability") or "").strip().lower()
    rigidity = str(raw.get("rigidity") or "").strip().lower()
    shape_retention = str(raw.get("requires_shape_retention") or "").strip().lower()
    requires_shape_retention = shape_retention in {"1", "true", "yes"}
    if diagnosis_code == "package_volume_overestimated":
        if foldability in {"good", "limited"} or rigidity == "soft":
            return "SOFT_GOODS_UNDER_FOLDED"
        return "UNKNOWN"
    if diagnosis_code == "package_volume_underestimated":
        if rigidity in {"hard", "semi_rigid"} or requires_shape_retention:
            return "HARD_GOODS_UNDER_PROTECTED"
        if foldability in {"good", "limited"} or rigidity == "soft":
            return "SOFT_GOODS_OVER_COMPRESSED"
        return "UNKNOWN"
    mapping = {
        "packed_weight_overestimated": "WEIGHT_OVERESTIMATED",
        "packed_weight_underestimated": "WEIGHT_UNDERESTIMATED",
        "packaging_context_incomplete": "UNKNOWN",
    }
    return mapping.get(diagnosis_code, "")

def _format(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}".rstrip("0").rstrip(".") or "0"


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是数字") from exc
    if not isfinite(number):
        raise ValueError(f"{field}必须是有限数字")
    if number < 0 or (positive and number == 0):
        raise ValueError(f"{field} {'必须大于 0' if positive else '不能小于 0'}")
    return number


def _id() -> str:
    return f"FB-{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"


def _continuous_underestimate(
    history: Iterable[dict[str, str]], category: str, profile_key: str
) -> int:
    count = 0
    for row in reversed(list(history)):
        if row.get("category_type") != category or row.get("packaging_profile_key") != profile_key:
            continue
        if row.get("error_direction") != "underestimate":
            break
        count += 1
    return count


def build_feedback_record(
    raw: dict[str, Any],
    config: dict[str, Any] | None = None,
    history: Iterable[dict[str, str]] = (),
) -> dict[str, str]:
    config = config or load_config()
    category = normalize_category(raw.get("category_type"), config)
    estimated = _number(raw.get("estimated_head_cost"), "estimated_head_cost", positive=True)
    actual = _number(raw.get("actual_head_cost"), "actual_head_cost")
    comparison = compare_head_cost_feedback(estimated, actual, category, config)
    context = dict(raw, estimated_head_cost=estimated, actual_head_cost=actual)
    diagnosis = diagnose_feedback(context, comparison)
    profile_key = str(raw.get("packaging_profile_key") or "").strip()
    profile = load_package_profiles().get(profile_key, {})
    behavior = profile.get("behavior", {})
    action = diagnosis["review_focus"]
    warning_at = int(config["correction_threshold"]["continuous_underestimate_warning"])
    if comparison["error_direction"] == "underestimate" and profile_key:
        consecutive = _continuous_underestimate(history, category, profile_key) + 1
        if consecutive >= warning_at:
            action += f" 同一包装画像已连续{consecutive}次低估，应优先复查保护空间和不可压缩部位。"

    conservative = raw.get("conservative_head_cost")
    in_range = False
    if conservative not in (None, ""):
        conservative = _number(conservative, "conservative_head_cost")
        in_range = min(estimated, conservative) <= actual <= max(estimated, conservative)

    feedback_id = str(raw.get("feedback_id") or _id())
    record = {field: str(raw.get(field) or "").strip() for field in FEEDBACK_FIELDS}
    record.update({
        "feedback_id": feedback_id,
        "date": str(raw.get("date") or datetime.now().astimezone().isoformat(timespec="seconds")),
        "product_id": str(raw.get("product_id") or feedback_id),
        "category_type": category,
        "packaging_method": record["packaging_method"] or str(profile.get("packaging_method") or ""),
        "foldability": record["foldability"] or str(behavior.get("foldability") or ""),
        "fold_count": record["fold_count"],
        "estimated_head_cost": _format(estimated),
        "conservative_head_cost": "" if conservative in (None, "") else _format(float(conservative)),
        "actual_head_cost": _format(actual),
        "estimated_chargeable_weight": _format(comparison["estimated_chargeable_weight"]),
        "implied_actual_chargeable_weight": _format(comparison["implied_actual_chargeable_weight"]),
        "error_amount": _format(comparison["error_amount"]),
        "error_percent": _format(comparison["error_percent"]),
        "error_direction": comparison["error_direction"],
        "need_attention": str(comparison["need_attention"]).lower(),
        "within_estimate_range": str(in_range).lower(),
        "diagnosis_code": diagnosis["diagnosis_code"],
        "error_reason_category": _error_reason_category(raw, diagnosis["diagnosis_code"]),
        "diagnosis_confidence": diagnosis["diagnosis_confidence"],
        "diagnosis_reason": diagnosis["diagnosis_reason"],
        "suggested_action": action,
        "applied_to_profile": str(raw.get("applied_to_profile") or "false").lower(),
    })
    return record


def read_feedback(path: Path) -> list[dict[str, str]]:
    return read_csv(path)


def deduplicate_feedback_rows(
    rows: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    positions: dict[str, int] = {}
    for row in rows:
        estimate_id = str(row.get("estimate_id") or "").strip()
        if estimate_id and estimate_id in positions:
            result[positions[estimate_id]] = row
        else:
            if estimate_id:
                positions[estimate_id] = len(result)
            result.append(row)
    return result


def _suggestion(rows: list[dict[str, str]], config: dict[str, Any]) -> str:
    minimum = int(config["correction_threshold"]["min_cases_for_profile_suggestion"])
    weights = [float(row["implied_actual_chargeable_weight"]) for row in rows]
    if len(rows) < minimum:
        return f"累计不足{minimum}条，仅监测。"
    attention = [row for row in rows if row.get("need_attention") == "true"]
    if len(attention) < max(2, len(rows) // 2):
        return "多数反馈处于允许误差或正常—保守区间，暂不修改包装画像。"
    code = dominant_diagnosis(rows)
    messages = {
        "package_volume_overestimated": "模型可能高估打包体积；复查可折叠性、折叠次数、压缩后厚度及是否误用纸盒。",
        "package_volume_underestimated": "模型可能低估打包体积；复查不可压缩部位、缓冲空间和包装外廓。",
        "packed_weight_overestimated": "模型可能高估包装后重量；复查销售数量、净重和包装材料。",
        "packed_weight_underestimated": "模型可能低估包装后重量；复查多件数量、硬质配件和保护材料。",
        "packaging_context_incomplete": "历史记录缺少估算上下文；先补齐商品图与包装判断，再调整画像。",
    }
    base = messages.get(code, "误差方向混合，优先复查尺寸重量范围，不自动修改参数。")
    weights = [float(row["implied_actual_chargeable_weight"]) for row in rows]
    return f"{base} 当前反推计费重量P50={_format(_quantile(weights, .5))}kg，P90={_format(_quantile(weights, .9))}kg。"


def generate_accuracy_report(
    feedback_path: Path,
    report_path: Path,
    config: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    config = config or load_config()
    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in deduplicate_feedback_rows(read_feedback(feedback_path)):
        groups[(row.get("category_type", ""), row.get("product_type", ""), row.get("packaging_profile_key", ""), row.get("size_class", ""))].append(row)

    report = []
    for (category, product_type, profile, size_class), rows in sorted(groups.items()):
        errors = [float(row["error_amount"]) for row in rows]
        percents = [float(row["error_percent"]) for row in rows]
        estimated_weights = [float(row["estimated_chargeable_weight"]) for row in rows]
        actual_weights = [float(row["implied_actual_chargeable_weight"]) for row in rows]
        coverage = sum(row.get("within_estimate_range") == "true" for row in rows)
        report.append({
            "category_type": category,
            "product_type": product_type,
            "packaging_profile_key": profile,
            "size_class": size_class,
            "case_count": str(len(rows)),
            "avg_error_amount": _format(mean(errors)),
            "avg_abs_error_amount": _format(mean(map(abs, errors))),
            "avg_error_percent": _format(mean(percents)),
            "avg_estimated_chargeable_weight": _format(mean(estimated_weights)),
            "avg_implied_actual_chargeable_weight": _format(mean(actual_weights)),
            "underestimate_count": str(sum(row["error_direction"] == "underestimate" for row in rows)),
            "overestimate_count": str(sum(row["error_direction"] == "overestimate" for row in rows)),
            "attention_count": str(sum(row["need_attention"] == "true" for row in rows)),
            "expected_range_count": str(coverage),
            "range_coverage_rate": _format(coverage / len(rows)),
            "implied_weight_p25": _format(_quantile(actual_weights, .25)),
            "implied_weight_p50": _format(_quantile(actual_weights, .5)),
            "implied_weight_p75": _format(_quantile(actual_weights, .75)),
            "implied_weight_p90": _format(_quantile(actual_weights, .9)),
            "dominant_diagnosis": dominant_diagnosis(rows),
            "suggested_profile_update": _suggestion(rows, config),
            "notes": MODE_NOTE + f" 反推计费重量中位数={_format(median(actual_weights))}kg。",
        })
    write_csv(report_path, report, REPORT_FIELDS)
    return report


def rebuild_diagnoses(
    feedback_path: Path,
    estimate_path: Path,
    config: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """用可用的估算记录补齐旧反馈的归因字段。"""
    config = config or load_config()
    estimate_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(estimate_path):
        estimate_groups[row.get("estimate_id", "")].append(row)
    rebuilt: list[dict[str, str]] = []
    for old in read_feedback(feedback_path):
        matches = estimate_groups.get(old.get("estimate_id", ""), [])
        normal = next((row for row in matches if row.get("estimate_mode") == "normal"), {})
        conservative = next((row for row in matches if row.get("estimate_mode") == "conservative"), {})
        context = dict(normal)
        if normal:
            context.update({
                "estimated_length_cm": normal.get("length_cm", ""),
                "estimated_width_cm": normal.get("width_cm", ""),
                "estimated_height_cm": normal.get("height_cm", ""),
                "estimated_actual_weight_kg": normal.get("actual_weight_kg", ""),
                "estimated_volume_weight_kg": normal.get("volume_weight_kg", ""),
                "conservative_head_cost": conservative.get("estimated_head_cost", ""),
            })
        context.update({key: value for key, value in old.items() if value not in (None, "")})
        rebuilt.append(build_feedback_record(context, config, rebuilt))
    write_csv(feedback_path, rebuilt, FEEDBACK_FIELDS)
    return rebuilt
