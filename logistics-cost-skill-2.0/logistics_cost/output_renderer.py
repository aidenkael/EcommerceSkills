"""确定性输出渲染器 — OUTPUT_CONTRACT_VERSION = 2026-08-04-v2

提供 render_head_only() 和 render_profit() 两个函数, 返回用于最终用户回复的完整 Markdown 字符串。
Agent 不得手工拼接表格, 不得在程序输出后改写/总结/解释/增加/删除/调整顺序。
"""

from __future__ import annotations

from typing import Any

from .profit_calculator import calculate_profit

OUTPUT_CONTRACT_VERSION = "2026-08-04-v2"

# 四行方案的固定顺序
_SCENARIO_ORDER = [
    ("normal", "义乌货代", "义乌正常"),
    ("conservative", "义乌货代", "义乌保守"),
    ("normal", "深圳货代", "深圳正常"),
    ("conservative", "深圳货代", "深圳保守"),
]

_HEAD_TABLE_HEADER = (
    "| 方案 | 包装尺寸（cm） | 包装后重量（g） | 计费重（g） | 纯头程（¥） | 固定费（¥） | 总头程（¥） |\n"
    "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
)

_PROFIT_TABLE_HEADER = (
    "| 国内成本 | 总头程 | 尾程 | 无活动售价 | 无活动利润（补贴状态） | 活动后售价 | 活动后利润（补贴状态） |\n"
    "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
)

_GREEN_SPAN_OPEN = '<span style="color:#16a34a">'
_GREEN_SPAN_CLOSE = '</span>'


def _fmt_price(val: float) -> str:
    return f"{val:.2f}"


def _fmt_rmb(val: float) -> str:
    return f"¥{val:.2f}"


def _fmt_int(val: float) -> str:
    return str(round(val))


def _fmt_usd(val: float) -> str:
    return f"${val:.2f}"


def _fmt_dims(dims: list[float]) -> str:
    if not dims or len(dims) < 3:
        return "—"
    return "×".join(_fmt_int(d) for d in dims[:3])


def _fmt_subsidy_status(subsidy_applied: bool) -> str:
    """生成补贴状态文本。补贴命中用绿色, 无补贴用普通文字。"""
    if subsidy_applied:
        return f"{_GREEN_SPAN_OPEN}补贴命中{_GREEN_SPAN_CLOSE}"
    return "无补贴"


def _fmt_product_summary(display: dict[str, Any]) -> str:
    """生成商品摘要句。"""
    title = display.get("title", "")
    quantity = display.get("quantity", 1)
    unit = display.get("unit", "件")
    purchase = display.get("purchase_price_rmb")
    domestic = display.get("domestic_freight_rmb")
    normal_pkg = display.get("normal_packaging", "")
    conservative_pkg = display.get("conservative_packaging", "")
    confidence = display.get("confidence", "low")

    if purchase is not None:
        purchase_str = f"¥{purchase}"
    else:
        purchase_str = "未识别"

    if domestic is not None:
        domestic_str = f"¥{domestic}"
    else:
        domestic_str = "未识别"

    return (
        f"商品：{title}，{quantity}{unit}；"
        f"采购价{purchase_str}，国内运费{domestic_str}；"
        f"正常档采用{normal_pkg}，保守档采用{conservative_pkg}，"
        f"识别置信度{confidence}。"
    )


def _build_head_table(result: dict[str, Any]) -> str:
    """构建四行七列头程表。"""
    rows = []
    for mode_key, provider_label, scenario_label in _SCENARIO_ORDER:
        mode = result.get(mode_key) or {}
        dims = mode.get("packaged_size_cm", [0, 0, 0])
        pkg_weight_g = round(float(mode.get("packaged_weight_kg", 0)) * 1000)
        cw_g = round(float(mode.get("chargeable_weight_kg", 0)) * 1000)
        costs = (mode.get("provider_costs") or {}).get(provider_label) or {}
        head_freight = float(costs.get("head_freight_rmb", 0))
        sfee = float(costs.get("fixed_service_fee_rmb", costs.get("service_fee_rmb", 0)))
        total = float(costs.get("total_cost_rmb", 0))

        rows.append(
            f"| {scenario_label} "
            f"| {_fmt_dims(dims)} "
            f"| {_fmt_int(pkg_weight_g)} "
            f"| {_fmt_int(cw_g)} "
            f"| {_fmt_price(head_freight)} "
            f"| {_fmt_price(sfee)} "
            f"| {_fmt_price(total)} |"
        )
    return _HEAD_TABLE_HEADER + "\n" + "\n".join(rows)


