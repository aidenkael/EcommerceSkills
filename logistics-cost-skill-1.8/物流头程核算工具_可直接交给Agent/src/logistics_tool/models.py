from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def _dims(value: Any) -> list[float] | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        for sep in ("x", "X", "×", "*"):
            value = value.replace(sep, ",")
        parts = [p.strip() for p in value.split(",") if p.strip()]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    elif isinstance(value, dict):
        parts = [value.get("length"), value.get("width"), value.get("height")]
    else:
        return None
    if len(parts) != 3:
        return None
    try:
        dims = [float(x) for x in parts]
    except (TypeError, ValueError):
        return None
    return dims if all(x > 0 for x in dims) else None


@dataclass
class ProductAnalysis:
    image_path: str
    product_name: str = "未命名商品"
    category: str = ""
    keywords: list[str] = field(default_factory=list)
    rigidity: str = "unknown"
    package_type: str = "未知"
    quantity: int = 1
    actual_weight_kg: float | None = None
    dimensions_cm: list[float] | None = None
    packed_weight_kg: float | None = None
    packed_dimensions_cm: list[float] | None = None
    compressible: bool = False
    fragile: bool = False
    confidence: str = "low"
    evidence: str = ""
    notes: str = ""
    provider: str = "agent"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProductAnalysis":
        aliases = {
            "name": "product_name",
            "商品名": "product_name",
            "图片路径": "image_path",
            "weight_kg": "actual_weight_kg",
            "重量kg": "actual_weight_kg",
            "尺寸cm": "dimensions_cm",
        }
        data = dict(raw)
        for old, new in aliases.items():
            if new not in data and old in data:
                data[new] = data[old]
        keywords = data.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [x.strip() for x in keywords.replace("，", ",").split(",") if x.strip()]
        rigidity = str(data.get("rigidity") or "unknown").lower()
        if rigidity not in {"soft", "hard", "mixed", "unknown"}:
            rigidity = "unknown"
        confidence = str(data.get("confidence") or "low").lower()
        confidence_map = {"高": "high", "中": "medium", "低": "low"}
        confidence = confidence_map.get(confidence, confidence)
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        try:
            quantity = max(1, int(data.get("quantity") or 1))
        except (TypeError, ValueError):
            quantity = 1
        return cls(
            image_path=str(data.get("image_path") or ""),
            product_name=str(data.get("product_name") or "未命名商品"),
            category=str(data.get("category") or ""),
            keywords=[str(x) for x in keywords],
            rigidity=rigidity,
            package_type=str(data.get("package_type") or "未知"),
            quantity=quantity,
            actual_weight_kg=_float_or_none(data.get("actual_weight_kg")),
            dimensions_cm=_dims(data.get("dimensions_cm")),
            packed_weight_kg=_float_or_none(data.get("packed_weight_kg")),
            packed_dimensions_cm=_dims(data.get("packed_dimensions_cm")),
            compressible=bool(data.get("compressible", False)),
            fragile=bool(data.get("fragile", False)),
            confidence=confidence,
            evidence=str(data.get("evidence") or ""),
            notes=str(data.get("notes") or ""),
            provider=str(data.get("provider") or "agent"),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
