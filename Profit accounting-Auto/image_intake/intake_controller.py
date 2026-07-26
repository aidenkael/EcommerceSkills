"""OCR 录入弹窗控制器（与 Tkinter 无关，可独立测试）。

职责：
- 管理图片列表（添加/删除/替换/改类型）
- 调用可注入的 OCR 引擎 + 字段提取器收集候选
- 管理用户勾选、编辑和 measurement_scope
- 确认时返回结构化选择结果（FieldSelection）

不写入正式商品字段、数据库或历史快照。
引擎异常不致命，记录 last_error 并继续处理其他图片。
"""
import os
import uuid
from typing import Optional, List, Dict

from image_intake.image_types import ImageType
from image_intake.result_models import OcrCandidate, FieldSelection, MeasurementScope
from ocr.base_engine import BaseOcrEngine, PlaceholderOcrEngine
from image_intake.extractors import extract_shein_price, extract_cost_shipping, extract_dimension


DIMENSION_FIELDS = frozenset({"weight_g", "length_cm", "width_cm", "height_cm"})
PRICE_FIELDS = frozenset({"shein_price_usd", "product_cost_rmb", "domestic_shipping_rmb"})


class OcrIntakeController:
    """OCR 录入状态控制器。UI 层只做展示，逻辑在此。"""

    def __init__(self, engine: Optional[BaseOcrEngine] = None):
        self._engine = engine if engine is not None else PlaceholderOcrEngine()
        self._extractors = {
            ImageType.SHEIN_PRICING: extract_shein_price,
            ImageType.SUPPLIER_COST_SHIPPING: extract_cost_shipping,
            ImageType.DIMENSIONS_WEIGHT: extract_dimension,
        }
        self._images: List[dict] = []
        self._candidates: List[OcrCandidate] = []
        self._selections: Dict[str, FieldSelection] = {}
        self._last_error: Optional[str] = None

    # ─── 只读属性 ──────────────────────────────────────────

    @property
    def engine_name(self) -> str:
        return self._engine.name

    @property
    def images(self) -> List[dict]:
        return list(self._images)

    @property
    def candidates(self) -> List[OcrCandidate]:
        return list(self._candidates)

    @property
    def selections(self) -> Dict[str, FieldSelection]:
        return dict(self._selections)

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    # ─── 图片管理 ──────────────────────────────────────────

    def add_image(self, path: str, image_type: ImageType) -> str:
        """添加图片，返回 image_id。"""
        if not isinstance(image_type, ImageType):
            raise ValueError("image_type 必须是 ImageType 枚举")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"图片不存在或不是普通文件: {path}")
        image_id = uuid.uuid4().hex
        self._images.append({
            "image_id": image_id,
            "path": path,
            "image_type": image_type,
            "filename": os.path.basename(path),
        })
        return image_id

    def remove_image(self, image_id: str) -> None:
        """移除图片及其候选和相关选择。"""
        self._images = [img for img in self._images if img["image_id"] != image_id]
        self._candidates = [c for c in self._candidates if c.source_image != image_id]
        # 移除引用了已删除候选的选择
        remaining_cids = {c.candidate_id for c in self._candidates}
        self._selections = {
            f: s for f, s in self._selections.items()
            if s.source_candidate_id in remaining_cids
        }

    def replace_image(self, image_id: str, new_path: str, new_type: ImageType) -> str:
        """替换图片：移除旧的，添加新的，返回新 image_id。"""
        if image_id not in {img["image_id"] for img in self._images}:
            raise ValueError(f"image_id 不存在: {image_id}")
        self.remove_image(image_id)
        return self.add_image(new_path, new_type)

    def set_image_type(self, image_id: str, image_type: ImageType) -> None:
        """切换图片类型。下次 process_all 后候选会按新类型重新提取。"""
        for img in self._images:
            if img["image_id"] == image_id:
                img["image_type"] = image_type
                return
        raise ValueError(f"image_id 不存在: {image_id}")

    # ─── OCR 处理 ──────────────────────────────────────────

    def process_all(self) -> List[OcrCandidate]:
        """对所有图片调引擎 + 提取器，收集候选。引擎异常不致命。"""
        self._candidates = []
        self._last_error = None
        for img in self._images:
            try:
                result = self._engine.recognize(img["path"], img["image_id"])
                extractor = self._extractors.get(img["image_type"])
                if extractor and result.lines:
                    cands = extractor(result.lines, img["image_id"])
                    self._candidates.extend(cands)
            except Exception as exc:
                self._last_error = f"处理图片 {img['filename']} 失败: {exc}"
        return list(self._candidates)

    def candidates_for_field(self, field_name: str) -> List[OcrCandidate]:
        return [c for c in self._candidates if c.field_name == field_name]

    def candidate_by_id(self, candidate_id: str) -> Optional[OcrCandidate]:
        return next((c for c in self._candidates if c.candidate_id == candidate_id), None)

    # ─── 选择与编辑 ────────────────────────────────────────

    def select_candidate(self, field_name: str, candidate_id: str) -> FieldSelection:
        """选中一个候选。价格类 scope=NOT_APPLICABLE，尺寸/重量类默认 UNKNOWN。"""
        c = self.candidate_by_id(candidate_id)
        if c is None:
            raise ValueError(f"候选不存在: {candidate_id}")
        if field_name in PRICE_FIELDS:
            scope = MeasurementScope.NOT_APPLICABLE
        else:
            scope = MeasurementScope.UNKNOWN
        sel = FieldSelection(
            field_name=field_name,
            source_candidate_id=candidate_id,
            confirmed_value=c.normalized_value,
            confirmed_unit=c.unit_normalized,
            measurement_scope=scope,
            user_modified=False,
        )
        self._selections[field_name] = sel
        return sel

    def set_measurement_scope(self, field_name: str, scope: MeasurementScope) -> None:
        if field_name not in self._selections:
            raise ValueError(f"字段未选中: {field_name}")
        if not isinstance(scope, MeasurementScope):
            raise ValueError("scope 必须是 MeasurementScope 枚举")
        old = self._selections[field_name]
        self._selections[field_name] = FieldSelection(
            field_name=old.field_name,
            source_candidate_id=old.source_candidate_id,
            confirmed_value=old.confirmed_value,
            confirmed_unit=old.confirmed_unit,
            measurement_scope=scope,
            user_modified=True,
        )

    def edit_confirmed_value(self, field_name: str, value, unit=None) -> None:
        if field_name not in self._selections:
            raise ValueError(f"字段未选中: {field_name}")
        old = self._selections[field_name]
        self._selections[field_name] = FieldSelection(
            field_name=old.field_name,
            source_candidate_id=old.source_candidate_id,
            confirmed_value=value,
            confirmed_unit=unit if unit is not None else old.confirmed_unit,
            measurement_scope=old.measurement_scope,
            user_modified=True,
        )

    def deselect(self, field_name: str) -> None:
        self._selections.pop(field_name, None)

    # ─── 确认 ──────────────────────────────────────────────

    def can_confirm(self) -> bool:
        """所有选中候选必须 selectable，否则不能确认。"""
        for sel in self._selections.values():
            c = self.candidate_by_id(sel.source_candidate_id)
            if c is None or not c.selectable:
                return False
        return True

    def confirm(self) -> Dict[str, FieldSelection]:
        """返回结构化选择结果。不写入正式字段、数据库或历史快照。"""
        if not self.can_confirm():
            raise RuntimeError("当前选择不满足确认条件（存在不可选候选或候选已删除）")
        return dict(self._selections)