def _find_lowest_head(result: dict[str, Any]) -> tuple[str, float]:
    """从四种方案中选出最低总头程, 相同时按固定顺序取第一个。"""
    lowest_scenario = ""
    lowest_cost = float("inf")
    for mode_key, provider_label, scenario_label in _SCENARIO_ORDER:
        mode = result.get(mode_key) or {}
        costs = (mode.get("provider_costs") or {}).get(provider_label) or {}
        total = float(costs.get("total_cost_rmb", float("inf")))
        if total < lowest_cost:
            lowest_cost = total
            lowest_scenario = scenario_label
    return lowest_scenario, lowest_cost


def _build_profit_table(
    domestic_cost: float,
    lowest_head: float,
    tail_rmb: float,
    profit_result: dict[str, Any],
) -> str:
    """构建一行七列利润表 (v2: 币种符号在数据单元格, 补贴状态在表头)。"""
    no_activity_price = profit_result.get("no_activity_price_usd", 0)
    no_activity_profit = profit_result.get("no_activity_profit_rmb", 0)
    no_subsidy_applied = profit_result.get("no_activity_subsidy_applied", False)
    activity_price = profit_result.get("activity_price_usd", 0)
    activity_profit = profit_result.get("activity_profit_rmb", 0)
    activity_subsidy_applied = profit_result.get("activity_subsidy_applied", False)

    no_status = _fmt_subsidy_status(no_subsidy_applied)
    act_status = _fmt_subsidy_status(activity_subsidy_applied)

    return (
        _PROFIT_TABLE_HEADER + "\n"
        f"| {_fmt_rmb(domestic_cost)} "
        f"| {_fmt_rmb(lowest_head)} "
        f"| {_fmt_rmb(tail_rmb)} "
        f"| {_fmt_usd(no_activity_price)} "
        f"| {_fmt_rmb(no_activity_profit)}（{no_status}） "
        f"| {_fmt_usd(activity_price)} "
        f"| {_fmt_rmb(activity_profit)}（{act_status}） |"
    )


def _build_parameter_summary(
    exchange_rate: float,
    tail_fee_usd: float,
    tail_rmb: float,
    target_profit_markup_percent: float,
    activity_reserve_percent: float,
    lowest_scenario: str,
    lowest_head: float,
) -> str:
    """生成参数摘要句。"""
    tail_usd_str = f"{tail_fee_usd:.2f}".rstrip("0").rstrip(".") if tail_fee_usd == int(tail_fee_usd) else f"{tail_fee_usd:.2f}"
    profit_pct = round(target_profit_markup_percent)
    reserve_pct = round(activity_reserve_percent)
    return (
        f"当前参数：汇率1 USD＝¥{exchange_rate}；"
        f"售价低于$29时享受SHEIN补贴$2.99；"
        f"尾程${tail_usd_str}＝¥{_fmt_price(tail_rmb)}；"
        f"目标利润率按成本{profit_pct}%；"
        f"活动预留{reserve_pct}%；"
        f"采用最低的{lowest_scenario}总头程¥{_fmt_price(lowest_head)}。"
    )


def _build_deduction_sentence(
    purchase_price: float | None,
    domestic_freight: float | None,
    lowest_scenario: str,
    profit_result: dict[str, Any],
) -> str:
    """生成推算句 (模式1, v2: 补贴状态在表头, 不再在推算句重复)。"""
    if purchase_price is None or domestic_freight is None:
        return "推算：头程已完成；利润部分因采购价或国内运费缺失无法计算。"

    total_cost = profit_result.get("total_cost_rmb", 0)
    no_activity_price = profit_result.get("no_activity_price_usd", 0)
    no_activity_profit = profit_result.get("no_activity_profit_rmb", 0)
    activity_price = profit_result.get("activity_price_usd", 0)
    activity_profit = profit_result.get("activity_profit_rmb", 0)
    show_hint = profit_result.get("show_hint", False)

    base = (
        f"推算：国内成本为采购价¥{purchase_price}＋国内运费¥{domestic_freight}；"
        f"采用{lowest_scenario}后核算成本为¥{_fmt_price(total_cost)}；"
        f"无活动售价为{_fmt_usd(no_activity_price)}，无活动利润为¥{_fmt_price(no_activity_profit)}；"
        f"活动后售价为{_fmt_usd(activity_price)}，活动后利润为¥{_fmt_price(activity_profit)}。"
    )

    if show_hint:
        base += "提示：活动后售价低于$29，已计入$2.99补贴。"

    return base


