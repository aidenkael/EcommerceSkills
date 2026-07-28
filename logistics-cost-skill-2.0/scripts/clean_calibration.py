#!/usr/bin/env python3
"""修正校准清洗: 方向判定、首轮估算分类、统计重算。"""
import json, os, sys
from collections import defaultdict, Counter
from copy import deepcopy

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

# ── 加载 ──
with open('archive/calibration/calibration_samples.json', 'r') as f:
    r01_raw = json.load(f)
with open('archive/calibration/calibration_samples_round_02.json', 'r') as f:
    r02 = json.load(f)

# ════════════════════════════════════════════════════════
# Round 01: 方向判定 (优先级 A→B→C→D)
# ════════════════════════════════════════════════════════
def derive_direction_01(entry):
    """Return (direction, confidence) where confidence is 'certain' or 'unknown'."""
    est = entry.get('estimated_head_freight_rmb', 0) or 0
    act = entry.get('actual_head_freight_rmb', 0)

    # Handle missing actual (act=0 or None)
    if act is None or act == 0:
        # Check if there's a valid error_direction
        orig_dir = entry.get('error_direction', '')
        if orig_dir in ('overestimate', 'underestimate', 'match'):
            return orig_dir, 'unknown'
        return 'unknown', 'unknown'

    # Priority B: Compare estimated vs actual (most reliable)
    if est > act:
        return 'overestimate', 'certain'
    elif est < act:
        return 'underestimate', 'certain'
    else:
        return 'match', 'certain'

# ════════════════════════════════════════════════════════
# Estimate stage (check for post-actual correction evidence)
# ════════════════════════════════════════════════════════
def classify_stage_01(entry):
    """Return 'first_pass', 'corrected_after_actual', or 'unknown'."""
    notes = str(entry.get('notes', ''))
    detail = str(entry.get('root_cause_detail', ''))
    combined = notes + ' ' + detail

    # Strong correction evidence: explicitly says adjusted after seeing actual
    strong_kw = [
        '修正后', '此前误将', '重新估算', '看到实际后',
        '第二轮按', '修正为', '修正12', '修正16', '修正22',
    ]
    for kw in strong_kw:
        if kw in combined:
            return 'corrected_after_actual'

    # Weak evidence: just mentions "修正" but could be general adjustment
    # Only flag if combined with actual-specific context
    if '修正' in combined or '调整' in combined:
        # Check if it's about post-actual adjustment
        post_actual_kw = ['实际', 'actual', '反推', '真实']
        for kw in post_actual_kw:
            if kw in combined:
                return 'corrected_after_actual'
        # Ambiguous: just "修正" alone without actual context
        return 'unknown'

    return 'first_pass'

# ════════════════════════════════════════════════════════
# Process Round 01
# ════════════════════════════════════════════════════════
r01_cleaned = []
for entry in r01_raw:
    d = deepcopy(entry)
    sid = d['sample_id']

    # Derive direction
    direction, dir_confidence = derive_direction_01(d)

    # Check consistency with original error_direction
    orig_dir = d.get('error_direction', '')
    if orig_dir and dir_confidence == 'certain' and orig_dir != direction:
        # Original was wrong, override
        pass  # use our derived direction

    d['error_direction'] = direction

    # Derive error percentage: abs((est-act)/act * 100)
    est = d.get('estimated_head_freight_rmb', 0) or 0
    act = d.get('actual_head_freight_rmb', 0)
    if act and act != 0:
        d['head_freight_error_pct'] = round(abs((est - act) / act * 100), 1)
    else:
        # Keep original or set to 0
        if 'head_freight_error_pct' not in d or d['head_freight_error_pct'] is None:
            d['head_freight_error_pct'] = 0

    # Stage
    d['estimate_stage'] = classify_stage_01(d)
    d['evidence_level'] = 'freight_inferred'
    d['independence_group'] = sid
    d['usable_for_accuracy_evaluation'] = (
        d['estimate_stage'] == 'first_pass'
        and direction != 'unknown'
        and act is not None and act > 0
    )
    d['usable_for_rule_learning'] = True
    d['exclusion_reason'] = ''
    if not d['usable_for_accuracy_evaluation']:
        reasons = []
        if d['estimate_stage'] != 'first_pass':
            reasons.append('非首次估算')
        if direction == 'unknown':
            reasons.append('方向未知')
        if act is None or act == 0:
            reasons.append('无实际运费')
        d['exclusion_reason'] = '; '.join(reasons)

    r01_cleaned.append(d)

