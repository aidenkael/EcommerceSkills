#!/usr/bin/env python3
"""合并清理两轮校准数据, 生成 cleaned JSON 和诊断报告。"""
import json, os, re
from collections import defaultdict, Counter
from copy import deepcopy

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 加载 ──
with open(os.path.join(BASE, 'archive/calibration/calibration_samples.json'), 'r') as f:
    r01 = json.load(f)
with open(os.path.join(BASE, 'archive/calibration/calibration_samples_round_02.json'), 'r') as f:
    r02 = json.load(f)

# Normalize round 01: derive 'error_direction' from head_freight_error_pct
def normalize_round01(entry):
    d_id = entry['sample_id']
    pct = entry.get('head_freight_error_pct')
    if pct is None:
        # Try alternative field names from round 01
        alt_names = ['trusted_error_pct', 'no_trust_error_pct', 'head_freight_error_no_trust_pct']
        for alt in alt_names:
            if alt in entry and entry[alt] is not None:
                pct = entry[alt]
                break
    if pct is None or not isinstance(pct, (int, float)):
        pct = 0
    if pct == 0:
        entry['error_direction'] = 'match'
    elif pct > 0:
        entry['error_direction'] = 'overestimate'
    else:
        entry['error_direction'] = 'underestimate'
    entry['head_freight_error_pct'] = abs(pct) if pct is not None else 0
    entry['evidence_level'] = 'freight_inferred'
    entry['estimate_stage'] = 'first_pass'
    entry['usable_for_accuracy_evaluation'] = True
    entry['usable_for_rule_learning'] = True
    entry['exclusion_reason'] = ''
    entry['independence_group'] = d_id
    return entry

r01 = [normalize_round01(d) for d in r01]
all_cal = r01 + r02

# ════════════════════════════════════════════════════════
# 分类逻辑
# ════════════════════════════════════════════════════════

# --- estimate_stage ---
CORRECTED_IDS = {
    'CAL-054': '第一轮按10×3×3/30-40g偏低43%, 修正12×5×4/80g后命中',
    'CAL-057': '第一轮OPP袋12×10×4cm低估57%, 修正挂卡纸盒16×13×5cm后命中',
    'CAL-062': '第一轮估60g偏低40%, 按商家规格100g修正后命中',
}
EXCLUDED_IDS = {
    'CAL-070': '实际尺寸已忘记, 按中段18inch估, 无法用于准确率',
}

def classify_estimate_stage(entry):
    sid = entry['sample_id']
    if sid in CORRECTED_IDS:
        return 'corrected_after_actual'
    if sid in EXCLUDED_IDS:
        return 'unknown'
    # Check notes/root_cause for correction keywords
    text = str(entry.get('notes','')) + str(entry.get('root_cause_detail',''))
    if any(kw in text for kw in ['修正后命中', '第二轮按', '第一轮估']):
        return 'corrected_after_actual'
    return 'first_pass'

# --- evidence_level ---
def classify_evidence(entry):
    text = str(entry.get('notes','')) + str(entry.get('root_cause_detail',''))
    if '实测' in text or 'actual_measured' in text:
        return 'actual_measured'
    if '商家规格' in text or 'merchant_spec' in text or '1688' in text:
        return 'merchant_spec'
    return 'freight_inferred'

# --- independence_group ---
GROUP_MAP = {
    'CAL-071': 'hair_claw_3ship',
    'CAL-072': 'hair_claw_3ship',
    'CAL-073': 'hair_claw_3ship',
}

def classify_independence(entry):
    sid = entry['sample_id']
    if sid in GROUP_MAP:
        return GROUP_MAP[sid]
    return sid  # unique

