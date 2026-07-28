"""尺寸和重量截图提取器：提取 weight_g / length_cm / width_cm / height_cm 候选。

单位归一化：kg/千克/公斤×1000→g；mm/毫米÷10→cm；g/克→g；cm/厘米→cm。
measurement_group_id 基于内容确定性生成：同组尺寸共享，不同表达式不同。
不自动判定裸件/包装 scope；不补高度；四维不生成完整三维。
"""
import re
from typing import List

from image_intake.result_models import OcrCandidate
from ocr.base_engine import OcrTextLine
from .common import (
    parse_number, is_valid_measure, make_candidate, make_group_id, dedupe,
    sort_candidates, normalize_weight, normalize_dim,
)


DIM_UNIT = r'(?:mm|毫米|cm|厘米)'
WEIGHT_UNIT = r'(?:kilogram|kg|gram|g|千克|公斤|克)'

# 连续乘号表达式：N×N×...×N unit（至少2个数字）
MULTI_EXPR = re.compile(
    r'(\d+(?:\.\d+)?)'
    r'((?:\s*[×x\*]\s*\d+(?:\.\d+)?)+)'
    r'\s*(' + DIM_UNIT + r')',
    re.IGNORECASE,
)

# 长/宽/高 文字同组
LWH_RE = re.compile(
    r'长\s*[：:]?\s*(\d+(?:\.\d+)?)\s*(' + DIM_UNIT + r')?'
    r'[\s,，]*宽\s*[：:]?\s*(\d+(?:\.\d+)?)\s*(' + DIM_UNIT + r')?'
    r'[\s,，]*高\s*[：:]?\s*(\d+(?:\.\d+)?)\s*(' + DIM_UNIT + r')?',
    re.IGNORECASE,
)

# 单独长/宽/高 + 可选单位
LEN_RE = re.compile(r'长\s*[：:]?\s*(\d+(?:\.\d+)?)\s*(' + DIM_UNIT + r')?', re.IGNORECASE)
WID_RE = re.compile(r'宽\s*[：:]?\s*(\d+(?:\.\d+)?)\s*(' + DIM_UNIT + r')?', re.IGNORECASE)
HEI_RE = re.compile(r'高\s*[：:]?\s*(\d+(?:\.\d+)?)\s*(' + DIM_UNIT + r')?', re.IGNORECASE)

# 单独 N dim_unit（无长宽高上下文）；前导不能是负号或数字，避免把 -5g 的 5 当正数
SINGLE_DIM_RE = re.compile(r'(?<![-\d])(\d+(?:\.\d+)?)\s*(' + DIM_UNIT + r')', re.IGNORECASE)
# 重量
WEIGHT_RE = re.compile(r'(?<![-\d])(\d+(?:\.\d+)?)\s*(' + WEIGHT_UNIT + r')', re.IGNORECASE)

# 尺寸/重量上下文词（排序用）
DIM_CONTEXT = re.compile(r'尺寸|规格|长|宽|高|重量|净重|毛重|裸重|包装', re.IGNORECASE)
# 重量词（分支5无单位尺寸排除用，避免把毛重/净重数字当尺寸）
WEIGHT_WORD = re.compile(r'重量|净重|毛重|裸重', re.IGNORECASE)

# 排除：百分比（件/销量/库存等无单位不会被尺寸正则匹配，不在此排除）
EXCLUDE_MARK = re.compile(r'\d+\s*%')
BARE_NUMBER = re.compile(r'(?<![A-Za-z])(\d+(?:\.\d+)?)(?![A-Za-z%])')


def extract(lines: List[OcrTextLine], source_image: str = "") -> List[OcrCandidate]:
    """从 OCR 文本行提取 weight_g / length_cm / width_cm / height_cm 候选。"""
    scored = []
    for idx, line in enumerate(lines):
        text = (line.text or "").strip()
        if not text:
            continue
        if EXCLUDE_MARK.search(text):
            continue
        has_ctx = bool(DIM_CONTEXT.search(text))
        for c in _extract_from_line(text, source_image, line.confidence):
            scored.append((has_ctx, -line.confidence, idx, c))
    return dedupe(sort_candidates(scored))


