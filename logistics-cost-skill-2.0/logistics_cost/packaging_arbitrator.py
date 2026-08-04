"""包装候选仲裁 — 证据驱动的字段级修复 (不整份重写 AI JSON)。

流程：
  深拷贝输入 → 字段合法化 → exact_calibration_applied? 立即返回
  → 证据门槛 → 结构分类纠正
  → 选择最多1条聚合规则 → 按字段修复正常档 → 按风险生成保守档 → 返回
"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any

# ---------- 硬结构强证据名单 ----------

HARD_STRUCTURE_FACTS = {
    "hard_bottom",
    "rigid_frame",
    "rigid_lining",
    "rigid_body",
    "hard_shell",
    "solid_hard_material",
    "rigid_container",
    "fragile_rigid_body",
}

PROTRUSION_FACTS = {
    "rigid_protrusion",
    "non_detachable_hard_protrusion",
}

# 非包类硬类型 — 不因缺少包类硬底/硬框证据自动降级
_NON_BAG_HARD_FORMS = {"hard_flat", "hard_3d"}

# 确保不因误判降级的非包类硬商品特征
_SPECIALIZED_PROTECTED_TYPES = {
    "hard_shell_case", "acrylic_box", "ceramic_cup", "glass_cup", "glass_vase",
    "hard_plastic_ornament", "rigid_cosmetic_mirror", "hard_container",
}

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


def _is_strong_source(source: str, location: str) -> bool:
    """来源是否为强证据。"""
    s = str(source or "").strip()
    if s in ("user_confirmed", "merchant_text"):
        return True
    if s == "image_visible" and str(location or "").strip():
        return True
    return False


def _has_strong_hard_evidence(ai_data: dict) -> bool:
    """检查是否有硬结构强证据。"""
    evidence_list = ai_data.get("structure_evidence", [])
    if not isinstance(evidence_list, list):
        return False
    for ev in evidence_list:
        fact = str(ev.get("fact", "")).strip()
        if fact in HARD_STRUCTURE_FACTS and _is_strong_source(
            ev.get("source", ""), ev.get("location", "")
        ):
            return True
    return False


def _has_strong_protrusion_evidence(ai_data: dict) -> bool:
    """检查是否有硬质突出件强证据（仅 PROTRUSION_FACTS 事实）。"""
    evidence_list = ai_data.get("structure_evidence", [])
    if not isinstance(evidence_list, list):
        return False
    for ev in evidence_list:
        fact = str(ev.get("fact", "")).strip()
        if fact in PROTRUSION_FACTS and _is_strong_source(
            ev.get("source", ""), ev.get("location", "")
        ):
            return True
    return False


def _is_non_bag_hard_commodity(d: dict) -> bool:
    """检查是否为非包类硬商品（不因缺少包类证据降级）。"""
    cat = d.get("category", "general")
    form = d.get("overall_form", "")
    rig = d.get("rigidity", "")
    # 非包 + hard_flat/hard_3d + hard → 不降级
    if cat != "bag" and form in _NON_BAG_HARD_FORMS and rig == "hard":
        return True
    # 特殊保护类型
    pt = _normalize(d.get("product_type", ""))
    for prot in _SPECIALIZED_PROTECTED_TYPES:
        if prot in pt:
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
        exact_calibration_applied: 是否已命中精确校准（命中时只做字段合法化后立即返回）
        rules_path: 聚合规则文件路径

    Returns:
        修复后的新 dict（深拷贝，不污染输入）
    """
    if ai_data is None:
        return {}

    d = copy.deepcopy(ai_data)

    # ---- 1. 字段合法化（无损） ----
    _sanitize_fields(d)

    # ---- 精确校准命中时, 只做合法化立即返回 ----
    if exact_calibration_applied:
        return d

    # ---- 2. 证据门槛检查 ----
    _evidence_gate(d)

    # ---- 3. 结构分类纠正 ----
    _correct_structure_classification(d)

    # ---- 4. 加载规则并匹配 ----
    rules = _load_rules(rules_path)
    matched_rule = _match_rule(d, rules)
    if matched_rule is None:
        return d

    # ---- 5. 按规则修复 ----
    d = _apply_rule_action(d, matched_rule)

    return d


