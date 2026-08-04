"""会话偏好管理 — 模式与利润参数持久化。

提供 load/update/get_mode/get_profit_params 四个函数。
保存到 config/local_user_preferences.json（被 Git 忽略）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 偏好文件路径
def _prefs_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "local_user_preferences.json"


def load() -> dict:
    try:
        with open(_prefs_path(), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(prefs: dict) -> None:
    with open(_prefs_path(), "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)


def get_mode() -> str | None:
    """返回保存的模式：'head_only' / 'profit' / None（未选择）。"""
    prefs = load()
    mode = prefs.get("active_mode")
    if mode in ("head_only", "profit"):
        return mode
    return None


def set_mode(mode: str) -> None:
    """保存当前模式，仅接受 'head_only' 或 'profit'。"""
    if mode not in ("head_only", "profit"):
        raise ValueError(f"无效模式: {mode}")
    prefs = load()
    prefs["active_mode"] = mode
    _save(prefs)


def get_profit_params() -> dict:
    """读取利润模式参数。"""
    prefs = load()
    return {
        "exchange_rate": prefs.get("exchange_rate"),
        "tail_fee_usd": prefs.get("tail_fee_usd"),
        "target_profit_markup_percent": prefs.get("target_profit_markup_percent"),
        "activity_reserve_percent": prefs.get("activity_reserve_percent"),
    }


def update_profit_params(params: dict) -> None:
    """更新利润参数。"""
    prefs = load()
    for key in ("exchange_rate", "tail_fee_usd", "target_profit_markup_percent", "activity_reserve_percent"):
        if key in params and params[key] is not None:
            prefs[key] = params[key]
    _save(prefs)
