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

# 新增: 结构形态与保守档风险来源 (v2 语义重构)
VALID_OVERALL_FORM = ("soft_flat", "soft_bulky", "flexible_long", "flexible_chain", "semi_structured_hollow", "hard_flat", "hard_3d", "mixed", "unknown")
VALID_CONSERVATIVE_RISK_BASIS = (
    "known_package_no_uncertainty",
    "weight_uncertainty",
    "thickness_uncertainty",
    "compression_uncertainty",
    "protection_uncertainty",
    "quantity_uncertainty",
    "mixed_uncertainty",
    "unknown",
)
VALID_SHAPE_RETENTION_SCOPE = ("none", "body", "whole")
VALID_MODIFIERS = ("nestable", "articulated", "fragile", "hollow")


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
    has_rigid_parts: bool = False
    requires_shape_retention: bool = False

    # ---- 必填: AI 估算 ----
    ai_net_weight_kg: float = 0.05                        # AI 估算净重 (kg)
    ai_package_size_cm: list[float] = field(default_factory=lambda: [15, 10, 4])
    ai_package_weight_kg: float = 0.06                    # AI 估算包装后重量

    # ---- 保守档 ----
    conservative_package_size_cm: list[float] = field(default_factory=list)
    conservative_package_weight_kg: float | None = None

    # ---- v2 新增: 结构形态 (必填, AI 根据商品本质形状填写) ----
    overall_form: str = "unknown"

    # ---- v2.2 新增: 组件级包装字段 ----
    rigid_body_size_cm: list[float] = field(default_factory=list)  # 主体最小不可压缩外廓
    foldable_parts: list[str] = field(default_factory=list)        # 可折部件列表 (handle/strap/brim...)
    detachable_parts: list[str] = field(default_factory=list)      # 可拆附件列表
    shape_retention_scope: str = "none"                            # none / body / whole
    modifiers: list[str] = field(default_factory=list)             # nestable/articulated/fragile/hollow

    # ---- v2 新增: 保守档风险来源 (可选, 说明为何保守档与正常档不同) ----
    conservative_risk_basis: str = "unknown"  # known_package_no_uncertainty/weight_uncertainty/thickness_uncertainty/...

    # ---- 可选: 包装方式建议 ----
    packaging_method: str = "OPP袋"
    folding_action: str = "常规折叠"
    compression_action: str = "轻度压缩"

    # ---- 可选: 包装类型元数据 (v1 校准新增) ----
    packaging_type: str = "unknown"        # opp_bag / retail_card / small_box / bubble_wrap / original_box / unknown
    weight_scope: str = "unknown"          # net_weight / packaged_weight / original_box_weight / unknown
    dimension_scope: str = "unknown"       # display_size / product_size / shipping_package_size / unknown

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
    if d.get("overall_form", "") not in VALID_OVERALL_FORM:
        d["overall_form"] = "unknown"
    if d.get("conservative_risk_basis", "") not in VALID_CONSERVATIVE_RISK_BASIS:
        d["conservative_risk_basis"] = "unknown"
    if d.get("shape_retention_scope", "") not in VALID_SHAPE_RETENTION_SCOPE:
        d["shape_retention_scope"] = "none"
    mods = d.get("modifiers", [])
    if isinstance(mods, list):
        d["modifiers"] = [m for m in mods if m in VALID_MODIFIERS]
    else:
        d["modifiers"] = []

    # v2.2 兼容映射: 旧类型 → 新类型
    _overall_form = d.get("overall_form", "")
    _old_to_new = {
        "soft_hollow": "semi_structured_hollow",
        "rigid_hollow": "hard_3d",
        "nestable_set": "hard_3d",
        "fragile_protruding": "hard_3d",
        "articulated": "mixed",
    }
    if _overall_form in _old_to_new:
        d["overall_form"] = _old_to_new[_overall_form]
        mods = d.get("modifiers", [])
        if "hollow" not in mods:
            mods.append("hollow")
        if _overall_form == "articulated" and "articulated" not in mods:
            mods.append("articulated")
        if _overall_form in ("fragile_protruding",) and "fragile" not in mods:
            mods.append("fragile")
        d["modifiers"] = mods

    # 数量默认
    d.setdefault("quantity", 1)
    d.setdefault("quantity_source", "assumed")

    # AI 估算字段默认
    d.setdefault("ai_net_weight_kg", 0.05)
    d.setdefault("ai_package_size_cm", [15, 10, 4])
    d.setdefault("ai_package_weight_kg", 0.06)

    # 保守档: 缺失时从正常档复制, 标记需复核 (不再使用固定机械放大)
    if not d.get("conservative_package_size_cm"):
        d["conservative_package_size_cm"] = list(d.get("ai_package_size_cm", [15, 10, 4]))
    if d.get("conservative_package_weight_kg") is None:
        d["conservative_package_weight_kg"] = d.get("ai_package_weight_kg", 0.06)
    if d.get("conservative_risk_basis", "") in ("", "unknown") and d.get("conservative_package_size_cm") == d.get("ai_package_size_cm"):
        # 保守档与正常档完全相同时, 检查是否有明确包装
        if d.get("dimension_scope") == "shipping_package_size" and d.get("weight_scope") == "packaged_weight":
            d["conservative_risk_basis"] = "known_package_no_uncertainty"

    # 可选字符串字段
    d.setdefault("packaging_method", "OPP袋")
    d.setdefault("folding_action", "")
    d.setdefault("compression_action", "")
    d.setdefault("packaging_type", "unknown")
    d.setdefault("weight_scope", "unknown")
    d.setdefault("dimension_scope", "unknown")
    d.setdefault("product_link", "")
    d.setdefault("image_path", "")
    d.setdefault("notes", "")
    d.setdefault("reasoning", "")
    d.setdefault("overall_form", "unknown")
    d.setdefault("conservative_risk_basis", "unknown")
    d.setdefault("rigid_body_size_cm", [])
    d.setdefault("foldable_parts", [])
    d.setdefault("detachable_parts", [])
    d.setdefault("shape_retention_scope", "none")
    d.setdefault("modifiers", [])

    # 布尔字段
    d.setdefault("has_rigid_parts", False)
    d.setdefault("requires_shape_retention", False)

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
        overall_form=d["overall_form"],
        conservative_risk_basis=d["conservative_risk_basis"],
        rigid_body_size_cm=d["rigid_body_size_cm"],
        foldable_parts=d["foldable_parts"],
        detachable_parts=d["detachable_parts"],
        shape_retention_scope=d["shape_retention_scope"],
        modifiers=d["modifiers"],
        packaging_method=d["packaging_method"],
        folding_action=d["folding_action"],
        compression_action=d["compression_action"],
        packaging_type=d["packaging_type"],
        weight_scope=d["weight_scope"],
        dimension_scope=d["dimension_scope"],
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
        "material": "unknown",
        "rigidity": ai.rigidity,
        "foldability": ai.foldability,
        "compression": ai.compressibility,
        "fragility": "low",
        "has_rigid_parts": ai.has_rigid_parts,
        "requires_shape_retention": ai.requires_shape_retention,
        "shape_retention_scope": ai.shape_retention_scope,
        "rigid_body_size_cm": list(ai.rigid_body_size_cm) if ai.rigid_body_size_cm else [],
        "foldable_parts": list(ai.foldable_parts),
        "detachable_parts": list(ai.detachable_parts),
        "modifiers": list(ai.modifiers),
        "overall_form": ai.overall_form,
        "quantity": ai.quantity,
        "size_class": size_class,
        "confidence": ai.confidence,
        "product_link": ai.product_link,
        "quantity_source": ai.quantity_source,
    }

    # 尺寸证据: raw_text 避免 "包装尺寸" 关键词导致被强制推断为 packaged_size
    pkg_size_text = f"AI推算商品外廓 {ai.ai_package_size_cm[0]}x{ai.ai_package_size_cm[1]}x{ai.ai_package_size_cm[2]}cm"
    raw_evidence = [
        {
            "evidence_type": "weight",
            "raw_text": f"AI推算净重 {ai.ai_net_weight_kg}kg",
            "value_kg": ai.ai_net_weight_kg,
            "source": "ai_estimated",
            "interpreted_as": "net_weight",
            "quantity_basis": ai.quantity,
            "confidence": ai.confidence,
        },
        {
            "evidence_type": "dimension",
            "raw_text": pkg_size_text,
            "value": list(ai.ai_package_size_cm),
            "unit": "cm",
            "source": "ai_estimated",
            "interpreted_as": "product_body_size",  # 避免 strict packaged_size 校验
            "quantity_basis": ai.quantity,
            "confidence": ai.confidence,
        },
    ]

    packaging_scenarios = {
        "normal": {
            "packaged_size_cm": list(ai.ai_package_size_cm),
            "packaged_weight_kg": ai.ai_package_weight_kg,
            "method": ai.packaging_method or "OPP袋",
            "folding_action": ai.folding_action or (
                "不折叠" if (ai.rigidity == "hard" or ai.has_rigid_parts or ai.requires_shape_retention) else "常规折叠"
            ),
            "compression_action": ai.compression_action or (
                "不压缩" if ai.rigidity == "hard" else "轻度压缩"
            ),
            "requires_box": ai.packaging_type in ("small_box", "original_box") or ai.shape_retention_scope == "whole",
            "requires_bubble_wrap": False,
            "used_evidence_indices": [0, 1],
            "reason": ai.reasoning or "AI推断包装",
            "confidence": ai.confidence,
            "overall_form": ai.overall_form,
        },
        "conservative": {
            "packaged_size_cm": list(ai.conservative_package_size_cm),
            "packaged_weight_kg": ai.conservative_package_weight_kg,
            "method": ai.packaging_method or "OPP袋",
            "folding_action": ai.folding_action or (
                "不折叠" if (ai.rigidity == "hard" or ai.has_rigid_parts or ai.requires_shape_retention) else "常规折叠"
            ),
            "compression_action": ai.compression_action or (
                "不压缩" if ai.rigidity == "hard" else "轻度压缩"
            ),
            "requires_box": ai.packaging_type in ("small_box", "original_box") or ai.shape_retention_scope == "whole",
            "requires_bubble_wrap": False,
            "used_evidence_indices": [0, 1],
            "reason": ai.reasoning or "AI推断保守包装",
            "confidence": ai.confidence,
            "overall_form": ai.overall_form,
            "risk_basis": ai.conservative_risk_basis,
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

    result = estimate(
        product_summary=summary,
        raw_evidence=evidence,
        packaging_scenarios=scenarios,
        product_link=ai.product_link,
        user_weight=uw,
    )

    result["ai_meta"] = ai_meta
    return result