# --- product_category (for grouping analysis) ---
def classify_product_category(entry):
    ptype = str(entry.get('product_type', '')).lower()
    cn = str(entry.get('product_cn', '')).lower()
    text = str(entry.get('notes','')) + str(entry.get('root_cause_detail',''))

    if any(kw in ptype + cn for kw in ['bag', 'handbag', 'backpack', 'clutch', 'pouch', 'cosmetic_bag', '化妆包', '包']):
        return 'bag'
    if any(kw in text for kw in ['薄款', '薄软', 'thin_fabric', '薄款面料', 'thin_knit', '薄面料']):
        return 'thin_soft'
    if any(kw in text for kw in ['软品', 'soft_volume', 'soft_goods']):
        return 'soft_goods'
    if any(kw in text for kw in ['挂卡', '零售包装', 'branded', '品牌', '纸盒']):
        return 'retail_packaging'
    if any(kw in text for kw in ['硬质部件', '突出', '扳手', '喷头', 'protrusion', '夹']):
        return 'rigid_protrusion'
    if any(kw in text for kw in ['发', 'hair', '假发', '发束', '发帘']):
        return 'hair_accessory'
    if 'match' == entry.get('error_direction'):
        return 'matched'
    return 'general'

# ════════════════════════════════════════════════════════
# 主处理
# ════════════════════════════════════════════════════════

cleaned = []
stats = {
    'total': 0,
    'first_pass': 0,
    'corrected_after_actual': 0,
    'unknown_stage': 0,
    'excluded': 0,
    'unique_groups': set(),
    'freight_inferred': 0,
    'merchant_spec': 0,
}

for entry in all_cal:
    d = deepcopy(entry)

    # Add classification fields
    d['estimate_stage'] = classify_estimate_stage(entry)
    d['evidence_level'] = classify_evidence(entry)
    d['independence_group'] = classify_independence(entry)
    d['product_category'] = classify_product_category(entry)

    # Usability flags
    if entry['sample_id'] == 'CAL-070':
        d['usable_for_accuracy_evaluation'] = False
        d['usable_for_rule_learning'] = True  # keep as case study
        d['exclusion_reason'] = '实际尺寸已忘记, 按中段尺寸估, 无法确定误差来源'
    elif d['estimate_stage'] == 'corrected_after_actual':
        d['usable_for_accuracy_evaluation'] = False  # not for first-pass accuracy
        d['usable_for_rule_learning'] = True
        d['exclusion_reason'] = f'修正后命中: {CORRECTED_IDS.get(entry["sample_id"], "")}'
    else:
        d['usable_for_accuracy_evaluation'] = True
        d['usable_for_rule_learning'] = True
        d['exclusion_reason'] = ''

    # Count
    stats['total'] += 1
    if d['estimate_stage'] == 'first_pass': stats['first_pass'] += 1
    elif d['estimate_stage'] == 'corrected_after_actual': stats['corrected_after_actual'] += 1
    else: stats['unknown_stage'] += 1

    if not d['usable_for_accuracy_evaluation']: stats['excluded'] += 1
    stats['unique_groups'].add(d['independence_group'])
    if d['evidence_level'] == 'freight_inferred': stats['freight_inferred'] += 1
    elif d['evidence_level'] == 'merchant_spec': stats['merchant_spec'] += 1

    cleaned.append(d)

