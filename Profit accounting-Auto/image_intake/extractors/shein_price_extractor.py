"""SHEIN 核价截图提取器：从 OCR 文本行提取 shein_price_usd 候选。

只生成候选，不自动选择最终核价。
人民币金额不进入美元候选；百分比/销量/库存等不当作价格。
"""
import re
from typing import List

from image_intake.result_models import OcrCandidate
from ocr.base_engine import OcrTextLine
from .common import (
    parse_number, is_valid_amount, make_candidate, dedupe, sort_candidates,
)


# 美元金额正则（按优先级）
USD_PATTERNS = [
    re.compile(r'US\$\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    re.compile(r'USD\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    re.compile(r'\$\s*(\d+(?:\.\d+)?)'),
    re.compile(r'(\d+(?:\.\d+)?)\s*美元'),
]

# 人民币标识（出现则该行金额不是美元）
RMB_MARK = re.compile(r'[¥￥]|RMB|CNY|元')

# 价格上下文词（仅用于排序，不自动选中）
PRICE_CONTEXT = re.compile(r'核价|定价|售价|价格|price', re.IGNORECASE)

# 排除模式：百分比、页码（起订量/销量等无货币符号不会被 USD 正则匹配，不在此排除）
EXCLUDE_MARK = re.compile(
    r'\d+\s*%|'
    r'\d+\s*页',
    re.IGNORECASE,
)

# 独立数字（前后非字母，避免匹配 USD15 中的 15）
BARE_NUMBER = re.compile(r'(?<![A-Za-z])(\d+(?:\.\d+)?)(?![A-Za-z])')


def _detect_usd_unit(text: str) -> str:
    """检测美元原始单位标识。"""
    if re.search(r'US\$', text, re.IGNORECASE):
        return 'US$'
    if re.search(r'\bUSD\b', text, re.IGNORECASE):
        return 'USD'
    if '$' in text:
        return '$'
    if '美元' in text:
        return '美元'
    return '$'


def extract(lines: List[OcrTextLine], source_image: str = "") -> List[OcrCandidate]:
    """从 OCR 文本行提取 shein_price_usd 候选。

    输入：list[OcrTextLine]（+ source_image 辅助参数，来自 OcrPageResult.image_id）
    输出：list[OcrCandidate]，按上下文/置信度/出现顺序排序，已去完全重复。
    """
    scored = []
    for idx, line in enumerate(lines):
        text = (line.text or "").strip()
        if not text:
            continue
        if EXCLUDE_MARK.search(text):
            continue
        has_ctx = bool(PRICE_CONTEXT.search(text))
        found_usd = False
        for pat in USD_PATTERNS:
            for m in pat.finditer(text):
                num = parse_number(m.group(1))
                if not is_valid_amount(num):
                    continue
                found_usd = True
                c = make_candidate(
                    field_name="shein_price_usd",
                    parsed_value=num,
                    source_image=source_image,
                    raw_text=text,
                    confidence=line.confidence,
                    normalized_value=num,
                    unit_original=_detect_usd_unit(text),
                    unit_normalized="usd",
                    selectable=True,
                )
                scored.append((has_ctx, -line.confidence, idx, c))
        # 无单位但有核价上下文：保留 parsed_value，不可选
        if not found_usd and has_ctx:
            # 排除人民币上下文
            if RMB_MARK.search(text):
                continue
            for m in BARE_NUMBER.finditer(text):
                num = parse_number(m.group(1))
                if not is_valid_amount(num):
                    continue
                c = make_candidate(
                    field_name="shein_price_usd",
                    parsed_value=num,
                    source_image=source_image,
                    raw_text=text,
                    confidence=line.confidence,
                    normalized_value=None,
                    unit_original=None,
                    unit_normalized=None,
                    selectable=False,
                )
                scored.append((has_ctx, -line.confidence, idx, c))
    return dedupe(sort_candidates(scored))
