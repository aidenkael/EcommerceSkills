"""会话偏好测试 — session_preferences.py。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from logistics_cost.session_preferences import (
    load, get_mode, set_mode, get_profit_params, update_profit_params, resolve_mode,
)

# 替换内部路径为临时目录
@pytest.fixture(autouse=True)
def _patch_prefs_path(monkeypatch, tmp_path):
    p = tmp_path / "local_user_preferences.json"
    monkeypatch.setattr("logistics_cost.session_preferences._prefs_path", lambda: p)
    yield


class TestFirstNoMode:
    def test_none_envelope_none_saved_returns_mode_required(self):
        mode, error = resolve_mode(None)
        assert mode is None
        assert error == "mode_required"

    def test_empty_envelope_returns_mode_required(self):
        mode, error = resolve_mode("")
        assert mode is None
        assert error == "mode_required"


class TestExplicitSelection:
    def test_set_head_only_then_reuse(self):
        set_mode("head_only")
        assert get_mode() == "head_only"
        mode, error = resolve_mode(None)
        assert mode == "head_only"
        assert error is None

    def test_set_profit_then_reuse(self):
        set_mode("profit")
        assert get_mode() == "profit"
        mode, error = resolve_mode(None)
        assert mode == "profit"
        assert error is None

    def test_explicit_switch(self):
        set_mode("head_only")
        set_mode("profit")
        assert get_mode() == "profit"


class TestEnvelopeOverrides:
    def test_envelope_mode_overrides_saved(self):
        set_mode("head_only")
        mode, error = resolve_mode("profit")
        assert mode == "profit"
        assert get_mode() == "profit"  # 已保存新值

    def test_envelope_invalid_mode_ignored(self):
        set_mode("head_only")
        mode, error = resolve_mode("bad_mode")
        assert mode is None
        assert error == "mode_required"


class TestFileNotFound:
    def test_no_file_returns_none(self, tmp_path):
        assert get_mode() is None


class TestCorruptJSON:
    def test_broken_json_no_crash(self, monkeypatch, tmp_path):
        p = tmp_path / "local_user_preferences.json"
        p.write_text("this is not json", encoding="utf-8")
        monkeypatch.setattr("logistics_cost.session_preferences._prefs_path", lambda: p)
        assert get_mode() is None


class TestInvalidMode:
    def test_raises_on_invalid_mode(self):
        with pytest.raises(ValueError):
            set_mode("invalid")


class TestProfitParams:
    def test_update_and_read(self):
        update_profit_params({"exchange_rate": 7.0, "tail_fee_usd": 5.0})
        params = get_profit_params()
        assert params["exchange_rate"] == 7.0
        assert params["tail_fee_usd"] == 5.0

    def test_null_not_update(self):
        update_profit_params({"exchange_rate": None})
        assert get_mode() is None  # 未设置模式，exchange_rate 也不会变


class TestAtomicWrite:
    def test_write_then_read(self):
        set_mode("head_only")
        update_profit_params({"exchange_rate": 6.8, "tail_fee_usd": 5.88})
        mode = get_mode()
        params = get_profit_params()
        assert mode == "head_only"
        assert params["exchange_rate"] == 6.8
