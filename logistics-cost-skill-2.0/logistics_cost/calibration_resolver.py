"""精确校准解析 — 程序化精确校准查询与覆盖。

提供 resolve_exact_calibration() 进行本地精确键查询，
以及 apply_calibration_override() 将命中的校准参数覆盖到 AI JSON。
两者均为纯本地纯函数，不引入第三方库。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _default_cases_path() -> Path:
    return Path(__file__).resolve().parent.parent / "knowledge" / "calibration_cases.jsonl"


def _normalize(text: str) -> str:
    """规范化文本：转小写、去首尾空格、合并空白、全角空格统一。"""
    if not text:
        return ""
    t = text.lower().strip()
    t = t.replace("\u3000", " ")  # 全角空格
    t = re.sub(r"\s+", " ", t)
    return t


def resolve_exact_calibration(
    title: str,
    selected_sku: str,
    quantity: int,
    cases_path: Path | None = None,
) -> dict | None:
    """精确校准查询 — 只返回第一个合法精确命中的案例。

    Args:
        title: 商品标题（原始，内部规范化）
        selected_sku: 当前 SKU（原始，内部规范化）
        quantity: 当前数量
        cases_path: 校准案例文件路径，默认 knowledge/calibration_cases.jsonl

    Returns:
        命中返回案例 dict；未命中返回 None
    """
    if not title or not selected_sku or quantity is None:
        return None

    norm_title = _normalize(title)
    norm_sku = _normalize(selected_sku)

    if not norm_title or not norm_sku:
        return None

    path = cases_path or _default_cases_path()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    case = json.loads(line)
                except json.JSONDecodeError:
                    continue  # 损坏行不影响后续查询

                # 状态过滤
                if case.get("status") != "validated":
                    continue
                if case.get("usage_scope") != "exact_product_sku_only":
                    continue
                if not case.get("runtime_override"):
                    continue

                # 数量
                if case.get("quantity") != quantity:
                    continue

                # SKU
                if _normalize(case.get("selected_sku", "")) != norm_sku:
                    continue

                # 标题标记
                markers = case.get("title_markers", [])
                if not markers:
                    continue
                if not all(_normalize(m) in norm_title for m in markers):
                    continue

                # 两档覆盖参数
                if not case.get("calibrated_estimate_normal") or not case.get("calibrated_estimate_conservative"):
                    continue

                return case
    except FileNotFoundError:
        pass
    return None


def apply_calibration_override(
    ai_data: dict,
    case: dict,
) -> dict:
    """将命中的校准参数覆盖到 AI JSON。

    只覆盖与包装运输有关的字段：
    - 正常档/保守档包装尺寸、重量、方法
    - runtime_overall_form / runtime_modifiers / shape_retention_scope
    - 对应品类的结构字段

    不得覆盖：采购价、国内运费、SKU、数量、汇率、尾程、利润率、活动预留
    """
    if ai_data is None or case is None:
        return ai_data

    normal = case.get("calibrated_estimate_normal") or {}
    conservative = case.get("calibrated_estimate_conservative") or {}

    # 包装尺寸（JSONL 用 cm 单位）
    if "packaged_size_cm" in normal:
        ai_data["ai_package_size_cm"] = normal["packaged_size_cm"]
    if "packaged_weight_g" in normal:
        pkg_weight_kg = normal["packaged_weight_g"] / 1000.0
        ai_data["ai_package_weight_kg"] = pkg_weight_kg
        # 同步 ai_net_weight_kg 以避免"包装重量小于净重"的校验阻断
        ai_data["ai_net_weight_kg"] = pkg_weight_kg
    if "packaging_method" in normal:
        ai_data["packaging_method"] = normal["packaging_method"]

    if "packaged_size_cm" in conservative:
        ai_data["conservative_package_size_cm"] = conservative["packaged_size_cm"]
    if "packaged_weight_g" in conservative:
        ai_data["conservative_package_weight_kg"] = conservative["packaged_weight_g"] / 1000.0

    # 结构字段
    if case.get("runtime_overall_form"):
        ai_data["overall_form"] = case["runtime_overall_form"]
    if case.get("runtime_modifiers"):
        ai_data["modifiers"] = list(case["runtime_modifiers"])
    if case.get("shape_retention_scope"):
        ai_data["shape_retention_scope"] = case["shape_retention_scope"]

    # 品类型字段
    if case.get("rigidity"):
        ai_data["rigidity"] = case["rigidity"]
    elif "foldable_parts" in case and case["foldable_parts"]:
        ai_data["foldability"] = "good"
        ai_data["compressibility"] = "good"
        ai_data["requires_shape_retention"] = False
        ai_data["has_rigid_parts"] = False
        ai_data["folding_action"] = "折叠压扁"
        ai_data["compression_action"] = "轻度压缩"

    # 标记校准元数据
    ai_data["_calibration_applied"] = True
    ai_data["_calibration_case_id"] = case.get("case_id", "")
    ai_data["_calibration_basis"] = case.get("evidence_scope", "")

    return ai_data
