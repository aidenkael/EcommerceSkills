"""Resolve page, user, OCR, and visual evidence before packaging or costing."""

from __future__ import annotations

import re
from math import isfinite
from typing import Any

from .config import load_config, positive_number


DIMENSION_CONTEXTS = {
    "packaged_size", "product_body_size", "unfolded_flat_size", "wearing_size",
    "size_chart", "carton_size", "variant_max_size", "unknown_context",
}
WEIGHT_CONTEXTS = {
    "gross_weight", "net_weight", "shipping_weight", "carton_weight",
    "variant_max_weight", "unknown_context",
}
REJECT_DIMENSION_CONTEXTS = {
    "unfolded_flat_size", "wearing_size", "size_chart", "carton_size", "variant_max_size",
}
REJECT_WEIGHT_CONTEXTS = {"shipping_weight", "carton_weight", "variant_max_weight"}
CONFIDENCE_SCORE = {"reject": 0, "low": 10, "medium": 20, "high": 30}
SOURCE_SCORE = {
    "unknown": 0, "ocr": 5, "image_visual": 10, "ai_estimated": 12, "page_text": 20, "user_provided": 40,
}
CARTON_WORDS = (
    "carton", "outer box", "case pack", "box of", "master case",
    "整箱", "箱规", "外箱", "装箱数",
)
SMALL_ITEM_WORDS = (
    "keychain", "key_chain", "hair_clip", "hair_accessory", "hairpin", "barrette",
    "bag_charm", "small_ornament", "small_decor", "钥匙扣", "发夹", "发饰", "包挂",
)
SOFT_MATERIAL_WORDS = (
    "fabric", "textile", "plush", "silicone", "soft_pu", "soft pu", "knit", "felt",
    "布", "针织", "毛绒", "硅胶", "软皮",
)
SOFT_PRODUCT_TYPES = (
    "socks", "sock", "stocking", "toe_socks", "invisible_socks", "ankle_socks",
    "shower_cap", "beanie", "thin_beanie", "thin_hat", "bucket_hat_soft",
    "arm_sleeves", "ice_sleeves", "uv_sleeves", "lace_sleeves", "lace_arm_warmers",
    "hair_extensions", "hair_weft", "hair_weft_piece", "hair_bundle",
    "bikini", "swimsuit", "bathing_suit", "swimwear",
    "fabric_ornament", "fabric_patch", "mistletoe_ornament",
    "drawstring_pouch", "fabric_pouch",
    "fabric_belt", "fabric_strap", "nylon_strap",
    "sleep_mask", "eye_mask",
    "fabric_gloves", "fabric_hat", "fabric_scarf", "fabric_headband",
    "cleaning_sponge", "sponge_block",
    "silicone_squishy", "apple_squishy",
    "cosplay_wig", "wig", "synthetic_wig",
    "peva_shower_cap", "shower_cap_peva",
    "non_woven_bag", "non_woven_pouch", "nonwoven",
)


