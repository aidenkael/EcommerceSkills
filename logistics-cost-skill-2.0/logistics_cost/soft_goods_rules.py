"""软品体积重规则 — 防止展开尺寸误用导致头程高估。

规则:
1. 软质/可折叠/可卷/可压缩商品不得使用展开尺寸直接计算体积重
2. 无可信包装尺寸时，优先按净重或AI估重计算
3. 体积重 > AI净重 × 3 时自动忽略体积重，标记复核
"""
from __future__ import annotations

from math import isfinite
from typing import Any

# ---------- 常量 ----------

SOFT_VOLUME_INFLATION_RATIO = 3.0  # 软品体积重超过净重此倍数即忽略

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
    scenario_label: str = "",
) -> dict[str, Any]:
    """检查软品体积重是否因展开尺寸误用而异常偏高。

    Args:
        volume_weight_kg: 体积重
        packaged_weight_kg: 打包后实重
        ai_net_weight_kg: AI 估算净重
        is_packaged_dimension: 尺寸是否为已验证的包装尺寸
        scenario_label: 场景标签(正常/保守)，仅用于警告文案

    Returns:
        {"volume_ignored": bool, "chargeable_kg": float, "warning": str}
    """
    result: dict[str, Any] = {
        "volume_ignored": False,
        "chargeable_kg": packaged_weight_kg,
        "warning": "",
    }

    if is_packaged_dimension:
        # 有可信包装尺寸，不介入
        result["chargeable_kg"] = round(max(packaged_weight_kg, volume_weight_kg), 4)
        return result

    if not isfinite(ai_net_weight_kg) or ai_net_weight_kg <= 0:
        result["chargeable_kg"] = round(max(packaged_weight_kg, volume_weight_kg), 4)
        return result

    if volume_weight_kg > ai_net_weight_kg * SOFT_VOLUME_INFLATION_RATIO:
        result["volume_ignored"] = True
        result["chargeable_kg"] = round(packaged_weight_kg, 4)
        result["warning"] = (
            f"软品展开尺寸疑似误用: {scenario_label}档体积重{volume_weight_kg:.3f}kg超过"
            f"AI净重{ai_net_weight_kg:.3f}kg的{SOFT_VOLUME_INFLATION_RATIO:.0f}倍，"
            f"已改用实重{result['chargeable_kg']}kg计算头程"
        )
    else:
        result["chargeable_kg"] = round(max(packaged_weight_kg, volume_weight_kg), 4)

    return result
