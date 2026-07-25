from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from logistics_tool.service import EstimatorService


class SmokeTests(unittest.TestCase):
    def test_image_only_analysis_returns_reviewable_result(self):
        service = EstimatorService(ROOT)
        result = service.estimate_analysis({
            "image_path": "data/calibration_images/IMG_065.png",
            "product_name": "黑色眼罩",
            "keywords": ["眼罩", "黑色"],
            "rigidity": "soft",
            "package_type": "OPP袋",
            "confidence": "medium",
            "evidence": "图片显示柔软黑色眼罩",
        })
        self.assertIn(result["recommended_provider"], {"深圳货代", "义乌货代"})
        self.assertGreater(result["chargeable_weight_kg"], 0)
        self.assertGreaterEqual(result["calibration"]["neighbor_count"], 1)
        json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