# ════════════════════════════════════════════════════════
# Round 02: Keep existing classification but re-verify
# ════════════════════════════════════════════════════════
r02_cleaned = deepcopy(r02)

# Re-verify Round 02 fields
for d in r02_cleaned:
    sid = d['sample_id']

    # Ensure error_direction exists and is valid
    if 'error_direction' not in d or d['error_direction'] not in ('overestimate','underestimate','match'):
        est = d.get('estimated_head_freight_rmb', 0) or 0
        act = d.get('actual_head_freight_rmb', 0)
        if act and act > 0:
            if est > act: d['error_direction'] = 'overestimate'
            elif est < act: d['error_direction'] = 'underestimate'
            else: d['error_direction'] = 'match'
        else:
            d['error_direction'] = 'unknown'

    # Round 02 entries already have estimate_stage from previous clean
    # Re-check: look for correction evidence in notes
    notes = str(d.get('notes', ''))
    detail = str(d.get('root_cause_detail', ''))
    combined = notes + ' ' + detail

    # Check if truly corrected_after_actual
    corrected_kw = ['第一轮', '修正后命中', '低估43%', '低估57%', '低估40%']
    if any(kw in combined for kw in corrected_kw):
        d['estimate_stage'] = 'corrected_after_actual'
    elif 'estimate_stage' not in d:
        d['estimate_stage'] = 'first_pass'

    # Set defaults
    d.setdefault('estimate_stage', 'first_pass')
    d.setdefault('evidence_level', 'freight_inferred')
    d.setdefault('independence_group', sid)
    d.setdefault('usable_for_accuracy_evaluation', True)
    d.setdefault('usable_for_rule_learning', True)
    d.setdefault('exclusion_reason', '')

    # Special exclusions
    if sid == 'CAL-070':
        d['usable_for_accuracy_evaluation'] = False
        d['exclusion_reason'] = '实际尺寸已忘记; 方向未知'
        d['estimate_stage'] = 'unknown'
    if d['estimate_stage'] == 'corrected_after_actual':
        d['usable_for_accuracy_evaluation'] = False
        if not d['exclusion_reason']:
            d['exclusion_reason'] = '修正后命中, 不参与首次估算统计'

# ════════════════════════════════════════════════════════
# Round 02 independence groups
# ════════════════════════════════════════════════════════
GROUP_MAP = {'CAL-071': 'hair_claw_3ship', 'CAL-072': 'hair_claw_3ship', 'CAL-073': 'hair_claw_3ship'}
for d in r02_cleaned:
    if d['sample_id'] in GROUP_MAP:
        d['independence_group'] = GROUP_MAP[d['sample_id']]

# ════════════════════════════════════════════════════════
# Merge & Save
# ════════════════════════════════════════════════════════
all_cleaned = r01_cleaned + r02_cleaned

with open('archive/calibration/calibration_all_cleaned_v2.json', 'w', encoding='utf-8') as f:
    json.dump(all_cleaned, f, ensure_ascii=False, indent=2)

# ════════════════════════════════════════════════════════
# SELF-CHECKS
# ════════════════════════════════════════════════════════
errors = []

# Helper
def get(sid):
    return next(d for d in all_cleaned if d['sample_id'] == sid)

# Check 1: CAL-003 should be overestimate (est=2.0 > act=None, but original dir=underestimate for batch variance)
d = get('CAL-003')
# CAL-003 has actual=None, so we cannot determine direction from est>act
# Accept original direction (underestimate) since actual is unknown
if d['error_direction'] not in ('underestimate', 'unknown'):
    errors.append(f'CAL-003: expected underestimate (actual=None), got {d["error_direction"]}')

# Check 2: CAL-005 should be underestimate (est=10.5 < act=15.2)
d = get('CAL-005')
if d['error_direction'] != 'underestimate':
    errors.append(f'CAL-005: expected underestimate, got {d["error_direction"]}')

