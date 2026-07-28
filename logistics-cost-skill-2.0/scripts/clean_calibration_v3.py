#!/usr/bin/env python3
"""v3 校准清洗: 统一运费解析、估算来源审计、候选规则修正分组。

变更要点:
1. resolve_actual_head_freight: actual_head_freight_rmb > avg > range中点 > None
2. resolve_estimated_head_freight: estimated_head_freight_rmb > no_trust > with_trust > None
3. stored_estimate_origin: 逐条审计 estimated 字段是否在看到实际后被替换
4. 候选规则分组: 不再仅靠notes关键词, 同时检查product_type/material/rigidity/root_cause/方向
"""
import json, os, sys, statistics
from collections import Counter
from copy import deepcopy

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

# ── 加载原始数据(不修改) ──
with open('archive/calibration/calibration_samples.json', 'r', encoding='utf-8') as f:
    r01_raw = json.load(f)
with open('archive/calibration/calibration_samples_round_02.json', 'r', encoding='utf-8') as f:
    r02 = json.load(f)

# ════════════════════════════════════════════════════════
# 1. 统一运费解析
# ════════════════════════════════════════════════════════

def resolve_actual_head_freight(entry):
    """优先级: actual_head_freight_rmb > avg > range中点 > None"""
    v = entry.get('actual_head_freight_rmb')
    if v is not None and isinstance(v, (int, float)) and v > 0:
        return float(v)
    v = entry.get('actual_head_freight_avg_rmb')
    if v is not None and isinstance(v, (int, float)) and v > 0:
        return float(v)
    rng = entry.get('actual_head_freight_range_rmb')
    if rng and isinstance(rng, list) and len(rng) >= 2:
        return sum(rng) / len(rng)
    return None

def resolve_estimated_head_freight(entry):
    """优先级: estimated_head_freight_rmb > no_trust > with_trust > None"""
    v = entry.get('estimated_head_freight_rmb')
    if v is not None and isinstance(v, (int, float)) and v > 0:
        return float(v)
    v = entry.get('estimated_no_trust_head') or entry.get('estimated_head_freight_no_trust')
    if v is not None and isinstance(v, (int, float)) and v > 0:
        return float(v)
    v = entry.get('estimated_with_trust_head') or entry.get('estimated_head_freight_with_trust')
    if v is not None and isinstance(v, (int, float)) and v > 0:
        return float(v)
    return None

# ════════════════════════════════════════════════════════
# 2. stored_estimate_origin 逐条审计
# ════════════════════════════════════════════════════════
# 判断对象: 当前 estimated_head_freight_rmb (或resolved estimate) 字段本身
#           是否在看到该样本实际运费后被替换。
#
# before_actual: 字段仍保存首次估算值, 可参与首次准确率
# benchmark_corrected_only: 只修正实际费用口径/证据解释, 估算未替换, 可参与
# root_cause_corrected_only: 只修正root_cause名称, 估算未替换, 可参与
# after_actual: 看到实际后把估算替换为命中值, 不参与首次准确率
# unknown: 无法确认, 不参与

