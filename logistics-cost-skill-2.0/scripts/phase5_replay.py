"""Phase 5: Replay calibration samples with current code."""
import json, os, sys
from pathlib import Path
from math import prod

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from logistics_cost.ai_schema import validate, estimate_from_ai_json
from logistics_cost.estimator import estimate
from logistics_cost.weight_rules import UserWeight, apply_weight_correction
from logistics_cost.calculator import calc_freight_costs

# Load cleaned data
cleaned_path = BASE / "archive" / "calibration" / "calibration_samples_cleaned_v1.json"
with open(cleaned_path, encoding="utf-8") as f:
    samples = json.load(f)

examples_dir = BASE / "examples"

print("# 第一轮校准回放报告\n")
print("> 日期: 2026-07-28\n")
print("## 一、概览\n")

total = len(samples)
excluded = [s["sample_id"] for s in samples if s.get("exclude_from_numeric_calibration")]
replayable = [s for s in samples if not s.get("exclude_from_numeric_calibration") and s.get("ai_json_path")]
print(f"- 总样本: {total}")
print(f"- 排除: {len(excluded)} ({', '.join(excluded)})")
print(f"- 可回放: {len(replayable)}")

print(f"\n## 二、排除样本明细\n")
for sid in excluded:
    s = next(x for x in samples if x["sample_id"] == sid)
    print(f"- **{sid}** ({s['product_cn']}): {s.get('evidence_level', '?')} - {s.get('root_cause', '?')}")
    issues = s.get("data_quality_issues", [])
    for i in issues:
        print(f"  - {i}")

print(f"\n## 三、回放结果\n")

results = []
for s in replayable:
    sid = s["sample_id"]
    ai_path = s.get("ai_json_path", "")
    try:
        with open(examples_dir / Path(ai_path).name, encoding="utf-8") as f:
            ai_data = json.load(f)
    except FileNotFoundError:
        print(f"- **{sid}**: AI JSON 文件缺失 ({ai_path})")
        continue

    # Run estimation
    try:
        r = estimate_from_ai_json(ai_data)
    except Exception as e:
        print(f"- **{sid}**: 回放异常 - {e}")
        continue

    if r["status"] != "calculated":
        print(f"- **{sid}**: blocked - {r.get('review_reasons', [])}")
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

    # Also record forwarder info
    fwd = s.get("freight_forwarder", "?")
    
    # Check if this sample benefits from ultra-light rule
    has_weight_data = s.get("1688_listed_weight_g") is not None
    listed_w = s.get("1688_listed_weight_g", 0)

    results.append({
        "sid": sid,
        "product_cn": s.get("product_cn", ""),
        "est_normal": est_normal,
        "act": act,
        "error_normal": error_normal,
        "error_pct_normal": error_pct_normal,
        "fwd": fwd,
        "rec_provider": rec_provider,
        "listed_weight_g": listed_w,
        "has_weight_data": has_weight_data,
    })

# Sort by error
results.sort(key=lambda x: x["error_normal"])

# Print summary
print("| 样本 | 商品 | 估算(正常档) | 实际 | 误差(元) | 误差(%) | 货代 | 推荐货代 |")
print("|------|------|-------------|------|---------|---------|------|---------|")
for r in results:
    print(f"| {r['sid']} | {r['product_cn']} | {r['est_normal']:.1f} | {r['act']:.1f} | {r['error_normal']:.1f} | {r['error_pct_normal']:.0f}% | {r['fwd']} | {r['rec_provider']} |")

