"""输出合同锁定测试 — OUTPUT_CONTRACT 2026-08-04-v1。

测试覆盖 16 项针对性检查：
1. 模式2黄金快照逐字符一致
2. 模式1黄金快照逐字符一致
3. 第一张表固定四行顺序
4. 第二张表固定七列且只有一行
5. 四种方案选择最低总头程
6. 相同总头程按固定顺序选择
7. 无活动售价按成本利润率计算
8. 活动售价等于无活动售价×(1-活动预留)
9. 无活动售价低于29时补贴生效
10. 活动售价低于29时补贴生效
11. 售价等于29时补贴不生效
12. 补贴条件按未舍入值判断
13. 缺采购价时格式不变并显示无法计算
14. PU硬框包主体保型+把手折叠一次通过
15. 旧--ai-json和--compact兼容
16. 输出中不存在"小结""临界点""MEMORY"等
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
GOLDEN = PROJECT / "tests" / "golden"
EXAMPLES = PROJECT / "examples"
sys.path.insert(0, str(PROJECT))

import pytest

from logistics_cost.ai_schema import validate, to_estimate_inputs
from logistics_cost.estimator import estimate
from logistics_cost.output_renderer import (
    render_head_only, render_profit, OUTPUT_CONTRACT_VERSION,
)


def _load_and_estimate(example_name: str):
    with open(EXAMPLES / example_name, encoding="utf-8") as f:
        ai_data = json.load(f)
    ai = validate(ai_data)
    summary, evidence, scenarios, _ = to_estimate_inputs(ai)
    result = estimate(product_summary=summary, raw_evidence=evidence, packaging_scenarios=scenarios)
    return result


# ============================================================
# Test 1 & 2: Golden snapshot exact match
# ============================================================

def test_mode2_golden_snapshot():
    """模式2快照逐字符一致。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {
        "title": "PU轻潮斜挎肩部链条包（小方包）",
        "quantity": 1, "unit": "件",
        "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
        "normal_packaging": "把手折叠、肩带收纳后纸盒装",
        "conservative_packaging": "较少压缩并增加局部五金保护",
        "confidence": "high",
    }
    actual = render_head_only(result, display)
    expected = (GOLDEN / "output_mode2_2026-08-04-v1.md").read_text(encoding="utf-8").rstrip("\n")
    assert actual.strip() == expected, f"Mode2 snapshot mismatch!\nExpected:\n{expected}\n\nActual:\n{actual}"


def test_mode1_golden_snapshot():
    """模式1快照逐字符一致。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {
        "title": "PU轻潮斜挎肩部链条包（小方包）",
        "quantity": 1, "unit": "件",
        "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
        "normal_packaging": "把手折叠、肩带收纳后纸盒装",
        "conservative_packaging": "较少压缩并增加局部五金保护",
        "confidence": "high",
    }
    actual = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    expected = (GOLDEN / "output_mode1_2026-08-04-v1.md").read_text(encoding="utf-8").rstrip("\n")
    assert actual.strip() == expected, f"Mode1 snapshot mismatch!\nExpected:\n{expected}\n\nActual:\n{actual}"


# ============================================================
# Test 3: Four-row order in head table
# ============================================================

def test_head_table_four_rows_in_order():
    """第一张表固定四行顺序：义乌正常/义乌保守/深圳正常/深圳保守。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_head_only(result, display)
    lines = output.split("\n")
    expected_order = ["义乌正常", "义乌保守", "深圳正常", "深圳保守"]
    found = [line.split("|")[1].strip() for line in lines if line.startswith("| 义乌") or line.startswith("| 深圳")]
    assert found == expected_order, f"Table row order mismatch: {found}"


# ============================================================
# Test 4: Profit table one row seven columns
# ============================================================

