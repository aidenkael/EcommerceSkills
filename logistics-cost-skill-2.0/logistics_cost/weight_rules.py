"""可信重量规则 — 用户重量修正逻辑。

规则:
- 可信净重 ≤ 50g → 不再固定+0.05kg, 改为 max(用户净重, AI包装计费重, 体积重)
- 可信净重 > 50g → 计费重量 = 净重 + 0.05kg, 再与体积重取较高值
- 低可信/约值/未核实/参考/多规格未知 → 回退AI估重，标记需复核
- 无用户重量 → 沿用AI估重
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------- 常量 ----------

VALID_WEIGHT_STATUS = ("未提供", "可信", "约值", "未核实", "参考", "低置信", "多规格未知")
TRUSTED_WEIGHT_STATUS = "可信"
WEIGHT_INCREMENT_KG = 0.05
ANOMALY_THRESHOLD_KG = 0.15
DEFAULT_NO_INCREMENT_MAX_G = 50

# ---------- UserWeight ----------

@dataclass
class UserWeight:
    """用户提供的商品重量信息。"""

    value: float
    unit: str = "g"
    trust_status: str = "可信"

    def __post_init__(self) -> None:
        if self.trust_status not in VALID_WEIGHT_STATUS:
            raise ValueError(
                f"invalid trust_status: {self.trust_status}, valid: {VALID_WEIGHT_STATUS}"
            )
        self.value_g: float
        self.value_kg: float
        if self.unit == "g":
            self.value_g = float(self.value)
            self.value_kg = round(self.value_g / 1000.0, 6)
        elif self.unit == "kg":
            self.value_kg = float(self.value)
            self.value_g = round(self.value_kg * 1000.0, 3)
        else:
            raise ValueError(f"unsupported unit: {self.unit}, use 'g' or 'kg'")

    @property
    def is_trusted(self) -> bool:
        return self.trust_status == TRUSTED_WEIGHT_STATUS


def build_user_weight(value: float | None, unit: str = "g", trust_status: str = "可信") -> UserWeight | None:
    """构造 UserWeight，value 为 None 时返回 None（无用户重量）。"""
    if value is None:
        return None
    return UserWeight(value, unit=unit, trust_status=trust_status)


# ---------- 重量修正逻辑 ----------

def apply_weight_correction(
    chargeable_kg_ai: float,
    volume_weight_kg: float,
    *,
    user_weight: UserWeight | None = None,
    no_increment_max_g: int = DEFAULT_NO_INCREMENT_MAX_G,
) -> dict[str, Any]:
    """根据用户重量修正计费重量。

    Args:
        chargeable_kg_ai: AI 估算的计费重量 (含包装+体积重比较后的值)
        volume_weight_kg: 体积重
        user_weight: 用户提供的重量信息
        no_increment_max_g: 超轻阈值(g), ≤此值的可信重量不再固定加增重

    Returns:
        {
            "chargeable_kg": 修正后计费重量,
            "user_weight_kg": 用户重量(kg),
            "trust_status": 可信状态,
            "weight_source": 来源说明,
            "added_005": 是否加了增量,
            "needs_review": 是否需要复核,
            "review_reason": 复核原因,
        }
    """
    result: dict[str, Any] = {
        "chargeable_kg": chargeable_kg_ai,
        "user_weight_kg": None,
        "trust_status": None,
        "weight_source": "无用户重量(沿用AI估重)",
        "added_005": False,
        "needs_review": False,
        "review_reason": "",
    }

    if user_weight is None or user_weight.trust_status == "未提供":
        if user_weight is not None:
            result["user_weight_kg"] = user_weight.value_kg
            result["trust_status"] = "未提供"
            result["weight_source"] = "无用户重量(未提供可信状态)"
        return result

    result["user_weight_kg"] = user_weight.value_kg
    result["trust_status"] = user_weight.trust_status

    if user_weight.is_trusted:
        if user_weight.value_g <= no_increment_max_g:
            # 超轻品: 不再固定加增重, 取三者较高值
            corrected = round(max(user_weight.value_kg, chargeable_kg_ai, volume_weight_kg), 4)
            result["chargeable_kg"] = corrected
            result["added_005"] = False
            result["weight_source"] = (
                f"用户可信超轻重量({user_weight.value_g:.0f}g, "
                f"≤{no_increment_max_g}g不加增重, "
                f"取max(用户{user_weight.value_kg:.3f}, AI{chargeable_kg_ai:.3f}, "
                f"体积{volume_weight_kg:.3f})={corrected:.4f}kg)"
            )
        else:
            corrected = round(user_weight.value_kg + WEIGHT_INCREMENT_KG, 4)
            result["chargeable_kg"] = round(max(corrected, volume_weight_kg), 4)
            result["added_005"] = True
            result["weight_source"] = (
                f"用户可信重量({user_weight.value_g:.0f}g + "
                f"{WEIGHT_INCREMENT_KG * 1000:.0f}g)"
            )
        return result

    # 低可信：回退 AI 估重，标记需复核
    status_labels = {
        "约值": "约值重量仅参考",
        "未核实": "重量未核实，仅参考",
        "参考": "参考重量仅参考",
        "低置信": "低置信重量仅参考",
        "多规格未知": "多规格且具体售出规格未知，重量不可用",
    }
    reason = status_labels.get(
        user_weight.trust_status,
        f"重量标记为'{user_weight.trust_status}'仅参考",
    )
    result["chargeable_kg"] = chargeable_kg_ai
    result["weight_source"] = f"用户重量低可信({user_weight.trust_status}，回退AI估重)"
    result["needs_review"] = True
    result["review_reason"] = f"需复核-{reason}"
    return result
