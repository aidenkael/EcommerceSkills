from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .calibration import CalibrationStore
from .calculator import calculate
from .config import ProjectConfig
from .image_hash import dhash_file, sha256_file
from .models import ProductAnalysis
from .utils import append_jsonl
from .vision import VisionAnalyzer


class EstimatorService:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.config = ProjectConfig(self.root)
        self.calibration = CalibrationStore(self.root, self.config.rules)
        self.vision = VisionAnalyzer(self.root)

    def estimate_analysis(
        self,
        raw: dict[str, Any],
        *,
        tail_cost_rmb: float | None = None,
        other_fixed_cost_rmb: float | None = None,
    ) -> dict[str, Any]:
        analysis = ProductAnalysis.from_dict(raw)
        image_path = self._resolve_image(analysis.image_path) if analysis.image_path else None
        image_sha = sha256_file(image_path) if image_path and image_path.exists() else None
        image_dhash = dhash_file(image_path) if image_path and image_path.exists() else None
        signal = self.calibration.match(analysis, image_sha256=image_sha, image_dhash=image_dhash)
        result = calculate(
            analysis,
            self.config.rules,
            signal,
            tail_cost_rmb=tail_cost_rmb,
            other_fixed_cost_rmb=other_fixed_cost_rmb,
        )
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        result["image_sha256"] = image_sha
        result["image_dhash"] = image_dhash
        return result

    def estimate_image(self, image_path: Path, provider: str = "auto") -> dict[str, Any]:
        resolved = image_path.resolve()
        raw = self.vision.analyze(resolved, provider=provider)
        raw["image_path"] = self._relative_or_absolute(resolved)
        raw["provider"] = self.vision.detect_provider(provider)
        return self.estimate_analysis(raw)

    def add_feedback(self, feedback: dict[str, Any]) -> None:
        feedback = dict(feedback)
        feedback.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        image_value = str(feedback.get("image_path") or "")
        if image_value:
            image_path = self._resolve_image(image_value)
            if image_path.exists():
                feedback.setdefault("image_sha256", sha256_file(image_path))
                feedback.setdefault("image_dhash", dhash_file(image_path))
        if feedback.get("actual_allocated_head_cost_rmb") is None and feedback.get("actual_cost_rmb") is not None:
            feedback["actual_allocated_head_cost_rmb"] = feedback["actual_cost_rmb"]
        feedback.setdefault("declared_weight_kg", feedback.get("actual_weight_kg"))
        feedback.setdefault("declared_dimensions_cm", feedback.get("dimensions_cm"))
        feedback.setdefault("product_label", feedback.get("product_name") or "用户反馈商品")
        append_jsonl(self.root / "data" / "feedback.jsonl", feedback)

    def _resolve_image(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.root / path).resolve()

    def _relative_or_absolute(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)
