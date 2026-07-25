from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from logistics_tool.service import EstimatorService


class RuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = EstimatorService(ROOT)

    def test_calibration_count(self):
        self.assertEqual(len(self.service.calibration.records), 79)

    def test_yiwu_cheaper_below_crossover(self):
        result = self.service.estimate_analysis({
            "image_path": "",
            "product_name": "测试小饰品",
            "rigidity": "hard",
            "package_type": "未知",
            "packed_weight_kg": 0.10,
            "packed_dimensions_cm": [1, 1, 1],
            "confidence": "high",
        })
        self.assertEqual(result["recommended_provider"], "义乌货代")
        w = result["chargeable_weight_kg"]
        self.assertAlmostEqual(result["provider_costs"]["深圳货代"]["estimated_cost_rmb"], 80.0 * w + 10.0, places=2)
        self.assertAlmostEqual(result["provider_costs"]["义乌货代"]["estimated_cost_rmb"], 100.0 * w + 6.0, places=2)

    def test_shenzhen_cheaper_above_crossover(self):
        result = self.service.estimate_analysis({
            "image_path": "",
            "product_name": "测试重商品",
            "rigidity": "hard",
            "package_type": "未知",
            "packed_weight_kg": 0.50,
            "packed_dimensions_cm": [1, 1, 1],
            "confidence": "high",
        })
        self.assertEqual(result["recommended_provider"], "深圳货代")
        w = result["chargeable_weight_kg"]
        self.assertAlmostEqual(result["provider_costs"]["深圳货代"]["estimated_cost_rmb"], 80.0 * w + 10.0, places=2)
        self.assertAlmostEqual(result["provider_costs"]["义乌货代"]["estimated_cost_rmb"], 100.0 * w + 6.0, places=2)

    def test_volumetric_weight(self):
        result = self.service.estimate_analysis({
            "image_path": "",
            "product_name": "体积测试",
            "rigidity": "hard",
            "package_type": "未知",
            "packed_weight_kg": 0.05,
            "packed_dimensions_cm": [10, 10, 10],
            "confidence": "high",
        })
        self.assertAlmostEqual(result["volumetric_weight_kg"], 0.125, places=4)
        self.assertAlmostEqual(result["raw_chargeable_weight_kg"], 0.125, places=4)


if __name__ == "__main__":
    unittest.main()