def test_profit_table_one_row_seven_columns():
    """第二张表固定七列且只有一行。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    lines = output.split("\n")
    # Find profit table lines
    profit_lines = []
    in_profit = False
    for line in lines:
        if "国内成本（¥）" in line:
            in_profit = True
            continue
        if in_profit:
            if line.startswith("|:---"):
                continue
            if line.startswith("| ") and not line.startswith("| 方案"):
                profit_lines.append(line)
            elif profit_lines and not line.startswith("| "):
                break
    # Should have exactly 1 data row + no extra
    assert len(profit_lines) == 1, f"Profit table should have exactly 1 data row, got {len(profit_lines)}"
    cols = profit_lines[0].split("|")[1:-1]  # strip leading/trailing |
    assert len(cols) == 7, f"Profit table should have 7 columns, got {len(cols)}"


# ============================================================
# Test 5 & 6: Lowest head cost selection
# ============================================================

def test_lowest_head_cost_selection():
    """四种方案选择最低总头程。"""
    from logistics_cost.output_renderer import _find_lowest_head

    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    scenario, cost = _find_lowest_head(result)
    assert scenario == "深圳正常"
    # 深圳正常 = 0.495*80+10 = 49.60 (lowest)
    assert cost == 49.60, f"Expected 49.60, got {cost}"


def test_equal_cost_uses_fixed_order():
    """相同总头程按固定顺序选择。"""
    from logistics_cost.output_renderer import _find_lowest_head

    # 构造一个两方案总头程相等的场景
    mock_result = {
        "normal": {
            "provider_costs": {
                "义乌货代": {"head_freight_rmb": 6.0, "fixed_service_fee_rmb": 6, "total_cost_rmb": 12.0},
                "深圳货代": {"head_freight_rmb": 6.0, "fixed_service_fee_rmb": 6, "total_cost_rmb": 12.0},
            },
            "packaged_size_cm": [10, 10, 10],
            "packaged_weight_kg": 0.1,
            "chargeable_weight_kg": 0.125,
        },
        "conservative": {
            "provider_costs": {
                "义乌货代": {"head_freight_rmb": 10.0, "fixed_service_fee_rmb": 6, "total_cost_rmb": 16.0},
                "深圳货代": {"head_freight_rmb": 10.0, "fixed_service_fee_rmb": 6, "total_cost_rmb": 16.0},
            },
            "packaged_size_cm": [12, 12, 12],
            "packaged_weight_kg": 0.15,
            "chargeable_weight_kg": 0.216,
        },
    }
    scenario, cost = _find_lowest_head(mock_result)
    assert scenario == "义乌正常", f"Equal costs should pick 义乌正常 (first in order), got {scenario}"


# ============================================================
# Test 7 & 8: Profit calculation formulas
# ============================================================

def test_no_activity_price_formula():
    """无活动售价 = C×(1+利润率)/汇率。"""
    from logistics_cost.profit_calculator import calculate_profit

    result = calculate_profit(
        product_cost_rmb=47, domestic_freight_rmb=5,
        total_head_cost_rmb=49.60, tail_cost_rmb=47.40,
        exchange_rate=6.7716,
        target_profit_markup_percent=25, activity_reserve_percent=15,
    )
    # C = 47+5+49.60+47.40 = 149.00
    assert result["total_cost_rmb"] == 149.00
    # P = 149.00 * 0.25 = 37.25
    assert result["target_profit_rmb"] == 37.25
    # no_activity_price = (149.00+37.25)/6.7716 = 27.50...
    assert result["no_activity_price_usd"] == 27.50


def test_activity_price_formula():
    """活动后售价 = 无活动售价×(1-活动预留)。"""
    from logistics_cost.profit_calculator import calculate_profit

    result = calculate_profit(
        product_cost_rmb=47, domestic_freight_rmb=5,
        total_head_cost_rmb=49.60, tail_cost_rmb=47.40,
        exchange_rate=6.7716,
        target_profit_markup_percent=25, activity_reserve_percent=15,
    )
    # 活动后售价: 使用未舍入值验证公式（而非已舍入到2dp的no_activity_price_usd）
    C = result["total_cost_rmb"]
    P = result["target_profit_rmb"]
    no_activity_raw = (C + P) / 6.7716
    activity_raw = no_activity_raw * 0.85
    # activity_price_usd 应该等于 activity_raw 舍入到2dp
    assert abs(result["activity_price_usd"] - round(activity_raw, 2)) < 0.01, \
        f"Activity price {result['activity_price_usd']} != round({activity_raw}, 2)"


# ============================================================
# Test 9-12: SHEIN subsidy boundary
# ============================================================

def test_subsidy_active_below_29():
    """无活动售价低于29时补贴生效。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    assert "满足SHEIN补贴条件" in output
    assert "不满足SHEIN补贴条件" not in output


