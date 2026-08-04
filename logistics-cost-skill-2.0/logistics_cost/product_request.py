"""商品请求对象 — 定义当前商品的独立请求与事实收集。

提供 create_product_request() 创建新请求，ProductRequest 类封装所有商品级数据。
每个新商品必须创建新的 ProductRequest，确保不跨商品污染。
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
    """基于商品身份稳定生成签名。"""
    parts = [
        _normalize(title),
        _normalize(sku),
        str(quantity),
        image_fingerprint,
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _make_request_id() -> str:
    """生成唯一请求ID。"""
    t = str(int(time.time() * 1000))
    return f"req-{t[-10:]}"


@dataclass
class Fact:
    """单个商品事实条目。"""
    field: str
    value: Any
    source: str        # user_confirmed / merchant_text / image_visible / ai_inferred / calibrated
    confidence: str = "medium"  # high / medium / low
    location: str = ""


@dataclass
class ProductRequest:
    """当前商品的完整请求对象。"""
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
    # 运行结果
    ai_data: dict = field(default_factory=dict)
    calibration_hit: bool = False
    calibration_case_id: str = ""
    run_stdout: str = ""
    result: dict = field(default_factory=dict)

    def add_fact(self, field: str, value: Any, source: str, confidence: str = "medium", location: str = "") -> None:
        """添加一个事实。更高优先级来源不覆盖。"""
        existing = self.get_fact(field)
        if existing:
            old_rank = _source_rank(existing.source)
            new_rank = _source_rank(source)
            if new_rank <= old_rank:
                return  # 不覆盖同优先级或更低来源
        self.facts = [f for f in self.facts if f.field != field]
        self.facts.append(Fact(field=field, value=value, source=source, confidence=confidence, location=location))

    def get_fact(self, field: str) -> Fact | None:
        for f in self.facts:
            if f.field == field:
                return f
        return None

    def get_fact_value(self, field: str, default: Any = None) -> Any:
        f = self.get_fact(field)
        return f.value if f else default


def _source_rank(source: str) -> int:
    """来源优先级排名（数字越小越优先）。"""
    ranks = {
        "user_confirmed": 1,
        "merchant_text": 2,
        "image_visible": 3,
        "calibrated": 4,
        "ai_inferred": 5,
    }
    return ranks.get(source, 99)


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
    """创建新的商品请求（每次新商品必须调用）。

    新请求自动清空商品级状态，保留用户偏好层。
    """
    sig = _make_product_signature(title, selected_sku, quantity, image_fingerprint)
    req = ProductRequest(
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
    return req
