"""1688 成本及运费截图提取器：提取 product_cost_rmb / domestic_shipping_rmb 候选。

商品成本和运费分别归类；多档阶梯价全部保留；不自动选最低价；
包邮/运费0元生成0元候选；无单位但有"单价"上下文保留不可选候选。
"""
import re
from typing import List

from image_intake.result_models import OcrCandidate
from ocr.base_engine import OcrTextLine
from .common import (
    parse_number, is_valid_amount, make_candidate, dedupe, sort_candidates,
)


# 人民币金额正则
RMB_PATTERNS = [
    re.compile(r'[¥￥]\s*(\d+(?:\.\d+)?)'),
    re.compile(r'(\d+(?:\.\d+)?)\s*元'),
    re.compile(r'(?:RMB|CNY)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
]

# 成本上下文
COST_CONTEXT = re.compile(
    r'单价|价格|商品价|采购价|批发价|成本|一件代发|起批价|阶梯价|SKU\s*价',
    re.IGNORECASE,
)
# 运费上下文
SHIPPING_CONTEXT = re.compile(
    r'运费|快递费|物流费|发货费|配送费|到仓运费|发往中转仓|送至中转仓'
)
# 包邮
BAOYOU = re.compile(r'包邮')

# 排除模式：百分比、满减门槛、优惠券（起订量/库存/销量无货币符号不会被 RMB 正则匹配，
# 且无成本/运费上下文时不生成候选，故不在此排除以免误杀阶梯价）
EXCLUDE_MARK = re.compile(
    r'\d+\s*%|'
    r'满\d+|'
    r'券|'
    r'优惠',
    re.IGNORECASE,
)

BARE_NUMBER = re.compile(r'(?<![A-Za-z])(\d+(?:\.\d+)?)(?![A-Za-z])')


def _detect_rmb_unit(text: str) -> str:
    if '¥' in text:
        return '¥'
    if '￥' in text:
        return '￥'
    if re.search(r'\bRMB\b', text, re.IGNORECASE):
        return 'RMB'
    if re.search(r'\bCNY\b', text, re.IGNORECASE):
        return 'CNY'
    if '元' in text:
        return '元'
    return '元'


def extract(lines: List[OcrTextLine], source_image: str = "") -> List[OcrCandidate]:
    """从 OCR 文本行提取 product_cost_rmb 和 domestic_shipping_rmb 候选。"""
    scored = []
    for idx, line in enumerate(lines):
        text = (line.text or "").strip()
        if not text:
            continue
        if EXCLUDE_MARK.search(text):
            continue
        is_cost = bool(COST_CONTEXT.search(text))
        is_ship = bool(SHIPPING_CONTEXT.search(text))

        # 包邮 → 0元运费候选
        if BAOYOU.search(text):
            c = make_candidate(
                field_name="domestic_shipping_rmb",
                parsed_value=0,
                source_image=source_image,
                raw_text=text,
                confidence=line.confidence,
                normalized_value=0,
                unit_original="包邮",
                unit_normalized="rmb",
                selectable=True,
            )
            scored.append((True, -line.confidence, idx, c))
            continue

        found_rmb = False
        for pat in RMB_PATTERNS:
            for m in pat.finditer(text):
                num = parse_number(m.group(1))
                if not is_valid_amount(num):
                    continue
                found_rmb = True
                # 归类：成本上下文 vs 运费上下文
                if is_cost and not is_ship:
                    field = "product_cost_rmb"
                    ctx = True
                elif is_ship and not is_cost:
                    field = "domestic_shipping_rmb"
                    ctx = True
                elif is_cost and is_ship:
                    # 同时出现成本和运费上下文，不强行归类
                    continue
                else:
                    # 无上下文，宁可不生成正式字段候选
                    continue
                c = make_candidate(
                    field_name=field,
                    parsed_value=num,
                    source_image=source_image,
                    raw_text=text,
                    confidence=line.confidence,
                    normalized_value=num,
                    unit_original=_detect_rmb_unit(text),
                    unit_normalized="rmb",
                    selectable=True,
                )
                scored.append((ctx, -line.confidence, idx, c))

        # 无货币符号但有"单价"等成本上下文：保留 parsed_value，不可选
        if not found_rmb and is_cost and not is_ship and not BAOYOU.search(text):
            for m in BARE_NUMBER.finditer(text):
                num = parse_number(m.group(1))
                if not is_valid_amount(num):
                    continue
                c = make_candidate(
                    field_name="product_cost_rmb",
                    parsed_value=num,
                    source_image=source_image,
                    raw_text=text,
                    confidence=line.confidence,
                    normalized_value=None,
                    unit_original=None,
                    unit_normalized=None,
                    selectable=False,
                )
                scored.append((True, -line.confidence, idx, c))
    return dedupe(sort_candidates(scored))
