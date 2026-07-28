"""三个提取器共用的文本、数值、单位和候选构造工具。

只提供最小工具集，不建立通用规则引擎。
"""
import hashlib
import math
import re
import uuid
from typing import List, Optional, Tuple

from image_intake.result_models import OcrCandidate


def parse_number(raw: str) -> Optional[float]:
    """解析数字字符串，处理千位分隔符，拒绝 NaN/Inf。不使用 eval。"""
    if raw is None:
        return None
    cleaned = str(raw).strip().replace(",", "").replace(" ", "")
    if not cleaned:
        return None
    # 只允许数字、小数点、负号
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    try:
        v = float(cleaned)
    except (ValueError, TypeError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def is_valid_amount(v: Optional[float]) -> bool:
    """金额必须为非负有限数（允许 0，如运费0元/包邮）。"""
    return v is not None and math.isfinite(v) and v >= 0


def is_valid_measure(v: Optional[float]) -> bool:
    """重量/尺寸必须大于0且有限（0 或负数不生成可用候选）。"""
    return v is not None and math.isfinite(v) and v > 0


def make_candidate(
    field_name: str,
    parsed_value: Optional[float],
    source_image: str,
    raw_text: str,
    confidence: float,
    normalized_value: Optional[float] = None,
    unit_original: Optional[str] = None,
    unit_normalized: Optional[str] = None,
    selectable: bool = False,
    measurement_group_id: Optional[str] = None,
) -> OcrCandidate:
    """构造 OcrCandidate（透传到 result_models，不改变字段含义）。"""
    return OcrCandidate(
        field_name=field_name,
        parsed_value=parsed_value,
        source_image=source_image,
        raw_text=raw_text,
        confidence=confidence,
        normalized_value=normalized_value,
        unit_original=unit_original,
        unit_normalized=unit_normalized,
        selectable=selectable,
        measurement_group_id=measurement_group_id,
    )


def make_group_id(content: str) -> str:
    """基于内容生成确定性 group_id。

    相同内容（同一表达式 + 来源）产生相同 group_id，便于完全重复行去重；
    不同内容产生不同 group_id，避免误关联。
    """
    digest = hashlib.md5(content.encode("utf-8")).hexdigest()[:8]
    return "grp_" + digest


def new_anon_group_id() -> str:
    """匿名 group_id（用于不需要去重关联的独立候选）。"""
    return "grp_" + uuid.uuid4().hex[:8]


def dedupe(candidates: List[OcrCandidate]) -> List[OcrCandidate]:
    """只去除完全相同的重复候选。

    去重条件（必须同时满足）：
    相同 field_name / normalized_value / source_image / raw_text / measurement_group_id
    来自不同图片、不同文本行或不同上下文的相同金额必须保留。
    """
    seen = set()
    result = []
    for c in candidates:
        key = (c.field_name, c.normalized_value, c.source_image, c.raw_text, c.measurement_group_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(c)
    return result


# ─── 重量归一化（统一为 g）─────────────────────────
WEIGHT_TO_G = {
    "g": 1.0, "gram": 1.0, "克": 1.0,
    "kg": 1000.0, "kilogram": 1000.0, "千克": 1000.0, "公斤": 1000.0,
}


def normalize_weight(value: float, unit: str) -> Tuple[Optional[float], Optional[str]]:
    """重量归一化为 g。返回 (normalized_value, "g")，未知单位返回 (None, None)。"""
    factor = WEIGHT_TO_G.get(unit.lower())
    if factor is None:
        return None, None
    return value * factor, "g"


# ─── 尺寸归一化（统一为 cm）─────────────────────────
DIM_TO_CM = {
    "cm": 1.0, "厘米": 1.0,
    "mm": 0.1, "毫米": 0.1,
}


def normalize_dim(value: float, unit: str) -> Tuple[Optional[float], Optional[str]]:
    """尺寸归一化为 cm。"""
    factor = DIM_TO_CM.get(unit.lower())
    if factor is None:
        return None, None
    return value * factor, "cm"


def sort_candidates(scored: List[tuple]) -> List[OcrCandidate]:
    """排序：上下文明确优先 > 置信度高优先 > 出现顺序。

    scored 元素: (has_context: bool, neg_confidence: float, line_index: int, candidate)
    """
    scored.sort(key=lambda t: (not t[0], t[1], t[2]))
    return [t[3] for t in scored]
