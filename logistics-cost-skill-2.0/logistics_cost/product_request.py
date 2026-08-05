"""商品请求对象 — 当前商品的独立请求与事实收集。

ProductRequest 是商品级状态的唯一容器。
事实系统：field + value + unit(内部kg/cm) + scope + source + confidence + location。
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    t = t.replace("\u3000", " ")
    t = re.sub(r"\s+", " ", t)
    return t


def _make_product_signature(title: str, sku: str, quantity: int, image_fingerprint: str = "") -> str:
    parts = [_normalize(title), _normalize(sku), str(quantity), image_fingerprint]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


_request_counter = 0


def _make_request_id() -> str:
    global _request_counter
    _request_counter += 1
    t = str(int(time.perf_counter_ns()))
    return f"req-{t[-8:]}-{_request_counter}"


@dataclass
class Fact:
    """单个商品事实条目。

    Attributes:
        field: 事实字段名 (net_weight / product_size / shipping_package_size / purchase_price 等)
        value: 值 (内部单位: 重量=kg, 尺寸=cm, 价格=RMB)
        unit: 传入单位，内部归一化后记录为 "kg" / "cm" / "rmb"
        scope: 语义范围 (product / shipping_package / display / unknown)
        source: 来源 (user_confirmed / merchant_text / image_visible / calibrated / ai_inferred)
        confidence: 置信度 (high / medium / low)
        location: 证据位置（可选）
    """
    field: str
    value: Any
    unit: str = ""
    scope: str = "unknown"
    source: str = "ai_inferred"
    confidence: str = "medium"
    location: str = ""


# 来源优先级排名（数字越小优先级越高）
_SOURCE_RANK = {
    "user_confirmed": 1,
    "merchant_text": 2,
    "image_visible": 3,
    "calibrated": 4,
    "ai_inferred": 5,
}


def _normalize_weight(value: Any, unit: str) -> float | None:
    """重量归一化到 kg。"""
    if value is None:
        return None
    try:
        v = float(value)
    except (ValueError, TypeError):
        return None
    u = (unit or "").lower().strip()
    if u in ("g", "gram", "grams"):
        return v / 1000.0
    if u in ("kg", "kilogram", "kilograms"):
        return v
    # 无单位时猜测：> 100 可能是 g
    if not u and v > 100:
        return v / 1000.0
    return v


@dataclass
class ProductRequest:
    """当前商品的完整请求对象。"""
    request_id: str = field(default_factory=_make_request_id)
    product_signature: str = ""

    title: str = ""
    selected_sku: str = ""
    quantity: int = 1
    unit: str = "件"

    image_path: str = ""
    image_fingerprint: str = ""

    purchase_price_rmb: float | None = None
    domestic_freight_rmb: float | None = None

    facts: list[Fact] = field(default_factory=list)

    ai_data_raw: dict = field(default_factory=dict)
    ai_data_arbitrated: dict = field(default_factory=dict)

    calibration_hit: bool = False
    calibration_case_id: str = ""

    result: dict = field(default_factory=dict)
    run_stdout: str = ""

    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    # ---- Fact 操作 ----

    def add_fact(self, field: str, value: Any, source: str, confidence: str = "medium",
                 unit: str = "", scope: str = "unknown", location: str = "") -> bool:
        """添加事实。高优先级覆盖低优先级，同优先级保留先添加。内部分量自动归一到kg。"""
        new_rank = _SOURCE_RANK.get(source, 99)
        existing = self.get_fact(field)
        if existing:
            old_rank = _SOURCE_RANK.get(existing.source, 99)
            if new_rank >= old_rank:
                return False
        # 重量归一化
        norm_value = value
        norm_unit = unit
        if field == "net_weight":
            nv = _normalize_weight(value, unit)
            if nv is not None:
                norm_value = nv
                norm_unit = "kg"
        if field in ("product_size", "shipping_package_size", "display_size") and unit in ("mm",):
            if isinstance(value, list):
                norm_value = [v / 10.0 for v in value]
            norm_unit = "cm"

        self.facts = [f for f in self.facts if f.field != field]
        self.facts.append(Fact(field=field, value=norm_value, unit=norm_unit or unit, scope=scope,
                               source=source, confidence=confidence, location=location))
        return True

    def get_fact(self, field: str) -> Fact | None:
        for f in self.facts:
            if f.field == field:
                return f
        return None

    def get_fact_value(self, field: str, default: Any = None) -> Any:
        f = self.get_fact(field)
        return f.value if f else default

    # ---- 统一重量解析 ----

    def get_resolved_net_weight(self) -> dict:
        """按优先级解析唯一有效净重（内部单位kg）。

        Returns:
            {"value_kg": float|None, "source": str, "confidence": str}
        """
        for source in ("user_confirmed", "merchant_text", "image_visible", "calibrated", "ai_inferred"):
            for f in self.facts:
                if f.field == "net_weight" and f.source == source and f.value is not None:
                    try:
                        return {"value_kg": float(f.value), "source": f.source, "confidence": f.confidence}
                    except (ValueError, TypeError):
                        continue
        return {"value_kg": None, "source": "unknown", "confidence": "low"}

    # ---- 统一尺寸解析 ----

    def get_resolved_dimensions(self) -> dict:
        """按优先级解析尺寸事实。

        Returns:
            {"dims_cm": list|None, "source": str, "scope": str, "confidence": str}
        """
        for source in ("user_confirmed", "merchant_text", "image_visible", "calibrated", "ai_inferred"):
            for scope in ("shipping_package_size", "product_size", "display_size"):
                for f in self.facts:
                    if f.field == scope and f.source == source and isinstance(f.value, list):
                        return {"dims_cm": f.value, "source": f.source, "scope": scope, "confidence": f.confidence}
        return {"dims_cm": None, "source": "unknown", "scope": "unknown", "confidence": "low"}

    # ---- 信封 facts 批导入 ----

    def import_envelope_facts(self, facts_list: list[dict]) -> None:
        """从信封 facts 数组批量导入事实。显式提供来源时保留该来源。"""
        if not isinstance(facts_list, list):
            return
        for item in facts_list:
            field = str(item.get("field", "") or "")
            source = str(item.get("source", "") or "")
            if not field or not source or source not in _SOURCE_RANK:
                continue
            self.add_fact(
                field=field,
                value=item.get("value"),
                source=source,
                confidence=str(item.get("confidence", "medium")),
                unit=str(item.get("unit", "")),
                scope=str(item.get("scope", "unknown")),
                location=str(item.get("location", "")),
            )


def create_product_request(
    title: str,
    selected_sku: str,
    quantity: int = 1,
    *,
    image_path: str = "",
    image_fingerprint: str = "",
    unit: str = "件",
    purchase_price_rmb: float | None = None,
    domestic_freight_rmb: float | None = None,
) -> ProductRequest:
    sig = _make_product_signature(title, selected_sku, quantity, image_fingerprint)
    return ProductRequest(
        product_signature=sig, title=title, selected_sku=selected_sku,
        quantity=quantity, unit=unit, image_path=image_path,
        image_fingerprint=image_fingerprint,
        purchase_price_rmb=purchase_price_rmb,
        domestic_freight_rmb=domestic_freight_rmb,
    )
