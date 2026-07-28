"""Phase 5: Replay calibration samples with current code.

Fixes applied (2026-07-28):
- Distinguish total/excluded/candidate/missing/blocked/success counts.
- "Replayable" = actually generated a result, not just having ai_json_path.
- Missing AI JSON files are listed, never counted as success.
- Ultra-light rule comparison reads each sample's own AI JSON for real
  packaged weight, size, volume weight, and soft-goods result — no
  hardcoded 0.06/0.03.
- Median via statistics.median (correct for even-length lists).
"""
import json, os, sys
from pathlib import Path
from math import prod
from statistics import median

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from logistics_cost.ai_schema import validate, to_estimate_inputs, estimate_from_ai_json
from logistics_cost.estimator import estimate
from logistics_cost.weight_rules import UserWeight, apply_weight_correction
from logistics_cost.calculator import calc_freight_costs, calc_volume_weight
from logistics_cost.config import load_config
from logistics_cost.soft_goods_rules import is_soft_goods, check_soft_goods_volume

# Load cleaned data
cleaned_path = BASE / "archive" / "calibration" / "calibration_samples_cleaned_v1.json"
with open(cleaned_path, encoding="utf-8") as f:
    samples = json.load(f)

examples_dir = BASE / "examples"
config = load_config()
divisor = float(config["volume_divisor"])

lines: list[str] = []
def out(s=""):
    lines.append(s)

out("# 第一轮校准回放报告")
out("")
out("> 日期: 2026-07-28")
out("")

# ========================================================
# Section 1: Overview with detailed counts
# ========================================================
out("## 一、概览")
out("")

total = len(samples)
excluded_samples = [s for s in samples if s.get("exclude_from_numeric_calibration")]
excluded_ids = [s["sample_id"] for s in excluded_samples]

# Candidates: not excluded AND has ai_json_path
candidate_samples = [
    s for s in samples
    if not s.get("exclude_from_numeric_calibration") and s.get("ai_json_path")
]

# Check missing AI JSON files
missing_ai: list[tuple[str, str]] = []
for s in candidate_samples:
    ai_path = s.get("ai_json_path", "")
    full_path = BASE / ai_path
    if not full_path.exists():
        missing_ai.append((s["sample_id"], ai_path))

# Blocked / exception samples
blocked_samples: list[tuple[str, str]] = []  # (sample_id, reason)

# ========================================================
# Section 2: Run replay
# ========================================================
results: list[dict] = []

for s in candidate_samples:
    sid = s["sample_id"]
    ai_path = s.get("ai_json_path", "")
    full_path = BASE / ai_path

    if not full_path.exists():
        # Already tracked in missing_ai; skip
        continue

    try:
        with open(full_path, encoding="utf-8") as f:
            ai_data = json.load(f)
    except Exception as e:
        blocked_samples.append((sid, f"JSON读取异常: {e}"))
        continue

    # Run estimation
    try:
        r = estimate_from_ai_json(ai_data)
    except Exception as e:
        blocked_samples.append((sid, f"回放异常: {e}"))
        continue

    if r["status"] != "calculated":
        reasons = r.get("review_reasons", [])
        blocked_samples.append((sid, f"blocked: {reasons}"))
        continue

    est_normal = r["normal"]["head_cost_cny"]
    est_conservative = r["conservative"]["head_cost_cny"]
    rec_provider = r["normal"]["recommended_provider"]

    # Actual head freight
    act = s.get("actual_head_freight_rmb")
    if act is None:
        act = s.get("actual_head_freight_avg_rmb")
    if isinstance(act, list):
        act = sum(act) / len(act)
    if act is None:
        act = 0

    error_normal = abs(est_normal - act)
    error_pct_normal = (error_normal / act * 100) if act > 0 else 0

    fwd = s.get("freight_forwarder", "?")

    # Check if this sample has listed weight data
    has_weight_data = s.get("1688_listed_weight_g") is not None
    listed_w = s.get("1688_listed_weight_g", 0)

    results.append({
        "sid": sid,
        "product_cn": s.get("product_cn", ""),
        "est_normal": est_normal,
        "est_conservative": est_conservative,
        "act": act,
        "error_normal": error_normal,
        "error_pct_normal": error_pct_normal,
        "fwd": fwd,
        "rec_provider": rec_provider,
        "listed_weight_g": listed_w,
        "has_weight_data": has_weight_data,
    })

