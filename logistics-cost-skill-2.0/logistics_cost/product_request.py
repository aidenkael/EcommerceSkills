"""商品请求对象 — 当前商品的独立请求与事实收集。

ProductRequest 是商品级状态的唯一容器：身份、事实、AI数据、计算、输出。
每次新商品必须创建新的 ProductRequest，确保不跨商品污染。
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
    """单个商品事实条目，带来源优先级。"""
    field: str
    value: Any
    source: str        # user_confirmed > merchant_text > image_visible > calibrated > ai_inferred
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


@dataclass
class ProductRequest:
    """当前商品的完整请求对象（唯一商品级状态容器）。"""
    request_id: str = field(default_factory=_make_request_id)
    product_signature: str = ""

    # 身份
    title: str = ""
    selected_sku: str = ""
    quantity: int = 1
    unit: str = "件"

    # 图片
    image_path: str = ""
    image_fingerprint: str = ""

    # 成本
    purchase_price_rmb: float | None = None
    domestic_freight_rmb: float | None = None

    # 事实
    facts: list[Fact] = field(default_factory=list)

    # AI 数据
    ai_data_raw: dict = field(default_factory=dict)
    ai_data_arbitrated: dict = field(default_factory=dict)

    # 校准
    calibration_hit: bool = False
    calibration_case_id: str = ""

    # 计算结果
    result: dict = field(default_factory=dict)
    run_stdout: str = ""

    # 时间
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    def add_fact(self, field: str, value: Any, source: str, confidence: str = "medium", location: str = "") -> bool:
        """添加事实。更高优先级来源覆盖低优先级，同优先级保留先添加的。

        Returns:
            是否实际添加/覆盖了事实
        """
        new_rank = _SOURCE_RANK.get(source, 99)
        existing = self.get_fact(field)
        if existing:
            old_rank = _SOURCE_RANK.get(existing.source, 99)
            # 新来源优先级低于或等于旧来源 → 拒绝覆盖
            if new_rank >= old_rank:
                return False
        # 更高优先级 → 覆盖
        self.facts = [f for f in self.facts if f.field != field]
        self.facts.append(Fact(field=field, value=value, source=source, confidence=confidence, location=location))
        return True

    def get_fact(self, field: str) -> Fact | None:
        for f in self.facts:
            if f.field == field:
                return f
        return None

    def get_fact_value(self, field: str, default: Any = None) -> Any:
        f = self.get_fact(field)
        return f.value if f else default

    def get_user_weight_info(self) -> tuple[float | None, str]:
        """获取用户确认或商家明确的重量信息（用于可信重量入口）。"""
        for source in ("user_confirmed", "merchant_text"):
            f = self.get_fact("net_weight_g")
            if f and f.source == source and isinstance(f.value, (int, float)):
                return (float(f.value), source)
        return (None, "未提供")

    def get_dimensions_info(self) -> tuple[list[float] | None, str, str]:
        """获取用户/商家明确的尺寸信息。"""
        for source in ("user_confirmed", "merchant_text"):
            f = self.get_fact("product_size_cm")
            if f and f.source == source and isinstance(f.value, list):
                return (f.value, source, "product_size")
            f = self.get_fact("shipping_package_size_cm")
            if f and f.source == source and isinstance(f.value, list):
                return (f.value, source, "shipping_package_size")
        return (None, "unknown", "unknown")


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
    """创建新的商品请求（每次新商品必须调用）。"""
    sig = _make_product_signature(title, selected_sku, quantity, image_fingerprint)
    return ProductRequest(
        product_signature=sig,
        title=title,
        selected_sku=selected_sku,
        quantity=quantity,
        unit=unit,
        image_path=image_path,
        image_fingerprint=image_fingerprint,
        purchase_price_rmb=purchase_price_rmb,
        domestic_freight_rmb=domestic_freight_rmb,
    )