class EvidenceResolutionError(ValueError):
    """Raised when evidence cannot be normalized safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _confidence(value: Any) -> str:
    result = _text(value).lower() or "low"
    return result if result in {"high", "medium", "low", "reject"} else "low"


def _source(value: Any) -> str:
    result = _text(value).lower() or "unknown"
    aliases = {"visual": "image_visual", "page_explicit": "page_text", "image": "image_visual"}
    result = aliases.get(result, result)
    return result if result in SOURCE_SCORE else "unknown"


def _numbers(value: Any, count: int) -> list[float]:
    if isinstance(value, dict):
        ordered = [value.get(key) for key in ("length", "width", "height")]
        if all(item is not None for item in ordered):
            value = ordered
    if isinstance(value, (list, tuple)) and len(value) == count:
        result = [positive_number(item, "evidence.value") for item in value]
        if not all(isfinite(item) for item in result):
            raise EvidenceResolutionError("证据值必须是有限数字")
        return result
    found = re.findall(r"[+\-−]?\d+(?:\.\d+)?", _text(value))
    if len(found) != count:
        raise EvidenceResolutionError(f"证据值需要 {count} 个数字: {value}")
    result = [positive_number(item, "evidence.value") for item in found]
    if not all(isfinite(item) for item in result):
        raise EvidenceResolutionError("证据值必须是有限数字")
    return result




def _unit_tokens(value: Any) -> set[str]:
    text = (
        _text(value).lower()
        .replace("毫米", "mm").replace("厘米", "cm")
        .replace("千克", "kg").replace("公斤", "kg")
        .replace("英寸", "in").replace("克", "g").replace("米", "m")
    )
    return {
        unit for unit in ("mm", "cm", "kg", "lb", "oz", "in", "g", "m")
        if re.search(rf"(?<![a-z]){unit}(?![a-z])", text)
    }


def _unit(raw: dict[str, Any], default: str) -> str:
    explicit = _text(raw.get("unit")).lower().replace("厘米", "cm").replace("毫米", "mm").replace("千克", "kg").replace("克", "g")
    found = _unit_tokens(f"{_text(raw.get('value'))} {_text(raw.get('raw_text'))}")
    native_key = "value_cm" if default == "cm" else "value_kg"
    if native_key in raw:
        if explicit and explicit != default:
            raise EvidenceResolutionError(f"{native_key} 与单位字段 {explicit} 冲突")
        if len(found) > 1:
            raise EvidenceResolutionError(f"{native_key} 的证据原文包含冲突单位: {sorted(found)}")
        return default
    if explicit:
        if found and found != {explicit}:
            raise EvidenceResolutionError(f"单位字段 {explicit} 与证据原文 {sorted(found)} 冲突")
        return explicit
    if len(found) > 1:
        raise EvidenceResolutionError(f"证据原文包含冲突单位: {sorted(found)}")
    if found:
        return next(iter(found))
    if (default == "cm" and "value_cm" in raw) or (default == "kg" and "value_kg" in raw):
        return default
    raise EvidenceResolutionError("证据缺少明确单位")


def _validate_native_equivalence(
    raw: dict[str, Any], native_values: list[float], default: str, count: int,
) -> None:
    raw_text = _text(raw.get("raw_text"))
    raw_value = raw.get("value")
    text_units = _unit_tokens(raw_text)
    if text_units:
        source = raw_text
        units = text_units
    else:
        source = raw_value
        units = _unit_tokens(raw_value)
    if not units:
        return
    if len(units) != 1:
        raise EvidenceResolutionError(f"规范值的原始证据包含冲突单位: {sorted(units)}")
    factors = {
        "cm": {"mm": 0.1, "cm": 1.0, "m": 100.0, "in": 2.54},
        "kg": {"kg": 1.0, "g": 0.001, "lb": 0.45359237, "oz": 0.028349523125},
    }
    factor = factors[default].get(next(iter(units)))
    if factor is None:
        raise EvidenceResolutionError("规范值与原始证据的单位类型冲突")
    raw_numbers = _numbers(source, count)
    converted = [number * factor for number in raw_numbers]
    native_sorted = sorted(native_values) if count == 3 else native_values
    converted_sorted = sorted(converted) if count == 3 else converted
    if any(
        abs(actual - expected) > max(abs(expected) * 0.01, 0.001)
        for actual, expected in zip(native_sorted, converted_sorted)
    ):
        raise EvidenceResolutionError("规范值与原始证据换算后的数值冲突")


def _dimension_cm(raw: dict[str, Any]) -> list[float]:
    value = raw.get("value_cm", raw.get("value"))
    numbers = _numbers(value, 3)
    unit = _unit(raw, "cm")
    if "value_cm" in raw:
        _validate_native_equivalence(raw, numbers, "cm", 3)
        return [round(number, 4) for number in numbers]
    factor = {"mm": 0.1, "cm": 1.0, "m": 100.0, "in": 2.54}.get(unit)
    if factor is None:
        raise EvidenceResolutionError(f"不支持的尺寸单位: {unit}")
    return [round(number * factor, 4) for number in numbers]


def _weight_kg(raw: dict[str, Any]) -> float:
    value = raw.get("value_kg", raw.get("value"))
    number = _numbers(value, 1)[0]
    unit = _unit(raw, "kg")
    if "value_kg" in raw:
        _validate_native_equivalence(raw, [number], "kg", 1)
        return round(number, 6)
    factor = {"kg": 1.0, "g": 0.001, "lb": 0.45359237, "oz": 0.028349523125}.get(unit)
    if factor is None:
        raise EvidenceResolutionError(f"不支持的重量单位: {unit}")
    return round(number * factor, 6)


def _infer_dimension_context(raw: dict[str, Any]) -> str:
    text = _text(raw.get("raw_text")).lower()
    if any(word in text for word in CARTON_WORDS):
        return "carton_size"
    if any(word in text for word in ("size chart", "尺码表", "胸围", "腰围")):
        return "size_chart"
    if any(word in text for word in ("unfolded", "flat size", "展开", "平铺")):
        return "unfolded_flat_size"
    if any(word in text for word in ("wearing size", "circumference", "佩戴尺寸", "头围")):
        return "wearing_size"
    if any(word in text for word in ("variant max", "maximum variant", "largest size", "最大变体", "最大尺码")):
        return "variant_max_size"
    if any(word in text for word in ("package size", "packaged size", "包装尺寸", "包裹尺寸")):
        return "packaged_size"
    if any(word in text for word in ("product size", "item size", "商品尺寸", "本体尺寸")):
        return "product_body_size"
    explicit = _text(raw.get("interpreted_as")).lower()
    if explicit in DIMENSION_CONTEXTS:
        return explicit
    return "unknown_context"


def _infer_weight_context(raw: dict[str, Any]) -> str:
    text = _text(raw.get("raw_text")).lower()
    if any(word in text for word in CARTON_WORDS):
        return "carton_weight"
    if any(word in text for word in ("shipping weight", "chargeable weight", "计费重量", "运输重量")):
        return "shipping_weight"
    if any(word in text for word in ("variant max", "maximum variant", "largest weight", "最大变体", "最大重量")):
        return "variant_max_weight"
    if any(word in text for word in ("gross weight", "毛重", "含包装")):
        return "gross_weight"
    if any(word in text for word in ("net weight", "净重")):
        return "net_weight"
    explicit = _text(raw.get("interpreted_as")).lower()
    if explicit in WEIGHT_CONTEXTS:
        return explicit
    return "unknown_context"


def _normalize(raw: dict[str, Any], index: int) -> dict[str, Any]:
    evidence_type = _text(raw.get("evidence_type")).lower()
    result = {
        **raw,
        "evidence_index": index,
        "evidence_type": evidence_type,
        "source": _source(raw.get("source")),
        "confidence": _confidence(raw.get("confidence")),
        "raw_text": _text(raw.get("raw_text")),
    }
    if evidence_type == "dimension":
        result["interpreted_as"] = _infer_dimension_context(raw)
        result["value_cm"] = _dimension_cm(raw)
    elif evidence_type == "weight":
        result["interpreted_as"] = _infer_weight_context(raw)
        result["value_kg"] = _weight_kg(raw)
    return result


def _is_small_item(summary: dict[str, Any]) -> bool:
    product_type = _text(summary.get("product_type")).lower()
    return any(word in product_type for word in SMALL_ITEM_WORDS) or _text(summary.get("size_class")).lower() in {"tiny", "small"}


def _is_soft(summary: dict[str, Any]) -> bool:
    material = _text(summary.get("material")).lower().replace("-", "_")
    product_type = _text(summary.get("product_type")).lower().replace("-", "_").replace(" ", "_")
    return (
        _text(summary.get("rigidity")).lower() == "soft"
        or _text(summary.get("foldability")).lower() in {"good", "limited"}
        or _text(summary.get("compression")).lower() in {"good", "limited", "moderate", "high"}
        or any(word in material for word in SOFT_MATERIAL_WORDS)
        or any(word in product_type for word in SOFT_PRODUCT_TYPES)
    )


def _volume_weight(dimensions: list[float], divisor: float) -> float:
    return dimensions[0] * dimensions[1] * dimensions[2] / divisor


def _same_scale(left: list[float], right: list[float], ratio: float) -> bool:
    left_sorted, right_sorted = sorted(left), sorted(right)
    return all(max(a / b, b / a) <= ratio for a, b in zip(left_sorted, right_sorted))



def _rank(candidate: dict[str, Any]) -> int:
    context_score = {
        "packaged_size": 50, "product_body_size": 35, "gross_weight": 40,
        "net_weight": 30, "shipping_weight": 20, "unknown_context": 0,
    }.get(candidate.get("interpreted_as"), 0)
    return context_score + SOURCE_SCORE[candidate["source"]] + CONFIDENCE_SCORE[candidate["confidence"]]


def _top_rank_conflicts(
    candidates: list[dict[str, Any]], value_key: str, ratio: float,
) -> list[dict[str, Any]]:
    if len(candidates) < 2:
        return []
    top_rank = max(_rank(candidate) for candidate in candidates)
    contenders = [candidate for candidate in candidates if _rank(candidate) == top_rank]
    for left_index, left in enumerate(contenders):
        for right in contenders[left_index + 1:]:
            if value_key == "value_cm":
                compatible = _same_scale(left[value_key], right[value_key], ratio)
            else:
                left_value, right_value = left[value_key], right[value_key]
                compatible = (
                    max(left_value / right_value, right_value / left_value) <= ratio
                )
            if not compatible:
                return contenders
    return []


def resolve_evidence(
    product_summary: dict[str, Any],
    raw_evidence: list[dict[str, Any]],
    *,
    config: dict[str, Any] | None = None,
    ai_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize, arbitrate, and explain which evidence may enter packaging."""
    config = config or load_config()
    quality = config.get("evidence_quality", {})
    divisor = float(config["volume_divisor"])
    max_axis = float(quality.get("max_axis_without_context_cm", 200))
    visual_conflict_ratio = float(quality.get("visual_conflict_ratio", 3))
    same_rank_dimension_ratio = float(quality.get("same_rank_dimension_conflict_ratio", 3))
    same_rank_weight_ratio = float(quality.get("same_rank_weight_conflict_ratio", 3))
    small_weight_limit = float(quality.get("small_item_max_weight_kg", 0.5))
    small_volume_limit = float(quality.get("small_item_max_volume_weight_kg", 0.3))
    soft_bag_volume_limit = float(quality.get("soft_bag_max_volume_weight_kg", 1.0))
    if ai_review is not None and not isinstance(ai_review, dict):
        raise EvidenceResolutionError("ai_review 必须是JSON对象")
    raw_ai_rejected = (ai_review or {}).get("rejected_evidence_indices", [])
    if not isinstance(raw_ai_rejected, list):
        raise EvidenceResolutionError("rejected_evidence_indices 必须是数组")
    if any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in raw_ai_rejected):
        raise EvidenceResolutionError("rejected_evidence_indices 只能包含非负整数")
    if any(index >= len(raw_evidence) for index in raw_ai_rejected):
        raise EvidenceResolutionError("rejected_evidence_indices包含越界索引")
    ai_rejected = set(raw_ai_rejected)

    normalized: list[dict[str, Any]] = []
    rejected_dimensions: list[dict[str, Any]] = []
    rejected_weights: list[dict[str, Any]] = []
    downweighted_dimensions: list[dict[str, Any]] = []
    downweighted_weights: list[dict[str, Any]] = []
    context_dimensions: list[dict[str, Any]] = []
    other_evidence: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    dimension_candidates: list[dict[str, Any]] = []
    weight_candidates: list[dict[str, Any]] = []
    small_item = _is_small_item(product_summary)
    soft_item = _is_soft(product_summary)
    summary_quantity = int(product_summary.get("quantity") or 1)
    summary_variant = _text(product_summary.get("selected_variant")).lower()

    def reject(candidate: dict[str, Any], code: str, reason: str) -> None:
        enriched = {**candidate, "decision": "reject", "reason_code": code, "reason": reason}
        target = rejected_dimensions if candidate["evidence_type"] == "dimension" else rejected_weights
        target.append(enriched)
        issues.append({"code": code, "severity": "high", "reason": reason})

    for index, raw in enumerate(raw_evidence or []):
        try:
            candidate = _normalize(raw, index)
        except (EvidenceResolutionError, ValueError) as exc:
            evidence_type = _text(raw.get("evidence_type")).lower()
            candidate = {**raw, "evidence_index": index, "evidence_type": evidence_type}
            if evidence_type in {"dimension", "weight"}:
                reject(candidate, "invalid_evidence_value", str(exc))
            else:
                other_evidence.append({**candidate, "decision": "reject", "reason": str(exc)})
            continue
        normalized.append(candidate)
        evidence_type = candidate["evidence_type"]
        if evidence_type not in {"dimension", "weight"}:
            other_evidence.append(candidate)
            continue
        if candidate["confidence"] == "reject":
            reject(candidate, "confidence_rejected", "证据可信度标记为 reject，不得进入包装计算")
            continue
        if index in ai_rejected:
            reject(candidate, "ai_review_rejected", "AI复核认为该证据不应进入包装计算")
            continue
        raw_text = candidate["raw_text"].lower()
        sku_scope = _text(candidate.get("sku_scope")).lower()
        selected_variant = _text(candidate.get("selected_variant")).lower()
        if sku_scope in {"multiple", "mixed", "all_variants"}:
            reject(candidate, "multi_sku_ambiguity", "多个SKU混合证据不能代表当前购买变体")
            continue
        if selected_variant and not summary_variant:
            reject(candidate, "selected_variant_missing", "证据属于特定变体，但商品摘要没有选定当前变体")
            continue
        if summary_variant and selected_variant != summary_variant:
            reject(candidate, "selected_variant_mismatch", "证据未明确对应商品摘要中的选定变体")
            continue
        if summary_quantity > 1:
            try:
                evidence_quantity = positive_number(
                    candidate.get("quantity_basis", candidate.get("quantity")), "evidence.quantity_basis",
                )
            except (TypeError, ValueError):
                reject(candidate, "quantity_scope_ambiguous", "多件销售数量缺少对应的尺寸或重量数量口径")
                continue
            if not evidence_quantity.is_integer() or int(evidence_quantity) != summary_quantity:
                reject(candidate, "quantity_scope_mismatch", "证据数量口径与商品销售数量不一致")
                continue
        if any(word in raw_text for word in CARTON_WORDS):
            reject(candidate, "carton_evidence", "页面文字表明这是整箱、外箱或装箱数据")
            continue

        if evidence_type == "dimension":
            context = candidate["interpreted_as"]
            dimensions = candidate["value_cm"]
            volume_weight = _volume_weight(dimensions, divisor)
            candidate["volume_weight_kg"] = round(volume_weight, 4)
            if context == "unfolded_flat_size" and soft_item and max(dimensions) > max_axis:
                reject(candidate, "oversized_unfolded_dimension", "软商品展开尺寸超过安全阈值，不得作为折叠依据")
                continue
            if small_item and volume_weight > small_volume_limit:
                reject(candidate, "small_item_volume_anomaly", "小饰品/发饰/钥匙扣候选尺寸导致体积重异常偏大")
                continue
            if product_summary.get("category_type") == "bag" and soft_item and volume_weight > soft_bag_volume_limit:
                reject(candidate, "soft_bag_volume_anomaly", "普通软袋候选尺寸导致体积重超过合理复核阈值")
                continue
            if context in REJECT_DIMENSION_CONTEXTS:
                reasons = {
                    "unfolded_flat_size": "展开/平铺尺寸只用于判断折叠，不可直接作为包装外廓",
                    "wearing_size": "佩戴尺寸不是商品包装外廓",
                    "size_chart": "尺码表尺寸不是单件包装尺寸",
                    "carton_size": "整箱尺寸不得用于单件头程计算",
                    "variant_max_size": "最大变体尺寸不能代表当前SKU",
                }
                if context == "unfolded_flat_size" and soft_item:
                    context_dimensions.append({**candidate, "decision": "context_only", "reason": reasons[context]})
                reject(candidate, f"rejected_{context}", reasons[context])
                continue
            if max(dimensions) > max_axis and context == "unknown_context":
                reject(candidate, "oversized_unknown_dimension", "来源不明尺寸明显偏大，可能存在单位或整箱语义错误")
                continue
            if candidate["source"] in {"page_text", "ocr"} and candidate["confidence"] == "low":
                candidate = {**candidate, "decision": "downweight", "reason": "低置信度页面尺寸仅作辅助，不进入包装计算"}
                downweighted_dimensions.append(candidate)
                issues.append({"code": "low_confidence_page_dimension", "severity": "medium", "reason": candidate["reason"]})
                continue
            if context == "unknown_context":
                candidate = {**candidate, "decision": "downweight", "reason": "尺寸上下文不明确，只能低权重参考"}
                downweighted_dimensions.append(candidate)
                issues.append({"code": "unknown_dimension_context", "severity": "medium", "reason": candidate["reason"]})
            else:
                dimension_candidates.append(candidate)
        else:
            context = candidate["interpreted_as"]
            weight = candidate["value_kg"]
            if context in REJECT_WEIGHT_CONTEXTS:
                reason = {"shipping_weight": "运输或计费重量不能作为实物包装重量", "carton_weight": "整箱重量不得用于单件头程计算", "variant_max_weight": "最大变体重量不能代表当前SKU"}[context]
                reject(candidate, f"rejected_{context}", reason)
                continue
            if small_item and weight > small_weight_limit:
                reject(candidate, "small_item_weight_anomaly", "小饰品/发饰/钥匙扣候选重量超过0.5kg复核阈值")
                continue
            if candidate["source"] in {"page_text", "ocr"} and candidate["confidence"] == "low":
                candidate = {**candidate, "decision": "downweight", "reason": "低置信度页面重量仅作辅助，不进入包装计算"}
                downweighted_weights.append(candidate)
                issues.append({"code": "low_confidence_page_weight", "severity": "medium", "reason": candidate["reason"]})
                continue
            if context == "unknown_context":
                candidate = {**candidate, "decision": "downweight", "reason": "重量上下文不明确，只能低权重参考"}
                downweighted_weights.append(candidate)
                issues.append({"code": "unknown_weight_context", "severity": "medium", "reason": candidate["reason"]})
            else:
                weight_candidates.append(candidate)

    visual_dimensions = [item for item in dimension_candidates if item["source"] == "image_visual"]
    if visual_dimensions:
        reference = max(visual_dimensions, key=_rank)
        kept: list[dict[str, Any]] = []
        for candidate in dimension_candidates:
            if candidate["source"] in {"page_text", "ocr"} and not _same_scale(
                candidate["value_cm"], reference["value_cm"], visual_conflict_ratio
            ):
                reject(candidate, "page_visual_dimension_conflict", "页面尺寸与图片视觉尺度严重冲突")
            else:
                kept.append(candidate)
        dimension_candidates = kept
    dimension_conflicts = _top_rank_conflicts(
        dimension_candidates, "value_cm", same_rank_dimension_ratio,
    )
    if dimension_conflicts:
        conflict_indices = {item["evidence_index"] for item in dimension_conflicts}
        for candidate in dimension_conflicts:
            reject(candidate, "same_rank_dimension_conflict", "同权重尺寸候选尺度严重冲突，不能按输入顺序任取")
        dimension_candidates = [
            item for item in dimension_candidates if item["evidence_index"] not in conflict_indices
        ]

    accepted_dimension = max(dimension_candidates, key=_rank) if dimension_candidates else None
    net_weights = [item["value_kg"] for item in weight_candidates if item["interpreted_as"] == "net_weight"]
    if net_weights:
        maximum_net = max(net_weights)
        kept_weights: list[dict[str, Any]] = []
        for candidate in weight_candidates:
            if candidate["interpreted_as"] == "gross_weight" and candidate["value_kg"] < maximum_net:
                reject(candidate, "gross_below_net_weight", "毛重小于净重，重量证据相互矛盾")
            else:
                kept_weights.append(candidate)
        weight_candidates = kept_weights
    weight_conflicts = _top_rank_conflicts(
        weight_candidates, "value_kg", same_rank_weight_ratio,
    )
    if weight_conflicts:
        conflict_indices = {item["evidence_index"] for item in weight_conflicts}
        for candidate in weight_conflicts:
            reject(candidate, "same_rank_weight_conflict", "同权重重量候选尺度严重冲突，不能按输入顺序任取")
        weight_candidates = [
            item for item in weight_candidates if item["evidence_index"] not in conflict_indices
        ]
    accepted_weight = max(weight_candidates, key=_rank) if weight_candidates else None
    if accepted_dimension:
        accepted_dimension = {
            **accepted_dimension, "decision": "accept",
            "reason": "通过上下文、单位、类别异常和图片冲突检查后得分最高",
        }
    if accepted_weight:
        accepted_weight = {
            **accepted_weight, "decision": "accept",
            "reason": "通过重量语义、单位和类别异常检查后得分最高",
        }

    review_reasons = [item["reason"] for item in issues]
    if _text(product_summary.get("confidence")).lower() == "low":
        review_reasons.append("商品摘要整体置信度低")
    if accepted_dimension and accepted_dimension["confidence"] != "high":
        review_reasons.append("采用的尺寸证据不是高置信度")
    if accepted_weight and accepted_weight["confidence"] != "high":
        review_reasons.append("采用的重量证据不是高置信度")
    if not accepted_dimension:
        review_reasons.append("没有可安全进入包装计算的尺寸证据")
    if not accepted_weight:
        review_reasons.append("没有可安全进入包装计算的重量证据")
    review_reasons = list(dict.fromkeys(review_reasons))
    has_dimension_basis = bool(accepted_dimension or context_dimensions)
    status = "blocked" if not has_dimension_basis or not accepted_weight else "suspect" if review_reasons else "trusted"
    return {
        "status": status,
        "accepted_dimensions": accepted_dimension,
        "accepted_weight": accepted_weight,
        "rejected_dimensions": rejected_dimensions,
        "rejected_weights": rejected_weights,
        "downweighted_dimensions": downweighted_dimensions,
        "downweighted_weights": downweighted_weights,
        "context_dimensions": context_dimensions,
        "other_evidence": other_evidence,
        "normalized_evidence": normalized,
        "issues": issues,
        "needs_review": status != "trusted",
        "review_reasons": review_reasons,
    }