def _build_head_deduction_sentence(result: dict[str, Any]) -> str:
    """生成推算句 (模式2)。"""
    normal_info = result.get("normal") or {}
    conservative_info = result.get("conservative") or {}

    # 商品主体与可折/可拆部件处理
    summary = result.get("product_summary") or {}
    folding = normal_info.get("folding_action", "")

    # 正常档与保守档的差异
    n_cw = round(float(normal_info.get("chargeable_weight_kg", 0)) * 1000)
    c_cw = round(float(conservative_info.get("chargeable_weight_kg", 0)) * 1000)

    # 计费重来源
    n_vol = round(float(normal_info.get("volume_weight_kg", 0)) * 1000)
    n_pkg = round(float(normal_info.get("packaged_weight_kg", 0)) * 1000)
    if n_vol > n_pkg:
        charge_source = "体积重主导"
    elif n_pkg > n_vol:
        charge_source = "实重主导"
    else:
        charge_source = "实重与体积重接近"

    lowest_scenario, lowest_cost = _find_lowest_head(result)

    return (
        f"推算：{folding or '主体保型'}；"
        f"正常档计费重{n_cw}g，保守档计费重{c_cw}g；"
        f"{charge_source}；"
        f"四种方案中{lowest_scenario}总头程最低，为¥{_fmt_price(lowest_cost)}。"
    )


# ---- 公开入口 ----

def render_head_only(
    result: dict[str, Any],
    product_display: dict[str, Any],
) -> str:
    """模式2：仅头程。返回完整 Markdown。"""
    summary = _fmt_product_summary(product_display)
    head_table = _build_head_table(result)
    deduction = _build_head_deduction_sentence(result)
    return f"{summary}\n\n{head_table}\n\n{deduction}"


def render_profit(
    result: dict[str, Any],
    product_display: dict[str, Any],
    exchange_rate: float,
    tail_fee_usd: float,
    target_profit_markup_percent: float,
    activity_reserve_percent: float,
) -> str:
    """模式1：利润核算。返回完整 Markdown。"""
    purchase_price = product_display.get("purchase_price_rmb")
    domestic_freight = product_display.get("domestic_freight_rmb")

    # 四行头程表
    summary = _fmt_product_summary(product_display)
    head_table = _build_head_table(result)

    # 找到最低头程
    lowest_scenario, lowest_head = _find_lowest_head(result)

    # 尾程人民币
    tail_rmb = round(tail_fee_usd * exchange_rate, 2)

    # 如果缺少采购价或国内运费, 仍保持相同结构但利润单元格显示无法计算
    if purchase_price is not None and domestic_freight is not None:
        domestic_cost = round(purchase_price + domestic_freight, 2)
        # 调用确定性利润计算器 (双售价模型)
        profit_result = calculate_profit(
            product_cost_rmb=purchase_price,
            domestic_freight_rmb=domestic_freight,
            total_head_cost_rmb=lowest_head,
            tail_cost_rmb=tail_rmb,
            exchange_rate=exchange_rate,
            target_profit_markup_percent=target_profit_markup_percent,
            activity_reserve_percent=activity_reserve_percent,
        )
        profit_table = _build_profit_table(domestic_cost, lowest_head, tail_rmb, profit_result)
        deduction = _build_deduction_sentence(purchase_price, domestic_freight, lowest_scenario, profit_result)
    else:
        domestic_cost_str = "无法计算"
        profit_table = (
            _PROFIT_TABLE_HEADER + "\n"
            f"| {domestic_cost_str} "
            f"| {_fmt_rmb(lowest_head)} "
            f"| {_fmt_rmb(tail_rmb)} "
            f"| 无法计算 "
            f"| 无法计算 "
            f"| 无法计算 "
            f"| 无法计算 |"
        )
        deduction = "推算：头程已完成；利润部分因采购价或国内运费缺失无法计算。"

    # 参数摘要
    param_text = _build_parameter_summary(
        exchange_rate, tail_fee_usd, tail_rmb,
        target_profit_markup_percent, activity_reserve_percent,
        lowest_scenario, lowest_head,
    )

    return f"{summary}\n\n{head_table}\n\n{param_text}\n\n{profit_table}\n\n{deduction}"