def _sanitize_fields(d: dict) -> None:
    """无损字段合法化：只补默认值/清理空白/材质标准化，不改变已有有效值。"""
    mf = d.get("material_family")
    if not mf or mf == "unknown":
        # 仅从显式 material 字段推断，不从 notes 中提取（避免误匹配）
        raw = str(d.get("material", "") or "")
        if raw and raw != "unknown":
            d["material_family"] = _normalize_material(raw)

    d.setdefault("material_family", "unknown")
    d.setdefault("structure_evidence", [])

    # 补齐缺失列表/字符串
    for key in ("foldable_parts", "detachable_parts", "modifiers"):
        if key not in d or d[key] is None:
            d[key] = []

    d.setdefault("packaging_method", "OPP袋")
    d.setdefault("folding_action", "不折叠")
    d.setdefault("compression_action", "不压缩")
    d.setdefault("overall_form", "unknown")


def _evidence_gate(d: dict) -> None:
    """硬结构证据门槛：无强证据的硬结构声明降级（非包类硬商品保护）。

    material_family=unknown 时不做证据门槛检查，保持向后兼容未标注材质的旧 AI JSON。
    """
    # 材质未知时跳过证据门槛，保持旧 AI JSON 兼容性
    if d.get("material_family") == "unknown":
        return

    # 非包类硬壳/硬质商品不降级
    if _is_non_bag_hard_commodity(d):
        return

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
    """纠正结构分类：soft_hollow 处理硬结构证据冲突。"""
    if d.get("overall_form") != "soft_hollow":
        return

    has_strong = _has_strong_hard_evidence(d)
    is_bag = d.get("category") == "bag"
    d.setdefault("modifiers", [])
    if "hollow" not in d["modifiers"]:
        d["modifiers"] = list(d["modifiers"]) + ["hollow"]

    if has_strong and is_bag:
        # 有硬底/硬框/硬衬强证据 + 包类 → 升级为半结构化
        d["overall_form"] = "semi_structured_hollow"
        d["rigidity"] = "semi_rigid"
        d["has_rigid_parts"] = True
        # 保留用户设置的 shape_retention_scope，不强制设为 whole
        if d.get("shape_retention_scope", "none") == "none":
            d["shape_retention_scope"] = "body"
        return

    # 无强证据：标准软品行为
    d["rigidity"] = "soft"
    d["has_rigid_parts"] = False
    d["requires_shape_retention"] = False
    d["shape_retention_scope"] = "none"


def _load_rules(path: Path | None) -> list[dict]:
    p = path or _default_rules_path()
    try:
        with open(p, encoding="utf-8") as f:
            rules = json.load(f)
        return [r for r in rules if r.get("enabled", True)]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _match_rule(d: dict, rules: list[dict]) -> dict | None:
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
    if "material_family" in match:
        if d.get("material_family", "unknown") not in match["material_family"]:
            return False
    if "category" in match:
        if d.get("category", "general") not in match["category"]:
            return False
    if "rigidity" in match:
        if d.get("rigidity", "soft") not in match["rigidity"]:
            return False
    if "foldability" in match:
        if d.get("foldability", "unknown") not in match["foldability"]:
            return False
    if match.get("no_strong_hard_evidence") and _has_strong_hard_evidence(d):
        return False
    if match.get("has_strong_hard_evidence") and not _has_strong_hard_evidence(d):
        return False
    if match.get("has_strong_protrusion_evidence") and not _has_strong_protrusion_evidence(d):
        return False
    if "product_type_keywords" in match:
        pt = _normalize(
            str(d.get("product_type", "")) + " " +
            str(d.get("product_title", "")) + " " +
            str(d.get("notes", ""))
        )
        if not any(kw.lower() in pt for kw in match["product_type_keywords"]):
            return False
    return True


