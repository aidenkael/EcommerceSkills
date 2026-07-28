"""OCR 录入候选与用户确认结果的数据结构。

设计原则：
- OCR 原始候选（OcrCandidate）不可变，用户修改不覆盖原始数据。
- 用户确认结果（FieldSelection）独立保存，记录最终采用值。
- 无单位时保留 parsed_value，但 normalized_value=None 且 selectable=False。
- 本步骤只定义结构，不实现文件读写。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class MeasurementScope(Enum):
    """尺寸/重量候选的测量范围。"""
    BARE = "bare"                          # 裸件
    PACKAGED = "packaged"                  # 包装
    UNKNOWN = "unknown"                    # 无法确认
    NOT_APPLICABLE = "not_applicable"      # 非尺寸类（价格/成本/运费）


# 尺寸/重量类字段（需要 measurement_scope = bare/packaged/unknown）
DIMENSION_FIELDS = frozenset({"weight_g", "length_cm", "width_cm", "height_cm"})

# 价格/成本/运费类字段（measurement_scope 固定为 not_applicable）
PRICE_FIELDS = frozenset({"shein_price_usd", "product_cost_rmb", "domestic_shipping_rmb"})


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class OcrCandidate:
    """单个 OCR 候选值（不可变）。

    用户修改不会覆盖此对象，修改结果写入 FieldSelection。
    """
    # 必填
    field_name: str
    parsed_value: Optional[float]              # OCR 解析出的数字（无单位也保留，不丢）
    source_image: str                           # 来源图片 ID
    raw_text: str                               # OCR 原文片段（如 "0.5kg" "约 12.8 元"）
    # 可选（有默认）
    confidence: float = 0.0
    normalized_value: Optional[float] = None    # 单位明确后的标准值（无单位时为 None）
    unit_original: Optional[str] = None         # 原始单位（"g"/"kg"/"mm"/"cm"/"$"/"元"，无单位为 None）
    unit_normalized: Optional[str] = None       # 归一化单位（"g"/"cm"/"usd"/"rmb"，无单位为 None）
    selectable: bool = False                    # 是否可被选中（无单位时默认 False）
    measurement_group_id: Optional[str] = None  # 关联同组长宽高重量；非尺寸类为 None
    candidate_id: str = field(default_factory=_new_id)


@dataclass
class FieldSelection:
    """用户最终确认或修改后的结果。

    用户修改数字、单位或 scope 后：
    - 原 OcrCandidate 保持不变；
    - 本对象保存最终确认值；
    - user_modified 设为 True。
    """
    field_name: str
    source_candidate_id: str                    # 来源候选 ID
    confirmed_value: Optional[float]            # 确认值（可为 None）
    confirmed_unit: Optional[str]               # 确认单位（可为 None）
    measurement_scope: MeasurementScope         # bare/packaged/unknown/not_applicable
    user_modified: bool = False                 # 用户是否修改过


@dataclass
class FieldCandidates:
    """一个字段的全部候选。

    不自动选择最低价，不删除重复来源。用户可在 UI 中勾选其中一个。
    """
    field_name: str
    candidates: list = field(default_factory=list)  # list[OcrCandidate]，按置信度降序
    selected_candidate_id: Optional[str] = None     # 用户选中的候选 ID，None=未选


@dataclass
class IntakeSession:
    """一次录入会话（本步骤只定义结构，不实现文件读写）。"""
    session_id: str
    created_at: str
    session_dir: str
    images: list = field(default_factory=list)           # [{"image_id","path","image_type","original_name"}]
    field_candidates: dict = field(default_factory=dict)  # key=field_name, value=FieldCandidates
    selections: dict = field(default_factory=dict)        # key=field_name, value=FieldSelection
    engine_name: str = "placeholder"
