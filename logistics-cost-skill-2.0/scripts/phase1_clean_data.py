"""Phase 1: Data validation and cleaning for 51 calibration samples."""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- Load original ----
src = os.path.join(BASE, "archive", "calibration", "calibration_samples.json")
with open(src, "r", encoding="utf-8") as f:
    raw = json.load(f)

print(f"Total records: {len(raw)}")
issues_log = []

# ========================================================
# 1. Known per-instruction fixes
# ========================================================

# CAL-017: error_direction fix (estimated 6.05 < actual 12.35 -> underestimate)
for s in raw:
    if s["sample_id"] == "CAL-017":
        old_dir = s.get("error_direction", "")
        s["error_direction"] = "underestimate"
        s["data_quality_issues"] = ["error_direction更正: overestimate->underestimate (估6.05<实际12.35)"]
        issues_log.append(f"CAL-017: error_direction {old_dir} -> underestimate")
        break

# CAL-009: conflict
for s in raw:
    if s["sample_id"] == "CAL-009":
        s["data_quality_status"] = "conflict"
        s["data_quality_issues"] = s.get("data_quality_issues", []) + [
            "actual_head_freight(18.9)与actual_chargeable_weight(0.189)与notes中的0.236kg冲突"
        ]
        s["exclude_from_numeric_calibration"] = True
        s["evidence_level"] = "manual_review_required"
        issues_log.append("CAL-009: 标记为数据冲突, 排除出数值校准")
        break

# CAL-026: needs_review
for s in raw:
    if s["sample_id"] == "CAL-026":
        s["data_quality_status"] = "needs_review"
        s["data_quality_issues"] = s.get("data_quality_issues", []) + [
            "根因名称EXACT_MATCH_VIA_CONSERVATIVE与说明中正常档/保守档结论不一致"
        ]
        s["exclude_from_numeric_calibration"] = True
        s["evidence_level"] = "manual_review_required"
        issues_log.append("CAL-026: 标记为需复核, 排除出数值校准")
        break

# CAL-029: forwarder_uncertain
for s in raw:
    if s["sample_id"] == "CAL-029":
        s["data_quality_status"] = "needs_review"
        s["data_quality_issues"] = s.get("data_quality_issues", []) + ["货代不确定(深圳或义乌)"]
        s["exclude_from_numeric_calibration"] = True
        s["evidence_level"] = "forwarder_uncertain"
        issues_log.append("CAL-029: 标记为货代不确定, 排除出数值校准")
        break

# ========================================================
# 2. Fix 1638 -> 1688 spelling
# ========================================================
for s in raw:
    sid = s["sample_id"]
    for old_key in ["1638_display_size_cm", "1638_display_volume_cm3", "1638_listed_weight_g"]:
        if old_key in s:
            new_key = old_key.replace("1638", "1688")
            s[new_key] = s.pop(old_key)
            issues_log.append(f"{sid}: {old_key} -> {new_key}")

# ========================================================
# 3. Auto validation
# ========================================================

# 3a. error_direction consistency
for s in raw:
    sid = s["sample_id"]
    est = s.get("estimated_head_freight_rmb")
    act = s.get("actual_head_freight_rmb")
    ed = s.get("error_direction", "")
    if est is None or act is None or ed is None:
        continue
    if isinstance(act, list):
        continue  # range values, skip strict check
    if est < act and ed == "overestimate":
        msg = f"{sid}: error_direction=overestimate but estimated({est})<actual({act}), should be underestimate"
        s.setdefault("data_quality_issues", []).append(msg)
        issues_log.append(msg)
    elif est > act and ed == "underestimate":
        msg = f"{sid}: error_direction=underestimate but estimated({est})>actual({act}), should be overestimate"
        s.setdefault("data_quality_issues", []).append(msg)
        issues_log.append(msg)

# 3b. Freight rate consistency check
for s in raw:
    sid = s["sample_id"]
    act_freight = s.get("actual_head_freight_rmb")
    if act_freight is None or isinstance(act_freight, list):
        continue
    act_cw = s.get("actual_chargeable_weight_kg")
    fwd = s.get("freight_forwarder", "")
    if act_cw is None or isinstance(act_cw, list):
        continue
    if "义乌" in str(fwd):
        rate = 100
    elif "深圳" in str(fwd):
        rate = 80
    else:
        continue
    expected = round(act_cw * rate, 2)
    diff = abs(expected - act_freight)
    if diff > 0.5:
        msg = f"{sid}: chargeable={act_cw}kg*{rate}={expected} vs actual={act_freight}, diff={diff:.1f}"
        s.setdefault("data_quality_issues", []).append(msg)
        issues_log.append(msg)

# 3c. Unit sanity check
for s in raw:
    sid = s["sample_id"]
    for field, val in s.items():
        if isinstance(val, (int, float)) and field.endswith("_g"):
            if val > 50000:
                msg = f"{sid}: {field}={val}g suspiciously large"
                s.setdefault("data_quality_issues", []).append(msg)
                issues_log.append(msg)

# ========================================================
# 4. Add standard fields with defaults
# ========================================================
for s in raw:
    s.setdefault("data_quality_status", "ok")
    if "data_quality_issues" not in s:
        s["data_quality_issues"] = []
    elif isinstance(s["data_quality_issues"], str):
        s["data_quality_issues"] = [s["data_quality_issues"]]
    s.setdefault("exclude_from_numeric_calibration", False)

    if "evidence_level" not in s:
        has_size = s.get("actual_package_size_cm") is not None
        has_weight = s.get("actual_weight_with_pkg_g") is not None
        has_cw = s.get("actual_chargeable_weight_kg") is not None
        has_range = any(isinstance(s.get(k), list) for k in [
            "actual_head_freight_rmb", "actual_chargeable_weight_kg"
        ])
        if has_size and has_weight and has_cw:
            s["evidence_level"] = "actual_package_measured"
        elif has_size or has_weight:
            s["evidence_level"] = "actual_measured"
        elif has_cw and not has_range:
            s["evidence_level"] = "freight_inferred"
        elif has_range:
            s["evidence_level"] = "range_inferred"
        else:
            s["evidence_level"] = "freight_inferred"

# ========================================================
# 5. Summary
# ========================================================
excluded_ids = [s["sample_id"] for s in raw if s.get("exclude_from_numeric_calibration")]
issue_ids = [s["sample_id"] for s in raw if s.get("data_quality_issues")]
evidence_levels = {}
for s in raw:
    el = s.get("evidence_level", "unknown")
    evidence_levels[el] = evidence_levels.get(el, 0) + 1

print(f"\nExcluded from calibration ({len(excluded_ids)}): {excluded_ids}")
print(f"Records with issues ({len(issue_ids)}): {issue_ids}")
print(f"\nEvidence levels:")
for k, v in sorted(evidence_levels.items()):
    print(f"  {k}: {v}")
print(f"\nValidation issues ({len(issues_log)}):")
for i in issues_log:
    print(f"  {i}")

# ========================================================
# 6. Write cleaned file
# ========================================================
dst = os.path.join(BASE, "archive", "calibration", "calibration_samples_cleaned_v1.json")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(raw, f, ensure_ascii=False, indent=2)

print(f"\nCleaned file: {dst}")
print(f"Records: {len(raw)}, Excluded: {len(excluded_ids)}, Issues logged: {len(issues_log)}")