STORED_ESTIMATE_ORIGIN = {
    # ── Round 01 ──
    'CAL-001': 'benchmark_corrected_only',
    'CAL-002': 'root_cause_corrected_only',
    'CAL-003': 'before_actual',
    'CAL-004': 'before_actual',
    'CAL-005': 'before_actual',
    'CAL-006': 'before_actual',
    'CAL-007': 'before_actual',
    'CAL-008': 'before_actual',
    'CAL-009': 'before_actual',
    'CAL-010': 'before_actual',
    'CAL-011': 'before_actual',
    'CAL-012': 'before_actual',
    'CAL-013': 'before_actual',
    'CAL-014': 'before_actual',
    'CAL-015': 'before_actual',
    'CAL-016': 'before_actual',
    'CAL-017': 'before_actual',
    'CAL-018': 'before_actual',
    'CAL-019': 'before_actual',
    'CAL-020': 'before_actual',
    'CAL-021': 'before_actual',
    'CAL-022': 'before_actual',
    'CAL-023': 'before_actual',
    'CAL-024': 'before_actual',
    'CAL-025': 'before_actual',
    'CAL-026': 'benchmark_corrected_only',
    'CAL-027': 'before_actual',
    'CAL-028': 'before_actual',
    'CAL-029': 'unknown',
    'CAL-030': 'before_actual',
    'CAL-031': 'before_actual',
    'CAL-032': 'before_actual',
    'CAL-033': 'before_actual',
    'CAL-034': 'before_actual',
    'CAL-035': 'before_actual',
    'CAL-036': 'before_actual',
    'CAL-037': 'before_actual',
    'CAL-038': 'before_actual',
    'CAL-039': 'before_actual',
    'CAL-040': 'before_actual',
    'CAL-041': 'before_actual',
    'CAL-042': 'before_actual',
    'CAL-043': 'before_actual',
    'CAL-044': 'before_actual',
    'CAL-045': 'before_actual',
    'CAL-046': 'before_actual',
    'CAL-047': 'before_actual',
    'CAL-048': 'before_actual',
    'CAL-049': 'before_actual',
    'CAL-050': 'before_actual',
    'CAL-051': 'before_actual',
    # ── Round 02 ──
    'CAL-052': 'before_actual',
    'CAL-053': 'before_actual',
    'CAL-054': 'after_actual',
    'CAL-055': 'before_actual',
    'CAL-056': 'before_actual',
    'CAL-057': 'after_actual',
    'CAL-058': 'before_actual',
    'CAL-059': 'before_actual',
    'CAL-060': 'before_actual',
    'CAL-061': 'before_actual',
    'CAL-062': 'after_actual',
    'CAL-063': 'before_actual',
    'CAL-064': 'before_actual',
    'CAL-065': 'before_actual',
    'CAL-066': 'before_actual',
    'CAL-067': 'before_actual',
    'CAL-068': 'before_actual',
    'CAL-069': 'before_actual',
    'CAL-070': 'unknown',
    'CAL-071': 'before_actual',
    'CAL-072': 'before_actual',
    'CAL-073': 'before_actual',
    'CAL-074': 'before_actual',
    'CAL-075': 'before_actual',
    'CAL-076': 'before_actual',
    'CAL-077': 'before_actual',
}

# 逐条审计依据 (原v2中15条corrected_after_actual)
AUDIT_REASONS = {
    'CAL-001': '估算55.0未替换。notes修正的是实际费用口径(44.2=纯头程非合计), 反推体积比从62%修正为80%。估算字段本身从未改动。',
    'CAL-002': '估算38.4未替换。root_cause从SOFT_GOODS_UNDER_FOLDED修正为AI_VISUAL_ERROR。估算字段未改动。',
    'CAL-007': '估算73.9未替换。notes描述了修正过程(73.9->18.48), 但stored字段仍为73.9(原始首次估算值)。修正只在notes中描述。',
    'CAL-009': '估算9.0未替换。notes修正了重量解释(硅胶密度), 估算字段未改。无实际运费(resolve返回None), 排除。',
    'CAL-021': '估算6.0(estimated_head_freight_no_trust)未替换。notes建议<=50g不加+0.05kg修正, 是规则建议非字段替换。',
    'CAL-026': '估算12.0未替换。notes修正的是匹配口径解释: 正常档含20g包材余量=保守级命中。估算字段未改动。',
    'CAL-031': '估算12.0未替换。notes中"不加+0.05kg修正"指不应用修正规则, 非看到实际后修正。估算字段从首次起就是12.0。',
    'CAL-033': '估算6.0(estimated_no_trust_head)未替换。notes"不加修正命中0%"指不应用+0.05kg规则, 非看到实际后替换。',
    'CAL-037': '估算10.0(正常档)未替换。保守档12.0命中实际, 但正常档10.0字段未改动。方向=underestimate(10.0<12.0)。',
    'CAL-041': '估算3.0(estimated_no_trust_head)未替换。notes"不加修正命中0%"同CAL-033模式。估算字段未改动。',
    'CAL-044': '估算17.3未替换。notes描述偏差原因(纸板内衬多15-20g), 未替换估算字段。',
    'CAL-047': '估算18.48未替换。notes描述偏差原因(乳胶3->2cm), 未替换估算字段。',
    'CAL-054': '第一轮估算4.5(10x3x3cm/30-40g), 看到实际8.0后修正为12x5x4cm/80g->8.0。stored字段已替换为命中值。',
    'CAL-057': '第一轮估算6.0(OPP袋45g), 看到实际14.0后修正为挂卡+纸盒140g->14.0。stored字段已替换为命中值。',
    'CAL-062': '第一轮估算6.0(60g), 看到实际10.0后按商家规格100g修正->10.0。stored字段已替换为命中值。',
}

# ════════════════════════════════════════════════════════
# 3. 方向判定
# ════════════════════════════════════════════════════════