# Actual success count
success_count = len(results)

out(f"- 总样本数: {total}")
out(f"- 排除数: {len(excluded_samples)} ({', '.join(excluded_ids)})")
out(f"- 具备 ai_json_path 的候选数: {len(candidate_samples)}")
out(f"- AI JSON 文件缺失数: {len(missing_ai)}")
out(f"- blocked/异常数: {len(blocked_samples)}")
out(f"- 实际成功回放数: {success_count}")
out("")

# ========================================================
# Section 2: Excluded samples detail
# ========================================================
out("## 二、排除样本明细")
out("")
for s in excluded_samples:
    sid = s["sample_id"]
    out(f"- **{sid}** ({s.get('product_cn', '?')}): {s.get('evidence_level', '?')} - {s.get('root_cause', '?')}")
    issues = s.get("data_quality_issues", [])
    for i in issues:
        out(f"  - {i}")
out("")

# ========================================================
# Section 3: Missing AI JSON list
# ========================================================
out("## 三、缺失 AI JSON 列表")
out("")
if missing_ai:
    out("| 样本 | 缺失路径 |")
    out("|------|---------|")
    for sid, path in missing_ai:
        out(f"| {sid} | {path} |")
else:
    out("无缺失（所有候选样本的 AI JSON 文件均存在）。")
out("")

# ========================================================
# Section 4: Blocked / exception list
# ========================================================
out("## 四、blocked/异常列表")
out("")
if blocked_samples:
    out("| 样本 | 原因 |")
    out("|------|------|")
    for sid, reason in blocked_samples:
        out(f"| {sid} | {reason} |")
else:
    out("无 blocked/异常样本。")
out("")

# ========================================================
# Section 5: Replay results
# ========================================================
out("## 五、回放结果")
out("")
out(f"> 实际成功回放: {success_count} 条")
out("")

# Sort by error
results.sort(key=lambda x: x["error_normal"])

out("| 样本 | 商品 | 估算(正常档) | 估算(保守档) | 实际 | 误差(元) | 误差(%) | 货代 | 推荐货代 |")
out("|------|------|-------------|-------------|------|---------|---------|------|---------|")
for r in results:
    out(f"| {r['sid']} | {r['product_cn']} | {r['est_normal']:.1f} | {r['est_conservative']:.1f} | {r['act']:.1f} | {r['error_normal']:.1f} | {r['error_pct_normal']:.0f}% | {r['fwd']} | {r['rec_provider']} |")

# ========================================================
# Section 6: Statistics (using statistics.median)
# ========================================================
out("")
out("## 六、误差统计")
out("")

errors = [r["error_normal"] for r in results]
errors_pct = [r["error_pct_normal"] for r in results]

if errors:
    avg_error = sum(errors) / len(errors)
    median_error = median(errors)
    avg_pct = sum(errors_pct) / len(errors_pct)
    median_pct = median(errors_pct)

    out(f"- 样本数: {len(errors)}")
    out(f"- 平均绝对误差: {avg_error:.2f} 元")
    out(f"- 中位绝对误差: {median_error:.2f} 元")
    out(f"- 平均百分比误差: {avg_pct:.0f}%")
    out(f"- 中位百分比误差: {median_pct:.0f}%")
    out("")

    # Error > 5 元 or > 10%
    large = [r for r in results if r["error_normal"] > 5 or r["error_pct_normal"] > 10]
    out(f"- 误差超过5元或10%: {len(large)} 条")
    for r in large:
        out(f"  - {r['sid']}: {r['product_cn']}, est={r['est_normal']:.1f}, act={r['act']:.1f}, error={r['error_normal']:.1f}元 ({r['error_pct_normal']:.0f}%)")
else:
    out("无可用统计数据（成功回放数为 0）。")
out("")

