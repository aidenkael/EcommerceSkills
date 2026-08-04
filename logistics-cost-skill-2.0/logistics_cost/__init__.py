"""物流成本核算核心包 — OUTPUT_CONTRACT 2026-08-04-v1。"""

from .calculator import (
    calc_chargeable_weight,
    calc_head_cost,
    calc_tail_cost,
    calc_total_cost,
    calc_volume_weight,
    calc_logistics,
    calc_freight_costs,
)
from .config import get_exchange_rate_status, load_config
from .estimator import estimate
from .weight_rules import UserWeight, WEIGHT_INCREMENT_KG
from .ai_schema import AiProductJson, validate, to_estimate_inputs
from .profit_calculator import calculate_profit
from .output_renderer import (
    OUTPUT_CONTRACT_VERSION,
    render_head_only,
    render_profit,
)

__all__ = [
    "load_config",
    "get_exchange_rate_status",
    "calc_volume_weight",
    "calc_chargeable_weight",
    "calc_head_cost",
    "calc_tail_cost",
    "calc_total_cost",
    "calc_logistics",
    "calc_freight_costs",
    "estimate",
    "UserWeight",
    "WEIGHT_INCREMENT_KG",
    "AiProductJson",
    "validate",
    "to_estimate_inputs",
    "calculate_profit",
    "OUTPUT_CONTRACT_VERSION",
    "render_head_only",
    "render_profit",
]