def derive_direction(est, act, raw_direction):
    """方向: est vs act 优先; 保留 conservative_match 标记"""
    if est is None or act is None:
        return 'unknown'
    if raw_direction == 'conservative_match':
        if est == act:
            return 'conservative_match'
        elif est < act:
            return 'underestimate'
        else:
            return 'overestimate'
    if est > act:
        return 'overestimate'
    elif est < act:
        return 'underestimate'
    else:
        return 'match'

# ════════════════════════════════════════════════════════
# 4. 处理所有条目
# ════════════════════════════════════════════════════════

all_raw = r01_raw + r02
all_cleaned = []

INDEPENDENCE_GROUPS = {
    'CAL-071': 'hair_claw_3ship',
    'CAL-072': 'hair_claw_3ship',
    'CAL-073': 'hair_claw_3ship',
}

for entry in all_raw:
    d = deepcopy(entry)
    sid = d['sample_id']

    actual = resolve_actual_head_freight(d)
    d['resolved_actual_head_freight_rmb'] = actual

    estimated = resolve_estimated_head_freight(d)
    d['resolved_estimated_head_freight_rmb'] = estimated

    raw_dir = d.get('error_direction', '')
    direction = derive_direction(estimated, actual, raw_dir)
    d['error_direction'] = direction

    if estimated is not None and actual is not None and actual > 0:
        d['head_freight_error_pct'] = round(abs((estimated - actual) / actual * 100), 1)
    else:
        d['head_freight_error_pct'] = None

    origin = STORED_ESTIMATE_ORIGIN.get(sid, 'unknown')
    d['stored_estimate_origin'] = origin

    if origin in ('before_actual', 'benchmark_corrected_only', 'root_cause_corrected_only'):
        d['estimate_stage'] = 'first_pass'
    elif origin == 'after_actual':
        d['estimate_stage'] = 'corrected_after_actual'
    else:
        d['estimate_stage'] = 'unknown'

    d['evidence_level'] = 'freight_inferred'
    d['independence_group'] = INDEPENDENCE_GROUPS.get(sid, sid)

    can_participate = (
        origin in ('before_actual', 'benchmark_corrected_only', 'root_cause_corrected_only')
        and actual is not None
        and estimated is not None
        and direction != 'unknown'
    )
    d['usable_for_accuracy_evaluation'] = can_participate
    d['usable_for_rule_learning'] = True

    reasons = []
    if origin == 'after_actual':
        reasons.append('估算在看到实际后被替换')
    if origin == 'unknown':
        reasons.append('估算来源未知')
    if actual is None:
        reasons.append('无实际运费')
    if estimated is None:
        reasons.append('无估算值')
    if sid == 'CAL-070':
        reasons.append('实际尺寸已忘记')
    d['exclusion_reason'] = '; '.join(reasons) if reasons else ''

    all_cleaned.append(d)

# ════════════════════════════════════════════════════════
# 5. 自检断言
# ════════════════════════════════════════════════════════
errors = []

def get(sid):
    return next(d for d in all_cleaned if d['sample_id'] == sid)

# CAL-003 不得以"无实际运费"排除
d = get('CAL-003')
assert d['resolved_actual_head_freight_rmb'] is not None, 'CAL-003 must have actual'
assert d['usable_for_accuracy_evaluation'] == True, 'CAL-003 must be usable'
assert d['error_direction'] == 'underestimate', f'CAL-003 dir wrong: {d["error_direction"]}'

# CAL-016 不得以"无实际运费"排除
d = get('CAL-016')
assert d['resolved_actual_head_freight_rmb'] is not None, 'CAL-016 must have actual'
assert d['usable_for_accuracy_evaluation'] == True, 'CAL-016 must be usable'
assert d['error_direction'] == 'overestimate', f'CAL-016 dir wrong: {d["error_direction"]}'

# CAL-054/057/062 必须是 after_actual
for sid in ['CAL-054', 'CAL-057', 'CAL-062']:
    d = get(sid)
    assert d['stored_estimate_origin'] == 'after_actual', f'{sid} must be after_actual'
    assert not d['usable_for_accuracy_evaluation'], f'{sid} must not be usable'

# CAL-001/002 仍可参与
for sid in ['CAL-001', 'CAL-002']:
    d = get(sid)
    assert d['usable_for_accuracy_evaluation'] == True, f'{sid} must be usable'

# CAL-007 估算未替换
d = get('CAL-007')
assert d['stored_estimate_origin'] == 'before_actual', 'CAL-007 must be before_actual'
assert d['usable_for_accuracy_evaluation'] == True, 'CAL-007 must be usable'