# ========================================================
# Section 7: Ultra-light weight rule impact
# ========================================================
out("## 七、超轻可信重量规则影响")
out("")

# Collect all samples with listed weight <=50g that have AI JSON and are not excluded
ultra_light_samples = [
    s for s in samples
    if s.get("1688_listed_weight_g") is not None
    and s["1688_listed_weight_g"] <= 50
    and not s.get("exclude_from_numeric_calibration")
    and s.get("ai_json_path")
]

out(f"### ≤50g 超轻样本 (共 {len(ultra_light_samples)} 条)")
out("")
out("> 每条样本读取其对应 AI JSON 中的真实包装重量和体积重，不使用统一写死的 0.06/0.03。")
out("")

out("| 样本 | 商品 | 参数表重量(g) | AI包装重(kg) | AI尺寸(cm) | 体积重(kg) | 软品处理 | 旧规则估算(元) | 新规则估算(元) | 实际(元) | 旧偏差 | 新偏差 | 改善 |")
out("|------|------|---------------|-------------|-----------|-----------|---------|---------------|---------------|---------|--------|--------|------|")

improved = 0
worsened = 0
unchanged = 0
ultra_detail: list[dict] = []

for s in ultra_light_samples:
    sid = s["sample_id"]
    cn = s.get("product_cn", "")
    w = s["1688_listed_weight_g"]

    ai_path = BASE / s.get("ai_json_path", "")
    if not ai_path.exists():
        out(f"| {sid} | {cn} | {w} | - | - | - | - | - | - | - | - | - | AI JSON缺失 |")
        continue

    try:
        with open(ai_path, encoding="utf-8") as f:
            ai_data = json.load(f)
    except Exception:
        out(f"| {sid} | {cn} | {w} | - | - | - | - | - | - | - | - | - | JSON读取失败 |")
        continue

    ai = validate(ai_data)
    ai_pkg_weight = ai.ai_package_weight_kg
    ai_size = ai.ai_package_size_cm
    vol_weight = round(prod(ai_size) / divisor, 4) if len(ai_size) == 3 else 0.0

    # Determine soft-goods status
    summary, _, _, _ = to_estimate_inputs(ai)
    soft = is_soft_goods(summary)
    soft_result = check_soft_goods_volume(
        vol_weight, ai_pkg_weight, ai.ai_net_weight_kg,
        is_packaged_dimension=False,
        scenario_label="normal",
    )
    soft_note = "忽略体积重" if soft_result["volume_ignored"] else ("软品取max" if soft else "非软品")

    # chargeable before weight correction: depends on soft result
    if soft_result["volume_ignored"]:
        chargeable_pre = soft_result["chargeable_kg"]
    else:
        chargeable_pre = round(max(ai_pkg_weight, vol_weight), 4)

    # Actual head freight
    act = s.get("actual_head_freight_rmb")
    if act is None:
        act = s.get("actual_head_freight_avg_rmb")
    if isinstance(act, list):
        act = sum(act) / len(act)
    if act is None:
        act = 0

    # Old rule: no_increment_max_g=0 (always add +0.05kg)
    old_r = apply_weight_correction(
        chargeable_kg_ai=chargeable_pre,
        volume_weight_kg=vol_weight,
        user_weight=UserWeight(w, "g", "可信"),
        no_increment_max_g=0,
    )
    old_cw = old_r["chargeable_kg"]
    old_f = calc_freight_costs(old_cw)
    old_rec = old_f["recommended_provider"]
    old_cost = old_f["provider_costs"][old_rec]["head_freight_rmb"]

    # New rule: no_increment_max_g=50 (current config default)
    new_r = apply_weight_correction(
        chargeable_kg_ai=chargeable_pre,
        volume_weight_kg=vol_weight,
        user_weight=UserWeight(w, "g", "可信"),
        no_increment_max_g=50,
    )
    new_cw = new_r["chargeable_kg"]
    new_f = calc_freight_costs(new_cw)
    new_rec = new_f["recommended_provider"]
    new_cost = new_f["provider_costs"][new_rec]["head_freight_rmb"]

    old_dev = abs(old_cost - act)
    new_dev = abs(new_cost - act)
    imp = old_dev - new_dev

    if imp > 0.1:
        improved += 1
    elif imp < -0.1:
        worsened += 1
    else:
        unchanged += 1

    sign = "+" if imp >= 0 else ""
    out(f"| {sid} | {cn} | {w} | {ai_pkg_weight} | {ai_size[0]}x{ai_size[1]}x{ai_size[2]} | {vol_weight} | {soft_note} | {old_cost:.1f} | {new_cost:.1f} | {act:.1f} | {old_dev:.1f}元 | {new_dev:.1f}元 | {sign}{imp:.1f}元 |")

    ultra_detail.append({
        "sid": sid,
        "ai_pkg_weight": ai_pkg_weight,
        "vol_weight": vol_weight,
        "old_cost": old_cost,
        "new_cost": new_cost,
        "act": act,
        "soft_note": soft_note,
    })