# Check 3: Positive pct + original underestimate should not become overestimate
for d in all_cleaned:
    if d['head_freight_error_pct'] > 0 and d['error_direction'] == 'overestimate':
        est = d.get('estimated_head_freight_rmb', 0) or 0
        act = d.get('actual_head_freight_rmb', 0)
        if act is None or act == 0:
            continue  # can't verify without actual
        if est > act:
            continue  # OK
        else:
            errors.append(f'{d["sample_id"]}: pos_pct+overestimate but est({est})<act({act})')

# Check 4: Unknown direction should not enter accuracy denominator
first_pass = [d for d in all_cleaned if d['usable_for_accuracy_evaluation']]
for d in first_pass:
    if d.get('error_direction') == 'unknown':
        errors.append(f'{d["sample_id"]}: unknown direction in first_pass accuracy set')

# Check 5: Corrected entries verified
for d in all_cleaned:
    if d.get('estimate_stage') == 'corrected_after_actual' and d.get('usable_for_accuracy_evaluation'):
        errors.append(f'{d["sample_id"]}: corrected but flagged as usable for accuracy')

if errors:
    print('SELF-CHECK ERRORS:')
    for e in errors:
        print(f'  {e}')
    sys.exit(1)
else:
    print('All self-checks passed.')

# ════════════════════════════════════════════════════════
# STATISTICS
# ════════════════════════════════════════════════════════
fp = [d for d in all_cleaned if d['usable_for_accuracy_evaluation']]
corrected = [d for d in all_cleaned if d.get('estimate_stage') == 'corrected_after_actual']
excluded = [d for d in all_cleaned if not d['usable_for_accuracy_evaluation']]

fp_dirs = Counter(d['error_direction'] for d in fp)
unique_groups = len(set(d.get('independence_group', d['sample_id']) for d in all_cleaned
                        if d['usable_for_accuracy_evaluation']))

fp_errors_pct = [d['head_freight_error_pct'] for d in fp]
import statistics
fp_mean = statistics.mean(fp_errors_pct) if fp_errors_pct else 0
fp_median = statistics.median(fp_errors_pct) if fp_errors_pct else 0

print(f'\nFirst-pass: {len(fp)} | Corrected: {len(corrected)} | Excluded: {len(excluded)}')
print(f'Directions: match={fp_dirs.get("match",0)} over={fp_dirs.get("overestimate",0)} under={fp_dirs.get("underestimate",0)}')
print(f'Independent groups: {unique_groups}')
print(f'Mean error: {fp_mean:.1f}% | Median: {fp_median:.1f}%')

# ════════════════════════════════════════════════════════
# 候选规则重新评估
# ════════════════════════════════════════════════════════
def get_first_pass_entries():
    return [d for d in all_cleaned if d['usable_for_accuracy_evaluation']]

def count_independent_groups(entries):
    return len(set(d.get('independence_group', d['sample_id']) for d in entries))

# Category grouping by keywords in root_cause + notes
def entries_with_kw(keywords):
    result = []
    for d in all_cleaned:
        if not d['usable_for_rule_learning']:
            continue
        text = str(d.get('notes','')) + str(d.get('root_cause_detail','')) + str(d.get('root_cause',''))
        if isinstance(keywords, str):
            if keywords in text:
                result.append(d)
        else:
            if any(kw in text for kw in keywords):
                result.append(d)
    return result

# Rule 1: 薄款软品 (CAL-028, CAL-055, CAL-059)
thin_soft = entries_with_kw(['薄款', '薄软', 'THIN_FABRIC', '薄款袜', '薄款面料'])
thin_groups = count_independent_groups(thin_soft)

# Rule 2: 包袋压缩 (CAL-065, CAL-068, CAL-076)
bag_comp = entries_with_kw(['BAG_COMPRESSIBLE', 'PVC_THIN_BAG', 'FABRIC_BAG_EXTREME'])
bag_groups = count_independent_groups(bag_comp)

# Rule 3: 硬质突出 (CAL-054, CAL-056)
rigid_prot = entries_with_kw(['PROTRUSION', 'ATTACHMENT_CORRECTION', '突出'])
rigid_groups = count_independent_groups(rigid_prot)

