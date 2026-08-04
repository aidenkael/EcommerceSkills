"""输出合同锁定测试 — OUTPUT_CONTRACT 2026-08-04-v2。

测试覆盖 16 项针对性检查：
1. 模式2黄金快照逐字符一致（保持不变）
2. 模式1黄金快照逐字符一致（v2）
3. 第一张表固定四行顺序
4. 第二张表固定七列且只有一行
5. 四种方案选择最低总头程
6. 相同总头程按固定顺序选择
7. 活动后利润包含补贴后等于目标利润
8. 活动后无补贴时仍等于目标利润
9. 无活动无补贴、活动后命中补贴 → show_hint=True
10. 无活动和活动后均命中补贴 → show_hint=False
11. 两个场景均无补贴 → show_hint=False
12. 售价未舍入值小于29时命中补贴
13. 售价正好29时无补贴
14. 表头不再包含（¥）和（USD）
15. 人民币数据带¥，美元售价数据带$
16. 补贴命中使用绿色span，无补贴不使用颜色
17. 第二张表仍为一行七列
18. 第一张头程表完全不变
19. 模式2黄金快照完全不变
20. 输出中不增加独立补贴列或额外段落
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
    _GREEN_SPAN_OPEN, _GREEN_SPAN_CLOSE,
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
    """模式2快照逐字符一致（v1保持不变）。"""
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
    """模式1快照逐字符一致（v2）。"""
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
    expected = (GOLDEN / "output_mode1_2026-08-04-v2.md").read_text(encoding="utf-8").rstrip("\n")
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
        if "国内成本 |" in line:
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
# Test 7 & 8: Profit calculation formulas (v2)
# ============================================================

def test_activity_profit_equals_target_with_subsidy():
    """活动后利润包含补贴后等于目标利润 C×t。"""
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
    # Activity profit should equal target profit
    assert abs(result["activity_profit_rmb"] - result["target_profit_rmb"]) < 0.02


def test_activity_profit_equals_target_no_subsidy():
    """活动后无补贴时仍等于目标利润。"""
    from logistics_cost.profit_calculator import calculate_profit

    # 高成本让售价远超$29, 不触发补贴
    result = calculate_profit(
        product_cost_rmb=80, domestic_freight_rmb=5,
        total_head_cost_rmb=60, tail_cost_rmb=47,
        exchange_rate=6.7716,
        target_profit_markup_percent=20, activity_reserve_percent=10,
    )
    # C = 80+5+60+47 = 192
    assert result["total_cost_rmb"] == 192.00
    assert result["activity_subsidy_applied"] == False
    # P = 192 * 0.20 = 38.40
    assert result["target_profit_rmb"] == 38.40
    # Activity profit should equal target profit even without subsidy
    assert abs(result["activity_profit_rmb"] - result["target_profit_rmb"]) < 0.02


# ============================================================
# Test 9-11: Subsidy state combinations and hint
# ============================================================

def test_no_activity_no_subsidy_activity_subsidy_hint():
    """无活动无补贴、活动后命中补贴 → show_hint=True。"""
    from logistics_cost.profit_calculator import calculate_profit

    # 调整参数让无活动售价 >= 29 但活动后 < 29
    # C=149, 无补贴时 no_activity = 149*1.25/6.7716 = 27.50 < 29 → 有补贴
    # 需要更低成本或更高汇率让无活动 >= 29
    result = calculate_profit(
        product_cost_rmb=60, domestic_freight_rmb=5,
        total_head_cost_rmb=50, tail_cost_rmb=50,
        exchange_rate=6.8,
        target_profit_markup_percent=20, activity_reserve_percent=15,
    )
    # C = 60+5+50+50 = 165
    # candidate = 165*1.20/6.8 = 198/6.8 = 29.117... >= 29 → no subsidy for activity
    # activity_price = 29.117 > 29 → no subsidy
    # So this gives both no subsidy. Let me try a different approach.
    
    # Need: no_activity >= 29, activity candidate < 29
    # no_activity = activity_price / (1-d), activity_price = candidate - S (if candidate < 29)
    # So: (candidate - S) / 0.85 >= 29 → candidate >= 29*0.85 + 2.99 = 24.65 + 2.99 = 27.64
    # Also: candidate < 29
    # So: 27.64 <= candidate < 29
    # E.g. candidate = 28.0
    # C * (1+t) / r = 28.0 → C * (1+t) = 28.0 * r
    # With r=6.7716, t=0.2: C = 28.0 * 6.7716 / 1.2 = 158.00
    # Let me try: C=158, t=20%, r=6.7716, d=15%
    result = calculate_profit(
        product_cost_rmb=53, domestic_freight_rmb=5,
        total_head_cost_rmb=52.6, tail_cost_rmb=47.4,
        exchange_rate=6.7716,
        target_profit_markup_percent=20, activity_reserve_percent=15,
    )
    # C = 53+5+52.6+47.4 = 158.00
    # candidate = 158*1.2/6.7716 = 189.6/6.7716 = 28.00
    # 28.00 < 29 → activity_subsidy = 2.99
    # activity_price = 28.00 - 2.99 = 25.01
    # no_activity_price = 25.01/0.85 = 29.42
    # 29.42 >= 29 → no_activity_subsidy = 0
    # show_hint = True
    print(f"no_activity_price: {result['no_activity_price_usd']}")
    print(f"no_activity_subsidy: {result['no_activity_subsidy_usd']}")
    print(f"activity_price: {result['activity_price_usd']}")
    print(f"activity_subsidy: {result['activity_subsidy_usd']}")
    print(f"show_hint: {result['show_hint']}")
    
    assert result["no_activity_subsidy_applied"] == False, "No-activity should have no subsidy"
    assert result["activity_subsidy_applied"] == True, "Activity should have subsidy"
    assert result["show_hint"] == True, "Should show hint when no-activity no subsidy but activity has subsidy"


def test_both_have_subsidy_no_hint():
    """无活动和活动后均命中补贴 → show_hint=False。"""
    from logistics_cost.profit_calculator import calculate_profit

    result = calculate_profit(
        product_cost_rmb=47, domestic_freight_rmb=5,
        total_head_cost_rmb=49.60, tail_cost_rmb=47.40,
        exchange_rate=6.7716,
        target_profit_markup_percent=25, activity_reserve_percent=15,
    )
    # Both prices < $29, both get subsidy
    assert result["no_activity_subsidy_applied"] == True
    assert result["activity_subsidy_applied"] == True
    assert result["show_hint"] == False


def test_neither_has_subsidy_no_hint():
    """两个场景均无补贴 → show_hint=False。"""
    from logistics_cost.profit_calculator import calculate_profit

    # 高成本让售价远超$29
    result = calculate_profit(
        product_cost_rmb=100, domestic_freight_rmb=5,
        total_head_cost_rmb=80, tail_cost_rmb=50,
        exchange_rate=6.7716,
        target_profit_markup_percent=20, activity_reserve_percent=10,
    )
    # C = 100+5+80+50 = 235, candidate = 235*1.2/6.7716 = 41.64 > 29
    assert result["no_activity_subsidy_applied"] == False
    assert result["activity_subsidy_applied"] == False
    assert result["show_hint"] == False


# ============================================================
# Test 12-13: SHEIN subsidy boundary
# ============================================================

def test_subsidy_applied_when_unrounded_below_29():
    """售价未舍入值小于29时命中补贴。"""
    from logistics_cost.profit_calculator import calculate_profit, _get_shein_subsidy_config, _apply_subsidy

    cfg = _get_shein_subsidy_config()
    # 28.999 should get subsidy
    assert _apply_subsidy(28.999, cfg) == 2.99
    # 28.994 rounded to 2dp = 28.99 but raw is 28.994 → should get subsidy
    assert _apply_subsidy(28.994, cfg) == 2.99


def test_subsidy_not_applied_at_exactly_29():
    """售价等于29.00时补贴不生效。"""
    from logistics_cost.profit_calculator import _get_shein_subsidy_config, _apply_subsidy

    cfg = _get_shein_subsidy_config()
    # 29.0 should NOT get subsidy
    assert _apply_subsidy(29.0, cfg) == 0.0


# ============================================================
# Test 14-15: Table format (v2 changes)
# ============================================================

def test_profit_table_header_no_currency_in_header():
    """第二张表表头不再包含（¥）和（USD）。"""
    from logistics_cost.output_renderer import _PROFIT_TABLE_HEADER
    assert "（¥）" not in _PROFIT_TABLE_HEADER, "Header should not contain (¥)"
    assert "（USD）" not in _PROFIT_TABLE_HEADER, "Header should not contain (USD)"


def test_rmb_cells_use_yen_symbol():
    """人民币数据单元格带¥符号。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    # Find profit data row
    for line in output.split("\n"):
        if line.startswith("| ¥"):
            assert "¥" in line, "RMB cells should use ¥ symbol"
            return
    pytest.fail("No RMB cell found in profit table")