out("")
out(f"- 改善: {improved} 条")
out(f"- 变差: {worsened} 条")
out(f"- 不变: {unchanged} 条")
out("")

# Note about what this comparison is
out("**说明**: 以上对比为「基于相同AI场景的重量规则对比」，即同一条 AI JSON 产生的真实包装重量和体积重，仅把 `no_increment_max_g` 从 0（旧规则：始终加增重）切换为 50（新规则：≤50g不加增重）。不是端到端回放。")
out("")

# List all weight-data samples
weighted = [r for r in results if r["has_weight_data"]]
out(f"### 全部含重量数据样本 ({len(weighted)} 条)")
out("")
out("| 样本 | 重量(g) | 估算 | 实际 | 误差 | 是否≤50g |")
out("|------|--------|------|------|------|---------|")
for r in weighted:
    w = r["listed_weight_g"]
    ultra = "是" if w <= 50 else "否"
    out(f"| {r['sid']} | {w} | {r['est_normal']:.1f} | {r['act']:.1f} | {r['error_normal']:.1f}元 ({r['error_pct_normal']:.0f}%) | {ultra} |")

# ========================================================
# Section 8: Non-replayable summary
# ========================================================
out("")
out("## 八、不可回放样本汇总")
out("")
for sid in excluded_ids:
    s = next(x for x in samples if x["sample_id"] == sid)
    issues = s.get("data_quality_issues", [])
    issue_text = "; ".join(issues) if issues else s.get("root_cause", "?")
    out(f"- **{sid}** ({s.get('product_cn', '?')}): {issue_text}")
out("")

# ========================================================
# Section 9: Known limitations
# ========================================================
out("## 九、已知限制")
out("")
freight_inferred_count = sum(1 for s in samples if s.get("evidence_level") == "freight_inferred" and not s.get("exclude_from_numeric_calibration"))
out(f"- {success_count}条可回放样本中 {freight_inferred_count}条 为 freight_inferred 级别")
out(f"- 超轻规则改善 {improved} 条, 变差 {worsened} 条, 不变 {unchanged} 条")
out(f"- 回放依赖 AI JSON 文件, AI 估算质量直接影响误差")
out(f"- 超轻规则对比为「基于相同AI场景的重量规则对比」, 非端到端回放")
out("")

# Write report
report_path = BASE / "archive" / "calibration" / "calibration_round_01_replay_report.md"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
    f.write("\n")

print(f"Report written to: {report_path}")
print(f"Total samples: {total}")
print(f"Excluded: {len(excluded_samples)}")
print(f"Candidates (with ai_json_path): {len(candidate_samples)}")
print(f"Missing AI JSON: {len(missing_ai)}")
print(f"Blocked/exception: {len(blocked_samples)}")
print(f"Successful replay: {success_count}")
if errors:
    print(f"Avg error: {sum(errors)/len(errors):.2f} yuan")
    print(f"Median error: {median(errors):.2f} yuan")
    print(f"Avg error %: {sum(errors_pct)/len(errors_pct):.0f}%")
    print(f"Median error %: {median(errors_pct):.0f}%")
print(f"Ultra-light improved: {improved}, worsened: {worsened}, unchanged: {unchanged}")
