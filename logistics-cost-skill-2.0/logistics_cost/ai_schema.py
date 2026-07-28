"""AI JSON 格式校验 — Codex 输出与未来视觉 API 的统一契约。

单一格式,两种方式进入:
1. Codex 手动识图 → 写入 JSON → run.py 加载
2. 未来视觉 API → 按此 schema 返回 → run.py 加载

required: product_type, ai_net_weight_kg, ai_package_size_cm, confidence
optional: quantity(默认1), category(默认general), user_weight_kg
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


VALID_CATEGORIES = ("general", "bag")
VALID_RIGIDITY = ("soft", "semi_rigid", "hard")
VALID_FOLDABILITY = ("good", "limited", "none", "unknown")
VALID_COMPRESSIBILITY = ("good", "limited", "none", "unknown")
VALID_CONFIDENCE = ("high", "medium", "low")
VALID_QUANTITY_SOURCE = ("user_confirmed", "ai_inferred", "assumed")
VALID_PACKAGING_TYPE = ("opp_bag", "retail_card", "small_box", "bubble_wrap", "original_box", "unknown")
VALID_WEIGHT_SCOPE = ("net_weight", "packaged_weight", "original_box_weight", "unknown")
VALID_DIMENSION_SCOPE = ("display_size", "product_size", "shipping_package_size", "unknown")
VALID_PACKAGING_STATE = (
    "full_flat_fold", "strong_compression", "moderate_compression",
    "shape_retained", "unknown",
)
VALID_PROPOSAL_SOURCE = ("legacy_local", "local_fallback", "external_ai", "vision_api", "user", "unknown")


@dataclass
class PackagingScenario:
    """AI 直接输出的包装方案 (正常档/保守档)。"""
    packaged_size_cm: list[float]   # [L, W, H] cm
    packaged_weight_kg: float
    method: str = "OPP袋"
    folding_action: str = ""
    compression_action: str = ""
    requires_box: bool = False
    requires_bubble_wrap: bool = False


@dataclass
class AiProductJson:
    """Codex 识别商品图片后输出的统一 JSON 格式。

    Codex 在 WorkBuddy 会话中通过 Read 工具读取图片像素, 按此 schema 输出 JSON 保存为文件。
    """

    # ---- 必填: 身份 ----
    product_type: str                                     # 商品类型 (如 "mid_calf_socks")
    confidence: str = "medium"                            # high / medium / low
    reasoning: str = ""                                   # 一句话判断理由

    # ---- 必填: 数量 ----
    quantity: int = 1                                     # 成交数量
    quantity_source: str = "assumed"                      # user_confirmed / ai_inferred / assumed

    # ---- 必填: 品类与结构 ----
    category: str = "general"                             # bag / general
    rigidity: str = "soft"                                # soft / semi_rigid / hard
    foldability: str = "good"                             # good / limited / none / unknown
    compressibility: str = "good"                         # good / limited / none / unknown
    has_rigid_parts: bool | None = None
    requires_shape_retention: bool | None = None

    # ---- 必填: AI 估算 ----
    ai_net_weight_kg: float = 0.05                        # AI 估算净重 (kg)
    ai_package_size_cm: list[float] = field(default_factory=lambda: [15, 10, 4])
    ai_package_weight_kg: float = 0.06                    # AI 估算包装后重量

    # ---- 保守档 (必填, AI 直接提供) ----
    conservative_package_size_cm: list[float] = field(default_factory=lambda: [20, 14, 6])
    conservative_package_weight_kg: float = 0.10

    # ---- 可选: 包装方式建议 ----
    packaging_method: str = "OPP袋"
    folding_action: str = "常规折叠"
    compression_action: str = "轻度压缩"

    # ---- 可选: 包装类型元数据 (v1 校准新增) ----
    packaging_type: str = "unknown"        # opp_bag / retail_card / small_box / bubble_wrap / original_box / unknown
    weight_scope: str = "unknown"          # net_weight / packaged_weight / original_box_weight / unknown
    dimension_scope: str = "unknown"       # display_size / product_size / shipping_package_size / unknown
    packaging_state: str = "unknown"
    has_hard_bottom: bool | None = None
    has_hard_backboard: bool | None = None
    has_frame: bool | None = None
    has_rigid_insert: bool | None = None
    retail_box_visible: bool | None = None
    hard_card_visible: bool | None = None
    protrusion_flattenable: bool | None = None
    proposal_source: str = "legacy_local"
    reasoning_summary: str = ""
    needs_review: bool = False
    default_fields_used: list[str] = field(default_factory=list)
    material: str = "unknown"

    # ---- 可选: 元数据 ----
    image_path: str = ""
    product_link: str = ""                                # 1688 链接, 仅保存
    notes: str = ""


def validate(ai: dict[str, Any]) -> AiProductJson:
    """校验并规范化 AI JSON。缺失字段填默认值, 非法值替换为 unknown。

    Raises:
        ValueError: 必填字段缺失或不合法
    """
    d = dict(ai)

    # 必填校验
    if not d.get("product_type"):
        raise ValueError("product_type 为空")

    # 枚举校验 + 默认值
    if d.get("category") not in VALID_CATEGORIES:
        d["category"] = "general"
    if d.get("rigidity") not in VALID_RIGIDITY:
        d["rigidity"] = "soft"
    if d.get("foldability") not in VALID_FOLDABILITY:
        d["foldability"] = "unknown"
    if d.get("compressibility") not in VALID_COMPRESSIBILITY:
        d["compressibility"] = "unknown"
    if d.get("confidence") not in VALID_CONFIDENCE:
        d["confidence"] = "medium"
    if d.get("quantity_source") not in VALID_QUANTITY_SOURCE:
        d["quantity_source"] = "assumed"
    if d.get("packaging_type") not in VALID_PACKAGING_TYPE:
        d["packaging_type"] = "unknown"
    if d.get("weight_scope") not in VALID_WEIGHT_SCOPE:
        d["weight_scope"] = "unknown"
    if d.get("dimension_scope") not in VALID_DIMENSION_SCOPE:
        d["dimension_scope"] = "unknown"
    if d.get("packaging_state") not in VALID_PACKAGING_STATE:
        d["packaging_state"] = "unknown"
    if d.get("proposal_source") not in VALID_PROPOSAL_SOURCE:
        d["proposal_source"] = "unknown"

    # 数量默认
    defaults_used = list(d.get("default_fields_used") or [])

    def use_default(name: str, value: Any) -> None:
        if name not in d:
            d[name] = value
            defaults_used.append(name)

    use_default("quantity", 1)
    use_default("quantity_source", "assumed")

    # AI 估算字段默认
    use_default("ai_net_weight_kg", 0.05)
    use_default("ai_package_size_cm", [15, 10, 4])
    use_default("ai_package_weight_kg", 0.06)
    use_default("conservative_package_size_cm", [20, 14, 6])
    use_default("conservative_package_weight_kg", 0.10)

    # 可选字符串字段
    d.setdefault("packaging_method", "OPP袋")
    d.setdefault("folding_action", "")
    d.setdefault("compression_action", "")
    d.setdefault("packaging_type", "unknown")
    d.setdefault("weight_scope", "unknown")
    d.setdefault("dimension_scope", "unknown")
    d.setdefault("packaging_state", "unknown")
    d.setdefault("proposal_source", "legacy_local")
    d.setdefault("reasoning_summary", "")
    d.setdefault("material", "unknown")
    d.setdefault("product_link", "")
    d.setdefault("image_path", "")
    d.setdefault("notes", "")
    d.setdefault("reasoning", "")

    # 布尔字段
    for name in (
        "has_rigid_parts", "requires_shape_retention", "has_hard_bottom",
        "has_hard_backboard", "has_frame", "has_rigid_insert",
        "retail_box_visible", "hard_card_visible", "protrusion_flattenable",
    ):
        d.setdefault(name, None)
        if d[name] is not None and not isinstance(d[name], bool):
            raise ValueError(f"{name} 必须是 true/false/null")
    d["default_fields_used"] = list(dict.fromkeys(defaults_used))
    d["needs_review"] = bool(d.get("needs_review")) or bool(defaults_used)
    if defaults_used:
        d["confidence"] = "low"

    # 构造
    return AiProductJson(
        product_type=d["product_type"],
        confidence=d["confidence"],
        reasoning=d["reasoning"],
        quantity=d["quantity"],
        quantity_source=d["quantity_source"],
        category=d["category"],
        rigidity=d["rigidity"],
        foldability=d["foldability"],
        compressibility=d["compressibility"],
        has_rigid_parts=d["has_rigid_parts"],
        requires_shape_retention=d["requires_shape_retention"],
        ai_net_weight_kg=d["ai_net_weight_kg"],
        ai_package_size_cm=d["ai_package_size_cm"],
        ai_package_weight_kg=d["ai_package_weight_kg"],
        conservative_package_size_cm=d["conservative_package_size_cm"],
        conservative_package_weight_kg=d["conservative_package_weight_kg"],
        packaging_method=d["packaging_method"],
        folding_action=d["folding_action"],
        compression_action=d["compression_action"],
        packaging_type=d["packaging_type"],
        weight_scope=d["weight_scope"],
        dimension_scope=d["dimension_scope"],
        packaging_state=d["packaging_state"],
        has_hard_bottom=d["has_hard_bottom"],
        has_hard_backboard=d["has_hard_backboard"],
        has_frame=d["has_frame"],
        has_rigid_insert=d["has_rigid_insert"],
        retail_box_visible=d["retail_box_visible"],
        hard_card_visible=d["hard_card_visible"],
        protrusion_flattenable=d["protrusion_flattenable"],
        proposal_source=d["proposal_source"],
        reasoning_summary=d["reasoning_summary"],
        needs_review=d["needs_review"],
        default_fields_used=d["default_fields_used"],
        material=d["material"],
        image_path=d["image_path"],
        product_link=d["product_link"],
        notes=d["notes"],
    )


def to_estimate_inputs(ai: AiProductJson) -> tuple[dict, list[dict], dict, dict]:
    """将 AiProductJson 转换为 estimator.estimate() 所需的四元组。

    Returns:
        (product_summary, raw_evidence, packaging_scenarios, ai_meta)
    """
    # 根据 AI 包装尺寸推断 size_class
    max_dim = max(ai.ai_package_size_cm) if ai.ai_package_size_cm else 15
    if max_dim > 30:
        size_class = "large"
    elif max_dim > 15:
        size_class = "medium"
    else:
        size_class = "small"

    product_summary = {
        "product_type": ai.product_type,
        "category_type": ai.category,
        "material": ai.material,
        "rigidity": ai.rigidity,
        "foldability": ai.foldability,
        "compression": ai.compressibility,
        "fragility": "low",
        "has_rigid_parts": ai.has_rigid_parts,
        "requires_shape_retention": ai.requires_shape_retention,
        "has_hard_bottom": ai.has_hard_bottom,
        "has_hard_backboard": ai.has_hard_backboard,
        "has_frame": ai.has_frame,
        "has_rigid_insert": ai.has_rigid_insert,
        "retail_box_visible": ai.retail_box_visible,
        "hard_card_visible": ai.hard_card_visible,
        "protrusion_flattenable": ai.protrusion_flattenable,
        "packaging_state": ai.packaging_state,
        "proposal_source": ai.proposal_source,
        "dimension_scope": ai.dimension_scope,
        "weight_scope": ai.weight_scope,
        "quantity": ai.quantity,
        "size_class": size_class,
        "confidence": ai.confidence,
        "product_link": ai.product_link,
        "quantity_source": ai.quantity_source,
    }

    dimension_context = {
        "shipping_package_size": "packaged_size",
        "product_size": "product_body_size",
        "display_size": "product_body_size",
    }.get(ai.dimension_scope, "product_body_size")
    weight_context = "gross_weight" if ai.weight_scope in {"packaged_weight", "original_box_weight"} else "net_weight"
    weight_value = ai.ai_package_weight_kg if weight_context == "gross_weight" else ai.ai_net_weight_kg
    pkg_size_text = f"AI尺寸候选 {ai.ai_package_size_cm[0]}x{ai.ai_package_size_cm[1]}x{ai.ai_package_size_cm[2]}cm"
    raw_evidence = [
        {
            "evidence_type": "weight",
            "raw_text": f"AI重量候选 {weight_value}kg",
            "value_kg": weight_value,
            "source": "ai_estimated",
            "interpreted_as": weight_context,
            "weight_scope": ai.weight_scope,
            "quantity_basis": ai.quantity,
            "confidence": ai.confidence,
        },
        {
            "evidence_type": "dimension",
            "raw_text": pkg_size_text,
            "value": list(ai.ai_package_size_cm),
            "unit": "cm",
            "source": "ai_estimated",
            "interpreted_as": dimension_context,
            "dimension_scope": ai.dimension_scope,
            "quantity_basis": ai.quantity,
            "confidence": ai.confidence,
            "needs_review": ai.needs_review,
        },
    ]

    packaging_scenarios = {
        "normal": {
            "packaged_size_cm": list(ai.ai_package_size_cm),
            "packaged_weight_kg": ai.ai_package_weight_kg,
            "method": ai.packaging_method or "OPP袋",
            "folding_action": ai.folding_action or "常规折叠",
            "compression_action": ai.compression_action or "轻度压缩",
            "requires_box": ai.has_rigid_parts or ai.requires_shape_retention,
            "requires_bubble_wrap": False,
            "used_evidence_indices": [0, 1],
            "reason": ai.reasoning or "AI推断包装",
            "confidence": ai.confidence,
            "needs_review": ai.needs_review,
        },
        "conservative": {
            "packaged_size_cm": list(ai.conservative_package_size_cm),
            "packaged_weight_kg": ai.conservative_package_weight_kg,
            "method": f"稍大{ai.packaging_method or '外袋'}",
            "folding_action": "较少折叠" if ai.foldability in ("good", "limited") else "无",
            "compression_action": "弱压缩" if ai.compressibility in ("good", "limited") else "无",
            "requires_box": ai.has_rigid_parts or ai.requires_shape_retention,
            "requires_bubble_wrap": False,
            "used_evidence_indices": [0, 1],
            "reason": f"AI推断保守包装 ({ai.confidence})",
            "confidence": ai.confidence,
        },
    }

    ai_meta = {
        "quantity_source": ai.quantity_source,
        "quantity": ai.quantity,
        "confidence": ai.confidence,
        "reasoning": ai.reasoning,
        "packaging_type": ai.packaging_type,
        "weight_scope": ai.weight_scope,
        "dimension_scope": ai.dimension_scope,
        "packaging_state": ai.packaging_state,
        "proposal_source": ai.proposal_source,
        "reasoning_summary": ai.reasoning_summary,
        "needs_review": ai.needs_review,
        "default_fields_used": list(ai.default_fields_used),
    }

    return product_summary, raw_evidence, packaging_scenarios, ai_meta


def estimate_from_ai_json(
    ai_data: dict,
    user_weight: float | None = None,
    user_weight_unit: str = "g",
    user_weight_trust: str = "可信",
    product_link: str = "",
) -> dict:
    """可供未来利润软件直接导入的薄入口。

    Args:
        ai_data: AI JSON dict (按 AiProductJson 格式)
        user_weight: 用户商品净重 (数值)
        user_weight_unit: "g" 或 "kg"
        user_weight_trust: 可信/约值/未核实/参考/低置信/多规格未知/未提供
        product_link: 1688 链接 (仅保存)

    Returns:
        统一估算结果 (同 estimator.estimate())
    """
    from .estimator import estimate
    from .weight_rules import UserWeight

    ai = validate(ai_data)
    if product_link:
        ai.product_link = product_link

    summary, evidence, scenarios, ai_meta = to_estimate_inputs(ai)

    uw = None
    if user_weight is not None:
        uw = UserWeight(user_weight, user_weight_unit, user_weight_trust)
    elif ai_data.get("user_weight_kg") is not None:
        embedded_trust = str(ai_data.get("user_weight_trust") or "未核实")
        uw = UserWeight(ai_data["user_weight_kg"], "kg", embedded_trust)
        ai_meta["embedded_user_weight_mapped"] = True
        if embedded_trust != "可信":
            ai_meta["needs_review"] = True

    result = estimate(
        product_summary=summary,
        raw_evidence=evidence,
        packaging_scenarios=scenarios,
        product_link=ai.product_link,
        user_weight=uw,
    )

    result["ai_meta"] = ai_meta
    if ai.needs_review:
        reason = (
            f"AI JSON 使用兼容默认值: {', '.join(ai.default_fields_used)}"
            if ai.default_fields_used
            else "AI输入主动要求人工复核"
        )
        result["needs_review"] = True
        result["review_reasons"] = list(dict.fromkeys(
            result.get("review_reasons", [])
            + [reason]
        ))
    return result