def _extract_from_line(text: str, source_image: str, confidence: float) -> List[OcrCandidate]:
    dim_candidates = []
    weight_candidates = []
    dim_handled = False

    # 1. 多元乘号表达式（三元/两维/四维+）
    for m in MULTI_EXPR.finditer(text):
        first = m.group(1)
        rest = m.group(2)
        unit = m.group(3)
        all_nums_str = [first] + re.findall(r'\d+(?:\.\d+)?', rest)
        nums = [parse_number(n) for n in all_nums_str]
        nums = [n for n in nums if n is not None]
        full = m.group(0).strip()
        if len(nums) == 3 and all(is_valid_measure(n) for n in nums):
            gid = make_group_id(full + source_image)
            for field, pv in (("length_cm", nums[0]), ("width_cm", nums[1]), ("height_cm", nums[2])):
                nv, _ = normalize_dim(pv, unit)
                dim_candidates.append(make_candidate(
                    field_name=field, parsed_value=pv, source_image=source_image,
                    raw_text=text, confidence=confidence,
                    normalized_value=nv, unit_original=unit, unit_normalized="cm",
                    selectable=True, measurement_group_id=gid,
                ))
            dim_handled = True
        elif len(nums) == 2 and all(is_valid_measure(n) for n in nums):
            # 两维：生成长宽，不补高度
            gid = make_group_id(full + source_image)
            for field, pv in (("length_cm", nums[0]), ("width_cm", nums[1])):
                nv, _ = normalize_dim(pv, unit)
                dim_candidates.append(make_candidate(
                    field_name=field, parsed_value=pv, source_image=source_image,
                    raw_text=text, confidence=confidence,
                    normalized_value=nv, unit_original=unit, unit_normalized="cm",
                    selectable=True, measurement_group_id=gid,
                ))
            dim_handled = True
        elif len(nums) >= 4:
            # 四维及以上：不生成完整三维，且阻止后续 SINGLE_DIM 误匹配末尾单位
            dim_handled = True

    # 2. 长/宽/高 文字同组
    if not dim_handled:
        m = LWH_RE.search(text)
        if m:
            g = m.groups()
            line_units = re.findall(DIM_UNIT, text, re.IGNORECASE)
            fallback = line_units[0] if line_units else None
            vals = [g[0], g[2], g[4]]
            units = [g[1] or fallback, g[3] or fallback, g[5] or fallback]
            nums = [parse_number(v) for v in vals]
            if (all(n is not None and is_valid_measure(n) for n in nums)
                    and all(u for u in units)):
                gid = make_group_id(text + source_image)
                for field, pv, u in (("length_cm", nums[0], units[0]),
                                     ("width_cm", nums[1], units[1]),
                                     ("height_cm", nums[2], units[2])):
                    nv, _ = normalize_dim(pv, u)
                    dim_candidates.append(make_candidate(
                        field_name=field, parsed_value=pv, source_image=source_image,
                        raw_text=text, confidence=confidence,
                        normalized_value=nv, unit_original=u, unit_normalized="cm",
                        selectable=True, measurement_group_id=gid,
                    ))
                dim_handled = True

    # 3. 单独长/宽/高 + 可选单位
    if not dim_handled:
        lwh_found = False
        for field, rgx in (("length_cm", LEN_RE), ("width_cm", WID_RE), ("height_cm", HEI_RE)):
            m = rgx.search(text)
            if m:
                num = parse_number(m.group(1))
                unit = m.group(2)
                if num is not None and is_valid_measure(num):
                    gid = make_group_id(field + text + source_image)
                    if unit:
                        nv, _ = normalize_dim(num, unit)
                        dim_candidates.append(make_candidate(
                            field_name=field, parsed_value=num, source_image=source_image,
                            raw_text=text, confidence=confidence,
                            normalized_value=nv, unit_original=unit, unit_normalized="cm",
                            selectable=True, measurement_group_id=gid,
                        ))
                    else:
                        dim_candidates.append(make_candidate(
                            field_name=field, parsed_value=num, source_image=source_image,
                            raw_text=text, confidence=confidence,
                            normalized_value=None, unit_original=None, unit_normalized=None,
                            selectable=False, measurement_group_id=gid,
                        ))
                    lwh_found = True
        if lwh_found:
            dim_handled = True

    # 4. 单独 N dim_unit（无长宽高上下文）→ length_cm 默认
    if not dim_handled:
        for m in SINGLE_DIM_RE.finditer(text):
            num = parse_number(m.group(1))
            unit = m.group(2)
            if num is not None and is_valid_measure(num):
                nv, _ = normalize_dim(num, unit)
                dim_candidates.append(make_candidate(
                    field_name="length_cm", parsed_value=num, source_image=source_image,
                    raw_text=text, confidence=confidence,
                    normalized_value=nv, unit_original=unit, unit_normalized="cm",
                    selectable=True,
                    measurement_group_id=make_group_id("dim" + text + source_image + str(num)),
                ))
                dim_handled = True

    # 5. 无单位 + 尺寸上下文（排除重量词）→ length_cm selectable=False
    if not dim_handled and DIM_CONTEXT.search(text) and not WEIGHT_WORD.search(text):
        for m in BARE_NUMBER.finditer(text):
            num = parse_number(m.group(1))
            if num is not None and is_valid_measure(num):
                dim_candidates.append(make_candidate(
                    field_name="length_cm", parsed_value=num, source_image=source_image,
                    raw_text=text, confidence=confidence,
                    normalized_value=None, unit_original=None, unit_normalized=None,
                    selectable=False,
                    measurement_group_id=make_group_id("bare" + text + source_image + str(num)),
                ))

    # 6. 重量（独立于尺寸，同行可同时有重量和尺寸）
    for m in WEIGHT_RE.finditer(text):
        num = parse_number(m.group(1))
        unit = m.group(2)
        if num is not None and is_valid_measure(num):
            nv, nu = normalize_weight(num, unit)
            if nv is not None:
                weight_candidates.append(make_candidate(
                    field_name="weight_g", parsed_value=num, source_image=source_image,
                    raw_text=text, confidence=confidence,
                    normalized_value=nv, unit_original=unit, unit_normalized=nu,
                    selectable=True,
                    measurement_group_id=make_group_id("w" + text + source_image + str(num) + str(nv)),
                ))

    return dim_candidates + weight_candidates
