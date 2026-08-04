"""端到端输出合同测试 — run.py --render-markdown stdout/stderr 契约。

使用 subprocess.run() 真正执行 run.py，不直接调用 renderer。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
GOLDEN = PROJECT / "tests" / "golden"
EXAMPLES = PROJECT / "examples"


def _run_envelope(envelope: dict) -> subprocess.CompletedProcess:
    """通过 subprocess 执行 run.py --stdin --render-markdown。"""
    return subprocess.run(
        [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown"],
        cwd=str(PROJECT),
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True, text=True,
    )


def _run_envelope_debug(envelope: dict) -> subprocess.CompletedProcess:
    """通过 subprocess 执行 run.py --stdin --render-markdown --debug。"""
    return subprocess.run(
        [sys.executable, str(PROJECT / "run.py"), "--stdin", "--render-markdown", "--debug"],
        cwd=str(PROJECT),
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True, text=True,
    )


def _make_mode2_envelope() -> dict:
    """构建模式2信封（pu_small_chain_shoulder_bag）。"""
    with open(EXAMPLES / "pu_small_chain_shoulder_bag_ai.json", encoding="utf-8") as f:
        ai_data = json.load(f)
    return {
        "mode": "head_only",
        "product_display": {
            "title": "PU轻潮斜挎肩部链条包（小方包）",
            "quantity": 1,
            "unit": "件",
            "purchase_price_rmb": 47,
            "domestic_freight_rmb": 5,
            "normal_packaging": "把手折叠、肩带收纳后纸盒装",
            "conservative_packaging": "较少压缩并增加局部五金保护",
            "confidence": "high",
        },
        "ai": ai_data,
    }


def _make_mode1_envelope() -> dict:
    """构建模式1信封（pu_small_chain_shoulder_bag）。"""
    with open(EXAMPLES / "pu_small_chain_shoulder_bag_ai.json", encoding="utf-8") as f:
        ai_data = json.load(f)
    return {
        "mode": "profit",
        "product_display": {
            "title": "PU轻潮斜挎肩部链条包（小方包）",
            "quantity": 1,
            "unit": "件",
            "purchase_price_rmb": 47,
            "domestic_freight_rmb": 5,
            "normal_packaging": "把手折叠、肩带收纳后纸盒装",
            "conservative_packaging": "较少压缩并增加局部五金保护",
            "confidence": "high",
        },
        "profit_parameters": {
            "exchange_rate": 6.7716,
            "tail_fee_usd": 7,
            "target_profit_markup_percent": 25,
            "activity_reserve_percent": 15,
        },
        "ai": ai_data,
    }


class TestMode2E2E:
    """模式2端到端测试"""

    def test_stdout_matches_golden_snapshot(self):
        """stdout逐字符符合模式2黄金快照。"""
        envelope = _make_mode2_envelope()
        r = _run_envelope(envelope)
        assert r.returncode == 0, f"stderr={r.stderr}"
        expected = (GOLDEN / "output_mode2_2026-08-04-v1.md").read_text(encoding="utf-8").rstrip("\n")
        assert r.stdout.strip() == expected, f"Mode2 stdout mismatch!"

    def test_no_code_fence(self):
        """stdout不含代码围栏。"""
        r = _run_envelope(_make_mode2_envelope())
        assert "```" not in r.stdout

    def test_no_calibration_text(self):
        """stdout不含校准说明。"""
        r = _run_envelope(_make_mode2_envelope())
        assert "校准" not in r.stdout
        assert "案例" not in r.stdout

    def test_no_case_id(self):
        """stdout不含案例ID。"""
        r = _run_envelope(_make_mode2_envelope())
        assert "PVC-COSMETIC" not in r.stdout
        assert "PU-001" not in r.stdout

    def test_stderr_empty(self):
        """stderr为空。"""
        r = _run_envelope(_make_mode2_envelope())
        assert r.stderr.strip() == ""

    def test_exit_code_zero(self):
        """exit code=0。"""
        r = _run_envelope(_make_mode2_envelope())
        assert r.returncode == 0


class TestMode1E2E:
    """模式1端到端测试"""

    def test_stdout_matches_golden_snapshot(self):
        """stdout逐字符符合模式1 v2黄金快照。"""
        envelope = _make_mode1_envelope()
        r = _run_envelope(envelope)
        assert r.returncode == 0, f"stderr={r.stderr}"
        expected = (GOLDEN / "output_mode1_2026-08-04-v2.md").read_text(encoding="utf-8").rstrip("\n")
        assert r.stdout.strip() == expected, f"Mode1 stdout mismatch!"

    def test_stderr_empty(self):
        """stderr为空。"""
        r = _run_envelope(_make_mode1_envelope())
        assert r.stderr.strip() == ""

    def test_exit_code_zero(self):
        """exit code=0。"""
        r = _run_envelope(_make_mode1_envelope())
        assert r.returncode == 0


class TestCalibrationHitE2E:
    """校准命中商品端到端测试"""

    def _make_calibration_mode_envelope(self) -> dict:
        """构建命中 PVC-COSMETIC-BAG-001 的信封。
        使用一个虚构 AI JSON，通过 product_display 提供 title/sku 让校准匹配。
        """
        return {
            "mode": "head_only",
            "product_display": {
                "title": "2026新款透明手提化妆包大容量防水包包HelloKitty可爱收纳包JL",
                "selected_sku": "凯蒂猫大包",
                "quantity": 1,
                "unit": "件",
                "purchase_price_rmb": 10,
                "domestic_freight_rmb": 3,
                "normal_packaging": "折叠压扁后袋装",
                "conservative_packaging": "较少压缩后袋装",
                "confidence": "medium",
            },
            "ai": {
                "product_type": "hello_kitty_cosmetic_bag",
                "quantity": 1,
                "category": "general",
                "rigidity": "soft",
                "foldability": "good",
                "compressibility": "good",
                "has_rigid_parts": False,
                "requires_shape_retention": False,
                "overall_form": "soft_bulky",
                "modifiers": ["hollow"],
                "shape_retention_scope": "none",
                "ai_net_weight_kg": 0.16,
                "ai_package_size_cm": [22, 18, 8],
                "ai_package_weight_kg": 0.18,
                "conservative_package_size_cm": [23, 19, 9],
                "conservative_package_weight_kg": 0.2,
                "confidence": "medium",
                "folding_action": "折叠压扁",
                "compression_action": "轻度压缩",
                "reasoning": "PVC软质空心化妆包",
            },
        }

    def test_format_guard_passes(self):
        """格式守卫通过（10行、四行七列表、无第11行）。"""
        r = _run_envelope(self._make_calibration_mode_envelope())
        assert r.returncode == 0, f"Format guard failed, stderr={r.stderr}"
        lines = r.stdout.strip().split("\n")
        assert len(lines) == 10, f"Expected 10 lines, got {len(lines)}"

    def test_no_calibration_description_in_stdout(self):
        """无案例说明。"""
        r = _run_envelope(self._make_calibration_mode_envelope())
        assert "PVC-COSMETIC" not in r.stdout
        assert "校准" not in r.stdout

    def test_lowest_total_head_13(self):
        """最低总头程¥13.00。"""
        r = _run_envelope(self._make_calibration_mode_envelope())
        # 义乌正常 = 0.07*100 + 6 = 13.00
        assert "¥13.00" in r.stdout, f"Expected ¥13.00 in output, got:\n{r.stdout}"

    def test_normal_weight_70g_in_table(self):
        """正常档计费重70g。"""
        r = _run_envelope(self._make_calibration_mode_envelope())
        # 义乌正常行应显示70g计费重
        lines = r.stdout.split("\n")
        yw_normal = [l for l in lines if l.startswith("| 义乌正常 |")][0]
        # 第4列是计费重
        cols = [c.strip() for c in yw_normal.split("|")]
        assert cols[4] == "70", f"Expected 70g for YW Normal, got {cols[4]}"


class TestDebugMode:
    """调试模式测试"""

    def test_case_id_only_in_stderr(self):
        """--debug 时案例ID只出现在stderr。"""
        envelope = {
            "mode": "head_only",
            "product_display": {
                "title": "2026新款透明手提化妆包大容量防水包包HelloKitty可爱收纳包JL",
                "selected_sku": "凯蒂猫大包",
                "quantity": 1,
                "unit": "件",
                "normal_packaging": "袋装",
                "conservative_packaging": "袋装",
                "confidence": "medium",
            },
            "ai": {
                "product_type": "hello_kitty_cosmetic_bag",
                "quantity": 1,
                "category": "general",
                "overall_form": "soft_bulky",
                "modifiers": ["hollow"],
                "ai_net_weight_kg": 0.16,
                "ai_package_size_cm": [22, 18, 8],
                "ai_package_weight_kg": 0.18,
                "conservative_package_size_cm": [23, 19, 9],
                "conservative_package_weight_kg": 0.2,
                "confidence": "medium",
                "folding_action": "折叠压扁",
                "compression_action": "轻度压缩",
            },
        }
        r = _run_envelope_debug(envelope)
        assert r.returncode == 0, f"stderr={r.stderr}"
        # stdout 不含 case ID
        assert "PVC-COSMETIC" not in r.stdout
        # stderr 包含 case ID
        assert "PVC-COSMETIC-BAG-001" in r.stderr
        # stdout 仍符合合同
        assert "```" not in r.stdout


class TestBlindSimilarTransparentBag:
    """相似透明软包盲测 — 不满足精确标题/SKU → 不走精确校准 → 走通用PVC规则"""

    def test_no_exact_calibration_hit(self):
        """不得命中精确案例。"""
        envelope = {
            "mode": "head_only",
            "product_display": {
                "title": "其他品牌透明PVC化妆包收纳袋",
                "selected_sku": "大号透明包",
                "quantity": 1,
                "unit": "件",
                "normal_packaging": "袋装",
                "conservative_packaging": "袋装",
                "confidence": "medium",
            },
            "ai": {
                "product_type": "transparent_pvc_cosmetic_bag",
                "category": "general",
                "rigidity": "soft",
                "foldability": "good",
                "compressibility": "good",
                "overall_form": "unknown",
                "material_family": "pvc",
                "dimension_scope": "display_size",
                "modifiers": ["hollow"],
                "ai_net_weight_kg": 0.16,
                "ai_package_size_cm": [22, 18, 8],
                "ai_package_weight_kg": 0.18,
                "conservative_package_size_cm": [23, 19, 9],
                "conservative_package_weight_kg": 0.2,
                "confidence": "medium",
                "folding_action": "折叠压扁",
                "compression_action": "轻度压缩",
            },
        }
        r = _run_envelope(envelope)
        assert r.returncode == 0, f"stderr={r.stderr}"
        # 不得使用 8~20cm 展示厚度直接计费
        output = r.stdout
        # 检查义乌正常行的计费重，应远低于 22×18×8/8000 = 0.396kg
        lines = output.split("\n")
        yw_normal = [l for l in lines if l.startswith("| 义乌正常 |")]
        if yw_normal:
            cols = [c.strip() for c in yw_normal[0].split("|")]
            cw_g = int(cols[4])
            assert cw_g < 300, f"Chargeable weight {cw_g}g too high, should not use display thickness"

    def test_not_using_semi_rigid_bypass(self):
        """不得通过semi_rigid绕过异常。"""
        envelope = {
            "mode": "head_only",
            "product_display": {
                "title": "其他品牌透明PVC化妆包收纳袋",
                "selected_sku": "大号透明包",
                "quantity": 1,
                "unit": "件",
                "normal_packaging": "袋装",
                "conservative_packaging": "袋装",
                "confidence": "medium",
            },
            "ai": {
                "product_type": "transparent_pvc_cosmetic_bag",
                "category": "general",
                "rigidity": "soft",
                "foldability": "good",
                "compressibility": "good",
                "overall_form": "unknown",
                "material_family": "pvc",
                "modifiers": ["hollow"],
                "ai_net_weight_kg": 0.16,
                "ai_package_size_cm": [22, 18, 8],
                "ai_package_weight_kg": 0.18,
                "conservative_package_size_cm": [23, 19, 9],
                "conservative_package_weight_kg": 0.2,
                "confidence": "medium",
                "folding_action": "折叠压扁",
                "compression_action": "轻度压缩",
            },
        }
        r = _run_envelope(envelope)
        assert r.returncode == 0
        # 输出不应出现 semi_rigid
        assert "semi_rigid" not in r.stdout