def test_usd_cells_use_dollar_symbol():
    """美元售价数据单元格带$符号。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    # Find profit data row
    for line in output.split("\n"):
        if line.startswith("| ¥"):
            assert "$" in line, "USD cells should use $ symbol"
            return
    pytest.fail("No USD cell found in profit table")


# ============================================================
# Test 16-17: Subsidy status visual
# ============================================================

def test_subsidy_hit_uses_green_span():
    """补贴命中使用绿色span标签。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    assert _GREEN_SPAN_OPEN in output, "Should contain green span for subsidy hit"
    assert "补贴命中" in output, "Should contain '补贴命中' text"


def test_no_subsidy_does_not_use_green_span():
    """无补贴时使用'无补贴'文字，不使用颜色。"""
    from logistics_cost.output_renderer import _fmt_subsidy_status
    status = _fmt_subsidy_status(False)
    assert _GREEN_SPAN_OPEN not in status, "No subsidy should not use green span"
    assert status == "无补贴", f"Expected '无补贴', got '{status}'"


# ============================================================
# Test 18: Head table unchanged (v2)
# ============================================================

def test_head_table_unchanged_in_v2():
    """第一张头程表完全不变。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    # Check head table header unchanged
    assert "| 方案 | 包装尺寸（cm） | 包装后重量（g） | 计费重（g） | 纯头程（¥） | 固定费（¥） | 总头程（¥） |" in output


# ============================================================
# Test 19: Missing data behavior
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
# Test 20: Legacy compatibility
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
# Test 21: No forbidden text in output
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
# Test 22: No independent subsidy column or extra paragraph
# ============================================================

def test_no_independent_subsidy_column():
    """输出中不增加独立补贴列。"""
    result = _load_and_estimate("pu_small_chain_shoulder_bag_ai.json")
    display = {"title": "test", "quantity": 1, "unit": "件",
               "purchase_price_rmb": 47, "domestic_freight_rmb": 5,
               "confidence": "low", "normal_packaging": "袋装", "conservative_packaging": "加保护"}
    output = render_profit(result, display,
                          exchange_rate=6.7716, tail_fee_usd=7,
                          target_profit_markup_percent=25, activity_reserve_percent=15)
    # Make sure no standalone "补贴" column exists (should only be in "补贴状态" column headers)
    profit_section = output.split("当前参数：")[1] if "当前参数：" in output else ""
    assert "| 补贴" not in profit_section and "| 补贴列" not in output


# ============================================================
# Version check
# ============================================================

def test_output_contract_version():
    """版本常量为 2026-08-04-v2。"""
    assert OUTPUT_CONTRACT_VERSION == "2026-08-04-v2"