# Save cleaned JSON
output_path = os.path.join(BASE, 'archive/calibration/calibration_all_cleaned_v2.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(cleaned, f, ensure_ascii=False, indent=2)

# ════════════════════════════════════════════════════════
# 诊断统计
# ════════════════════════════════════════════════════════

# First-pass accuracy (exclude corrected and excluded)
first_pass = [d for d in cleaned if d['estimate_stage'] == 'first_pass' and d['usable_for_accuracy_evaluation']]
corrected_entries = [d for d in cleaned if d['estimate_stage'] == 'corrected_after_actual']

# Per-direction stats
fp_dirs = Counter(d['error_direction'] for d in first_pass)
fp_matches = fp_dirs.get('match', 0)
fp_over = fp_dirs.get('overestimate', 0)
fp_under = fp_dirs.get('underestimate', 0)

# Per-category stats
cat_stats = defaultdict(lambda: {'over': 0, 'under': 0, 'match': 0, 'count': 0})
for d in first_pass:
    cat = d['product_category']
    cat_stats[cat]['count'] += 1
    d_op = d['error_direction']
    if d_op == 'match': cat_stats[cat]['match'] += 1
    elif d_op == 'overestimate': cat_stats[cat]['over'] += 1
    elif d_op == 'underestimate': cat_stats[cat]['under'] += 1

# Median/mean error (first_pass only)
import statistics
fp_errors = [d['head_freight_error_pct'] for d in first_pass]
fp_mean = sum(fp_errors) / len(fp_errors) if fp_errors else 0
fp_median = statistics.median(fp_errors) if fp_errors else 0

# Corrected stats
corr_stats = Counter(d['error_direction'] for d in corrected_entries)

# ════════════════════════════════════════════════════════
# 候选规则 (需 ≥2 独立商品组)
# ════════════════════════════════════════════════════════

def group_entries(category_keyword):
    """Return entries matching category that are first_pass and have same error direction."""
    result = []
    for d in first_pass:
        if category_keyword in str(d.get('notes','')) + str(d.get('root_cause_detail','')) + str(d.get('root_cause','')):
            result.append(d)
    return result

# Rule 1: Thin soft goods (薄款软品)
thin_soft = [d for d in cleaned if d.get('product_category') == 'thin_soft' and d['usable_for_rule_learning']]
# Also include CAL-059 (same root cause as CAL-055)
thin_soft_all = []
for d in cleaned:
    if d.get('root_cause', '') == 'SOFT_VOLUME_OVERESTIMATED_THIN_FABRIC' or d.get('root_cause', '') == 'SOFT_VOLUME_OVERESTIMATED':
        thin_soft_all.append(d)
    pcat = d.get('product_category', '')
    if pcat == 'thin_soft':
        thin_soft_all.append(d)

# Deduplicate
seen = set()
thin_uniq = []
for d in thin_soft_all:
    grp = d.get('independence_group', d['sample_id'])
    if grp not in seen:
        seen.add(grp)
        thin_uniq.append(d)

# Rule 2: Bag compression (包袋压缩) - CAL-065/068/076
bag_compression = [d for d in cleaned if d.get('root_cause') in (
    'BAG_COMPRESSIBLE_THICKNESS_NOT_ACCOUNTED',
    'PVC_THIN_BAG_FULLY_FOLDED',
    'FABRIC_BAG_EXTREME_COMPRESSION'
) and d['usable_for_rule_learning']]

# Rule 3: Rigid protrusion (硬质突出) - CAL-054/056
rigid_prot = [d for d in cleaned if d.get('root_cause', '') in (
    'PACKAGE_VOLUME_UNDERESTIMATED_PROTRUSION',
    'DEAD_ON_AFTER_ATTACHMENT_CORRECTION'
) and d['usable_for_rule_learning']]

candidate_rules = []
if len(set(d.get('independence_group', d['sample_id']) for d in thin_uniq)) >= 2:
    candidate_rules.append({
        'rule': 'thin_soft_fabric_volume_correction',
        'description': '薄款针织/弹性面料(袜/袖套): 折叠后体积重偏高40-50%, 建议包装厚度≤3cm或体积重阈值降至×2',
        'supporting_entries': [d['sample_id'] for d in thin_uniq],
        'independent_groups': len(set(d.get('independence_group', d['sample_id']) for d in thin_uniq)),
        'suggested_action': 'ai_package_size_cm厚度从4cm→3cm, 或提高soft_volume_ignore阈值'
    })

if len(set(d.get('independence_group', d['sample_id']) for d in bag_compression)) >= 3:
    candidate_rules.append({
        'rule': 'bag_three_tier_compression',
        'description': '包袋品类三档压缩规则: 皮包×0.65 / PVC薄款全折叠3cm模板 / 布包×0.4',
        'supporting_entries': [d['sample_id'] for d in bag_compression],
        'independent_groups': len(set(d.get('independence_group', d['sample_id']) for d in bag_compression)),
        'suggested_action': '在AI JSON生成时按材质分类选择压缩因子'
    })

if len(set(d.get('independence_group', d['sample_id']) for d in rigid_prot)) >= 2:
    candidate_rules.append({
        'rule': 'rigid_protrusion_packaging',
        'description': '手柄/夹扣类硬质突出商品: 商家规格仅本体尺寸, 包装需加+2cm厚度和额外配件重量',
        'supporting_entries': [d['sample_id'] for d in rigid_prot],
        'independent_groups': len(set(d.get('independence_group', d['sample_id']) for d in rigid_prot)),
        'suggested_action': 'has_rigid_parts=true时ai_package_size_cm厚度≥本体+2cm'
    })

# ════════════════════════════════════════════════════════
# 生成诊断报告
# ════════════════════════════════════════════════════════

report_lines = []
def w(line=''):
    report_lines.append(line)

w('# CALIBRATION FINAL DIAGNOSTIC')
w()
w(f'## 数据概览')
w(f'- 总记录数: {stats["total"]} (CAL-001 ~ CAL-077)')
w(f'- 首次估算样本: {stats["first_pass"]}')
w(f'- 修正后样本: {stats["corrected_after_actual"]}')
w(f'- 排除样本: {stats["excluded"]}')
w(f'- 独立商品组: {len(stats["unique_groups"])}')
w(f'- 证据类型: freight_inferred={stats["freight_inferred"]}, merchant_spec={stats["merchant_spec"]}')
w()

w('## 首次估算准确率')
w(f'- 命中(match): {fp_matches} ({fp_matches/len(first_pass)*100:.1f}%)')
w(f'- 高估(overestimate): {fp_over} ({fp_over/len(first_pass)*100:.1f}%)')
w(f'- 低估(underestimate): {fp_under} ({fp_under/len(first_pass)*100:.1f}%)')
w(f'- 平均误差: {fp_mean:.1f}%')
w(f'- 中位误差: {fp_median:.1f}%')
w()

w('## 修正后结果')
w(f'- 修正样本数: {len(corrected_entries)}')
for d in corrected_entries:
    w(f'  - {d["sample_id"]}: {d.get("error_direction")} {d.get("head_freight_error_pct",0)}% ({CORRECTED_IDS.get(d["sample_id"],"修正")})')
w()

w('## 按商品品类分组')
for cat, s in sorted(cat_stats.items()):
    w(f'- **{cat}**: {s["count"]}条, 命中{s["match"]}, 高估{s["over"]}, 低估{s["under"]}')
w()

w('## 排除样本')
for d in cleaned:
    if not d['usable_for_accuracy_evaluation']:
        w(f'- {d["sample_id"]}: {d["exclusion_reason"]}')
w()

w('## 独立商品组 (合并3次重复发货)')
w(f'- 唯一组数: {len(stats["unique_groups"])}')
w(f'- CAL-071/072/073 -> hair_claw_3ship (1组)')
w()

w('## 候选修正规则 (≥2独立组支持)')
if candidate_rules:
    for i, r in enumerate(candidate_rules, 1):
        w(f'### 候选 {i}: {r["rule"]}')
        w(f'- 描述: {r["description"]}')
        w(f'- 支持条目: {", ".join(r["supporting_entries"])}')
        w(f'- 独立组数: {r["independent_groups"]}')
        w(f'- 建议: {r["suggested_action"]}')
        w()
else:
    w('无满足条件的候选规则')
    w()

w('## 已排除 / 不作全局修改的')
w('- CAL-070: 规格忘记, 仅保留为案例')
w('- CAL-071/072/073: 同组重复发货, 不独立推动算法修改')
w('- 修正后命中条目: 反映"诊断→修正"流程效果, 不计入首次估算准确率')
w('- Round 01 (CAL-001~051): 历史基线, 本次不调整')
w()

report = '\n'.join(report_lines)
report_path = os.path.join(BASE, 'archive/calibration/calibration_final_diagnostic.md')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report)

# Summary for console
print(f'Cleaned: {len(cleaned)} entries -> {output_path}')
print(f'Report: {report_path}')
print(f'First-pass: {len(first_pass)}, Corrected: {len(corrected_entries)}, Excluded: {stats["excluded"]}')
print(f'Unique groups: {len(stats["unique_groups"])}')
print(f'Match: {fp_matches}/{len(first_pass)} ({fp_matches/len(first_pass)*100:.1f}%)')
print(f'Mean error: {fp_mean:.1f}%, Median: {fp_median:.1f}%')
print(f'Candidate rules: {len(candidate_rules)}')