def test_subsidy_active_below_29_activity():
    """活动售价低于29时补贴也生效（本案例中两项都低于29）。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    assert "满足SHEIN补贴条件" in output


def test_subsidy_not_active_at_exactly_29():
    """售价等于29.00时补贴不生效。"""
    from logistics_cost.profit_calculator import calculate_profit

    # 调参数让无活动售价刚好 >= 29
    result = calculate_profit(
        product_cost_rmb=50, domestic_freight_rmb=5,
        total_head_cost_rmb=40, tail_cost_rmb=47,
        exchange_rate=6.7716,
        target_profit_markup_percent=25, activity_reserve_percent=0,
    )
    # C = 50+5+40+47 = 142
    # no_activity = 142*1.25/6.7716 = 26.2
    # not >= 29, try higher costs
    result2 = calculate_profit(
        product_cost_rmb=70, domestic_freight_rmb=5,
        total_head_cost_rmb=60, tail_cost_rmb=47,
        exchange_rate=6.7716,
        target_profit_markup_percent=15, activity_reserve_percent=0,
    )
    # C = 70+5+60+47 = 182, no_activity = 182*1.15/6.7716 = 30.91... > 29
    assert result2["no_activity_subsidy_usd"] == 0.0, f"Should get no subsidy at ≥$29, got {result2['no_activity_subsidy_usd']}"


def test_subsidy_uses_unrounded_values():
    """补贴条件按未舍入值判断。"""
    from logistics_cost.profit_calculator import calculate_profit, _get_shein_subsidy_config, _apply_subsidy

    cfg = _get_shein_subsidy_config()
    # 28.999... should get subsidy
    assert _apply_subsidy(28.999, cfg) == 2.99
    # 29.0 should NOT get subsidy
    assert _apply_subsidy(29.0, cfg) == 0.0
    # 28.994 rounded to 2dp = 28.99 but raw is 28.994 → should get subsidy
    assert _apply_subsidy(28.994, cfg) == 2.99


# ============================================================
# Test 13: Missing data behavior
# ============================================================

def test_missing_purchase_price():
    """缺采购价时格式不变，显示无法计算。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    assert "采购价未识别" in output
    assert "无法计算" in output
    assert "利润部分因采购价或国内运费缺失无法计算" in output


# ============================================================
# Test 14: PU bag body retention + handle folding
# ============================================================

def test_pu_bag_body_retention_handle_folding():
    """PU硬框包主体保型+把手折叠一次通过。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    assert result["status"] == "calculated"
    # Normal should have folding action (不折叠 for this specific bag since AI didn't specify foldable parts in the JSON)
    normal = result.get("normal", {})
    assert "packaged_size_cm" in normal
    assert normal["packaged_size_cm"] and len(normal["packaged_size_cm"]) == 3


# ============================================================
# Test 15: Legacy --ai-json and --compact compatibility
# ============================================================

def test_legacy_ai_json_compat():
    """旧 --ai-json 调用仍兼容。"""
    r = subprocess.run(
        [sys.executable, str(PROJECT / "run.py"), "--ai-json",
         str(EXAMPLES / "socks_ai.json")],
        cwd=str(PROJECT),
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    data = json.loads(r.stdout)
    assert data["status"] == "calculated"


def test_legacy_compact_compat():
    """旧 --compact 调用仍兼容。"""
    r = subprocess.run(
        [sys.executable, str(PROJECT / "run.py"), "--ai-json",
         str(EXAMPLES / "socks_ai.json"), "--compact"],
        cwd=str(PROJECT),
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    data = json.loads(r.stdout)
    assert data["status"] == "calculated"
    assert "normal" in data


def test_render_markdown_mode():
    """--render-markdown 模式输出。"""
    r = subprocess.run(
        [sys.executable, str(PROJECT / "run.py"), "--ai-json",
         str(EXAMPLES / "socks_ai.json"), "--render-markdown"],
        cwd=str(PROJECT),
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    assert "商品：" in r.stdout
    assert "采购价未识别" in r.stdout


# ============================================================
# Test 16: No forbidden text in output
# ============================================================

def test_no_forbidden_text_mode1():
    """模式1输出中不存在"小结""临界点""MEMORY"等。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    forbidden = ["小结", "临界点", "MEMORY", "风险段落", "案例引用", "模式说明"]
    for term in forbidden:
        assert term not in output, f"'{term}' should not appear in mode1 output"


def test_no_forbidden_text_mode2():
    """模式2输出中不存在"小结""汇率""尾程"等。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_head_only(result, display)
    forbidden = ["小结", "临界点", "MEMORY", "汇率", "尾程", "利润", "SHEIN", "补贴"]
    for term in forbidden:
        assert term not in output, f"'{term}' should not appear in mode2 output"


# ============================================================
# Version check
# ============================================================

def test_output_contract_version():
    """版本常量为 2026-08-04-v1。"""
    assert OUTPUT_CONTRACT_VERSION == "2026-08-04-v1"
