"""Deterministic, single-rule profit adjustment evaluation."""

from decimal import Decimal, InvalidOperation


CONDITION_FIELDS = {
    "final_price_usd", "final_price_rmb", "product_cost_rmb", "logistics_cost_rmb", None,
}
OPERATORS = {"<", "<=", ">", ">=", "=="}
DIRECTIONS = {"income", "cost"}
TYPES = {"fixed", "percent"}
CURRENCIES = {"USD", "RMB"}
PERCENTAGE_BASES = {"final_price_rmb", "product_cost_rmb", "logistics_cost_rmb"}


def _decimal(value):
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


def validate_rule_values(rule):
    name = str(rule.get("display_name", "")).strip()
    condition_field = rule.get("condition_field") or None
    operator = rule.get("condition_operator") or None
    condition_value = _decimal(rule.get("condition_value"))
    direction = rule.get("adjustment_direction")
    adjustment_type = rule.get("adjustment_type")
    adjustment_value = _decimal(rule.get("adjustment_value"))
    currency = rule.get("currency")
    percentage_base = rule.get("percentage_base") or None
    if not name or len(name) > 60:
        raise ValueError("规则名称必须为1至60个字符")
    if condition_field not in CONDITION_FIELDS:
        raise ValueError("条件字段无效")
    if condition_field is None:
        if operator is not None or rule.get("condition_value") not in (None, ""):
            raise ValueError("无条件规则不能填写比较方式或阈值")
    elif operator not in OPERATORS or condition_value is None:
        raise ValueError("条件规则必须填写有效比较方式和阈值")
    if direction not in DIRECTIONS or adjustment_type not in TYPES or currency not in CURRENCIES:
        raise ValueError("调整方向、类型或币种无效")
    if adjustment_value is None or adjustment_value < 0:
        raise ValueError("调整金额或比例必须为有限且非负的数字")
    if adjustment_type == "percent":
        if percentage_base not in PERCENTAGE_BASES:
            raise ValueError("百分比规则必须明确选择计算基数")
    elif percentage_base is not None:
        raise ValueError("固定金额规则不能设置百分比基数")
    return {
        "display_name": name, "condition_field": condition_field,
        "condition_operator": operator, "condition_value": None if condition_value is None else float(condition_value),
        "adjustment_direction": direction, "adjustment_type": adjustment_type,
        "adjustment_value": float(adjustment_value), "currency": currency,
        "percentage_base": percentage_base,
    }


def evaluate_rule(rule, context, exchange_rate):
    """Return an immutable calculation record; amounts are normalised to RMB."""
    if not rule:
        return {"selected": False, "matched": False, "reason": "未选择规则", "adjustment_rmb": 0.0}
    exchange = _decimal(exchange_rate)
    if exchange is None or exchange <= 0:
        return {"selected": True, "matched": False, "reason": "汇率无效", "adjustment_rmb": 0.0}
    condition_field = rule.get("condition_field") or None
    condition_value = _decimal(rule.get("condition_value"))
    actual_value = _decimal(context.get(condition_field)) if condition_field else None
    if condition_field:
        if actual_value is None:
            label = "最终售价" if condition_field.startswith("final_price") else "条件输入"
            return {"selected": True, "matched": False, "reason": f"缺少{label}", "condition_input": None, "adjustment_rmb": 0.0}
        comparison = {"<": actual_value < condition_value, "<=": actual_value <= condition_value,
                      ">": actual_value > condition_value, ">=": actual_value >= condition_value,
                      "==": actual_value == condition_value}[rule.get("condition_operator")]
        if not comparison:
            return {"selected": True, "matched": False, "reason": "不满足条件", "condition_input": float(actual_value), "adjustment_rmb": 0.0}
    value = _decimal(rule.get("adjustment_value"))
    if rule.get("adjustment_type") == "percent":
        base = _decimal(context.get(rule.get("percentage_base")))
        if base is None:
            return {"selected": True, "matched": False, "reason": "缺少百分比计算基数", "adjustment_rmb": 0.0}
        amount_rmb = base * value / Decimal("100")
        amount_original = value
    else:
        amount_original = value
        amount_rmb = value * exchange if rule.get("currency") == "USD" else value
    signed = amount_rmb if rule.get("adjustment_direction") == "income" else -amount_rmb
    return {"selected": True, "matched": True, "reason": "满足条件", "condition_input": float(actual_value) if actual_value is not None else None,
            "amount_original": float(amount_original), "currency": rule.get("currency"),
            "exchange_rate": float(exchange), "adjustment_rmb": float(signed)}