# after_actual 不参与
for d in all_cleaned:
    if d.get('stored_estimate_origin') == 'after_actual' and d.get('usable_for_accuracy_evaluation'):
        errors.append(f'{d["sample_id"]}: after_actual but usable')

# unknown 方向不参与
for d in all_cleaned:
    if d.get('error_direction') == 'unknown' and d.get('usable_for_accuracy_evaluation'):
        errors.append(f'{d["sample_id"]}: unknown direction but usable')

# CAL-029 无估算值
d = get('CAL-029')
assert d['resolved_estimated_head_freight_rmb'] is None, 'CAL-029 should have no estimate'
assert not d['usable_for_accuracy_evaluation'], 'CAL-029 should not be usable'

if errors:
    print('SELF-CHECK ERRORS:')
    for e in errors:
        print(f'  {e}')
    sys.exit(1)
else:
    print('All self-checks passed.')

# ════════════════════════════════════════════════════════
# 6. 统计
# ════════════════════════════════════════════════════════
fp = [d for d in all_cleaned if d['usable_for_accuracy_evaluation']]
excluded = [d for d in all_cleaned if not d['usable_for_accuracy_evaluation']]
after_actual = [d for d in all_cleaned if d['stored_estimate_origin'] == 'after_actual']
benchmark_corrected = [d for d in all_cleaned if d['stored_estimate_origin'] == 'benchmark_corrected_only']
root_cause_corrected = [d for d in all_cleaned if d['stored_estimate_origin'] == 'root_cause_corrected_only']
unknown_origin = [d for d in all_cleaned if d['stored_estimate_origin'] == 'unknown']

fp_dirs = Counter(d['error_direction'] for d in fp)
unique_groups = len(set(d.get('independence_group', d['sample_id']) for d in fp))

fp_errors = [d['head_freight_error_pct'] for d in fp if d['head_freight_error_pct'] is not None]
fp_mean = statistics.mean(fp_errors) if fp_errors else 0
fp_median = statistics.median(fp_errors) if fp_errors else 0

print(f'\n=== v3 Statistics ===')
print(f'Total: {len(all_cleaned)}')
print(f'Usable for accuracy: {len(fp)}')
print(f'after_actual: {len(after_actual)}')
print(f'benchmark_corrected_only: {len(benchmark_corrected)}')
print(f'root_cause_corrected_only: {len(root_cause_corrected)}')
print(f'unknown: {len(unknown_origin)}')
print(f'Excluded: {len(excluded)}')
print(f'Independent groups: {unique_groups}')
print(f'Directions: match={fp_dirs.get("match",0)} conservative_match={fp_dirs.get("conservative_match",0)} over={fp_dirs.get("overestimate",0)} under={fp_dirs.get("underestimate",0)}')
print(f'Mean error: {fp_mean:.1f}% | Median: {fp_median:.1f}%')

# ════════════════════════════════════════════════════════
# 7. 候选规则分组 (v3)
# ════════════════════════════════════════════════════════

# Rule 1: thin_soft_fabric_volume_correction
# 仅保留真正薄袜/薄针织/袖套; 移除CAL-068(PVC包)和CAL-075(PVC包)
thin_soft_ids = []
for d in all_cleaned:
    pt = d.get('product_type', '')
    mat = d.get('material', '')
    rig = d.get('rigidity', '')
    rc = d.get('root_cause', '')
    dirn = d.get('error_direction', '')
    cn = str(d.get('product_cn', ''))
    is_thin_sock = any(kw in pt.lower() for kw in ['socks', 'toe_socks', 'tabi']) and rig == 'soft'
    is_sleeve = 'sleeve' in pt.lower() or '袖' in cn
    is_thin_fabric_rc = 'THIN_FABRIC' in rc
    if (is_thin_sock or is_sleeve or is_thin_fabric_rc) and dirn == 'overestimate' and d['usable_for_rule_learning']:
        thin_soft_ids.append(d['sample_id'])
thin_soft_groups = len(set(get(sid)['independence_group'] for sid in thin_soft_ids))

# Rule 2a: leather_bag_compression
leather_bag_ids = ['CAL-065']

# Rule 2b: thin_pvc_full_fold
pvc_fold_ids = ['CAL-068']
pvc_fold_counterexample = ['CAL-075']

# Rule 2c: fabric_backpack_compression
fabric_bag_ids = ['CAL-076']

