"""
配置管理器

汇率和固定物流参数通过 DatabaseManager 的 config 表持久化。
ConfigManager 是对 DatabaseManager 配置功能的轻量封装。
"""


class ConfigManager:
    """运行时配置读写封装"""

    def __init__(self, db_manager):
        self._db = db_manager

    def get_float(self, key: str, default: float = 0.0) -> float:
        """读取浮点配置"""
        val = self._db.get_config(key)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def set_float(self, key: str, value: float):
        """写入浮点配置"""
        self._db.set_config(key, str(value))

    def get_str(self, key: str, default: str = "") -> str:
        """读取字符串配置"""
        val = self._db.get_config(key)
        return val if val is not None else default

    def set_str(self, key: str, value: str):
        """写入字符串配置"""
        self._db.set_config(key, value)

    # 便捷属性

    @property
    def exchange_rate(self) -> float:
        """汇率 (1 USD = ? RMB)"""
        return self.get_float("exchange_rate", 7.20)

    @exchange_rate.setter
    def exchange_rate(self, val: float):
        self.set_float("exchange_rate", val)

    @property
    def head_haul_rate(self) -> float:
        """头程单价 (元/kg)"""
        return self.get_float("head_haul_rate", 100.0)

    @head_haul_rate.setter
    def head_haul_rate(self, val: float):
        self.set_float("head_haul_rate", val)

    @property
    def fixed_service_fee(self) -> float:
        """固定服务费 (元)"""
        return self.get_float("fixed_service_fee", 6.0)

    @fixed_service_fee.setter
    def fixed_service_fee(self, val: float):
        self.set_float("fixed_service_fee", val)

    @property
    def default_tail_haul(self) -> float:
        """默认尾程费用 (元)"""
        return self.get_float("default_tail_haul", 40.0)

    @default_tail_haul.setter
    def default_tail_haul(self, val: float):
        self.set_float("default_tail_haul", val)