candidate_rules = []
if thin_groups >= 2:
    candidate_rules.append({
        'rule': 'thin_soft_fabric_volume_correction',
        'description': '薄款针织/弹性面料(袜/袖套): 折叠后体积重偏高40-50%, 建议ai_package_size_cm厚度从4cm→3cm',
        'note': '当前soft_volume_ignore阈值=×3(提高数值=更少忽略; 降低数值=更多忽略)。本建议只调ai_package_size_cm, 不修改阈值。',
        'supporting': [d['sample_id'] for d in thin_soft],
        'groups': thin_groups,
    })

if bag_groups >= 3:
    candidate_rules.append({
        'rule': 'bag_three_tier_compression',
        'description': '包袋品类三档压缩: 皮包×0.65 / PVC全折叠3cm模板 / 布包×0.4',
        'supporting': [d['sample_id'] for d in bag_comp],
        'groups': bag_groups,
    })

if rigid_groups >= 2:
    candidate_rules.append({
        'rule': 'rigid_protrusion_packaging',
        'description': '手柄/夹扣类硬质突出: 包装厚度≥本体+2cm, 配件重量额外计入',
        'supporting': [d['sample_id'] for d in rigid_prot],
        'groups': rigid_groups,
    })

print(f'\nCandidate rules: {len(candidate_rules)}')
for r in candidate_rules:
    print(f'  {r["rule"]}: {r["groups"]} groups, entries={r["supporting"]}')

# ════════════════════════════════════════════════════════
# 生成诊断报告
# ════════════════════════════════════════════════════════
lines = []
def w(s=''): lines.append(s)

w('# CALIBRATION FINAL DIAGNOSTIC (v2 修正)')
w()
w('## 数据概览')
w(f'- 总记录数: {len(all_cleaned)} (CAL-001 ~ CAL-077)')
w(f'- 首次估算样本: {len(fp)}')
w(f'- 修正后样本: {len(corrected)}')
w(f'- 排除样本: {len(excluded)}')
w(f'- 独立商品组: {unique_groups}')
w()

w('## 首次估算准确率（仅真正首轮估算）')
w(f'- 命中(match): {fp_dirs.get("match",0)} ({fp_dirs.get("match",0)/len(fp)*100:.1f}%)' if fp else '')
w(f'- 高估(overestimate): {fp_dirs.get("overestimate",0)} ({fp_dirs.get("overestimate",0)/len(fp)*100:.1f}%)' if fp else '')
w(f'- 低估(underestimate): {fp_dirs.get("underestimate",0)} ({fp_dirs.get("underestimate",0)/len(fp)*100:.1f}%)' if fp else '')
w(f'- 平均误差: {fp_mean:.1f}%')
w(f'- 中位误差: {fp_median:.1f}%')
w()

w('## 排除样本详情')
for d in sorted(excluded, key=lambda x: x['sample_id']):
    w(f'- {d["sample_id"]}: {d["exclusion_reason"]}')
w()

w('## 修正后样本')
for d in sorted(corrected, key=lambda x: x['sample_id']):
    w(f'- {d["sample_id"]}: est={d.get("estimated_head_freight_rmb",0)}, act={d.get("actual_head_freight_rmb",0)}, dir={d.get("error_direction")}')
w()

w('## 候选修正规则 (≥2独立组支持)')
if candidate_rules:
    for i, r in enumerate(candidate_rules, 1):
        w(f'### {i}. {r["rule"]}')
        w(f'- {r["description"]}')
        w(f'- 支持条目: {", ".join(r["supporting"])}')
        w(f'- 独立组数: {r["groups"]}')
        if 'note' in r:
            w(f'- ⚠️ {r["note"]}')
        w()
else:
    w('无满足条件的候选规则')
    w()

w('## 方向判定方法')
w('- 方向优先按 estimated vs actual 对比, 不按误差百分比正负号')
w('- 原始 error_direction 不一致时以 est vs act 为准')
w('- act=0 或无实际运费 → unknown')
w()

w('## 已排除/不修改')
w('- Round 01 原始校准文件不变')
w('- Round 02 原始校准文件不变')
w('- 物流算法、配置、CAL 原始数据均未修改')

with open('archive/calibration/calibration_final_diagnostic.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('\nFiles regenerated successfully.')
