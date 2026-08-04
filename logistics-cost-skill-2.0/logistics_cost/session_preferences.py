"""会话偏好管理 — 模式与利润参数持久化。

提供 load/update/get_mode/set_mode/get_profit_params/update_profit_params。
保存到 config/local_user_preferences.json（被 Git 忽略）。
采用安全写入：先写临时文件，成功后原子替换。
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _prefs_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "local_user_preferences.json"


def load() -> dict:
    try:
        p = _prefs_path()
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            text = f.read().strip()
            if not text:
                return {}
            return json.loads(text) or {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save(prefs: dict) -> None:
    """安全写入：临时文件 + 原子替换。"""
    p = _prefs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(prefs, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp", prefix=".prefs_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(p))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


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


def resolve_mode(envelope_mode: str | None) -> tuple[str | None, str | None]:
    """解析运行模式。

    Returns:
        (mode, error_reason)
        mode=None 且 error_reason 非空时表示需要用户选择模式。
    """
    if envelope_mode and envelope_mode in ("head_only", "profit"):
        set_mode(envelope_mode)
        return (envelope_mode, None)

    # 信封提供了无效的 mode 值
    if envelope_mode and envelope_mode not in ("head_only", "profit"):
        return (None, "mode_required")

    saved = get_mode()
    if saved:
        return (saved, None)

    return (None, "mode_required")