# Rule 3: rigid_protrusion_packaging (移除CAL-047)
rigid_prot_ids = ['CAL-054', 'CAL-056']
soft_flattened_ids = ['CAL-047']  # 移至观察

# ════════════════════════════════════════════════════════
# 8. 保存 JSON
# ════════════════════════════════════════════════════════
with open('archive/calibration/calibration_all_cleaned_v3.json', 'w', encoding='utf-8') as f:
    json.dump(all_cleaned, f, ensure_ascii=False, indent=2)

# ════════════════════════════════════════════════════════
# 9. 诊断报告
# ════════════════════════════════════════════════════════
L = []
def w(s=''):
    L.append(s)

total_fp = len(fp)

w('# CALIBRATION FINAL DIAGNOSTIC (v3)')
w()
w('## 数据概览')
w(f'- 总记录数: {len(all_cleaned)} (CAL-001 ~ CAL-077)')
w(f'- 首次估算可用样本: {len(fp)}')
w(f'- after_actual (不参与首次统计): {len(after_actual)}')
w(f'- benchmark_corrected_only (仍可参与): {len(benchmark_corrected)}')
w(f'- root_cause_corrected_only (仍可参与): {len(root_cause_corrected)}')
w(f'- unknown (不参与): {len(unknown_origin)}')
w(f'- 排除样本: {len(excluded)}')
w(f'- 独立商品组: {unique_groups}')
w()

w('## 首次估算准确率')
if total_fp > 0:
    w(f'- 命中(match): {fp_dirs.get("match", 0)} ({fp_dirs.get("match", 0) / total_fp * 100:.1f}%)')
    w(f'- 保守命中(conservative_match): {fp_dirs.get("conservative_match", 0)} ({fp_dirs.get("conservative_match", 0) / total_fp * 100:.1f}%)')
    w(f'- 高估(overestimate): {fp_dirs.get("overestimate", 0)} ({fp_dirs.get("overestimate", 0) / total_fp * 100:.1f}%)')
    w(f'- 低估(underestimate): {fp_dirs.get("underestimate", 0)} ({fp_dirs.get("underestimate", 0) / total_fp * 100:.1f}%)')
w(f'- 平均误差: {fp_mean:.1f}%')
w(f'- 中位误差: {fp_median:.1f}%')
w()

w('## after_actual 样本 (估算在看到实际后被替换, 不参与首次统计)')
for d in sorted(after_actual, key=lambda x: x['sample_id']):
    w(f'- {d["sample_id"]}: est={d["resolved_estimated_head_freight_rmb"]}, act={d["resolved_actual_head_freight_rmb"]}, dir={d["error_direction"]}')
w()

w('## benchmark_corrected_only (只修正实际费用口径/证据解释, 估算未替换, 仍可参与)')
for d in sorted(benchmark_corrected, key=lambda x: x['sample_id']):
    w(f'- {d["sample_id"]}: est={d["resolved_estimated_head_freight_rmb"]}, act={d["resolved_actual_head_freight_rmb"]}, dir={d["error_direction"]}')
w()

w('## root_cause_corrected_only (只修正root_cause名称, 估算未替换, 仍可参与)')
for d in sorted(root_cause_corrected, key=lambda x: x['sample_id']):
    w(f'- {d["sample_id"]}: est={d["resolved_estimated_head_freight_rmb"]}, act={d["resolved_actual_head_freight_rmb"]}, dir={d["error_direction"]}')
w()

w('## unknown 样本 (无法确认估算来源, 不参与)')
for d in sorted(unknown_origin, key=lambda x: x['sample_id']):
    w(f'- {d["sample_id"]}: {d["exclusion_reason"]}')
w()

w('## 排除样本详情')
for d in sorted(excluded, key=lambda x: x['sample_id']):
    w(f'- {d["sample_id"]}: {d["exclusion_reason"]} (origin={d["stored_estimate_origin"]})')
w()

w('## stored_estimate_origin 逐条审计依据')
w('(原v2中15条corrected_after_actual的重新审计结果)')
w()
for sid in ['CAL-001', 'CAL-002', 'CAL-007', 'CAL-009', 'CAL-021', 'CAL-026',
            'CAL-031', 'CAL-033', 'CAL-037', 'CAL-041', 'CAL-044', 'CAL-047',
            'CAL-054', 'CAL-057', 'CAL-062']:
    d = get(sid)
    reason = AUDIT_REASONS.get(sid, '')
    w(f'- **{sid}**: {reason}')
    w(f'  - resolved_est={d["resolved_estimated_head_freight_rmb"]}, resolved_act={d["resolved_actual_head_freight_rmb"]}, dir={d["error_direction"]}, origin={d["stored_estimate_origin"]}')
