"""第一版人工指定的图片类型。

本阶段不自动判断图片类型，由用户在上传时手动选择。
"""
from enum import Enum


class ImageType(Enum):
    """用户人工指定的图片类型（第一版 5 种）。"""
    PRODUCT_MAIN_IMAGE = "product_main_image"
    SHEIN_PRICING = "shein_pricing"
    SUPPLIER_COST_SHIPPING = "supplier_cost_shipping"
    DIMENSIONS_WEIGHT = "dimensions_weight"
    SUPPLEMENTARY = "supplementary"


IMAGE_TYPE_LABELS = {
    ImageType.PRODUCT_MAIN_IMAGE: "商品主图",
    ImageType.SHEIN_PRICING: "SHEIN 核价截图",
    ImageType.SUPPLIER_COST_SHIPPING: "1688 成本及运费截图",
    ImageType.DIMENSIONS_WEIGHT: "尺寸和重量截图",
    ImageType.SUPPLEMENTARY: "补充截图",
}


def image_type_label(image_type: ImageType) -> str:
    """返回图片类型的中文显示名称。"""
    return IMAGE_TYPE_LABELS.get(image_type, image_type.value)
