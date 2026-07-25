"""配置读取与基础校验。"""

from __future__ import annotations

import json
from datetime import date, datetime
from math import isfinite
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "logistics_config.json"
DEFAULT_PROFILES_PATH = BASE_DIR / "data" / "package_profiles.json"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    config = _read_json(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    required = {
        "formula_version",
        "volume_divisor",
        "tail_fee_usd",
        "usd_cny_rate",
        "categories",
        "correction_threshold",
    }
    if missing := required.difference(config):
        raise ValueError(f"物流配置缺少字段: {', '.join(sorted(missing))}")
    return config


def load_package_profiles(
    profiles_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(profiles_path) if profiles_path else DEFAULT_PROFILES_PATH
    if not path.is_file():
        return {}
    return _read_json(path)


def normalize_category(value: Any, config: dict[str, Any]) -> str:
    raw = str(value or "").strip()
    category = {"包类": "bag", "非包类": "general"}.get(raw, raw.lower())
    if category not in config["categories"]:
        raise ValueError("category_type 只能是 bag 或 general")
    return category


def positive_number(value: Any, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name}必须是数字，不能是布尔值")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if not isfinite(number):
        raise ValueError(f"{name}必须是有限数字")
    if number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{name} 必须{'大于等于 0' if allow_zero else '大于 0'}")
    return number


def get_exchange_rate_status(
    config: dict[str, Any] | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    config = config or load_config()
    updated_raw = str(config.get("usd_cny_rate_updated_at") or "").strip()
    max_age_days = int(config.get("usd_cny_rate_max_age_days", 7))
    source = str(config.get("usd_cny_rate_source") or "unknown")
    if not updated_raw:
        return {"updated_at": "", "source": source, "age_days": None,
                "max_age_days": max_age_days, "is_stale": True}
    try:
        updated_at = datetime.strptime(updated_raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("usd_cny_rate_updated_at 必须是 YYYY-MM-DD") from exc
    age_days = ((as_of or date.today()) - updated_at).days
    return {"updated_at": updated_raw, "source": source, "age_days": age_days,
            "max_age_days": max_age_days, "is_stale": age_days > max_age_days}