w()

w('## 候选规则 (v3 修正分组)')
w()
w('### 1. thin_soft_fabric_volume_correction')
w('- 适用: 薄袜/薄针织/袖套类, 折叠后体积重偏高40-50%')
w(f'- 支持条目: {", ".join(thin_soft_ids)}')
w(f'- 独立组数: {thin_soft_groups}')
w('- v3修正: 移除CAL-068(PVC包)和CAL-075(PVC包), 仅保留真正薄款面料')
w()

w('### 2a. leather_bag_compression')
w('- 适用: PU皮/真皮半硬包, 厚度x0.65')
w(f'- 支持条目: {", ".join(leather_bag_ids)}')
w('- 独立组数: 1')
w('- 状态: 单样本, 仅观察')
w()

w('### 2b. thin_pvc_full_fold')
w('- 适用: PVC薄款透明化妆包, 全折叠(10x10x3cm模板)')
w(f'- 支持条目: {", ".join(pvc_fold_ids)}')
w('- 独立组数: 1')
w(f'- 反例/边界: {", ".join(pvc_fold_counterexample)} (CAL-075: PVC但压缩非全折叠, 证明需区分薄款vs有底厚款)')
w('- 状态: 单样本+1反例, 仅观察')
w()

w('### 2c. fabric_backpack_compression')
w('- 适用: 牛津布/帆布软包, 厚度x0.4')
w(f'- 支持条目: {", ".join(fabric_bag_ids)}')
w('- 独立组数: 1')
w('- 状态: 单样本, 仅观察')
w()

w('### 3. rigid_protrusion_packaging')
w('- 适用: 不可压缩硬质突出(手柄/夹扣/扳手), 包装厚度>=本体+2cm')
w(f'- 支持条目: {", ".join(rigid_prot_ids)}')
w('- 独立组数: 2')
w('- v3修正: 移除CAL-047(乳胶头套=soft_flattened_protrusion, 方向是压平减小厚度, 非硬质加厚)')
w(f'- 移至观察: {", ".join(soft_flattened_ids)} (软质压平, 非硬质突出)')
w()

w('## 最终建议 (不实施)')
w()
w('### 可进入AI包装估算提示规则')
w(f'- thin_soft_fabric_volume_correction: {thin_soft_groups}独立组支持, 方向一致(均高估), 可建议薄款袜/袖套ai_package_size_cm厚度从4cm->3cm')
w(f'- rigid_protrusion_packaging: 2独立组支持, 可建议手柄/夹扣类包装厚度+2cm')
w()
w('### 仅保留观察')
w('- leather_bag_compression (CAL-065): 单样本, 需更多皮包验证')
w('- thin_pvc_full_fold (CAL-068): 单样本+1反例(CAL-075), 需更多PVC包验证')
w('- fabric_backpack_compression (CAL-076): 单样本, 需更多布包验证')
w('- soft_flattened_protrusion (CAL-047): 单样本, 乳胶/软质突出压平')
w()
w('### 数据不足不得实施')
w('- 包袋三档压缩规则各仅1样本, 不得合并为已验证固定规则')
w('- leather/pvc/fabric三个子类型需各自>=3独立组方可实施')
w()

w('## 方向判定方法')
w('- 方向按 resolved_estimated vs resolved_actual 对比')
w('- conservative_match保留: 正常档数值碰巧相等但含包材余量, 不计为true match')
w('- 原始error_direction不一致时以 resolved est vs act 为准')
w('- est或act为None -> unknown')
w()

w('## 实际运费解析方法')
w('- 优先级: actual_head_freight_rmb > actual_head_freight_avg_rmb > actual_head_freight_range_rmb中点 > None')
w('- CAL-003: actual_head_freight_avg_rmb=4.35 (actual_head_freight_rmb不存在)')
w('- CAL-016: actual_head_freight_avg_rmb=4.65 (actual_head_freight_rmb不存在)')
w()

w('## 已排除/不修改')
w('- Round 01 原始校准文件不变')
w('- Round 02 原始校准文件不变')
w('- 物流算法、配置、AI JSON均未修改')

with open('archive/calibration/calibration_final_diagnostic_v3.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(L))

print('\nFiles generated:')
print('  archive/calibration/calibration_all_cleaned_v3.json')
print('  archive/calibration/calibration_final_diagnostic_v3.md')