def _apply_rule_action(d: dict, rule: dict) -> dict:
    action = rule.get("action") or {}
    dim_scope = d.get("dimension_scope", "unknown")
    dims = list(d.get("ai_package_size_cm", [15, 10, 4]))
    dims_con = list(d.get("conservative_package_size_cm", dims))

    # ---- set_overall_form ----
    if action.get("set_overall_form"):
        d["overall_form"] = action["set_overall_form"]

    # ---- no_display_thickness_as_shipping ----
    if action.get("no_display_thickness_as_shipping"):
        if dim_scope == "shipping_package_size":
            pass  # 三轴全部保持不变
        else:
            dims = _fix_thickness_min_axis_only(dims, action, is_conservative=False)
            dims_con = _fix_thickness_min_axis_only(dims_con, action, is_conservative=True)
            # 保证保守厚度 >= 正常厚度
            if dims_con[_min_axis(dims_con)] < dims[_min_axis(dims)]:
                dims_con[_min_axis(dims_con)] = dims[_min_axis(dims)]

    # ---- compress_min_axis_only ----
    elif action.get("compress_min_axis_only"):
        dims = _compress_min_axis(dims, action, scale_key="min_axis_scale_normal")
        dims_con = _compress_min_axis(dims_con, action, scale_key="min_axis_scale_conservative")

    # ---- no_full_folding ----
    elif action.get("no_full_folding"):
        dims = _partial_min_axis_fix(dims, action, scale_key="min_axis_scale_normal")
        dims_con = _partial_min_axis_fix(dims_con, action, scale_key="min_axis_scale_conservative")

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


def _fix_thickness_min_axis_only(
    dims: list[float], action: dict, is_conservative: bool
) -> list[float]:
    """薄款透明软包：只修最小轴(厚度)，保留两个较大轴。"""
    ref_pkg = (
        action["conservative_reference_package_cm"] if is_conservative
        else action["normal_reference_package_cm"]
    )
    if not ref_pkg or len(ref_pkg) < 3:
        ref_pkg = [10, 10, 3]

    # 找出两个较大轴和参考的两个较大轴
    result = list(dims)
    idx_min = _min_axis(dims)
    large_axes = [dims[i] for i in range(3) if i != idx_min]
    ref_large = [ref_pkg[i] for i in range(3) if i != _min_axis(ref_pkg)]

    # 比例基于两个较大轴面积
    current_area = large_axes[0] * large_axes[1] if len(large_axes) == 2 else dims[0] * dims[1]
    ref_area = ref_large[0] * ref_large[1] if len(ref_large) == 2 else ref_pkg[0] * ref_pkg[1]
    ratio = math.sqrt(current_area / ref_area) if ref_area > 0 else 1.0
    ratio = max(action.get("scale_min", 0.55), min(action.get("scale_max", 2.8), ratio))

    ref_min_axis = ref_pkg[_min_axis(ref_pkg)]
    result[idx_min] = max(1, round(ref_min_axis * ratio, 1))
    return result


def _compress_min_axis(
    dims: list[float], action: dict, scale_key: str
) -> list[float]:
    idx = _min_axis(dims)
    scale = action.get(scale_key, 0.75)
    min_val = action.get("min_axis_cm", 1.5)
    result = list(dims)
    result[idx] = max(min_val, round(dims[idx] * scale, 1))
    return result


def _partial_min_axis_fix(
    dims: list[float], action: dict, scale_key: str
) -> list[float]:
    idx = _min_axis(dims)
    scale = action.get(scale_key, 0.72)
    min_val = action.get("min_axis_cm", 4.0)
    result = list(dims)
    result[idx] = max(min_val, round(dims[idx] * scale, 1))
    return result


def _add_protection_min_axis(
    dims: list[float], action: dict, is_conservative: bool
) -> list[float]:
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
