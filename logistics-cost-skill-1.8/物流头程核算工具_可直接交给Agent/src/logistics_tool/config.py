from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import load_json


class ProjectConfig:
    def __init__(self, root: Path):
        self.root = root
        self.rules: dict[str, Any] = load_json(root / "config" / "freight_rules.json")
        self.runtime: dict[str, Any] = load_json(root / "config" / "runtime.json")

    @property
    def divisor(self) -> float:
        return float(self.rules["volume_weight_divisor_cm3_per_kg"])

    @property
    def package_adjustments(self) -> dict[str, Any]:
        return self.rules["package_adjustments"]

    @property
    def providers(self) -> dict[str, Any]:
        return {k: v for k, v in self.rules["providers"].items() if v.get("enabled", True)}