# Statistics
errors = [r["error_normal"] for r in results]
errors_pct = [r["error_pct_normal"] for r in results]
avg_error = sum(errors) / len(errors)
median_error = sorted(errors)[len(errors)//2]
avg_pct = sum(errors_pct) / len(errors_pct)
median_pct = sorted(errors_pct)[len(errors_pct)//2]

print(f"\n## 四、误差统计\n")
print(f"- 平均绝对误差: {avg_error:.2f} 元")
print(f"- 中位绝对误差: {median_error:.2f} 元")
print(f"- 平均百分比误差: {avg_pct:.0f}%")
print(f"- 中位百分比误差: {median_pct:.0f}%")

# Error > 5 元 or > 10%
large = [r for r in results if r["error_normal"] > 5 or r["error_pct_normal"] > 10]
print(f"- 误差超过5元或10%: {len(large)} 条")
for r in large:
    print(f"  - {r['sid']}: {r['product_cn']}, est={r['est_normal']:.1f}, act={r['act']:.1f}, error={r['error_normal']:.1f}元 ({r['error_pct_normal']:.0f}%)")

# ========================================================
# Ultra-light weight rule impact analysis
# ========================================================
print(f"\n## 五、超轻可信重量规则影响\n")

# Collect all samples with listed weight ≤50g
ultra_light_samples = [s for s in samples if s.get("1688_listed_weight_g") is not None and s["1688_listed_weight_g"] <= 50]
print(f"### ≤50g 超轻样本 (共 {len(ultra_light_samples)} 条)\n")

print("| 样本 | 商品 | 参数表重量(g) | 旧规则估算(元) | 新规则估算(元) | 实际(元) | 旧偏差 | 新偏差 | 改善 |")
print("|------|------|---------------|---------------|---------------|---------|--------|--------|------|")

improved = 0
worsened = 0
unchanged = 0

for s in ultra_light_samples:
    sid = s["sample_id"]
    cn = s.get("product_cn", "")
    w = s["1688_listed_weight_g"]
    
    # Get act freight
    act = s.get("actual_head_freight_rmb")
    if act is None:
        act = s.get("actual_head_freight_avg_rmb")
    if isinstance(act, list):
        act = sum(act) / len(act)
    if act is None:
        act = 0
    
    # Simulate old rule (+0.05kg always)
    old_r = apply_weight_correction(
        chargeable_kg_ai=0.06, volume_weight_kg=0.03,
        user_weight=UserWeight(w, "g", "可信"),
        no_increment_max_g=0,
    )
    old_cw = old_r["chargeable_kg"]
    old_f = calc_freight_costs(old_cw)
    old_rec = old_f["recommended_provider"]
    old_cost = old_f["provider_costs"][old_rec]["head_freight_rmb"]
    
    # New rule (≤50g no increment)
    new_r = apply_weight_correction(
        chargeable_kg_ai=0.06, volume_weight_kg=0.03,
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
    print(f"| {sid} | {cn} | {w} | {old_cost:.1f} | {new_cost:.1f} | {act:.1f} | {old_dev:.1f}元 | {new_dev:.1f}元 | {sign}{imp:.1f}元 |")

print(f"\n- 改善: {improved} 条")
print(f"- 变差: {worsened} 条")
print(f"- 不变: {unchanged} 条")
print(f"- 其中实际端到端回放: CAL-021（有AI JSON + 参数表49g + 调用了weight_rules）")
# All other ≤50g samples are theoretical simulations - their AI JSONs don't have user_weight
theory_ids = [s["sample_id"] for s in ultra_light_samples if s["sample_id"] != "CAL-021"]
print(f"- 基于可信重量的理论模拟: {', '.join(theory_ids)}（假设用户提供--weight-value时的新旧规则对比）")
print()

# Note about actual replay with weight-value
print("**说明**: 以上对比均为纯头程费（不含固定服务费）。头程费 = 计费重量 × 费率单价，不与含固定服务费的总费用混淆。")

# List all weight-data samples
weighted = [r for r in results if r["has_weight_data"]]
print(f"### 全部含重量数据样本 ({len(weighted)} 条)\n")
print("| 样本 | 重量(g) | 估算 | 实际 | 误差 | 是否≤50g |")
print("|------|--------|------|------|------|---------|")
for r in weighted:
    w = r["listed_weight_g"]
    ultra = "是" if w <= 50 else "否"
    print(f"| {r['sid']} | {w} | {r['est_normal']:.1f} | {r['act']:.1f} | {r['error_normal']:.1f}元 ({r['error_pct_normal']:.0f}%) | {ultra} |")

print(f"\n## 六、不可回放样本汇总\n")
print(f"- CAL-009: 数据冲突 (计费重/头程/说明不一致)")
print(f"- CAL-026: 需人工复核 (正常/保守结论不一致)")
print(f"- CAL-029: 货代来源不确定 (深圳或义乌)")
print(f"\n## 七、已知限制\n")
freight_inferred_count = sum(1 for s in samples if s.get("evidence_level") == "freight_inferred")
print(f"- {len(results)}条可回放样本中 {freight_inferred_count}条 为 freight_inferred 级别")
print(f"- 超轻规则改善 {improved} 条, 变差 {worsened} 条, 不变 {unchanged} 条")
print(f"- 回放依赖 AI JSON 文件, AI 估算质量直接影响误差")
