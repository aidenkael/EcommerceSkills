"""OCR 字段候选提取器集合。

三个提取器统一接口：
    extract(lines: list[OcrTextLine], source_image: str = "") -> list[OcrCandidate]

输入：OCR 文本行列表（source_image 来自 OcrPageResult.image_id，作为辅助参数）。
输出：OcrCandidate 列表，已按上下文/置信度/出现顺序排序并去完全重复。
"""
from image_intake.extractors.shein_price_extractor import extract as extract_shein_price
from image_intake.extractors.cost_shipping_extractor import extract as extract_cost_shipping
from image_intake.extractors.dimension_extractor import extract as extract_dimension

__all__ = [
    "extract_shein_price",
    "extract_cost_shipping",
    "extract_dimension",
]
