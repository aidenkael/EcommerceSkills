"""Replay the final local calibration against cleaned v3 samples.

The script never excludes additional samples and reports missing fixtures and
blocked estimates separately.  Use --exclude-added-fixtures to reproduce the
65-sample cohort available at source commit 0ff6260.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, median

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from logistics_cost.ai_schema import estimate_from_ai_json


SOFT_IDS = {
    "CAL-032", "CAL-047", "CAL-049", "CAL-055", "CAL-059",
    "CAL-065", "CAL-068", "CAL-075", "CAL-076",
}
ADDED_FIXTURE_IDS = {"CAL-055", "CAL-059"}


def _metrics(rows: list[dict], mode: str) -> dict:
    errors = [abs(row[mode] - row["actual"]) for row in rows]
    percentages = [
        error / row["actual"] * 100
        for error, row in zip(errors, rows)
        if row["actual"] > 0
    ]
    return {
        "samples": len(rows),
        "mae_rmb": round(mean(errors), 4),
        "median_absolute_error_rmb": round(median(errors), 4),
        "mean_absolute_percentage_error": round(mean(percentages), 4),
        "median_absolute_percentage_error": round(median(percentages), 4),
        "within_5_rmb": sum(error <= 5 for error in errors),
        "overestimate": sum(row[mode] > row["actual"] for row in rows),
        "underestimate": sum(row[mode] < row["actual"] for row in rows),
        "match": sum(row[mode] == row["actual"] for row in rows),
    }


def replay(*, exclude_added_fixtures: bool = False) -> dict:
    samples = json.loads(
        (BASE / "archive" / "calibration" / "calibration_all_cleaned_v3.json")
        .read_text(encoding="utf-8")
    )
    rows: list[dict] = []
    missing: list[str] = []
    blocked: list[dict] = []
    excluded = [sample["sample_id"] for sample in samples if not sample.get("usable_for_accuracy_evaluation")]
    for sample in samples:
        sid = sample["sample_id"]
        if not sample.get("usable_for_accuracy_evaluation"):
            continue
        if exclude_added_fixtures and sid in ADDED_FIXTURE_IDS:
            continue
        fixture = BASE / str(sample.get("ai_json_path") or "")
        if not fixture.is_file():
            missing.append(sid)
            continue
        try:
            result = estimate_from_ai_json(json.loads(fixture.read_text(encoding="utf-8")))
        except Exception as exc:  # report real replay failures without hiding samples
            blocked.append({"sample_id": sid, "reason": str(exc)})
            continue
        if result["status"] != "calculated":
            blocked.append({"sample_id": sid, "reason": result.get("review_reasons", [])})
            continue
        actual = sample.get("resolved_actual_head_freight_rmb")
        if actual is None:
            blocked.append({"sample_id": sid, "reason": "resolved actual head freight missing"})
            continue
        rows.append({
            "sample_id": sid,
            "normal": float(result["normal"]["head_cost_cny"]),
            "conservative": float(result["conservative"]["head_cost_cny"]),
            "actual": float(actual),
            "soft_group": sid in SOFT_IDS,
            "applied_rules": result["packaging_calibration"]["applied_rules"],
        })
    soft = [row for row in rows if row["soft_group"]]
    non_soft = [row for row in rows if not row["soft_group"]]
    return {
        "source_file_samples": len(samples),
        "accuracy_eligible": sum(bool(sample.get("usable_for_accuracy_evaluation")) for sample in samples),
        "excluded": excluded,
        "missing_fixtures": missing,
        "blocked": blocked,
        "replayed": len(rows),
        "overall": {mode: _metrics(rows, mode) for mode in ("normal", "conservative")},
        "soft_group": {mode: _metrics(soft, mode) for mode in ("normal", "conservative")},
        "non_soft_group": {mode: _metrics(non_soft, mode) for mode in ("normal", "conservative")},
        "representative_rows": [
            row for row in rows
            if row["sample_id"] in SOFT_IDS | {"CAL-045", "CAL-064"}
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exclude-added-fixtures", action="store_true")
    args = parser.parse_args()
    print(json.dumps(
        replay(exclude_added_fixtures=args.exclude_added_fixtures),
        ensure_ascii=False,
        indent=2,
    ))
