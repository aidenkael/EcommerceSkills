"""业务规则上下文比较。"""

RULE_CONTEXT_KEYS = (
    "forwarder",
    "head_haul_rate",
    "fixed_service_fee",
    "tail_haul_cost",
    "volume_divisor",
    "exchange_rate",
    "rule_version",
)


def compare_rule_contexts(saved, current, tolerance=0.001):
    """返回规则差异，包含缺失值与已有值之间的变化。"""
    saved = saved or {}
    current = current or {}
    differences = {}
    for key in RULE_CONTEXT_KEYS:
        old = saved.get(key)
        new = current.get(key)
        if old is None or new is None:
            if old != new:
                differences[key] = (old, new)
            continue
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            if abs(float(old) - float(new)) > tolerance:
                differences[key] = (old, new)
        elif old != new:
            differences[key] = (old, new)
    return differences
