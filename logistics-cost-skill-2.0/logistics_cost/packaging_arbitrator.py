"""包装候选仲裁 — 证据驱动的字段级修复 (不整份重写 AI JSON)。

流程：
  原始AI JSON → 字段标准化 → 证据门槛 → 结构分类纠正
  → 选择最多1条聚合规则 → 按字段修复正常档 → 按风险生成保守档 → 返回
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

# ---------- 硬结构强证据名单 ----------

HARD_STRUCTURE_FACTS = {"hard_bottom", "rigid_frame", "rigid_lining"}
WEAK_STRUCTURE_ITEMS = {"拉链", "提手", "肩带", "金属扣", "金属拉链头", "装饰牌", "包边", "普通五金"}

# ---------- 材质标准化映射 ----------

_MATERIAL_NORM = {
    "pvc": "pvc", "聚氯乙烯": "pvc",
    "tpu": "tpu",
    "pu": "pu", "聚氨酯皮": "pu", "人造革": "pu",
    "oxford": "oxford", "牛津布": "oxford",
    "canvas": "canvas", "帆布": "canvas",
    "fabric": "fabric", "布料": "fabric", "涤纶布": "fabric",
    "thin_textile": "thin_textile", "薄针织": "thin_textile", "冰丝": "thin_textile", "丝袜": "thin_textile",
    "透明软塑料": "transparent_soft_plastic", "透明塑料薄膜": "transparent_soft_plastic",
    "clear soft plastic": "transparent_soft_plastic",
}


def _default_rules_path() -> Path:
    return Path(__file__).resolve().parent.parent / "knowledge" / "packaging_arbitration_rules.json"


def _min_axis(dims: list[float]) -> int:
    if not dims or len(dims) < 3:
        return 2
    vals = [dims[0], dims[1], dims[2]]
    return vals.index(min(vals))


def _has_strong_hard_evidence(ai_data: dict) -> bool:
    """检查是否有硬结构强证据。"""
    evidence_list = ai_data.get("structure_evidence", [])
    if not isinstance(evidence_list, list):
        return False
    for ev in evidence_list:
        fact = str(ev.get("fact", "")).strip()
        source = str(ev.get("source", "")).strip()
        location = str(ev.get("location", "")).strip()
        if fact in HARD_STRUCTURE_FACTS:
            if source in ("user_confirmed", "merchant_text"):
                return True
            if source == "image_visible" and location:
                return True
    return False


def _has_strong_protrusion_evidence(ai_data: dict) -> bool:
    """检查是否有硬质突出件强证据。"""
    evidence_list = ai_data.get("structure_evidence", [])
    if not isinstance(evidence_list, list):
        return not all(ai_data.get(key) in ("soft", "none", False, "") for key in ("rigidity",))
    for ev in evidence_list:
        fact = str(ev.get("fact", "")).strip()
        if fact not in HARD_STRUCTURE_FACTS and ev.get("source") in ("user_confirmed", "merchant_text"):
            return True
    return False


def _normalize_material(raw: str) -> str:
    if not raw:
        return "unknown"
    key = raw.lower().strip().replace("-", "_").replace(" ", "_")
    for pattern, norm in _MATERIAL_NORM.items():
        if pattern in key:
            return norm
    return "unknown"


# ---------- 主函数 ----------

def arbitrate_packaging_candidate(
    ai_data: dict,
    *,
    exact_calibration_applied: bool = False,
    rules_path: Path | None = None,
) -> dict:
    """仲裁 AI 包装候选。

    Args:
        ai_data: 原始 AI JSON
        exact_calibration_applied: 是否已命中精确校准（命中时只做字段合法化）
        rules_path: 聚合规则文件路径

    Returns:
        修复后的新 dict
    """
    if ai_data is None:
        return {}

    d = dict(ai_data)  # 不污染输入

    # ---- 1. 字段标准化 ----
    _standardize_fields(d)

    # ---- 2. 证据门槛检查 ----
    _evidence_gate(d)

    # ---- 3. 结构分类纠正 ----
    _correct_structure_classification(d)

    # 精确校准已应用时，不再应用通用聚合规则
    if exact_calibration_applied:
        return d

    # ---- 4. 加载规则并匹配 ----
    rules = _load_rules(rules_path)
    matched_rule = _match_rule(d, rules)
    if matched_rule is None:
        return d

    # ---- 5. 按规则修复正常档 ----
    d = _apply_rule_action(d, matched_rule)

    return d


def _standardize_fields(d: dict) -> None:
    """标准化字段默认值。"""
    if "material_family" not in d or d.get("material_family") == "unknown":
        raw = d.get("material_family") or d.get("material") or d.get("notes", "") or ""
        if isinstance(raw, str) and raw and raw != "unknown":
            d["material_family"] = _normalize_material(raw)
        else:
            d.setdefault("material_family", "unknown")

    d.setdefault("structure_evidence", [])


def _evidence_gate(d: dict) -> None:
    """硬结构证据门槛：无强证据的硬结构声明降级。"""
    has_strong = _has_strong_hard_evidence(d)

    rigidity = d.get("rigidity", "")
    has_rigid = d.get("has_rigid_parts", False)
    requires_retention = d.get("requires_shape_retention", False)
    retention_scope = d.get("shape_retention_scope", "none")
    overall_form = d.get("overall_form", "")

    needs_strong = (
        rigidity in ("semi_rigid", "hard")
        or has_rigid
        or requires_retention
        or retention_scope in ("body", "whole")
        or overall_form in ("semi_structured_hollow", "hard_3d")
    )

    if needs_strong and not has_strong:
        d["rigidity"] = "soft"
        d["has_rigid_parts"] = False
        d["requires_shape_retention"] = False
        d["shape_retention_scope"] = "none"
        if overall_form in ("semi_structured_hollow", "hard_3d"):
            d["overall_form"] = "unknown"
        d.setdefault("_arbitration_note", "")
        current = d.get("_arbitration_note", "")
        d["_arbitration_note"] = (current + ";unsupported_rigidity_claim").strip(";")


def _correct_structure_classification(d: dict) -> None:
    """纠正结构分类：soft_hollow 类型使用软品逻辑。"""
    if d.get("overall_form") == "soft_hollow":
        if d.get("rigidity") not in ("soft",):
            d["rigidity"] = "soft"
        d["has_rigid_parts"] = False
        d["requires_shape_retention"] = False
        d["shape_retention_scope"] = "none"
        d.setdefault("modifiers", [])
        if "hollow" not in d["modifiers"]:
            d["modifiers"] = list(d["modifiers"]) + ["hollow"]


def _load_rules(path: Path | None) -> list[dict]:
    p = path or _default_rules_path()
    try:
        with open(p, encoding="utf-8") as f:
            rules = json.load(f)
        return [r for r in rules if r.get("enabled", True)]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _match_rule(d: dict, rules: list[dict]) -> dict | None:
    """匹配第一条最高优先级规则。"""
    matched = None
    best_priority = -1

    for rule in rules:
        m = rule.get("match") or {}
        if not _check_match(d, m):
            continue
        priority = rule.get("priority", 0)
        if priority > best_priority:
            best_priority = priority
            matched = rule

    return matched


def _check_match(d: dict, match: dict) -> bool:
    """检查单条规则的匹配条件。"""
    # material_family
    if "material_family" in match:
        mf = d.get("material_family", "unknown")
        allowed = match["material_family"]
        if mf not in allowed:
            return False

    # category
    if "category" in match:
        cat = d.get("category", "general")
        if cat not in match["category"]:
            return False

    # rigidity
    if "rigidity" in match:
        rig = d.get("rigidity", "soft")
        if rig not in match["rigidity"]:
            return False

    # foldability
    if "foldability" in match:
        fold = d.get("foldability", "unknown")
        if fold not in match["foldability"]:
            return False

    # no_strong_hard_evidence
    if match.get("no_strong_hard_evidence", False):
        if _has_strong_hard_evidence(d):
            return False

    # has_strong_hard_evidence
    if match.get("has_strong_hard_evidence", False):
        if not _has_strong_hard_evidence(d):
            return False

    # has_strong_protrusion_evidence
    if match.get("has_strong_protrusion_evidence", False):
        if not _has_strong_protrusion_evidence(d):
            return False

    # product_type_keywords
    if "product_type_keywords" in match:
        pt = _normalize(
            (d.get("product_type") or "") + " " +
            (d.get("product_title") or "") + " " +
            (d.get("notes") or "")
        )
        keywords = match["product_type_keywords"]
        if not any(kw.lower() in pt for kw in keywords):
            return False

    return True


def _apply_rule_action(d: dict, rule: dict) -> dict:
    """应用匹配规则的 action 到 AI JSON。"""
    action = rule.get("action") or {}
    dims = d.get("ai_package_size_cm", [15, 10, 4])
    dims_con = d.get("conservative_package_size_cm", list(dims))

    # ---- set_overall_form ----
    if action.get("set_overall_form"):
        d["overall_form"] = action["set_overall_form"]

    # ---- no_display_thickness_as_shipping ----
    if action.get("no_display_thickness_as_shipping"):
        dims = _fix_thickness_from_display(dims, d, action, is_conservative=False)
        dims_con = _fix_thickness_from_display(dims_con, d, action, is_conservative=True)

    # ---- compress_min_axis_only ----
    elif action.get("compress_min_axis_only"):
        dims = _compress_min_axis(
            dims, action, scale_key="min_axis_scale_normal", is_conservative=False
        )
        dims_con = _compress_min_axis(
            dims_con, action, scale_key="min_axis_scale_conservative", is_conservative=True
        )

    # ---- no_full_folding ----
    elif action.get("no_full_folding"):
        dims = _partial_min_axis_fix(
            dims, action, scale_key="min_axis_scale_normal", is_conservative=False
        )
        dims_con = _partial_min_axis_fix(
            dims_con, action, scale_key="min_axis_scale_conservative", is_conservative=True
        )

    # ---- add_min_axis_protection_only ----
    elif action.get("add_min_axis_protection_only"):
        dims = _add_protection_min_axis(dims, action, is_conservative=False)
        dims_con = _add_protection_min_axis(dims_con, action, is_conservative=True)

    d["ai_package_size_cm"] = dims
    d["conservative_package_size_cm"] = dims_con

    # ---- 包装方法 ----
    if action.get("normal_packaging_method"):
        d["packaging_method"] = action["normal_packaging_method"]

    if action.get("fold_handles"):
        d["folding_action"] = "把手折叠"
    if action.get("store_straps"):
        d["folding_action"] = (d.get("folding_action", "") + "、肩带收纳").strip("、")

    if action.get("no_default_hard_box"):
        d["packaging_type"] = "opp_bag"

    return d


def _fix_thickness_from_display(
    dims: list[float], d: dict, action: dict, is_conservative: bool
) -> list[float]:
    """透明软包：展示厚度不得作运输厚度，用参考比例缩放。"""
    ref_prod = action.get("reference_product_size_cm", [22, 11, 18])
    ref_pkg = (
        action["conservative_reference_package_cm"] if is_conservative
        else action["normal_reference_package_cm"]
    )
    if not ref_pkg or len(ref_pkg) < 3:
        ref_pkg = [10, 10, 3]

    # 按当前体积/参考体积的立方根比例缩放
    current_vol = dims[0] * dims[1] * dims[2]
    ref_vol = ref_prod[0] * ref_prod[1] * ref_prod[2]
    ratio = (current_vol / ref_vol) ** (1 / 3) if ref_vol > 0 else 1.0
    ratio = max(action.get("scale_min", 0.55), min(action.get("scale_max", 2.8), ratio))

    new_dims = [
        max(1, round(ref_pkg[0] * ratio, 1)),
        max(1, round(ref_pkg[1] * ratio, 1)),
        max(1, round(ref_pkg[2] * ratio, 1)),
    ]
    return new_dims


def _compress_min_axis(
    dims: list[float], action: dict, scale_key: str, is_conservative: bool
) -> list[float]:
    """只压缩最小轴。"""
    idx = _min_axis(dims)
    scale = action.get(scale_key, 0.75)
    min_val = action.get("min_axis_cm", 1.5)
    result = list(dims)
    result[idx] = max(min_val, round(dims[idx] * scale, 1))
    return result


def _partial_min_axis_fix(
    dims: list[float], action: dict, scale_key: str, is_conservative: bool
) -> list[float]:
    """结构型PVC：部分调整最小轴。"""
    idx = _min_axis(dims)
    scale = action.get(scale_key, 0.72)
    min_val = action.get("min_axis_cm", 4.0)
    result = list(dims)
    result[idx] = max(min_val, round(dims[idx] * scale, 1))
    return result


def _add_protection_min_axis(
    dims: list[float], action: dict, is_conservative: bool
) -> list[float]:
    """硬质突出件：最小轴承增加保护空间。"""
    idx = _min_axis(dims)
    add = action.get("protection_conservative_cm" if is_conservative else "protection_normal_cm", 2.0)
    result = list(dims)
    result[idx] += add
    return result


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    t = t.replace("\u3000", " ")
    t = re.sub(r"\s+", " ", t)
    return t
