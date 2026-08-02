"""软品体积重规则 — v2 统一策略。

规则:
1. 软质/可折叠/可卷/可压缩商品不得使用展开尺寸直接计算体积重
2. 无可信包装尺寸时, 优先按净重或AI估重计算
3. 两档使用一致的软品体积策略, 不再分别判定阈值
4. 策略决定后, 两档各自用实际包装参数计算
"""
from __future__ import annotations

from math import isfinite
from typing import Any

# ---------- 常量 ----------

SOFT_VOLUME_INFLATION_RATIO = 3.0  # 软品体积重超过净重此倍数即忽略

# ---------- 统一软品体积策略 ----------

SOFT_VOLUME_POLICY_VERIFIED = "verified_packaged_dimensions"
SOFT_VOLUME_POLICY_SOFT_FLAT = "soft_flat_unverified_dimensions"
SOFT_VOLUME_POLICY_SOFT_BULKY = "soft_bulky_unverified_dimensions"
SOFT_VOLUME_POLICY_NOT_SOFT = "not_soft"


def determine_soft_volume_policy(
    is_soft: bool,
    is_packaged_dimension: bool,
    overall_form: str = "unknown",
    ai_net_weight_kg: float = 0.0,
    normal_volume_weight_kg: float = 0.0,
) -> str:
    """在进入两档计算前确定统一的软品体积策略。

    Returns:
        verified_packaged_dimensions | soft_flat_unverified_dimensions |
        soft_bulky_unverified_dimensions | not_soft
    """
    if is_packaged_dimension:
        return SOFT_VOLUME_POLICY_VERIFIED

    if not is_soft:
        return SOFT_VOLUME_POLICY_NOT_SOFT

    # soft_flat: 正常档体积重已超标 → 忽略体积重
    # soft_bulky: 允许体积重参与比较, 不给无条件忽略
    if overall_form == "soft_bulky":
        return SOFT_VOLUME_POLICY_SOFT_BULKY

    # soft_flat / unknown: 统一基于正常档判定
    if isfinite(ai_net_weight_kg) and ai_net_weight_kg > 0:
        if normal_volume_weight_kg > ai_net_weight_kg * SOFT_VOLUME_INFLATION_RATIO:
            return SOFT_VOLUME_POLICY_SOFT_FLAT

    # 未触发阈值: 正常计算
    return SOFT_VOLUME_POLICY_NOT_SOFT

# ---------- 软品识别 ----------

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


def _text(value: Any) -> str:
    return str(value or "").strip()


def is_soft_goods(summary: dict[str, Any]) -> bool:
    """根据商品摘要判断是否为软品。"""
    rigidity = _text(summary.get("rigidity")).lower()
    foldability = _text(summary.get("foldability")).lower()
    compression = _text(summary.get("compression")).lower()
    material = _text(summary.get("material")).lower().replace("-", "_")
    product_type = _text(summary.get("product_type")).lower().replace("-", "_").replace(" ", "_")
    return (
        rigidity == "soft"
        or foldability in {"good", "limited"}
        or compression in {"good", "limited", "moderate", "high"}
        or any(word in material for word in SOFT_MATERIAL_WORDS)
        or any(word in product_type for word in SOFT_PRODUCT_TYPES)
    )


# ---------- 体积重过冲检查 ----------

def check_soft_goods_volume(
    volume_weight_kg: float,
    packaged_weight_kg: float,
    ai_net_weight_kg: float,
    *,
    is_packaged_dimension: bool = False,
    soft_volume_policy: str = SOFT_VOLUME_POLICY_NOT_SOFT,
    scenario_label: str = "",
) -> dict[str, Any]:
    """使用统一策略检查软品体积重。

    soft_volume_policy 必须在进入两档前由 determine_soft_volume_policy() 确定。

    Args:
        volume_weight_kg: 体积重
        packaged_weight_kg: 打包后实重
        ai_net_weight_kg: AI 估算净重
        is_packaged_dimension: 是否已验证包装尺寸 (内部兼容, 策略已统一)
        soft_volume_policy: 统一软品体积策略
        scenario_label: 场景标签, 仅用于诊断

    Returns:
        {"volume_ignored": bool, "chargeable_kg": float, "policy_used": str, "warning": str}
    """
    result: dict[str, Any] = {
        "volume_ignored": False,
        "chargeable_kg": packaged_weight_kg,
        "policy_used": soft_volume_policy,
        "warning": "",
    }

    if soft_volume_policy == SOFT_VOLUME_POLICY_VERIFIED:
        result["chargeable_kg"] = round(max(packaged_weight_kg, volume_weight_kg), 4)
        return result

    if soft_volume_policy == SOFT_VOLUME_POLICY_NOT_SOFT:
        result["chargeable_kg"] = round(max(packaged_weight_kg, volume_weight_kg), 4)
        return result

    if soft_volume_policy == SOFT_VOLUME_POLICY_SOFT_FLAT:
        result["volume_ignored"] = True
        result["chargeable_kg"] = round(packaged_weight_kg, 4)
        result["warning"] = (
            f"软品统一策略soft_flat: {scenario_label}档体积重{volume_weight_kg:.3f}kg"
            f"已忽略, 使用实重{result['chargeable_kg']}kg"
        )
        return result

    if soft_volume_policy == SOFT_VOLUME_POLICY_SOFT_BULKY:
        # soft_bulky: 允许体积重参与, 但正常档若已超标则保守档也取max
        result["chargeable_kg"] = round(max(packaged_weight_kg, volume_weight_kg), 4)
        return result

    return result
