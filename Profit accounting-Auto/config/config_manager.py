"""
配置管理器 v2

支持双货代规则（深圳/义乌），通过 DatabaseManager 的 route_config 表持久化。
"""

VOLUME_DIVISOR = 8000
DEFAULT_TAIL_HAUL = 40.0

FORWARDER_LABELS = {
    "shenzhen": "深圳",
    "yiwu": "义乌",
}


class ConfigManager:
    """运行时配置读写封装"""

    def __init__(self, db_manager):
        self._db = db_manager

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self._db.get_config(key)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def set_float(self, key: str, value: float):
        self._db.set_config(key, str(value))

    # ─── 全局配置 ──────────────────────────────────────────

    @property
    def exchange_rate(self) -> float:
        return self.get_float("exchange_rate", 7.20)

    @exchange_rate.setter
    def exchange_rate(self, val: float):
        self.set_float("exchange_rate", val)

    @property
    def default_tail_haul(self) -> float:
        return self.get_float("default_tail_haul", DEFAULT_TAIL_HAUL)

    @default_tail_haul.setter
    def default_tail_haul(self, val: float):
        self.set_float("default_tail_haul", val)

    @property
    def volume_divisor(self) -> int:
        return VOLUME_DIVISOR

    # ─── 货代规则 ──────────────────────────────────────────

    def get_route_rates(self, forwarder: str) -> dict | None:
        """获取货代费率 {head_haul_rate, fixed_service_fee}"""
        return self._db.get_route_rates(forwarder)

    def get_all_routes(self) -> list[dict]:
        return self._db.get_all_routes()

    def get_forwarder_label(self, forwarder: str) -> str:
        return FORWARDER_LABELS.get(forwarder, forwarder or "未知")

    @property
    def rule_version(self) -> int:
        return self._db.get_rule_version()

    # ─── 兼容旧属性（已移除 head_haul_rate / fixed_service_fee 全局属性）───
    # 这些现在由货代决定，不再全局配置
