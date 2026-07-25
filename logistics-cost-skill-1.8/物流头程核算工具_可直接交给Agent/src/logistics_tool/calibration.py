from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .image_hash import hamming_hex
from .models import ProductAnalysis
from .utils import clamp, jaccard, load_jsonl, percentile, text_tokens, weighted_median


@dataclass
class Neighbor:
    record: dict[str, Any]
    score: float
    image_distance: int | None = None
    exact_sha: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "id": self.record.get("id"),
            "product_label": self.record.get("product_label"),
            "score": round(self.score, 4),
            "image_distance": self.image_distance,
            "actual_cost_rmb": self.record.get("actual_allocated_head_cost_rmb"),
            "legacy_ai_cost_rmb": self.record.get("legacy_ai_cost_rmb"),
            "actual_to_legacy_ratio": self.record.get("actual_to_legacy_ratio"),
            "declared_weight_kg": self.record.get("declared_weight_kg"),
            "declared_dimensions_cm": self.record.get("declared_dimensions_cm"),
            "supplemental_info": self.record.get("supplemental_info"),
        }


class CalibrationStore:
    def __init__(self, root: Path, rules: dict[str, Any]):
        self.root = root
        self.rules = rules
        self.records = load_jsonl(root / "data" / "calibration_records.jsonl")
        self.feedback = load_jsonl(root / "data" / "feedback.jsonl")
        self._prepare()

    def _prepare(self) -> None:
        for rec in self.records:
            text = " ".join(str(rec.get(k) or "") for k in (
                "product_label", "legacy_reason", "supplemental_info", "legacy_classification"
            ))
            rec["_tokens"] = text_tokens(text)
        for idx, rec in enumerate(self.feedback, start=1):
            rec.setdefault("id", f"F{idx}")
            rec.setdefault("product_label", rec.get("product_name") or "用户反馈商品")
            rec.setdefault("rigidity", rec.get("rigidity") or "unknown")
            rec.setdefault("package_type", rec.get("package_type") or "未知")
            rec.setdefault("declared_weight_kg", rec.get("actual_weight_kg"))
            rec.setdefault("declared_dimensions_cm", rec.get("dimensions_cm"))
            rec.setdefault("actual_allocated_head_cost_rmb", rec.get("actual_cost_rmb"))
            if rec.get("actual_to_legacy_ratio") is None:
                actual = rec.get("actual_allocated_head_cost_rmb")
                baseline = rec.get("estimated_head_cost_rmb_at_time")
                if actual is not None and baseline not in (None, 0):
                    rec["actual_to_legacy_ratio"] = float(actual) / float(baseline)
            text = " ".join(str(rec.get(k) or "") for k in (
                "product_label", "product_name", "category", "keywords", "evidence", "notes"
            ))
            rec["_tokens"] = text_tokens(text)
        self.all_records = self.records + self.feedback

    def _record_score(
        self,
        analysis: ProductAnalysis,
        rec: dict[str, Any],
        image_sha256: str | None,
        image_dhash: str | None,
    ) -> Neighbor:
        query_text = " ".join([analysis.product_name, analysis.category, " ".join(analysis.keywords), analysis.evidence, analysis.notes])
        text_score = jaccard(text_tokens(query_text), rec.get("_tokens") or set())
        score = text_score * 0.72
        if text_score > 0:
            if analysis.rigidity != "unknown" and analysis.rigidity == rec.get("rigidity"):
                score += 0.10
            if analysis.package_type != "未知" and analysis.package_type == rec.get("package_type"):
                score += 0.10
        if analysis.fragile and any(x in str(rec.get("legacy_reason") or "") for x in ("玻璃", "陶瓷", "易碎")):
            score += 0.05
        exact_sha = bool(image_sha256 and image_sha256 == rec.get("image_sha256"))
        distance = hamming_hex(image_dhash, rec.get("image_dhash"))
        if exact_sha:
            score += 1.5
        elif distance is not None:
            if distance <= 4:
                score += 1.0
            elif distance <= 8:
                score += 0.65
            elif distance <= 14:
                score += 0.25
        return Neighbor(record=rec, score=score, image_distance=distance, exact_sha=exact_sha)

    def match(
        self,
        analysis: ProductAnalysis,
        image_sha256: str | None = None,
        image_dhash: str | None = None,
    ) -> dict[str, Any]:
        cfg = self.rules["calibration"]
        candidates = [self._record_score(analysis, rec, image_sha256, image_dhash) for rec in self.all_records]
        candidates.sort(key=lambda n: n.score, reverse=True)
        selected = [n for n in candidates if n.score >= float(cfg["min_similarity"])][: int(cfg["max_neighbors"])]
        # Exact/near image matches should never be excluded by weak text.
        visual = [n for n in candidates if n.exact_sha or (n.image_distance is not None and n.image_distance <= 8)]
        merged: list[Neighbor] = []
        seen: set[str] = set()
        for n in visual + selected:
            rid = str(n.record.get("id", ""))
            if rid not in seen:
                merged.append(n)
                seen.add(rid)
        merged.sort(key=lambda n: n.score, reverse=True)
        merged = merged[: int(cfg["max_neighbors"])]

        ratio_values: list[float] = []
        ratio_weights: list[float] = []
        ref_weights: list[float] = []
        ref_weight_weights: list[float] = []
        actual_costs: list[float] = []
        for n in merged:
            weight = max(0.01, n.score)
            ratio = n.record.get("actual_to_legacy_ratio")
            if ratio is not None:
                ratio_values.append(float(ratio))
                ratio_weights.append(weight)
            ref = n.record.get("declared_weight_kg") or n.record.get("legacy_ai_chargeable_weight_kg")
            if ref is not None and float(ref) > 0:
                ref_weights.append(float(ref))
                ref_weight_weights.append(weight)
            actual = n.record.get("actual_allocated_head_cost_rmb")
            if actual is not None:
                actual_costs.append(float(actual))

        ratio = weighted_median(ratio_values, ratio_weights)
        if ratio is not None:
            lo, hi = cfg["ratio_clip"]
            ratio = clamp(float(ratio), float(lo), float(hi))
        reference_weight = weighted_median(ref_weights, ref_weight_weights)
        top = merged[0] if merged else None
        exact = bool(top and top.exact_sha)
        near_duplicate = bool(top and top.image_distance is not None and top.image_distance <= 4)
        strong = bool(top and top.score >= 0.65)

        if exact:
            strength = float(cfg["exact_duplicate_correction_strength"])
        elif near_duplicate:
            strength = float(cfg["near_duplicate_correction_strength"])
        elif strong:
            strength = float(cfg["strong_match_correction_strength"])
        else:
            strength = float(cfg["default_correction_strength"])

        return {
            "neighbor_count": len(merged),
            "top_similarity": round(top.score, 4) if top else 0.0,
            "exact_image_match": exact,
            "near_duplicate_image_match": near_duplicate,
            "historical_correction_ratio": ratio,
            "correction_strength": strength,
            "reference_weight_kg": reference_weight,
            "historical_actual_cost_rmb": {
                "min": min(actual_costs) if actual_costs else None,
                "q1": percentile(actual_costs, 0.25),
                "median": percentile(actual_costs, 0.50),
                "q3": percentile(actual_costs, 0.75),
                "max": max(actual_costs) if actual_costs else None,
            },
            "neighbors": [n.public() for n in merged],
        }
